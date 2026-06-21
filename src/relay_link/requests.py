"""Request-body models for endpoints that take a JSON payload.

These mirror the API's request schemas. ``to_body()`` produces a dict keyed by
the API's camelCase field names, omitting any field the caller left unset so we
never send nulls the API doesn't expect.
"""

from __future__ import annotations

from typing import Any, Optional, Union

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from .models import TradeType


class _RequestBase(BaseModel):
    """Base for request-body models: camelCase aliasing plus :meth:`to_body`.

    Subclasses declare fields in snake_case; serialization maps them to the
    API's camelCase names. Fields may also be set by their Python name thanks to
    ``populate_by_name``.
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )

    def to_body(self) -> dict[str, Any]:
        """Serialize to a JSON-ready request body.

        Returns:
            A dict keyed by the API's camelCase field names, with any field the
            caller left unset (or explicitly ``None``) omitted so the request
            never sends nulls the API does not expect.
        """
        return self.model_dump(by_alias=True, exclude_none=True, exclude_unset=True)


class QuoteRequest(_RequestBase):
    """Body for ``POST /quote/v2`` (and the deprecated ``POST /quote``).

    The first seven fields are required; the rest are optional tuning knobs that
    are only sent when set. Usually built for you by
    :meth:`relay_link.RelayClient.get_quote`, but exposed for callers that want
    to construct and reuse a request explicitly.
    """

    user: str = Field(description="Address depositing funds and submitting transactions.")
    origin_chain_id: int = Field(description="Chain ID to bridge/swap from.")
    destination_chain_id: int = Field(description="Chain ID to bridge/swap to.")
    origin_currency: str = Field(description="Origin token address (zero address = native).")
    destination_currency: str = Field(
        description="Destination token address (zero address = native)."
    )
    amount: str = Field(description="Amount in the smallest unit (e.g. wei), as a string.")
    trade_type: Union[TradeType, str] = Field(
        description="Whether ``amount`` is the input or desired output of the swap."
    )

    recipient: Optional[str] = Field(
        default=None, description="Recipient on the destination chain (defaults to ``user``)."
    )
    txs: Optional[list[dict[str, Any]]] = Field(
        default=None, description="Destination-chain calls to execute (``to``/``value``/``data``)."
    )
    referrer: Optional[str] = Field(default=None, description="Referrer tag for attribution.")
    referrer_address: Optional[str] = Field(default=None, description="Referrer address.")
    refund_to: Optional[str] = Field(default=None, description="Address to refund to on failure.")
    slippage_tolerance: Optional[str] = Field(
        default=None, description="Slippage tolerance in basis points (e.g. ``50`` = 0.5%)."
    )
    app_fees: Optional[list[dict[str, Any]]] = Field(
        default=None, description="App fees to charge (``recipient``/``fee`` in basis points)."
    )
    use_external_liquidity: Optional[bool] = Field(
        default=None, description="Use canonical+ bridging (more liquidity, slower)."
    )
    use_fallbacks: Optional[bool] = Field(
        default=None, description="Allow specific fallback routes."
    )
    use_permit: Optional[bool] = Field(
        default=None, description="Use an EIP-3009 permit when bridging (e.g. USDC)."
    )
    use_deposit_address: Optional[bool] = Field(
        default=None, description="Use a deposit address instead of calldata."
    )
    topup_gas: Optional[bool] = Field(
        default=None, description="Include a destination-chain gas topup for the recipient."
    )
    subsidize_fees: Optional[bool] = Field(
        default=None, description="Have the request sponsor cover the fees."
    )


class PriceRequest(_RequestBase):
    """Body for ``POST /price`` (non-executable price estimate).

    Like :class:`QuoteRequest` but ``user`` is optional, and the response
    contains no executable steps. Usually built for you by
    :meth:`relay_link.RelayClient.get_price`.
    """

    user: Optional[str] = Field(
        default=None, description="Address that would deposit (optional for a price-only call)."
    )
    origin_chain_id: int = Field(description="Chain ID to bridge/swap from.")
    destination_chain_id: int = Field(description="Chain ID to bridge/swap to.")
    origin_currency: str = Field(description="Origin token address (zero address = native).")
    destination_currency: str = Field(
        description="Destination token address (zero address = native)."
    )
    amount: str = Field(description="Amount in the smallest unit (e.g. wei), as a string.")
    trade_type: Union[TradeType, str] = Field(
        description="Whether ``amount`` is the input or desired output of the swap."
    )

    recipient: Optional[str] = Field(
        default=None, description="Recipient on the destination chain (defaults to ``user``)."
    )
    txs: Optional[list[dict[str, Any]]] = Field(
        default=None, description="Destination-chain calls to execute (``to``/``value``/``data``)."
    )
    referrer: Optional[str] = Field(default=None, description="Referrer tag for attribution.")
    refund_to: Optional[str] = Field(default=None, description="Address to refund to on failure.")
    slippage_tolerance: Optional[str] = Field(
        default=None, description="Slippage tolerance in basis points (e.g. ``50`` = 0.5%)."
    )
    app_fees: Optional[list[dict[str, Any]]] = Field(
        default=None, description="App fees to charge (``recipient``/``fee`` in basis points)."
    )
    use_external_liquidity: Optional[bool] = Field(
        default=None, description="Use canonical+ bridging (more liquidity, slower)."
    )
    use_fallbacks: Optional[bool] = Field(
        default=None, description="Allow specific fallback routes."
    )
    use_permit: Optional[bool] = Field(
        default=None, description="Use an EIP-3009 permit when bridging (e.g. USDC)."
    )
    use_deposit_address: Optional[bool] = Field(
        default=None, description="Use a deposit address instead of calldata."
    )
