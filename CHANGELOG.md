# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-06-21

Initial release.

### Added
- Synchronous `RelayClient` and asynchronous `AsyncRelayClient` over `httpx`,
  sharing configuration and request-shaping logic.
- Endpoints: `GET /chains`, `POST /quote/v2`, `POST /price`,
  `GET /intents/status/v3`, `GET /requests`, and `GET /currencies/token/price`.
- `poll_status()` helper that polls execution status until a terminal state
  (`success`, `failure`, or `refund`).
- Pydantic v2 response models with camelCase aliasing and tolerant parsing
  (`extra="allow"`) so the large, fast-evolving parts of the API
  (`feeSponsorship`, `details`, `protocol`) never break parsing.
- `QuoteRequest` / `PriceRequest` request-body models with `to_body()`
  serialization that omits unset fields.
- Retry/backoff for HTTP `429` and transient `5xx` responses: exponential
  backoff honoring `Retry-After` (clamped to >= 0, capped at 30s), with
  configurable `max_retries` and `backoff_base`.
- Typed exception hierarchy: `RelayError` base, `RelayAPIError`,
  `RelayRateLimitError` (with `retry_after`), `RelayConnectionError`, and
  `RelayTimeoutError` (raw `httpx` transport errors are wrapped).
- Configurable `base_url` and optional `api_key` with a configurable header
  name. Quotes are public and need no key.
- Optional `exec` extra (`web3`, `solders`) for signing the transaction steps a
  quote returns.
- `py.typed` marker, runnable `examples/`, and a GitHub Actions CI workflow with
  a lint job and a Python 3.9-3.13 test matrix.
- Rich Google-style docstrings (Args/Returns/Raises, with examples on
  `get_quote`) across the sync and async clients, and `Field(description=...)`
  metadata on the response and request models.
- `CHANGELOG.md`, `CONTRIBUTING.md`, and README badges (CI status, PyPI
  version, license, supported Python versions).

[Unreleased]: https://github.com/robertruben98/relay-link-py/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/robertruben98/relay-link-py/releases/tag/v0.1.0
