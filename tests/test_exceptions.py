"""Tests for the exception hierarchy."""

from __future__ import annotations

import httpx
import pytest

from relay_link.exceptions import RelayAPIError, RelayError


def test_relay_api_error_is_relay_error() -> None:
    assert issubclass(RelayAPIError, RelayError)


def test_relay_api_error_carries_status_and_body() -> None:
    err = RelayAPIError(status_code=400, message="bad request", body={"error": "x"})
    assert err.status_code == 400
    assert err.body == {"error": "x"}
    assert "400" in str(err)
    assert "bad request" in str(err)


def test_from_response_builds_api_error() -> None:
    response = httpx.Response(422, json={"message": "invalid amount"})
    err = RelayAPIError.from_response(response)
    assert err.status_code == 422
    assert err.body == {"message": "invalid amount"}
    assert "invalid amount" in str(err)


def test_from_response_tolerates_non_json_body() -> None:
    response = httpx.Response(500, text="upstream exploded")
    err = RelayAPIError.from_response(response)
    assert err.status_code == 500
    assert err.body is None


def test_relay_error_is_exception() -> None:
    with pytest.raises(RelayError):
        raise RelayError("boom")
