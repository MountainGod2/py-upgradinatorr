"""Unit tests for media selection and filtering helpers."""

import pytest

from upgradinatorr.starr.media import MediaFilter, get_media_title, select_random_media


def test_select_random_media_max_returns_all() -> None:
    """The max keyword should bypass random sampling."""
    items = [{"id": 1}, {"id": 2}]
    assert select_random_media(items, "max") == items


@pytest.mark.parametrize(
    ("item", "app_name", "expected_title"),
    [
        ({"title": "Alien"}, "radarr", "Alien"),
        ({"title": "The Expanse"}, "sonarr", "The Expanse"),
        ({"artistName": "Boards of Canada"}, "lidarr", "Boards of Canada"),
        ({"authorName": "Ursula K. Le Guin"}, "readarr", "Ursula K. Le Guin"),
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
