"""Unit tests for Starr application clients and media selection."""

from http import HTTPStatus

import aiohttp
import pytest

from upgradinatorr.starr.client import (
    RETRYABLE_STATUS_CODES,
    StarrAPIError,
    StarrClient,
    _is_retryable_exception,
)
from upgradinatorr.starr.media import MediaFilter, get_media_title, select_random_media


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


def test_select_random_media_max_returns_all() -> None:
    """The max keyword should bypass random sampling."""
    items = [{"id": 1}, {"id": 2}]
    assert select_random_media(items, "max") == items


@pytest.mark.parametrize(
    ("item", "app_name", "expected_title"),
    [
        ({"title": "2001: A Space Odyssey"}, "radarr", "2001: A Space Odyssey"),
        ({"title": "The Wire"}, "sonarr", "The Wire"),
        ({"artistName": "Pink Floyd"}, "lidarr", "Pink Floyd"),
        ({"authorName": "Stephen King"}, "readarr", "Stephen King"),
    ],
)
def test_get_media_title_uses_application_specific_field(
    item: dict[str, str],
    app_name: str,
    expected_title: str,
) -> None:
    """Each app should use the correct display-name field."""
    assert get_media_title(item, app_name) == expected_title


def test_filter_attended_applies_all_constraints() -> None:
    """Attended mode should exclude tagged items and apply optional filters."""
    media_items = [
        {
            "id": 1,
            "monitored": True,
            "tags": [],
            "status": "released",
            "qualityProfileId": 10,
        },
        {
            "id": 2,
            "monitored": True,
            "tags": [5],
            "status": "released",
            "qualityProfileId": 10,
        },
        {
            "id": 3,
            "monitored": True,
            "tags": [99],
            "status": "announced",
            "qualityProfileId": 99,
        },
    ]

    media_filter = MediaFilter(
        monitored=True,
        tag_id=5,
        status="released",
        quality_profile_id=10,
        ignore_tag_id=99,
    )

    filtered = media_filter.filter_attended(media_items)

    assert [item["id"] for item in filtered] == [1]
