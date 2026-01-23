"""Media filtering logic for Starr applications."""

import random
from typing import Any, Optional

from rich.console import Console

console = Console(width=100)


class MediaFilter:
    """Filter media items based on configuration criteria."""

    def __init__(
        self,
        monitored: bool,
        tag_id: int,
        status: Optional[str] = None,
        quality_profile_id: Optional[int] = None,
        ignore_tag_id: Optional[int] = None,
    ) -> None:
        """Initialize media filter.

        Args:
            monitored: Filter by monitored status
            tag_id: Tag ID to filter by
            status: Optional status to filter by
            quality_profile_id: Optional quality profile ID to filter by
            ignore_tag_id: Optional tag ID to exclude from results
        """
        self.monitored = monitored
        self.tag_id = tag_id
        self.status = status
        self.quality_profile_id = quality_profile_id
        self.ignore_tag_id = ignore_tag_id

    def filter_unattended(self, media: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Filter media for unattended mode (only items WITH the tag)."""
        return [
            item
            for item in media
            if item.get("monitored") == self.monitored and self.tag_id in item.get("tags", [])
        ]

    def filter_attended(self, media: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Filter media for attended mode (items WITHOUT the tag)."""
        filtered = [
            item
            for item in media
            if item.get("monitored") == self.monitored and self.tag_id not in item.get("tags", [])
        ]

        # Apply optional filters
        if self.status:
            filtered = [item for item in filtered if item.get("status") == self.status]

        if self.quality_profile_id:
            filtered = [
                item for item in filtered if item.get("qualityProfileId") == self.quality_profile_id
            ]

        if self.ignore_tag_id:
            filtered = [item for item in filtered if self.ignore_tag_id not in item.get("tags", [])]

        return filtered

    @staticmethod
    def select_random(media: list[dict[str, Any]], count: int | str) -> list[dict[str, Any]]:
        """Select random media items based on count.

        Args:
            media: List of media items
            count: Number of items to select, or "max" for all

        Returns:
            Selected media items
        """
        if count == "max":
            return media

        count_int = int(count) if isinstance(count, str) else count
        return random.sample(media, min(count_int, len(media)))

    @staticmethod
    def get_media_title(item: dict[str, Any], app_name: str) -> str:
        """Get the title/name of a media item based on app type."""
        title_fields = {
            "radarr": "title",
            "sonarr": "title",
            "lidarr": "artistName",
            "readarr": "authorName",
        }
        return str(item.get(title_fields.get(app_name, "title"), "Unknown"))
