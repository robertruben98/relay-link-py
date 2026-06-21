"""Tests for retry/backoff helpers and the network-error exception hierarchy."""

from __future__ import annotations

from datetime import datetime, timezone

from relay_link.exceptions import (
    RelayAPIError,
    RelayConnectionError,
    RelayError,
    RelayRateLimitError,
    RelayTimeoutError,
)
from relay_link.transport import backoff_delay, parse_retry_after


def test_network_error_subclasses() -> None:
    assert issubclass(RelayConnectionError, RelayError)
    assert issubclass(RelayTimeoutError, RelayError)
    assert issubclass(RelayRateLimitError, RelayAPIError)


def test_rate_limit_error_carries_retry_after() -> None:
    err = RelayRateLimitError(status_code=429, message="slow down", retry_after=2.5)
    assert err.status_code == 429
    assert err.retry_after == 2.5
    assert isinstance(err, RelayAPIError)


def test_parse_retry_after_numeric_seconds() -> None:
    assert parse_retry_after({"Retry-After": "5"}) == 5.0
    assert parse_retry_after({"retry-after": "0.5"}) == 0.5


def test_parse_retry_after_absent_returns_none() -> None:
    assert parse_retry_after({}) is None


def test_parse_retry_after_http_date() -> None:
    now = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    delay = parse_retry_after({"Retry-After": "Mon, 01 Jan 2024 00:00:10 GMT"}, now=now)
    assert delay == 10.0


def test_parse_retry_after_clamps_past_date_to_zero() -> None:
    now = datetime(2024, 1, 1, 0, 0, 30, tzinfo=timezone.utc)
    # A date in the past must clamp to a non-negative delay.
    delay = parse_retry_after({"Retry-After": "Mon, 01 Jan 2024 00:00:10 GMT"}, now=now)
    assert delay == 0.0


def test_parse_retry_after_unparseable_returns_none() -> None:
    assert parse_retry_after({"Retry-After": "not-a-date"}) is None


def test_backoff_delay_is_exponential() -> None:
    assert backoff_delay(base=0.5, attempt=0, retry_after=None) == 0.5
    assert backoff_delay(base=0.5, attempt=1, retry_after=None) == 1.0
    assert backoff_delay(base=0.5, attempt=2, retry_after=None) == 2.0


def test_backoff_delay_caps_at_max() -> None:
    # A huge attempt count must not produce an unbounded sleep.
    delay = backoff_delay(base=1.0, attempt=20, retry_after=None, max_delay=30.0)
    assert delay == 30.0


def test_backoff_delay_honors_retry_after_when_larger() -> None:
    assert backoff_delay(base=0.5, attempt=0, retry_after=10.0) == 10.0


def test_backoff_delay_clamps_negative_retry_after() -> None:
    assert backoff_delay(base=0.5, attempt=0, retry_after=-5.0) == 0.5
