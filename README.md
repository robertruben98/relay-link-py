# relay-link-py

A typed Python client for the [Relay Protocol](https://relay.link) API — a fast
crosschain bridge and swap protocol. Sync and async, pydantic v2 models,
`py.typed`, no network needed to import.

- Base URL: `https://api.relay.link` (configurable)
- API reference: <https://docs.relay.link/references/api/overview>
- OpenAPI spec: <https://api.relay.link/documentation/json>

## Install

```bash
pip install relay-link-py
```

Python 3.9+ is supported. The data layer needs only `httpx` and `pydantic`.
Signing the transaction steps a quote returns is out of scope for the core
client; install the optional extra if you want `web3` / `solders` available:

```bash
pip install "relay-link-py[exec]"
```

## Quickstart

```python
from relay_link import RelayClient, TradeType

NATIVE = "0x0000000000000000000000000000000000000000"

with RelayClient() as client:
    # List supported chains (no API key required)
    chains = client.get_chains()
    print(f"{len(chains)} chains supported")

    # Get an executable quote: bridge 1 ETH from Base (8453) to Optimism (10)
    quote = client.get_quote(
        user="0x03508bb71268bba25ecacc8f620e01866650532c",
        origin_chain_id=8453,
        destination_chain_id=10,
        origin_currency=NATIVE,
        destination_currency=NATIVE,
        amount="1000000000000000000",  # 1 ETH in wei
        trade_type=TradeType.EXACT_INPUT,
    )
    for step in quote.steps:
        print(step.kind, step.id, step.action)
```

### Async

```python
import asyncio
from relay_link import AsyncRelayClient, TradeType

async def main():
    async with AsyncRelayClient() as client:
        chains = await client.get_chains()
        print(len(chains))

asyncio.run(main())
```

### Polling execution status

After you submit a step's transaction on-chain, poll its `requestId` until it
reaches a terminal state (`success`, `failure`, or `refund`):

```python
status = client.poll_status(request_id="0x...", interval=2, timeout=120)
print(status.status, status.tx_hashes)
```

## Configuration

```python
client = RelayClient(
    base_url="https://api.relay.link",  # configurable
    api_key="your-key",                 # optional; sent on every request
    api_key_header="x-api-key",         # configurable header name
    timeout=30.0,
    max_retries=3,                      # retries for 429 / 5xx responses
    backoff_base=0.5,                   # exponential backoff base (seconds)
)
```

Quotes are public and need no API key.

### Retries and errors

`429` and transient `5xx` responses are retried up to `max_retries` times with
exponential backoff, honoring a `Retry-After` header when present. The
exception hierarchy:

- `RelayError` — base class for everything this library raises.
  - `RelayAPIError` — non-2xx response; carries `status_code`, `message`, `body`.
    - `RelayRateLimitError` — `429` after retries are exhausted; adds `retry_after`.
  - `RelayConnectionError` — could not reach the API.
  - `RelayTimeoutError` — the request timed out.

## API surface

| Method | Endpoint | Description |
| --- | --- | --- |
| `get_chains()` | `GET /chains` | List supported chains |
| `get_quote(...)` | `POST /quote/v2` | Executable bridge/swap/call quote |
| `get_price(...)` | `POST /price` | Non-executable price estimate |
| `get_status(request_id=...)` | `GET /intents/status/v3` | Execution status |
| `poll_status(request_id=...)` | `GET /intents/status/v3` | Poll to a terminal state |
| `get_requests(...)` | `GET /requests` | List relay requests |
| `get_token_price(address=..., chain_id=...)` | `GET /currencies/token/price` | Token USD price |

`AsyncRelayClient` exposes the same methods as awaitables.

## Development

```bash
uv pip install -e ".[dev]"
ruff check .
mypy --strict src tests
pytest                  # unit tests (network mocked)
pytest -m integration   # one live test against GET /chains
```

## License

MIT
