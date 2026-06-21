"""Tests for the synchronous RelayClient. All HTTP is mocked with respx."""

from __future__ import annotations

import httpx
import pytest
import respx

from relay_link import RelayClient
from relay_link.exceptions import RelayAPIError
from relay_link.models import Quote, TradeType

BASE = "https://api.relay.link"


@pytest.fixture
def client() -> RelayClient:
    return RelayClient()


def test_default_base_url(client: RelayClient) -> None:
    assert client.base_url == "https://api.relay.link"


def test_custom_base_url_strips_trailing_slash() -> None:
    c = RelayClient(base_url="https://staging.relay.link/")
    assert c.base_url == "https://staging.relay.link"


@respx.mock
def test_get_chains_parses_response(client: RelayClient) -> None:
    respx.get(f"{BASE}/chains").mock(
        return_value=httpx.Response(
            200, json={"chains": [{"id": 1, "name": "ethereum", "displayName": "Ethereum"}]}
        )
    )
    chains = client.get_chains()
    assert len(chains) == 1
    assert chains[0].id == 1
    assert chains[0].display_name == "Ethereum"


@respx.mock
def test_get_chains_passes_include_chains(client: RelayClient) -> None:
    route = respx.get(f"{BASE}/chains").mock(return_value=httpx.Response(200, json={"chains": []}))
    client.get_chains(include_chains="1,10")
    assert route.calls.last.request.url.params["includeChains"] == "1,10"


@respx.mock
def test_get_quote_posts_body_and_parses(client: RelayClient) -> None:
    route = respx.post(f"{BASE}/quote/v2").mock(
        return_value=httpx.Response(
            200,
            json={
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
                        "currency": {"chainId": 1, "symbol": "ETH", "decimals": 18},
                        "amount": "100",
                    }
                },
            },
        )
    )
    quote = client.get_quote(
        user="0xuser",
        origin_chain_id=8453,
        destination_chain_id=10,
        origin_currency="0x0",
        destination_currency="0x0",
        amount="1000000000000000000",
        trade_type=TradeType.EXACT_INPUT,
    )
    assert isinstance(quote, Quote)
    assert quote.steps[0].id == "deposit"
    sent = route.calls.last.request
    import json as _json

    body = _json.loads(sent.content)
    assert body["user"] == "0xuser"
    assert body["originChainId"] == 8453
    assert body["tradeType"] == "EXACT_INPUT"


@respx.mock
def test_get_status_parses(client: RelayClient) -> None:
    route = respx.get(f"{BASE}/intents/status/v3").mock(
        return_value=httpx.Response(200, json={"status": "success", "txHashes": ["0xaaa"]})
    )
    status = client.get_status(request_id="0xreq")
    assert status.status == "success"
    assert route.calls.last.request.url.params["requestId"] == "0xreq"


@respx.mock
def test_get_requests_parses(client: RelayClient) -> None:
    respx.get(f"{BASE}/requests").mock(
        return_value=httpx.Response(
            200,
            json={
                "continuation": "c1",
                "requests": [{"id": "r1", "status": "success", "user": "0xu"}],
            },
        )
    )
    resp = client.get_requests(user="0xu", limit=5)
    assert resp.continuation == "c1"
    assert resp.requests[0].id == "r1"


@respx.mock
def test_get_token_price_parses(client: RelayClient) -> None:
    route = respx.get(f"{BASE}/currencies/token/price").mock(
        return_value=httpx.Response(200, json={"price": 1.0005})
    )
    tp = client.get_token_price(address="0xtoken", chain_id=1)
    assert tp.price == 1.0005
    params = route.calls.last.request.url.params
    assert params["address"] == "0xtoken"
    assert params["chainId"] == "1"


@respx.mock
def test_get_price_posts_and_parses(client: RelayClient) -> None:
    respx.post(f"{BASE}/price").mock(
        return_value=httpx.Response(200, json={"fees": {}, "details": {"operation": "bridge"}})
    )
    price = client.get_price(
        origin_chain_id=1,
        destination_chain_id=10,
        origin_currency="0x0",
        destination_currency="0x0",
        amount="100",
        trade_type=TradeType.EXACT_INPUT,
    )
    assert price.details == {"operation": "bridge"}


@respx.mock
def test_api_key_header_sent() -> None:
    c = RelayClient(api_key="secret-key")
    route = respx.get(f"{BASE}/chains").mock(return_value=httpx.Response(200, json={"chains": []}))
    c.get_chains()
    assert route.calls.last.request.headers["x-api-key"] == "secret-key"


@respx.mock
def test_custom_api_key_header_name() -> None:
    c = RelayClient(api_key="secret-key", api_key_header="authorization")
    route = respx.get(f"{BASE}/chains").mock(return_value=httpx.Response(200, json={"chains": []}))
    c.get_chains()
    assert route.calls.last.request.headers["authorization"] == "secret-key"


@respx.mock
def test_error_response_raises_relay_api_error(client: RelayClient) -> None:
    respx.post(f"{BASE}/quote/v2").mock(
        return_value=httpx.Response(422, json={"message": "invalid amount"})
    )
    with pytest.raises(RelayAPIError) as exc_info:
        client.get_quote(
            user="0xuser",
            origin_chain_id=1,
            destination_chain_id=10,
            origin_currency="0x0",
            destination_currency="0x0",
            amount="0",
            trade_type=TradeType.EXACT_INPUT,
        )
    assert exc_info.value.status_code == 422
    assert "invalid amount" in str(exc_info.value)


def test_context_manager_closes() -> None:
    with RelayClient() as c:
        assert isinstance(c, RelayClient)


@respx.mock
def test_poll_status_returns_on_terminal_state(client: RelayClient) -> None:
    responses = [
        httpx.Response(200, json={"status": "pending"}),
        httpx.Response(200, json={"status": "pending"}),
        httpx.Response(200, json={"status": "success", "txHashes": ["0xaaa"]}),
    ]
    respx.get(f"{BASE}/intents/status/v3").mock(side_effect=responses)
    status = client.poll_status(request_id="0xreq", interval=0, timeout=10)
    assert status.status == "success"


@respx.mock
def test_poll_status_times_out(client: RelayClient) -> None:
    respx.get(f"{BASE}/intents/status/v3").mock(
        return_value=httpx.Response(200, json={"status": "pending"})
    )
    from relay_link.exceptions import RelayError

    with pytest.raises(RelayError):
        client.poll_status(request_id="0xreq", interval=0, timeout=0)
