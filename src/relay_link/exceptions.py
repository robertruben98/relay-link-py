"""Exception hierarchy for the Relay client."""

from __future__ import annotations

from typing import Any, Optional

import httpx


class RelayError(Exception):
    """Base class for every error raised by this library.

    Catch this to handle any failure — API errors, rate limiting, connection
    failures and timeouts all subclass it.
    """


class RelayAPIError(RelayError):
    """Raised when the Relay API returns a non-2xx response.

    Attributes:
        status_code: The HTTP status code of the response.
        message: A human-readable message, extracted from the response body
            when possible (the ``message`` or ``error`` field), else the
            HTTP reason phrase.
        body: The parsed JSON body, or ``None`` if it was not valid JSON.
    """

    def __init__(
        self,
        status_code: int,
        message: str,
        body: Optional[Any] = None,
    ) -> None:
        """Build an API error.

        Args:
            status_code: HTTP status code of the failing response.
            message: Human-readable error message.
            body: Parsed response body, if any.
        """
        self.status_code = status_code
        self.message = message
        self.body = body
        super().__init__(f"Relay API error {status_code}: {message}")

    @classmethod
    def from_response(cls, response: httpx.Response) -> RelayAPIError:
        """Construct an error from an httpx response.

        Args:
            response: The non-2xx response to wrap.

        Returns:
            An instance of ``cls`` whose ``message`` is taken from the body's
            ``message``/``error`` field when present, otherwise the HTTP reason
            phrase. ``body`` holds the parsed JSON, or ``None`` if the body is
            not valid JSON.
        """
        body: Optional[Any] = None
        message = response.reason_phrase or "request failed"
        try:
            body = response.json()
        except ValueError:
            body = None
        if isinstance(body, dict):
            extracted = body.get("message") or body.get("error")
            if isinstance(extracted, str):
                message = extracted
        return cls(status_code=response.status_code, message=message, body=body)


class RelayRateLimitError(RelayAPIError):
    """Raised on HTTP 429 once retries are exhausted.

    A subclass of :class:`RelayAPIError`, so ``status_code`` (always 429),
    ``message`` and ``body`` are available too.

    Attributes:
        retry_after: The server-advised wait in seconds parsed from the
            ``Retry-After`` header, or ``None`` when the header was absent or
            unparseable.
    """

    def __init__(
        self,
        status_code: int,
        message: str,
        body: Optional[Any] = None,
        retry_after: Optional[float] = None,
    ) -> None:
        """Build a rate-limit error.

        Args:
            status_code: HTTP status code (429).
            message: Human-readable error message.
            body: Parsed response body, if any.
            retry_after: Server-advised wait in seconds, if available.
        """
        super().__init__(status_code=status_code, message=message, body=body)
        self.retry_after = retry_after


class RelayConnectionError(RelayError):
    """Raised when the request fails to reach the API.

    Wraps a non-timeout :class:`httpx.TransportError` (e.g. a refused or reset
    connection, or DNS failure). The original exception is available via
    ``__cause__``.
    """


class RelayTimeoutError(RelayError):
    """Raised when the request to the API times out.

    Wraps an :class:`httpx.TimeoutException` (connect, read, write or pool
    timeout). The original exception is available via ``__cause__``.
    """
