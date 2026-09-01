"""Shared media display mapping for CLI and TUI renderers."""

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class MediaDisplayRow:
    """Normalized display fields for one media item."""

    title: str
    year: str
    status: str
    monitored: bool
    extra: str


def build_media_display_row(item: dict[str, Any], app_type: str) -> MediaDisplayRow:
    """Convert app-specific media payloads into a common display shape."""
    status = str(item.get("status", "unknown")).title()
    monitored = bool(item.get("monitored"))

    if app_type in {"radarr", "sonarr"}:
        extra = ""
        if app_type == "sonarr":
            seasons = str(
                item.get("seasonCount", item.get("statistics", {}).get("seasonCount", "?"))
            )
            extra = f"S: {seasons}"

        return MediaDisplayRow(
            title=item.get("title", "Unknown"),
            year=str(item.get("year", "")),
            status=status,
            monitored=monitored,
            extra=extra,
        )

    if app_type == "lidarr":
        return MediaDisplayRow(
            title=item.get("artistName", "Unknown"),
            year="",
            status=status,
            monitored=monitored,
            extra="",
        )

    if app_type == "readarr":
        return MediaDisplayRow(
            title=item.get("authorName", "Unknown"),
            year="",
            status=status,
            monitored=monitored,
            extra="",
        )

    return MediaDisplayRow(
        title=item.get("title", "Unknown"),
        year=str(item.get("year", "")),
        status=status,
        monitored=monitored,
        extra="",
    )
