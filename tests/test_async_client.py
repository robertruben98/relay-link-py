"""Tests for the asynchronous AsyncRelayClient. All HTTP is mocked with respx."""

from __future__ import annotations

import httpx
import pytest
import respx

from relay_link import AsyncRelayClient
from relay_link.exceptions import RelayAPIError, RelayError
from relay_link.models import Quote, TradeType

BASE = "https://api.relay.link"


@respx.mock
async def test_async_get_chains() -> None:
    respx.get(f"{BASE}/chains").mock(
        return_value=httpx.Response(200, json={"chains": [{"id": 1, "name": "ethereum"}]})
    )
    async with AsyncRelayClient() as client:
        chains = await client.get_chains()
    assert chains[0].id == 1


@respx.mock
async def test_async_get_quote() -> None:
    respx.post(f"{BASE}/quote/v2").mock(
        return_value=httpx.Response(200, json={"steps": [], "fees": {}})
    )
    async with AsyncRelayClient() as client:
        quote = await client.get_quote(
            user="0xuser",
            origin_chain_id=8453,
            destination_chain_id=10,
            origin_currency="0x0",
            destination_currency="0x0",
            amount="100",
            trade_type=TradeType.EXACT_INPUT,
        )
    assert isinstance(quote, Quote)


@respx.mock
async def test_async_error_raises() -> None:
    respx.get(f"{BASE}/chains").mock(return_value=httpx.Response(500, json={"message": "boom"}))
    async with AsyncRelayClient() as client:
        with pytest.raises(RelayAPIError):
            await client.get_chains()


@respx.mock
async def test_async_get_status_and_requests() -> None:
    respx.get(f"{BASE}/intents/status/v3").mock(
        return_value=httpx.Response(200, json={"status": "success"})
    )
    respx.get(f"{BASE}/requests").mock(
        return_value=httpx.Response(200, json={"requests": [], "continuation": None})
    )
    async with AsyncRelayClient() as client:
        status = await client.get_status(request_id="0xreq")
        reqs = await client.get_requests()
    assert status.status == "success"
    assert reqs.requests == []


@respx.mock
async def test_async_poll_status_terminal() -> None:
    responses = [
        httpx.Response(200, json={"status": "pending"}),
        httpx.Response(200, json={"status": "failure"}),
    ]
    respx.get(f"{BASE}/intents/status/v3").mock(side_effect=responses)
    async with AsyncRelayClient() as client:
        status = await client.poll_status(request_id="0xreq", interval=0, timeout=10)
    assert status.status == "failure"


@respx.mock
async def test_async_poll_status_times_out() -> None:
    respx.get(f"{BASE}/intents/status/v3").mock(
        return_value=httpx.Response(200, json={"status": "pending"})
    )
    async with AsyncRelayClient() as client:
        with pytest.raises(RelayError):
            await client.poll_status(request_id="0xreq", interval=0, timeout=0)
