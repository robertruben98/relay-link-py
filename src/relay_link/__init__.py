"""relay-link-py: a Python client for the Relay Protocol API (relay.link).

Quickstart
----------
>>> from relay_link import RelayClient, TradeType
>>> client = RelayClient()
>>> chains = client.get_chains()
"""

from __future__ import annotations

from .client import (
    DEFAULT_BASE_URL,
    TERMINAL_STATUSES,
    AsyncRelayClient,
    RelayClient,
)
from .exceptions import RelayAPIError, RelayError
from .models import (
    Chain,
    ChainCurrency,
    ChainsResponse,
    Currency,
    CurrencyMetadata,
    Fee,
    FeeBreakdown,
    Price,
    Quote,
    RelayRequest,
    RequestsResponse,
    Step,
    StepItem,
    TokenPrice,
    TradeType,
    TransactionStatus,
)
from .requests import PriceRequest, QuoteRequest

__version__ = "0.1.0"

__all__ = [
    "DEFAULT_BASE_URL",
    "TERMINAL_STATUSES",
    "AsyncRelayClient",
    "RelayClient",
    "RelayError",
    "RelayAPIError",
    "Chain",
    "ChainCurrency",
    "ChainsResponse",
    "Currency",
    "CurrencyMetadata",
    "Fee",
    "FeeBreakdown",
    "Price",
    "Quote",
    "RelayRequest",
    "RequestsResponse",
    "Step",
    "StepItem",
    "TokenPrice",
    "TradeType",
    "TransactionStatus",
    "PriceRequest",
    "QuoteRequest",
    "__version__",
]
