"""Pydantic models for the Relay Protocol API.

Field names use snake_case in Python and map to the API's camelCase via the
configured alias generator. Models allow extra fields so the deeply-nested,
fast-evolving parts of the API (e.g. ``feeSponsorship``) never break parsing.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field
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
    """Display and classification metadata for a :class:`Currency`."""

    logo_uri: Optional[str] = Field(default=None, description="URL of the token's logo image.")
    verified: Optional[bool] = Field(
        default=None, description="Whether the token is on Relay's verified list."
    )
    is_native: Optional[bool] = Field(
        default=None,
        description="Whether this is the chain's native gas currency (e.g. ETH), not an ERC-20.",
    )


class Currency(RelayModel):
    """A token on a specific chain, as returned inside fees and quote details."""

    chain_id: Optional[int] = Field(default=None, description="Chain ID the token lives on.")
    address: Optional[str] = Field(
        default=None,
        description="Token contract address; the zero address denotes the native gas currency.",
    )
    symbol: Optional[str] = Field(default=None, description="Ticker symbol, e.g. ``USDC``.")
    name: Optional[str] = Field(default=None, description="Human-readable token name.")
    decimals: Optional[int] = Field(
        default=None, description="Number of decimals the smallest unit divides into."
    )
    metadata: Optional[CurrencyMetadata] = Field(
        default=None, description="Display/classification metadata for the token."
    )


class Fee(RelayModel):
    """A single fee bucket: the currency charged plus its amounts.

    ``amount`` is the raw value in the currency's smallest unit;
    ``amount_formatted`` is the same value scaled by ``decimals``; and
    ``amount_usd`` is the USD equivalent. Some buckets (e.g. ``relayer_service``)
    can be negative, representing a network reward rather than a charge.
    """

    currency: Currency = Field(description="The currency this fee is denominated in.")
    amount: Optional[str] = Field(
        default=None, description="Fee amount in the currency's smallest unit (e.g. wei)."
    )
    amount_formatted: Optional[str] = Field(
        default=None, description="``amount`` scaled by the currency's decimals."
    )
    amount_usd: Optional[str] = Field(default=None, description="USD value of the fee.")
    minimum_amount: Optional[str] = Field(
        default=None, description="Minimum acceptable amount in the smallest unit."
    )


class FeeBreakdown(RelayModel):
    """The set of fee buckets returned with a :class:`Quote` or :class:`Price`.

    Every bucket is optional; the API only populates the ones relevant to the
    route. ``relayer`` is the sum of ``relayer_gas`` and ``relayer_service``.
    """

    gas: Optional[Fee] = Field(default=None, description="Origin-chain gas fee for the deposit.")
    relayer: Optional[Fee] = Field(
        default=None, description="Combined relayer fee (gas + service)."
    )
    relayer_gas: Optional[Fee] = Field(default=None, description="Destination-chain gas fee.")
    relayer_service: Optional[Fee] = Field(
        default=None,
        description="Fee paid to the relay solver; may be negative (a network reward).",
    )
    app: Optional[Fee] = Field(
        default=None, description="Fee paid to the integrating app, claimed separately."
    )
    subsidized: Optional[Fee] = Field(
        default=None, description="Portion of fees covered by a request sponsor."
    )


class StepCheck(RelayModel):
    """An endpoint to poll to confirm a :class:`StepItem` completed."""

    endpoint: Optional[str] = Field(
        default=None, description="Path to poll for completion of the step item."
    )
    method: Optional[str] = Field(default=None, description="HTTP method to use for the check.")


class StepItem(RelayModel):
    """A single signature or transaction within a :class:`Step`.

    A step may bundle several items of the same kind that can be executed
    together. ``data`` holds the kind-specific payload to sign or submit.
    """

    status: Optional[str] = Field(
        default=None, description="``complete`` or ``incomplete`` for this item."
    )
    data: Optional[dict[str, Any]] = Field(
        default=None,
        description="Transaction or signature payload to submit (kind-specific shape).",
    )
    check: Optional[StepCheck] = Field(
        default=None, description="Endpoint to poll to confirm completion, when applicable."
    )


class Step(RelayModel):
    """One step (signature or transaction) required to execute a quote."""

    id: Optional[str] = Field(
        default=None, description="Step identifier, e.g. ``deposit``, ``approve``, ``swap``."
    )
    action: Optional[str] = Field(default=None, description="Call to action for the step.")
    description: Optional[str] = Field(
        default=None, description="Human-readable description of the step."
    )
    kind: Optional[str] = Field(default=None, description="``transaction`` or ``signature``.")
    request_id: Optional[str] = Field(
        default=None, description="Identifier tying related transactions together."
    )
    deposit_address: Optional[str] = Field(
        default=None, description="Deposit address for the request, when one is used."
    )
    items: list[StepItem] = Field(
        default_factory=list, description="The signatures/transactions making up this step."
    )


class Quote(RelayModel):
    """An executable quote: the steps to run plus the fee breakdown.

    Returned by :meth:`relay_link.RelayClient.get_quote`. ``details``,
    ``fee_sponsorship`` and ``protocol`` are intentionally loose dicts — they
    are large, optional, and evolve frequently, so they are passed through
    verbatim rather than modeled exhaustively.
    """

    steps: list[Step] = Field(
        default_factory=list, description="Ordered steps to execute the bridge/swap/call."
    )
    fees: Optional[FeeBreakdown] = Field(
        default=None, description="Breakdown of the fees for the route."
    )
    details: Optional[dict[str, Any]] = Field(
        default=None, description="Swap summary (rate, impact, currencies in/out, etc.)."
    )
    fee_sponsorship: Optional[dict[str, Any]] = Field(
        default=None, description="Granular fee-sponsorship breakdown, when sponsorship applies."
    )
    protocol: Optional[dict[str, Any]] = Field(
        default=None, description="Protocol-version metadata for the route."
    )


class Price(RelayModel):
    """A non-executable price estimate (``POST /price``).

    Returned by :meth:`relay_link.RelayClient.get_price`. Unlike :class:`Quote`
    it contains no executable steps — only the fee breakdown and swap details.
    """

    fees: Optional[FeeBreakdown] = Field(
        default=None, description="Breakdown of the estimated fees."
    )
    details: Optional[dict[str, Any]] = Field(
        default=None, description="Swap summary (rate, impact, currencies in/out, etc.)."
    )


class ChainContracts(RelayModel):
    """Relay contract addresses deployed on a :class:`Chain`."""

    multicall3: Optional[str] = Field(default=None, description="Multicall3 contract address.")
    multicaller: Optional[str] = Field(default=None, description="Relay multicaller address.")
    only_owner_multicaller: Optional[str] = Field(
        default=None, description="Owner-restricted multicaller address."
    )
    relay_receiver: Optional[str] = Field(
        default=None, description="Relay receiver contract address."
    )
    erc20_router: Optional[str] = Field(default=None, description="ERC-20 router address.")
    approval_proxy: Optional[str] = Field(default=None, description="Approval proxy address.")
    # The live API returns ``v3`` as a nested object (e.g. its own router and
    # approval-proxy addresses), despite the OpenAPI spec typing it as a string.
    v3: Optional[dict[str, Any]] = Field(
        default=None,
        description="v3 protocol contract addresses (a nested object, not a string).",
    )


class ChainCurrency(RelayModel):
    """The native currency of a :class:`Chain`."""

    id: Optional[str] = Field(default=None, description="Relay currency identifier.")
    symbol: Optional[str] = Field(default=None, description="Ticker symbol, e.g. ``ETH``.")
    name: Optional[str] = Field(default=None, description="Human-readable currency name.")
    address: Optional[str] = Field(
        default=None, description="Contract address; the zero address for a native currency."
    )
    decimals: Optional[int] = Field(default=None, description="Number of decimals.")
    supports_bridging: Optional[bool] = Field(
        default=None, description="Whether the currency can be bridged via Relay."
    )


class Chain(RelayModel):
    """A chain supported by Relay (``GET /chains``).

    Only ``id`` is guaranteed present; everything else is optional because the
    API tailors the payload to the chain and request.
    """

    id: int = Field(description="Numeric chain ID.")
    name: Optional[str] = Field(default=None, description="Internal chain slug, e.g. ``base``.")
    display_name: Optional[str] = Field(
        default=None, description="Human-readable chain name, e.g. ``Base``."
    )
    http_rpc_url: Optional[str] = Field(default=None, description="Public HTTP RPC endpoint.")
    ws_rpc_url: Optional[str] = Field(default=None, description="Public WebSocket RPC endpoint.")
    explorer_url: Optional[str] = Field(default=None, description="Block explorer base URL.")
    explorer_name: Optional[str] = Field(default=None, description="Block explorer name.")
    deposit_enabled: Optional[bool] = Field(
        default=None, description="Whether deposits (bridging from this chain) are enabled."
    )
    token_support: Optional[str] = Field(
        default=None, description="Token support level: ``All`` or ``Limited``."
    )
    disabled: Optional[bool] = Field(
        default=None, description="Whether the chain is currently disabled."
    )
    vm_type: Optional[str] = Field(
        default=None, description="VM family, e.g. ``evm``, ``svm``, ``tvm``."
    )
    currency: Optional[ChainCurrency] = Field(
        default=None, description="The chain's native gas currency."
    )
    withdrawal_fee: Optional[float] = Field(default=None, description="Withdrawal fee.")
    deposit_fee: Optional[float] = Field(default=None, description="Deposit fee.")
    surge_enabled: Optional[bool] = Field(
        default=None, description="Whether surge pricing is active for the chain."
    )
    contracts: Optional[ChainContracts] = Field(
        default=None, description="Relay contract addresses on this chain."
    )
    solver_addresses: Optional[list[str]] = Field(
        default=None, description="Known solver addresses operating on this chain."
    )
    tags: Optional[list[str]] = Field(default=None, description="Descriptive tags for the chain.")


class ChainsResponse(RelayModel):
    """Wrapper for the ``GET /chains`` response body."""

    chains: list[Chain] = Field(default_factory=list, description="The list of supported chains.")


class TransactionStatus(RelayModel):
    """Execution status of a relay request (``GET /intents/status/v3``).

    Returned by :meth:`relay_link.RelayClient.get_status`. ``status`` reaches a
    terminal value of ``success``, ``failure`` or ``refund`` (see
    :data:`relay_link.TERMINAL_STATUSES`); intermediate values include
    ``waiting``, ``pending``, ``depositing`` and ``submitted``.
    """

    status: Optional[str] = Field(
        default=None, description="Current execution status of the request."
    )
    origin_chain_id: Optional[int] = Field(default=None, description="Origin chain ID.")
    destination_chain_id: Optional[int] = Field(default=None, description="Destination chain ID.")
    tx_hashes: Optional[list[str]] = Field(
        default=None, description="Outgoing (destination) transaction hashes."
    )
    in_tx_hashes: Optional[list[str]] = Field(
        default=None, description="Incoming (origin) transaction hashes."
    )
    details: Optional[str] = Field(
        default=None, description="Extra status detail, e.g. a failure reason."
    )
    quote_created_at: Optional[int] = Field(
        default=None, description="Unix timestamp when the quote was created."
    )
    updated_at: Optional[int] = Field(
        default=None, description="Unix timestamp of the last status update."
    )


class RelayRequest(RelayModel):
    """A single relay request record (``GET /requests``)."""

    id: Optional[str] = Field(default=None, description="Request identifier.")
    status: Optional[str] = Field(default=None, description="Current status of the request.")
    user: Optional[str] = Field(default=None, description="Address that initiated the request.")
    recipient: Optional[str] = Field(
        default=None, description="Address receiving the funds, if different from the user."
    )
    data: Optional[dict[str, Any]] = Field(
        default=None, description="Full request payload as stored by Relay."
    )
    created_at: Optional[str] = Field(
        default=None, description="ISO-8601 timestamp the request was created."
    )
    updated_at: Optional[str] = Field(
        default=None, description="ISO-8601 timestamp the request was last updated."
    )


class RequestsResponse(RelayModel):
    """Paginated response for ``GET /requests``.

    Returned by :meth:`relay_link.RelayClient.get_requests`. Pass
    ``continuation`` back into the next call to page through results.
    """

    continuation: Optional[str] = Field(
        default=None, description="Cursor for the next page, or ``None`` on the last page."
    )
    requests: list[RelayRequest] = Field(
        default_factory=list, description="The page of relay request records."
    )


class TokenPrice(RelayModel):
    """Token price in USD (``GET /currencies/token/price``).

    Returned by :meth:`relay_link.RelayClient.get_token_price`.
    """

    price: Optional[float] = Field(default=None, description="Token price in USD.")
