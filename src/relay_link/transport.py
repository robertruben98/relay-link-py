"""Shared HTTP plumbing: Retry-After parsing and backoff computation.

The logic here is transport-agnostic so the sync and async clients share
identical retry behavior and it is tested once. ``time`` and ``asyncio`` are
imported at module scope so tests can patch out the actual sleeping.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Mapping
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Optional

# ``time`` and ``asyncio`` are re-exported so the clients (and tests, which
# monkeypatch the sleeps) reference a single, patchable module attribute.
__all__ = [
    "asyncio",
    "time",
    "RETRYABLE_STATUSES",
    "DEFAULT_MAX_BACKOFF",
    "parse_retry_after",
    "backoff_delay",
]

#: HTTP statuses worth retrying: rate limiting plus transient server errors.
RETRYABLE_STATUSES = frozenset({429, 500, 502, 503, 504})

#: Cap on a single backoff wait so a high attempt count can't sleep forever.
DEFAULT_MAX_BACKOFF = 30.0


def parse_retry_after(
    headers: Mapping[str, str], *, now: Optional[datetime] = None
) -> Optional[float]:
    """Extract the ``Retry-After`` delay in seconds, if present.

    Per RFC 7231 the header may be either a number of seconds (delta) or an
    HTTP-date. Both forms are supported; an HTTP-date is converted to a delay
    relative to ``now`` (defaulting to the current UTC time) and clamped to a
    non-negative value. Returns ``None`` when the header is absent or
    unparseable, so callers fall back to exponential backoff.
    """
    value = headers.get("Retry-After") or headers.get("retry-after")
    if value is None:
        return None

    text = str(value).strip()

    # Form 1: a number of seconds.
    try:
        return float(text)
    except ValueError:
        pass

    # Form 2: an HTTP-date.
    try:
        target = parsedate_to_datetime(text)
    except (TypeError, ValueError):
        return None
    if target is None:
        return None
    if target.tzinfo is None:
        target = target.replace(tzinfo=timezone.utc)

    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)

    delay = (target - current).total_seconds()
    return max(0.0, delay)


def backoff_delay(
    *,
    base: float,
    attempt: int,
    retry_after: Optional[float],
    max_delay: float = DEFAULT_MAX_BACKOFF,
) -> float:
    """Compute the wait before the next retry (exponential, server-hint aware).

    ``attempt`` is zero-based. A server-provided ``Retry-After`` wins when it is
    larger than the computed exponential backoff. Negative ``Retry-After``
    values are ignored (clamped) so a stale HTTP-date can't shorten the wait
    below the backoff. The result is capped at ``max_delay``.
    """
    computed = base * float(2**attempt)
    if retry_after is not None and retry_after > 0:
        computed = max(computed, retry_after)
    return min(computed, max_delay)
