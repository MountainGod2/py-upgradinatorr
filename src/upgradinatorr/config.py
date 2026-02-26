"""Configuration management for Upgradinatorr."""

import re
from pathlib import Path
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SUPPORTED_APPS: set[str] = {"radarr", "sonarr", "lidarr", "readarr"}


def get_application_type(app_name: str) -> str:
    """Resolve an application instance name to a supported Starr app type.

    Examples:
        - "radarr" -> "radarr"
        - "radarr4k" -> "radarr"
        - "My-Sonarr" -> "sonarr"
    """
    lowered = app_name.lower()
    for supported_app in _supported_apps_by_length():
        if supported_app in lowered:
            return supported_app

    supported = ", ".join(sorted(SUPPORTED_APPS))
    msg = f"{app_name} is not a supported application. Supported applications: {supported}"
    raise ValueError(msg)


def _supported_apps_by_length() -> list[str]:
    """Return supported apps sorted longest-first for stable substring matching."""
    supported_apps = list(SUPPORTED_APPS)
    supported_apps.sort(key=lambda app: len(app), reverse=True)
    return supported_apps


class NotificationConfig(BaseModel):
    """Notification settings for Discord and Notifiarr."""

    model_config = ConfigDict(extra="forbid")

    discord_webhook: str | None = Field(None, alias="DiscordWebhook")
    notifiarr_webhook: str | None = Field(None, alias="NotifiarrPassthroughWebhook")
    notifiarr_channel_id: str | None = Field(None, alias="NotifiarrPassthroughDiscordChannelId")

    @field_validator("discord_webhook")
    @classmethod
    def validate_discord_webhook(cls, v: str | None) -> str | None:
        """Validate that the Discord webhook URL is in the correct format."""
        if v and not re.match(r"https://discord\.com/api/webhooks/\d{17,19}/[A-Za-z0-9_-]{68,}", v):
            msg = "Discord webhook must match format: https://discord.com/api/webhooks/ID/TOKEN"
            raise ValueError(
                msg,
            )
        return v

    @field_validator("notifiarr_webhook")
    @classmethod
    def validate_notifiarr_webhook(cls, v: str | None) -> str | None:
        """Validate that the Notifiarr webhook URL is in the correct format."""
        if v and not re.match(
            r"https://notifiarr\.com/api/v1/notification/passthrough/"
            r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
            v,
        ):
            msg = (
                "Notifiarr webhook must match format: "
                "https://notifiarr.com/api/v1/notification/passthrough/UUID"
            )
            raise ValueError(
                msg,
            )
        return v

    @field_validator("notifiarr_channel_id")
    @classmethod
    def validate_channel_id(cls, v: str | None) -> str | None:
        """Validate that the Notifiarr Discord channel ID is 17-19 digits."""
        if v and not re.match(r"^\d{17,19}$", v):
            msg = "Discord channel ID must be 17-19 digits"
            raise ValueError(msg)
        return v

    @model_validator(mode="after")
    def validate_no_quotes(self) -> Self:
        """Ensure no configuration values contain quotes."""
        for field_name, field_value in self.model_dump().items():
            if isinstance(field_value, str) and '"' in field_value:
                msg = (
                    f"Configuration value for '{field_name}' in Notifications section "
                    "contains quotes which are not allowed. "
                    "Please remove all quotes from your configuration."
                )
                raise ValueError(
                    msg,
                )
        return self


class ApplicationConfig(BaseModel):
    """Configuration for a Starr application instance."""

    model_config = ConfigDict(extra="forbid")

    api_key: str = Field(..., alias="ApiKey", min_length=32, max_length=32)
    url: str = Field(..., alias="Url")
    count: str | int = Field(..., alias="Count")
    monitored: bool = Field(default=True, alias="Monitored")
    unattended: bool = Field(default=False, alias="Unattended")
    tag_name: str = Field(..., alias="TagName", min_length=1)
    ignore_tag: str | None = Field(None, alias="IgnoreTag")
    quality_profile_name: str | None = Field(None, alias="QualityProfileName")

    # Application-specific status fields
    movie_status: str | None = Field(None, alias="MovieStatus")
    series_status: str | None = Field(None, alias="SeriesStatus")
    artist_status: str | None = Field(None, alias="ArtistStatus")
    author_status: str | None = Field(None, alias="AuthorStatus")

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Validate that the URL starts with http:// or https:// and does not end with a slash."""
        if not v.startswith(("http://", "https://")):
            msg = "URL must start with http:// or https://"
            raise ValueError(msg)
        return v.rstrip("/")

    @field_validator("count")
    @classmethod
    def validate_count(cls, v: str | int) -> str | int:
        """Validate that count is a positive integer or 'max'."""
        if isinstance(v, str):
            if v.lower() == "max":
                return "max"
            try:
                v = int(v)
            except ValueError as e:
                msg = "Count must be 'max' or a positive integer"
                raise ValueError(msg) from e

        if v < 1:
            msg = "Count must be greater than 0"
            raise ValueError(msg)
        return v

    @field_validator("movie_status")
    @classmethod
    def validate_movie_status(cls, v: str | None) -> str | None:
        """Validate that the movie status is one of the allowed values."""
        if v == "in cinemas":
            v = "inCinemas"
        if v and v not in ["tba", "announced", "inCinemas", "released", "deleted"]:
            msg = "MovieStatus must be one of: tba, announced, inCinemas, released, deleted"
            raise ValueError(
                msg,
            )
        return v

    @field_validator("series_status")
    @classmethod
    def validate_series_status(cls, v: str | None) -> str | None:
        """Validate that the series status is one of the allowed values."""
        if v and v not in ["continuing", "ended", "upcoming", "deleted"]:
            msg = "SeriesStatus must be one of: continuing, ended, upcoming, deleted"
            raise ValueError(msg)
        return v

    @field_validator("artist_status")
    @classmethod
    def validate_artist_status(cls, v: str | None) -> str | None:
        """Validate that the artist status is one of the allowed values."""
        if v and v not in ["continuing", "ended"]:
            msg = "ArtistStatus must be one of: continuing, ended"
            raise ValueError(msg)
        return v

    @field_validator("author_status")
    @classmethod
    def validate_author_status(cls, v: str | None) -> str | None:
        """Validate that the author status is one of the allowed values."""
        if v and v not in ["continuing", "ended"]:
            msg = "AuthorStatus must be one of: continuing, ended"
            raise ValueError(msg)
        return v

    @model_validator(mode="after")
    def validate_no_quotes(self) -> Self:
        """Ensure no configuration values contain quotes."""
        for field_name, field_value in self.model_dump().items():
            if isinstance(field_value, str) and '"' in field_value:
                msg = (
                    f"Configuration value for '{field_name}' contains quotes "
                    "which are not allowed. Please remove all quotes from your configuration."
                )
                raise ValueError(
                    msg,
                )
        return self


def validate_application_name(app_name: str) -> None:
    """Validate that the application name is supported.

    Args:
        app_name: Name of the application to validate

    Raises:
        ValueError: If application is not supported

    """
    get_application_type(app_name)


def parse_ini_config(config_path: Path) -> dict[str, dict[str, str]]:
    """Parse INI configuration file into nested dictionary.

    Also merges General section webhooks into Notifications section for backward compatibility.
    When both are defined, General section values take precedence.
    """
    config: dict[str, dict[str, str]] = {}
    current_section = None

    with config_path.open() as f:
        for raw_line in f:
            line = raw_line.strip()

            if not line or line.startswith(";"):
                continue

            if line.startswith("[") and line.endswith("]"):
                current_section = line[1:-1]
                config[current_section] = {}
                continue

            if "=" in line and current_section:
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()

                if not key.startswith(";"):
                    config[current_section][key] = value

    # General section takes precedence if both are defined
    if "General" in config:
        if "Notifications" not in config:
            config["Notifications"] = {}

        for key in [
            "DiscordWebhook",
            "NotifiarrPassthroughWebhook",
            "NotifiarrPassthroughDiscordChannelId",
        ]:
            if key in config["General"]:
                config["Notifications"][key] = config["General"][key]

    return config
