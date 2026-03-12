"""Unit tests for Starr client retry helpers and request behavior."""

from http import HTTPStatus

import aiohttp
import pytest

from upgradinatorr.starr.client import (
    RETRYABLE_STATUS_CODES,
    StarrAPIError,
    StarrClient,
    _is_retryable_exception,
)


def test_is_retryable_exception_handles_connection_errors() -> None:
    """Transient network errors should be considered retryable."""
    exc = aiohttp.ClientConnectionError("boom")
    assert _is_retryable_exception(exc)


def test_is_retryable_exception_respects_starr_status_codes() -> None:
    """Only specific API status codes should be retried."""
    retryable = StarrAPIError(HTTPStatus.TOO_MANY_REQUESTS, "rate limit", "radarr")
    non_retryable = StarrAPIError(HTTPStatus.BAD_REQUEST, "bad request", "radarr")

    assert retryable.status in RETRYABLE_STATUS_CODES
    assert _is_retryable_exception(retryable)
    assert not _is_retryable_exception(non_retryable)


@pytest.mark.asyncio
async def test_request_once_requires_session() -> None:
    """Internal request helper should fail fast when client is not initialized."""
    client = StarrClient("radarr", "http://localhost:7878", "a" * 32)

    with pytest.raises(RuntimeError, match="Client not initialized"):
        await client._request_once("GET", "movie")
