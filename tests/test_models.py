"""Tests for relay_link pydantic models."""

from __future__ import annotations

from relay_link.models import (
    Chain,
    ChainsResponse,
    Currency,
    Fee,
    FeeBreakdown,
    Quote,
    RequestsResponse,
    Step,
    TokenPrice,
    TradeType,
    TransactionStatus,
)


def test_currency_parses_full_payload() -> None:
    cur = Currency.model_validate(
        {
            "chainId": 8453,
            "address": "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913",
            "symbol": "USDC",
            "name": "USD Coin",
            "decimals": 6,
            "metadata": {"logoURI": "https://x/logo.png", "verified": True, "isNative": False},
        }
    )
    assert cur.chain_id == 8453
    assert cur.symbol == "USDC"
    assert cur.decimals == 6
    assert cur.metadata is not None
    assert cur.metadata.is_native is False


def test_fee_parses_currency_amount() -> None:
    fee = Fee.model_validate(
        {
            "currency": {"chainId": 1, "address": "0x0", "symbol": "ETH", "decimals": 18},
            "amount": "30754920",
            "amountFormatted": "30.75492",
            "amountUsd": "30.901612",
            "minimumAmount": "30454920",
        }
    )
    assert fee.amount == "30754920"
    assert fee.amount_usd == "30.901612"
    assert fee.currency.symbol == "ETH"


def test_step_parses_items_and_check() -> None:
    step = Step.model_validate(
        {
            "id": "deposit",
            "action": "Confirm transaction in your wallet",
            "description": "Depositing funds",
            "kind": "transaction",
            "requestId": "0xabc",
            "items": [
                {
                    "status": "incomplete",
                    "data": {"to": "0xdef", "value": "1", "chainId": 1},
                    "check": {"endpoint": "/intents/status?requestId=0xabc", "method": "GET"},
                }
            ],
        }
    )
    assert step.id == "deposit"
    assert step.request_id == "0xabc"
    assert step.items[0].status == "incomplete"
    assert step.items[0].check is not None
    assert step.items[0].check.method == "GET"


def test_quote_parses_steps_and_fees() -> None:
    quote = Quote.model_validate(
        {
            "steps": [
                {
                    "id": "deposit",
                    "action": "Confirm",
                    "description": "d",
                    "kind": "transaction",
                    "items": [{"status": "incomplete", "data": {}}],
                }
            ],
            "fees": {
                "gas": {
                    "currency": {"chainId": 1, "address": "0x0", "symbol": "ETH", "decimals": 18},
                    "amount": "100",
                }
            },
        }
    )
    assert len(quote.steps) == 1
    assert quote.fees is not None
    assert quote.fees.gas is not None
    assert quote.fees.gas.amount == "100"


def test_quote_tolerates_unknown_fields() -> None:
    # The API returns deeply nested feeSponsorship/details that we don't model
    # exhaustively. Parsing must not fail on extra keys.
    quote = Quote.model_validate(
        {
            "steps": [],
            "fees": {},
            "feeSponsorship": {"quoted": {"deeply": {"nested": True}}},
            "details": {"operation": "bridge", "rate": "1.0"},
            "protocol": {"v": 2},
            "someBrandNewField": 123,
        }
    )
    assert quote.steps == []


def test_fee_breakdown_optional_buckets() -> None:
    fb = FeeBreakdown.model_validate({})
    assert fb.gas is None
    assert fb.relayer is None
    assert fb.app is None


def test_trade_type_enum_values() -> None:
    assert TradeType.EXACT_INPUT.value == "EXACT_INPUT"
    assert TradeType.EXACT_OUTPUT.value == "EXACT_OUTPUT"
    assert TradeType.EXPECTED_OUTPUT.value == "EXPECTED_OUTPUT"


def test_chain_parses_minimal() -> None:
    chain = Chain.model_validate(
        {
            "id": 8453,
            "name": "base",
            "displayName": "Base",
            "depositEnabled": True,
            "tokenSupport": "All",
            "disabled": False,
            "vmType": "evm",
        }
    )
    assert chain.id == 8453
    assert chain.display_name == "Base"
    assert chain.deposit_enabled is True
    assert chain.vm_type == "evm"


def test_chain_parses_nested_v3_contracts() -> None:
    # The live API returns contracts.v3 as a nested object, even though the
    # OpenAPI spec types it as a string. Parsing must accept the object form.
    chain = Chain.model_validate(
        {
            "id": 1,
            "contracts": {
                "multicall3": "0xca11",
                "v3": {
                    "erc20Router": "0xb92f",
                    "approvalProxy": "0xccc8",
                },
            },
        }
    )
    assert chain.contracts is not None
    assert chain.contracts.multicall3 == "0xca11"
    assert chain.contracts.v3 == {"erc20Router": "0xb92f", "approvalProxy": "0xccc8"}


def test_chains_response_wraps_list() -> None:
    resp = ChainsResponse.model_validate(
        {"chains": [{"id": 1, "name": "ethereum", "displayName": "Ethereum"}]}
    )
    assert len(resp.chains) == 1
    assert resp.chains[0].id == 1


def test_transaction_status_parses() -> None:
    status = TransactionStatus.model_validate(
        {
            "status": "success",
            "originChainId": 8453,
            "destinationChainId": 10,
            "txHashes": ["0xaaa"],
            "inTxHashes": ["0xbbb"],
        }
    )
    assert status.status == "success"
    assert status.tx_hashes == ["0xaaa"]
    assert status.in_tx_hashes == ["0xbbb"]


def test_requests_response_parses() -> None:
    resp = RequestsResponse.model_validate(
        {
            "continuation": "cursor123",
            "requests": [
                {
                    "id": "req1",
                    "status": "success",
                    "user": "0xuser",
                    "data": {"foo": "bar"},
                }
            ],
        }
    )
    assert resp.continuation == "cursor123"
    assert resp.requests[0].id == "req1"
    assert resp.requests[0].data == {"foo": "bar"}


def test_token_price_parses() -> None:
    tp = TokenPrice.model_validate({"price": 1.0005})
    assert tp.price == 1.0005
