"""Request-body models for endpoints that take a JSON payload.

These mirror the API's request schemas. ``to_body()`` produces a dict keyed by
the API's camelCase field names, omitting any field the caller left unset so we
never send nulls the API doesn't expect.
"""

from __future__ import annotations

from typing import Any, Optional, Union

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from .models import TradeType


class _RequestBase(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )

    def to_body(self) -> dict[str, Any]:
        """Serialize to a camelCase dict, omitting unset and ``None`` values."""
        return self.model_dump(by_alias=True, exclude_none=True, exclude_unset=True)


class QuoteRequest(_RequestBase):
    """Body for ``POST /quote/v2`` (and the deprecated ``POST /quote``)."""

    user: str
    origin_chain_id: int
    destination_chain_id: int
    origin_currency: str
    destination_currency: str
    amount: str
    trade_type: Union[TradeType, str]

    recipient: Optional[str] = None
    txs: Optional[list[dict[str, Any]]] = None
    referrer: Optional[str] = None
    referrer_address: Optional[str] = None
    refund_to: Optional[str] = None
    slippage_tolerance: Optional[str] = None
    app_fees: Optional[list[dict[str, Any]]] = None
    use_external_liquidity: Optional[bool] = None
    use_fallbacks: Optional[bool] = None
    use_permit: Optional[bool] = None
    use_deposit_address: Optional[bool] = None
    topup_gas: Optional[bool] = None
    subsidize_fees: Optional[bool] = None


class PriceRequest(_RequestBase):
    """Body for ``POST /price`` (non-executable price estimate)."""

    user: Optional[str] = None
    origin_chain_id: int
    destination_chain_id: int
    origin_currency: str
    destination_currency: str
    amount: str
    trade_type: Union[TradeType, str]

    recipient: Optional[str] = None
    txs: Optional[list[dict[str, Any]]] = None
    referrer: Optional[str] = None
    refund_to: Optional[str] = None
    slippage_tolerance: Optional[str] = None
    app_fees: Optional[list[dict[str, Any]]] = None
    use_external_liquidity: Optional[bool] = None
    use_fallbacks: Optional[bool] = None
    use_permit: Optional[bool] = None
    use_deposit_address: Optional[bool] = None
