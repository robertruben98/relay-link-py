"""Exception hierarchy for the Relay client."""

from __future__ import annotations

from typing import Any, Optional

import httpx


class RelayError(Exception):
    """Base class for all errors raised by this library."""


class RelayAPIError(RelayError):
    """Raised when the Relay API returns a non-2xx response."""

    def __init__(
        self,
        status_code: int,
        message: str,
        body: Optional[Any] = None,
    ) -> None:
        self.status_code = status_code
        self.message = message
        self.body = body
        super().__init__(f"Relay API error {status_code}: {message}")

    @classmethod
    def from_response(cls, response: httpx.Response) -> RelayAPIError:
        """Build an error from an httpx response, extracting a useful message."""
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
