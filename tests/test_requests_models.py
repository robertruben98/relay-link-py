"""Tests for request-body models and serialization to the API's camelCase."""

from __future__ import annotations

from relay_link.models import TradeType
from relay_link.requests import PriceRequest, QuoteRequest


def test_quote_request_serializes_to_camel_case() -> None:
    req = QuoteRequest(
        user="0xuser",
        origin_chain_id=8453,
        destination_chain_id=10,
        origin_currency="0x0",
        destination_currency="0x0",
        amount="1000000000000000000",
        trade_type=TradeType.EXACT_INPUT,
    )
    body = req.to_body()
    assert body["user"] == "0xuser"
    assert body["originChainId"] == 8453
    assert body["destinationChainId"] == 10
    assert body["originCurrency"] == "0x0"
    assert body["tradeType"] == "EXACT_INPUT"


def test_quote_request_omits_unset_optionals() -> None:
    req = QuoteRequest(
        user="0xuser",
        origin_chain_id=1,
        destination_chain_id=10,
        origin_currency="0x0",
        destination_currency="0x0",
        amount="100",
        trade_type=TradeType.EXACT_INPUT,
    )
    body = req.to_body()
    assert "recipient" not in body
    assert "slippageTolerance" not in body
    assert "useExternalLiquidity" not in body


def test_quote_request_includes_set_optionals() -> None:
    req = QuoteRequest(
        user="0xuser",
        origin_chain_id=1,
        destination_chain_id=10,
        origin_currency="0x0",
        destination_currency="0x0",
        amount="100",
        trade_type=TradeType.EXACT_INPUT,
        recipient="0xrecipient",
        slippage_tolerance="50",
        use_external_liquidity=True,
    )
    body = req.to_body()
    assert body["recipient"] == "0xrecipient"
    assert body["slippageTolerance"] == "50"
    assert body["useExternalLiquidity"] is True


def test_quote_request_accepts_plain_string_trade_type() -> None:
    req = QuoteRequest(
        user="0xuser",
        origin_chain_id=1,
        destination_chain_id=10,
        origin_currency="0x0",
        destination_currency="0x0",
        amount="100",
        trade_type="EXACT_OUTPUT",
    )
    assert req.to_body()["tradeType"] == "EXACT_OUTPUT"


def test_price_request_serializes() -> None:
    req = PriceRequest(
        user="0xuser",
        origin_chain_id=1,
        destination_chain_id=10,
        origin_currency="0x0",
        destination_currency="0x0",
        amount="100",
        trade_type=TradeType.EXACT_INPUT,
    )
    body = req.to_body()
    assert body["amount"] == "100"
    assert body["tradeType"] == "EXACT_INPUT"
