"""Synchronous and asynchronous clients for the Relay Protocol API."""

from __future__ import annotations

import asyncio
import time
from types import TracebackType
from typing import Any, Optional, Union

import httpx

from . import transport
from .exceptions import (
    RelayAPIError,
    RelayConnectionError,
    RelayError,
    RelayRateLimitError,
    RelayTimeoutError,
)
from .models import (
    Chain,
    ChainsResponse,
    Price,
    Quote,
    RequestsResponse,
    TokenPrice,
    TransactionStatus,
)
from .requests import PriceRequest, QuoteRequest
from .transport import RETRYABLE_STATUSES, backoff_delay, parse_retry_after

DEFAULT_BASE_URL = "https://api.relay.link"
DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF_BASE = 0.5

#: Status values that mean the request will not change further.
TERMINAL_STATUSES = frozenset({"success", "failure", "refund"})


def _clean_params(params: dict[str, Any]) -> dict[str, Any]:
    """Drop ``None`` values so they aren't sent as empty query params."""
    return {k: v for k, v in params.items() if v is not None}


class _BaseRelayClient:
    """Shared configuration and request-shaping logic."""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        api_key: Optional[str] = None,
        api_key_header: str = "x-api-key",
        timeout: float = 30.0,
        max_retries: int = DEFAULT_MAX_RETRIES,
        backoff_base: float = DEFAULT_BACKOFF_BASE,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.api_key_header = api_key_header
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_base = backoff_base

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers[self.api_key_header] = self.api_key
        return headers

    def _should_retry(self, response: httpx.Response, attempt: int) -> bool:
        return response.status_code in RETRYABLE_STATUSES and attempt < self.max_retries

    def _delay_for(self, response: httpx.Response, attempt: int) -> float:
        return backoff_delay(
            base=self.backoff_base,
            attempt=attempt,
            retry_after=parse_retry_after(response.headers),
        )

    @staticmethod
    def _success(response: httpx.Response) -> Any:
        """Parse a successful response, or raise the right typed API error."""
        if response.is_success:
            return response.json()
        if response.status_code == 429:
            body: Optional[Any] = None
            try:
                body = response.json()
            except ValueError:
                body = None
            base_err = RelayAPIError.from_response(response)
            raise RelayRateLimitError(
                status_code=429,
                message=base_err.message,
                body=body,
                retry_after=parse_retry_after(response.headers),
            )
        raise RelayAPIError.from_response(response)


class RelayClient(_BaseRelayClient):
    """Synchronous client for the Relay Protocol API.

    Use it as a context manager so the underlying HTTP connection is closed
    automatically:

    >>> with RelayClient() as client:
    ...     chains = client.get_chains()

    All methods raise a :class:`RelayError` subclass on failure (see the
    module's exception hierarchy). 429 and transient 5xx responses are retried
    transparently with exponential backoff.
    """

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        api_key: Optional[str] = None,
        api_key_header: str = "x-api-key",
        timeout: float = 30.0,
        max_retries: int = DEFAULT_MAX_RETRIES,
        backoff_base: float = DEFAULT_BACKOFF_BASE,
        http_client: Optional[httpx.Client] = None,
    ) -> None:
        """Create a synchronous client.

        Args:
            base_url: Base URL of the Relay API. A trailing slash is stripped.
            api_key: Optional API key sent on every request. Quotes are public
                and need no key.
            api_key_header: Header name to send ``api_key`` under.
            timeout: Per-request timeout in seconds (used only when this client
                creates its own HTTP client).
            max_retries: Maximum retries for 429 and transient 5xx responses.
            backoff_base: Base delay in seconds for exponential backoff between
                retries.
            http_client: An existing :class:`httpx.Client` to use. When given,
                the caller owns its lifecycle and :meth:`close` will not close
                it; otherwise the client creates and owns one.
        """
        super().__init__(base_url, api_key, api_key_header, timeout, max_retries, backoff_base)
        self._client = http_client or httpx.Client(timeout=timeout)
        self._owns_client = http_client is None

    def __enter__(self) -> RelayClient:
        """Enter the context manager, returning this client."""
        return self

    def __exit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> None:
        """Exit the context manager, closing the client."""
        self.close()

    def close(self) -> None:
        """Close the underlying HTTP client if this instance created it.

        A no-op when an ``http_client`` was supplied to the constructor, since
        the caller owns that client's lifecycle.
        """
        if self._owns_client:
            self._client.close()

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[dict[str, Any]] = None,
        json_body: Optional[dict[str, Any]] = None,
    ) -> Any:
        url = f"{self.base_url}{path}"
        attempt = 0
        while True:
            try:
                response = self._client.request(
                    method,
                    url,
                    params=_clean_params(params or {}),
                    json=json_body,
                    headers=self._headers(),
                )
            except httpx.TimeoutException as exc:
                raise RelayTimeoutError(f"Request to {url} timed out") from exc
            except httpx.TransportError as exc:
                raise RelayConnectionError(f"Failed to connect to {url}: {exc}") from exc

            if self._should_retry(response, attempt):
                delay = self._delay_for(response, attempt)
                if delay > 0:
                    transport.time.sleep(delay)
                attempt += 1
                continue
            return self._success(response)

    def _get(self, path: str, params: Optional[dict[str, Any]] = None) -> Any:
        return self._request("GET", path, params=params)

    def _post(self, path: str, json_body: dict[str, Any]) -> Any:
        return self._request("POST", path, json_body=json_body)

    def get_chains(self, include_chains: Optional[str] = None) -> list[Chain]:
        """List the chains supported by Relay (``GET /chains``).

        Args:
            include_chains: Optional comma-separated chain IDs to restrict the
                response to (e.g. ``"1,10,8453"``).

        Returns:
            The list of supported :class:`~relay_link.Chain` objects.

        Raises:
            RelayAPIError: The API returned a non-2xx response.
            RelayConnectionError: The API could not be reached.
            RelayTimeoutError: The request timed out.
        """
        data = self._get("/chains", {"includeChains": include_chains})
        return ChainsResponse.model_validate(data).chains

    def get_quote(
        self,
        *,
        user: str,
        origin_chain_id: int,
        destination_chain_id: int,
        origin_currency: str,
        destination_currency: str,
        amount: str,
        trade_type: Union[str, Any],
        **extra: Any,
    ) -> Quote:
        """Get an executable quote for a bridge/swap/call (``POST /quote/v2``).

        Args:
            user: Address depositing funds and submitting transactions.
            origin_chain_id: Chain ID to bridge/swap from.
            destination_chain_id: Chain ID to bridge/swap to.
            origin_currency: Origin token address (the zero address for the
                native gas currency).
            destination_currency: Destination token address (zero = native).
            amount: Amount in the currency's smallest unit (e.g. wei), as a
                string.
            trade_type: A :class:`~relay_link.TradeType` (or its string value)
                deciding whether ``amount`` is the input or desired output.
            **extra: Any additional :class:`~relay_link.QuoteRequest` fields,
                e.g. ``recipient``, ``slippage_tolerance``, ``app_fees``.

        Returns:
            A :class:`~relay_link.Quote` with the steps to execute and the fee
            breakdown.

        Raises:
            RelayAPIError: The API rejected the request (e.g. an invalid route).
            RelayRateLimitError: Rate limited after retries were exhausted.
            RelayConnectionError: The API could not be reached.
            RelayTimeoutError: The request timed out.

        Example:
            >>> with RelayClient() as client:
            ...     quote = client.get_quote(
            ...         user="0x03508bb71268bba25ecacc8f620e01866650532c",
            ...         origin_chain_id=8453,
            ...         destination_chain_id=10,
            ...         origin_currency="0x0000000000000000000000000000000000000000",
            ...         destination_currency="0x0000000000000000000000000000000000000000",
            ...         amount="1000000000000000000",  # 1 ETH in wei
            ...         trade_type=TradeType.EXACT_INPUT,
            ...     )
            >>> for step in quote.steps:
            ...     print(step.kind, step.id)
        """
        req = QuoteRequest(
            user=user,
            origin_chain_id=origin_chain_id,
            destination_chain_id=destination_chain_id,
            origin_currency=origin_currency,
            destination_currency=destination_currency,
            amount=amount,
            trade_type=trade_type,
            **extra,
        )
        data = self._post("/quote/v2", req.to_body())
        return Quote.model_validate(data)

    def get_price(
        self,
        *,
        origin_chain_id: int,
        destination_chain_id: int,
        origin_currency: str,
        destination_currency: str,
        amount: str,
        trade_type: Union[str, Any],
        user: Optional[str] = None,
        **extra: Any,
    ) -> Price:
        """Get a non-executable price estimate (``POST /price``).

        Like :meth:`get_quote` but returns only fees and swap details, with no
        executable steps — useful for display and comparison.

        Args:
            origin_chain_id: Chain ID to bridge/swap from.
            destination_chain_id: Chain ID to bridge/swap to.
            origin_currency: Origin token address (zero = native).
            destination_currency: Destination token address (zero = native).
            amount: Amount in the currency's smallest unit, as a string.
            trade_type: A :class:`~relay_link.TradeType` (or its string value).
            user: Optional depositing address; not required for a price-only
                call.
            **extra: Any additional :class:`~relay_link.PriceRequest` fields.

        Returns:
            A :class:`~relay_link.Price` with the estimated fee breakdown and
            swap details.

        Raises:
            RelayAPIError: The API rejected the request.
            RelayRateLimitError: Rate limited after retries were exhausted.
            RelayConnectionError: The API could not be reached.
            RelayTimeoutError: The request timed out.
        """
        req = PriceRequest(
            user=user,
            origin_chain_id=origin_chain_id,
            destination_chain_id=destination_chain_id,
            origin_currency=origin_currency,
            destination_currency=destination_currency,
            amount=amount,
            trade_type=trade_type,
            **extra,
        )
        data = self._post("/price", req.to_body())
        return Price.model_validate(data)

    def get_status(self, *, request_id: str) -> TransactionStatus:
        """Get the execution status of a request (``GET /intents/status/v3``).

        Args:
            request_id: The request identifier from a quote step's
                ``request_id``.

        Returns:
            A :class:`~relay_link.TransactionStatus` snapshot.

        Raises:
            RelayAPIError: The API returned a non-2xx response.
            RelayConnectionError: The API could not be reached.
            RelayTimeoutError: The request timed out.
        """
        data = self._get("/intents/status/v3", {"requestId": request_id})
        return TransactionStatus.model_validate(data)

    def get_requests(
        self,
        *,
        user: Optional[str] = None,
        hash: Optional[str] = None,
        origin_chain_id: Optional[int] = None,
        destination_chain_id: Optional[int] = None,
        limit: Optional[int] = None,
        continuation: Optional[str] = None,
    ) -> RequestsResponse:
        """List relay requests (``GET /requests``).

        All filters are optional; omitted ones are not sent. Page through
        results by passing the previous response's ``continuation`` back in.

        Args:
            user: Filter to requests initiated by this address.
            hash: Filter to a specific transaction hash.
            origin_chain_id: Filter by origin chain ID.
            destination_chain_id: Filter by destination chain ID.
            limit: Maximum number of records to return.
            continuation: Pagination cursor from a previous response.

        Returns:
            A :class:`~relay_link.RequestsResponse` page of records plus the
            next ``continuation`` cursor.

        Raises:
            RelayAPIError: The API returned a non-2xx response.
            RelayConnectionError: The API could not be reached.
            RelayTimeoutError: The request timed out.
        """
        params = {
            "user": user,
            "hash": hash,
            "originChainId": origin_chain_id,
            "destinationChainId": destination_chain_id,
            "limit": limit,
            "continuation": continuation,
        }
        data = self._get("/requests", params)
        return RequestsResponse.model_validate(data)

    def get_token_price(self, *, address: str, chain_id: int) -> TokenPrice:
        """Get a token's USD price (``GET /currencies/token/price``).

        Args:
            address: Token contract address.
            chain_id: Chain ID the token lives on.

        Returns:
            A :class:`~relay_link.TokenPrice` with the USD price.

        Raises:
            RelayAPIError: The API returned a non-2xx response.
            RelayConnectionError: The API could not be reached.
            RelayTimeoutError: The request timed out.
        """
        data = self._get(
            "/currencies/token/price",
            {"address": address, "chainId": chain_id},
        )
        return TokenPrice.model_validate(data)

    def poll_status(
        self,
        *,
        request_id: str,
        interval: float = 2.0,
        timeout: float = 120.0,
    ) -> TransactionStatus:
        """Poll :meth:`get_status` until the request reaches a terminal state.

        Repeatedly calls :meth:`get_status`, sleeping ``interval`` seconds
        between polls, until ``status`` is one of
        :data:`~relay_link.TERMINAL_STATUSES` (``success``, ``failure`` or
        ``refund``).

        Args:
            request_id: The request identifier to poll.
            interval: Seconds to wait between polls.
            timeout: Maximum total seconds to poll before giving up.

        Returns:
            The terminal :class:`~relay_link.TransactionStatus`.

        Raises:
            RelayError: The timeout elapsed before reaching a terminal state.
            RelayAPIError: A status request returned a non-2xx response.
            RelayConnectionError: The API could not be reached.
            RelayTimeoutError: A status request timed out.
        """
        deadline = time.monotonic() + timeout
        while True:
            status = self.get_status(request_id=request_id)
            if status.status in TERMINAL_STATUSES:
                return status
            if time.monotonic() >= deadline:
                raise RelayError(
                    f"poll_status timed out after {timeout}s; last status: {status.status!r}"
                )
            time.sleep(interval)


class AsyncRelayClient(_BaseRelayClient):
    """Asynchronous client for the Relay Protocol API.

    Use it as an async context manager so the underlying HTTP connection is
    closed automatically:

    >>> async with AsyncRelayClient() as client:
    ...     chains = await client.get_chains()

    It mirrors :class:`RelayClient` exactly, with every method returning an
    awaitable. The same retry and error-handling behavior applies.
    """

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        api_key: Optional[str] = None,
        api_key_header: str = "x-api-key",
        timeout: float = 30.0,
        max_retries: int = DEFAULT_MAX_RETRIES,
        backoff_base: float = DEFAULT_BACKOFF_BASE,
        http_client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        """Create an asynchronous client.

        Args:
            base_url: Base URL of the Relay API. A trailing slash is stripped.
            api_key: Optional API key sent on every request.
            api_key_header: Header name to send ``api_key`` under.
            timeout: Per-request timeout in seconds (used only when this client
                creates its own HTTP client).
            max_retries: Maximum retries for 429 and transient 5xx responses.
            backoff_base: Base delay in seconds for exponential backoff.
            http_client: An existing :class:`httpx.AsyncClient` to use. When
                given, the caller owns its lifecycle and :meth:`aclose` will not
                close it; otherwise the client creates and owns one.
        """
        super().__init__(base_url, api_key, api_key_header, timeout, max_retries, backoff_base)
        self._client = http_client or httpx.AsyncClient(timeout=timeout)
        self._owns_client = http_client is None

    async def __aenter__(self) -> AsyncRelayClient:
        """Enter the async context manager, returning this client."""
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> None:
        """Exit the async context manager, closing the client."""
        await self.aclose()

    async def aclose(self) -> None:
        """Close the underlying async HTTP client if this instance created it.

        A no-op when an ``http_client`` was supplied to the constructor.
        """
        if self._owns_client:
            await self._client.aclose()

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[dict[str, Any]] = None,
        json_body: Optional[dict[str, Any]] = None,
    ) -> Any:
        url = f"{self.base_url}{path}"
        attempt = 0
        while True:
            try:
                response = await self._client.request(
                    method,
                    url,
                    params=_clean_params(params or {}),
                    json=json_body,
                    headers=self._headers(),
                )
            except httpx.TimeoutException as exc:
                raise RelayTimeoutError(f"Request to {url} timed out") from exc
            except httpx.TransportError as exc:
                raise RelayConnectionError(f"Failed to connect to {url}: {exc}") from exc

            if self._should_retry(response, attempt):
                delay = self._delay_for(response, attempt)
                if delay > 0:
                    await transport.asyncio.sleep(delay)
                attempt += 1
                continue
            return self._success(response)

    async def _get(self, path: str, params: Optional[dict[str, Any]] = None) -> Any:
        return await self._request("GET", path, params=params)

    async def _post(self, path: str, json_body: dict[str, Any]) -> Any:
        return await self._request("POST", path, json_body=json_body)

    async def get_chains(self, include_chains: Optional[str] = None) -> list[Chain]:
        """List the chains supported by Relay (``GET /chains``).

        Args:
            include_chains: Optional comma-separated chain IDs to restrict the
                response to (e.g. ``"1,10,8453"``).

        Returns:
            The list of supported :class:`~relay_link.Chain` objects.

        Raises:
            RelayAPIError: The API returned a non-2xx response.
            RelayConnectionError: The API could not be reached.
            RelayTimeoutError: The request timed out.
        """
        data = await self._get("/chains", {"includeChains": include_chains})
        return ChainsResponse.model_validate(data).chains

    async def get_quote(
        self,
        *,
        user: str,
        origin_chain_id: int,
        destination_chain_id: int,
        origin_currency: str,
        destination_currency: str,
        amount: str,
        trade_type: Union[str, Any],
        **extra: Any,
    ) -> Quote:
        """Get an executable quote for a bridge/swap/call (``POST /quote/v2``).

        Args:
            user: Address depositing funds and submitting transactions.
            origin_chain_id: Chain ID to bridge/swap from.
            destination_chain_id: Chain ID to bridge/swap to.
            origin_currency: Origin token address (zero = native).
            destination_currency: Destination token address (zero = native).
            amount: Amount in the currency's smallest unit (e.g. wei), as a
                string.
            trade_type: A :class:`~relay_link.TradeType` (or its string value)
                deciding whether ``amount`` is the input or desired output.
            **extra: Any additional :class:`~relay_link.QuoteRequest` fields,
                e.g. ``recipient``, ``slippage_tolerance``, ``app_fees``.

        Returns:
            A :class:`~relay_link.Quote` with the steps to execute and the fee
            breakdown.

        Raises:
            RelayAPIError: The API rejected the request (e.g. an invalid route).
            RelayRateLimitError: Rate limited after retries were exhausted.
            RelayConnectionError: The API could not be reached.
            RelayTimeoutError: The request timed out.

        Example:
            >>> async with AsyncRelayClient() as client:
            ...     quote = await client.get_quote(
            ...         user="0x03508bb71268bba25ecacc8f620e01866650532c",
            ...         origin_chain_id=8453,
            ...         destination_chain_id=10,
            ...         origin_currency="0x0000000000000000000000000000000000000000",
            ...         destination_currency="0x0000000000000000000000000000000000000000",
            ...         amount="1000000000000000000",
            ...         trade_type=TradeType.EXACT_INPUT,
            ...     )
        """
        req = QuoteRequest(
            user=user,
            origin_chain_id=origin_chain_id,
            destination_chain_id=destination_chain_id,
            origin_currency=origin_currency,
            destination_currency=destination_currency,
            amount=amount,
            trade_type=trade_type,
            **extra,
        )
        data = await self._post("/quote/v2", req.to_body())
        return Quote.model_validate(data)

    async def get_price(
        self,
        *,
        origin_chain_id: int,
        destination_chain_id: int,
        origin_currency: str,
        destination_currency: str,
        amount: str,
        trade_type: Union[str, Any],
        user: Optional[str] = None,
        **extra: Any,
    ) -> Price:
        """Get a non-executable price estimate (``POST /price``).

        Like :meth:`get_quote` but returns only fees and swap details, with no
        executable steps.

        Args:
            origin_chain_id: Chain ID to bridge/swap from.
            destination_chain_id: Chain ID to bridge/swap to.
            origin_currency: Origin token address (zero = native).
            destination_currency: Destination token address (zero = native).
            amount: Amount in the currency's smallest unit, as a string.
            trade_type: A :class:`~relay_link.TradeType` (or its string value).
            user: Optional depositing address; not required for a price-only
                call.
            **extra: Any additional :class:`~relay_link.PriceRequest` fields.

        Returns:
            A :class:`~relay_link.Price` with the estimated fee breakdown and
            swap details.

        Raises:
            RelayAPIError: The API rejected the request.
            RelayRateLimitError: Rate limited after retries were exhausted.
            RelayConnectionError: The API could not be reached.
            RelayTimeoutError: The request timed out.
        """
        req = PriceRequest(
            user=user,
            origin_chain_id=origin_chain_id,
            destination_chain_id=destination_chain_id,
            origin_currency=origin_currency,
            destination_currency=destination_currency,
            amount=amount,
            trade_type=trade_type,
            **extra,
        )
        data = await self._post("/price", req.to_body())
        return Price.model_validate(data)

    async def get_status(self, *, request_id: str) -> TransactionStatus:
        """Get the execution status of a request (``GET /intents/status/v3``).

        Args:
            request_id: The request identifier from a quote step's
                ``request_id``.

        Returns:
            A :class:`~relay_link.TransactionStatus` snapshot.

        Raises:
            RelayAPIError: The API returned a non-2xx response.
            RelayConnectionError: The API could not be reached.
            RelayTimeoutError: The request timed out.
        """
        data = await self._get("/intents/status/v3", {"requestId": request_id})
        return TransactionStatus.model_validate(data)

    async def get_requests(
        self,
        *,
        user: Optional[str] = None,
        hash: Optional[str] = None,
        origin_chain_id: Optional[int] = None,
        destination_chain_id: Optional[int] = None,
        limit: Optional[int] = None,
        continuation: Optional[str] = None,
    ) -> RequestsResponse:
        """List relay requests (``GET /requests``).

        All filters are optional; omitted ones are not sent. Page through
        results by passing the previous response's ``continuation`` back in.

        Args:
            user: Filter to requests initiated by this address.
            hash: Filter to a specific transaction hash.
            origin_chain_id: Filter by origin chain ID.
            destination_chain_id: Filter by destination chain ID.
            limit: Maximum number of records to return.
            continuation: Pagination cursor from a previous response.

        Returns:
            A :class:`~relay_link.RequestsResponse` page of records plus the
            next ``continuation`` cursor.

        Raises:
            RelayAPIError: The API returned a non-2xx response.
            RelayConnectionError: The API could not be reached.
            RelayTimeoutError: The request timed out.
        """
        params = {
            "user": user,
            "hash": hash,
            "originChainId": origin_chain_id,
            "destinationChainId": destination_chain_id,
            "limit": limit,
            "continuation": continuation,
        }
        data = await self._get("/requests", params)
        return RequestsResponse.model_validate(data)

    async def get_token_price(self, *, address: str, chain_id: int) -> TokenPrice:
        """Get a token's USD price (``GET /currencies/token/price``).

        Args:
            address: Token contract address.
            chain_id: Chain ID the token lives on.

        Returns:
            A :class:`~relay_link.TokenPrice` with the USD price.

        Raises:
            RelayAPIError: The API returned a non-2xx response.
            RelayConnectionError: The API could not be reached.
            RelayTimeoutError: The request timed out.
        """
        data = await self._get(
            "/currencies/token/price",
            {"address": address, "chainId": chain_id},
        )
        return TokenPrice.model_validate(data)

    async def poll_status(
        self,
        *,
        request_id: str,
        interval: float = 2.0,
        timeout: float = 120.0,
    ) -> TransactionStatus:
        """Poll :meth:`get_status` until the request reaches a terminal state.

        Repeatedly calls :meth:`get_status`, awaiting ``interval`` seconds
        between polls, until ``status`` is one of
        :data:`~relay_link.TERMINAL_STATUSES` (``success``, ``failure`` or
        ``refund``).

        Args:
            request_id: The request identifier to poll.
            interval: Seconds to wait between polls.
            timeout: Maximum total seconds to poll before giving up.

        Returns:
            The terminal :class:`~relay_link.TransactionStatus`.

        Raises:
            RelayError: The timeout elapsed before reaching a terminal state.
            RelayAPIError: A status request returned a non-2xx response.
            RelayConnectionError: The API could not be reached.
            RelayTimeoutError: A status request timed out.
        """
        deadline = time.monotonic() + timeout
        while True:
            status = await self.get_status(request_id=request_id)
            if status.status in TERMINAL_STATUSES:
                return status
            if time.monotonic() >= deadline:
                raise RelayError(
                    f"poll_status timed out after {timeout}s; last status: {status.status!r}"
                )
            await asyncio.sleep(interval)
