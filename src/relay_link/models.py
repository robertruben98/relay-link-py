"""Pydantic models for the Relay Protocol API.

Field names use snake_case in Python and map to the API's camelCase via the
configured alias generator. Models allow extra fields so the deeply-nested,
fast-evolving parts of the API (e.g. ``feeSponsorship``) never break parsing.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class RelayModel(BaseModel):
    """Base model: camelCase aliases, populate by name, tolerate extras."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="allow",
    )


class TradeType(str, Enum):
    """Whether ``amount`` is the input or the desired output of the swap."""

    EXACT_INPUT = "EXACT_INPUT"
    EXACT_OUTPUT = "EXACT_OUTPUT"
    EXPECTED_OUTPUT = "EXPECTED_OUTPUT"


class CurrencyMetadata(RelayModel):
    logo_uri: Optional[str] = None
    verified: Optional[bool] = None
    is_native: Optional[bool] = None


class Currency(RelayModel):
    """A token on a specific chain."""

    chain_id: Optional[int] = None
    address: Optional[str] = None
    symbol: Optional[str] = None
    name: Optional[str] = None
    decimals: Optional[int] = None
    metadata: Optional[CurrencyMetadata] = None


class Fee(RelayModel):
    """A single fee bucket: a currency plus formatted amounts."""

    currency: Currency
    amount: Optional[str] = None
    amount_formatted: Optional[str] = None
    amount_usd: Optional[str] = None
    minimum_amount: Optional[str] = None


class FeeBreakdown(RelayModel):
    """The set of fee buckets returned with a quote or price."""

    gas: Optional[Fee] = None
    relayer: Optional[Fee] = None
    relayer_gas: Optional[Fee] = None
    relayer_service: Optional[Fee] = None
    app: Optional[Fee] = None
    subsidized: Optional[Fee] = None


class StepCheck(RelayModel):
    """An endpoint to poll to confirm a step item completed."""

    endpoint: Optional[str] = None
    method: Optional[str] = None


class StepItem(RelayModel):
    status: Optional[str] = None
    data: Optional[dict[str, Any]] = None
    check: Optional[StepCheck] = None


class Step(RelayModel):
    """One step (signature or transaction) required to execute a quote."""

    id: Optional[str] = None
    action: Optional[str] = None
    description: Optional[str] = None
    kind: Optional[str] = None
    request_id: Optional[str] = None
    deposit_address: Optional[str] = None
    items: list[StepItem] = []


class Quote(RelayModel):
    """An executable quote: the steps to run plus the fee breakdown.

    ``details``, ``fee_sponsorship`` and ``protocol`` are intentionally loose
    dicts — they are large, optional, and evolve frequently.
    """

    steps: list[Step] = []
    fees: Optional[FeeBreakdown] = None
    details: Optional[dict[str, Any]] = None
    fee_sponsorship: Optional[dict[str, Any]] = None
    protocol: Optional[dict[str, Any]] = None


class Price(RelayModel):
    """A non-executable price estimate (POST /price)."""

    fees: Optional[FeeBreakdown] = None
    details: Optional[dict[str, Any]] = None


class ChainContracts(RelayModel):
    multicall3: Optional[str] = None
    multicaller: Optional[str] = None
    only_owner_multicaller: Optional[str] = None
    relay_receiver: Optional[str] = None
    erc20_router: Optional[str] = None
    approval_proxy: Optional[str] = None
    # The live API returns ``v3`` as a nested object (e.g. its own router and
    # approval-proxy addresses), despite the OpenAPI spec typing it as a string.
    v3: Optional[dict[str, Any]] = None


class ChainCurrency(RelayModel):
    id: Optional[str] = None
    symbol: Optional[str] = None
    name: Optional[str] = None
    address: Optional[str] = None
    decimals: Optional[int] = None
    supports_bridging: Optional[bool] = None


class Chain(RelayModel):
    """A chain supported by Relay."""

    id: int
    name: Optional[str] = None
    display_name: Optional[str] = None
    http_rpc_url: Optional[str] = None
    ws_rpc_url: Optional[str] = None
    explorer_url: Optional[str] = None
    explorer_name: Optional[str] = None
    deposit_enabled: Optional[bool] = None
    token_support: Optional[str] = None
    disabled: Optional[bool] = None
    vm_type: Optional[str] = None
    currency: Optional[ChainCurrency] = None
    withdrawal_fee: Optional[float] = None
    deposit_fee: Optional[float] = None
    surge_enabled: Optional[bool] = None
    contracts: Optional[ChainContracts] = None
    solver_addresses: Optional[list[str]] = None
    tags: Optional[list[str]] = None


class ChainsResponse(RelayModel):
    chains: list[Chain] = []


class TransactionStatus(RelayModel):
    """Execution status of a relay request (GET /intents/status/v3)."""

    status: Optional[str] = None
    origin_chain_id: Optional[int] = None
    destination_chain_id: Optional[int] = None
    tx_hashes: Optional[list[str]] = None
    in_tx_hashes: Optional[list[str]] = None
    details: Optional[str] = None
    quote_created_at: Optional[int] = None
    updated_at: Optional[int] = None


class RelayRequest(RelayModel):
    """A single relay request record (GET /requests)."""

    id: Optional[str] = None
    status: Optional[str] = None
    user: Optional[str] = None
    recipient: Optional[str] = None
    data: Optional[dict[str, Any]] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class RequestsResponse(RelayModel):
    continuation: Optional[str] = None
    requests: list[RelayRequest] = []


class TokenPrice(RelayModel):
    """Token price in USD (GET /currencies/token/price)."""

    price: Optional[float] = None
