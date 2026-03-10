"""Constants for Upgradinatorr."""

from typing import TypedDict

# Tag IDs for dry-run mode to avoid conflicts with real tags
DRY_RUN_TAG_ID = -1
DRY_RUN_IGNORE_TAG_ID = -2

MAX_DISCORD_DESCRIPTION_LENGTH = 4096


class AppColor(TypedDict):
    """Color configuration for an application."""

    hex: str
    decimal: int
    thumbnail: str


APP_COLORS: dict[str, AppColor] = {
    "radarr": {
        "hex": "FFC230",
        "decimal": 16761392,
        "thumbnail": "https://gh.notifiarr.com/images/icons/radarr.png",
    },
    "sonarr": {
        "hex": "00CCFF",
        "decimal": 52479,
        "thumbnail": "https://gh.notifiarr.com/images/icons/sonarr.png",
    },
    "lidarr": {
        "hex": "009252",
        "decimal": 37458,
        "thumbnail": "https://gh.notifiarr.com/images/icons/lidarr.png",
    },
    "readarr": {
        "hex": "8E2222",
        "decimal": 9314850,
        "thumbnail": "https://gh.notifiarr.com/images/icons/readarr.png",
    },
}

STATUS_FIELDS = {
    "radarr": "movie_status",
    "sonarr": "series_status",
    "lidarr": "artist_status",
    "readarr": "author_status",
}
