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

    >>> client = RelayClient()
    >>> chains = client.get_chains()
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
        super().__init__(base_url, api_key, api_key_header, timeout, max_retries, backoff_base)
        self._client = http_client or httpx.Client(timeout=timeout)
        self._owns_client = http_client is None

    def __enter__(self) -> RelayClient:
        return self

    def __exit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> None:
        self.close()

    def close(self) -> None:
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
        """List supported chains (``GET /chains``)."""
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
        """Get an executable quote (``POST /quote/v2``)."""
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
        """Get a non-executable price estimate (``POST /price``)."""
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
        """Get the execution status of a request (``GET /intents/status/v3``)."""
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
        """List relay requests (``GET /requests``)."""
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
        """Get a token's USD price (``GET /currencies/token/price``)."""
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
        """Poll ``get_status`` until a terminal state or ``timeout`` seconds.

        Raises :class:`RelayError` if the timeout elapses first.
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

    >>> async with AsyncRelayClient() as client:
    ...     chains = await client.get_chains()
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
        super().__init__(base_url, api_key, api_key_header, timeout, max_retries, backoff_base)
        self._client = http_client or httpx.AsyncClient(timeout=timeout)
        self._owns_client = http_client is None

    async def __aenter__(self) -> AsyncRelayClient:
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> None:
        await self.aclose()

    async def aclose(self) -> None:
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
        """List supported chains (``GET /chains``)."""
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
        """Get an executable quote (``POST /quote/v2``)."""
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
        """Get a non-executable price estimate (``POST /price``)."""
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
        """Get the execution status of a request (``GET /intents/status/v3``)."""
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
        """List relay requests (``GET /requests``)."""
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
        """Get a token's USD price (``GET /currencies/token/price``)."""
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
        """Poll ``get_status`` until a terminal state or ``timeout`` seconds.

        Raises :class:`RelayError` if the timeout elapses first.
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
