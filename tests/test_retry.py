"""Tests for the client's retry/backoff loop and network-error wrapping.

Sleeps are patched out so the tests run instantly.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from relay_link import AsyncRelayClient, RelayClient
from relay_link.exceptions import (
    RelayConnectionError,
    RelayRateLimitError,
    RelayTimeoutError,
)

BASE = "https://api.relay.link"


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    import relay_link.transport as transport

    monkeypatch.setattr(transport.time, "sleep", lambda _s: None)

    async def _async_noop(_s: float) -> None:
        return None

    monkeypatch.setattr(transport.asyncio, "sleep", _async_noop)


@respx.mock
def test_retries_429_then_succeeds() -> None:
    route = respx.get(f"{BASE}/chains").mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "0"}, json={"message": "slow"}),
            httpx.Response(200, json={"chains": [{"id": 1}]}),
        ]
    )
    client = RelayClient(max_retries=3)
    chains = client.get_chains()
    assert chains[0].id == 1
    assert route.call_count == 2


@respx.mock
def test_retries_5xx_then_succeeds() -> None:
    route = respx.get(f"{BASE}/chains").mock(
        side_effect=[
            httpx.Response(503, json={"message": "unavailable"}),
            httpx.Response(200, json={"chains": []}),
        ]
    )
    client = RelayClient(max_retries=3)
    client.get_chains()
    assert route.call_count == 2


@respx.mock
def test_exhausts_retries_then_raises_rate_limit_error() -> None:
    respx.get(f"{BASE}/chains").mock(
        return_value=httpx.Response(429, headers={"Retry-After": "0"}, json={"message": "no"})
    )
    client = RelayClient(max_retries=2)
    with pytest.raises(RelayRateLimitError) as exc:
        client.get_chains()
    assert exc.value.status_code == 429


@respx.mock
def test_exhausts_retries_on_5xx_then_raises() -> None:
    respx.get(f"{BASE}/chains").mock(return_value=httpx.Response(500, json={"message": "boom"}))
    client = RelayClient(max_retries=1)
    from relay_link.exceptions import RelayAPIError

    with pytest.raises(RelayAPIError) as exc:
        client.get_chains()
    assert exc.value.status_code == 500


@respx.mock
def test_4xx_not_retried() -> None:
    route = respx.get(f"{BASE}/chains").mock(
        return_value=httpx.Response(404, json={"message": "missing"})
    )
    client = RelayClient(max_retries=3)
    from relay_link.exceptions import RelayAPIError

    with pytest.raises(RelayAPIError):
        client.get_chains()
    assert route.call_count == 1


@respx.mock
def test_connect_error_wrapped() -> None:
    respx.get(f"{BASE}/chains").mock(side_effect=httpx.ConnectError("refused"))
    client = RelayClient(max_retries=0)
    with pytest.raises(RelayConnectionError):
        client.get_chains()


@respx.mock
def test_timeout_error_wrapped() -> None:
    respx.get(f"{BASE}/chains").mock(side_effect=httpx.ConnectTimeout("timed out"))
    client = RelayClient(max_retries=0)
    with pytest.raises(RelayTimeoutError):
        client.get_chains()


@respx.mock
async def test_async_retries_429_then_succeeds() -> None:
    route = respx.get(f"{BASE}/chains").mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "0"}, json={"message": "slow"}),
            httpx.Response(200, json={"chains": [{"id": 1}]}),
        ]
    )
    async with AsyncRelayClient(max_retries=3) as client:
        chains = await client.get_chains()
    assert chains[0].id == 1
    assert route.call_count == 2


@respx.mock
async def test_async_timeout_wrapped() -> None:
    respx.get(f"{BASE}/chains").mock(side_effect=httpx.ReadTimeout("timed out"))
    async with AsyncRelayClient(max_retries=0) as client:
        with pytest.raises(RelayTimeoutError):
            await client.get_chains()


@respx.mock
async def test_async_connect_error_wrapped() -> None:
    respx.get(f"{BASE}/chains").mock(side_effect=httpx.ConnectError("refused"))
    async with AsyncRelayClient(max_retries=0) as client:
        with pytest.raises(RelayConnectionError):
            await client.get_chains()
