"""Configuration management for Upgradinatorr."""

import re
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field, field_validator, ConfigDict, model_validator

# Supported Starr applications
SUPPORTED_APPS = {"radarr", "sonarr", "lidarr", "readarr"}


class NotificationConfig(BaseModel):
    """Notification settings for Discord and Notifiarr."""

    model_config = ConfigDict(extra="forbid")

    discord_webhook: Optional[str] = Field(None, alias="DiscordWebhook")
    notifiarr_webhook: Optional[str] = Field(None, alias="NotifiarrPassthroughWebhook")
    notifiarr_channel_id: Optional[str] = Field(None, alias="NotifiarrPassthroughDiscordChannelId")

    @field_validator("discord_webhook")
    @classmethod
    def validate_discord_webhook(cls, v: Optional[str]) -> Optional[str]:
        if v and not re.match(r"https://discord\.com/api/webhooks/\d{17,19}/[A-Za-z0-9_-]{68,}", v):
            raise ValueError(
                "Discord webhook must match format: https://discord.com/api/webhooks/ID/TOKEN"
            )
        return v

    @field_validator("notifiarr_webhook")
    @classmethod
    def validate_notifiarr_webhook(cls, v: Optional[str]) -> Optional[str]:
        if v and not re.match(
            r"https://notifiarr\.com/api/v1/notification/passthrough/"
            r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
            v,
        ):
            raise ValueError(
                "Notifiarr webhook must match format: "
                "https://notifiarr.com/api/v1/notification/passthrough/UUID"
            )
        return v

    @field_validator("notifiarr_channel_id")
    @classmethod
    def validate_channel_id(cls, v: Optional[str]) -> Optional[str]:
        if v and not re.match(r"^\d{17,19}$", v):
            raise ValueError("Discord channel ID must be 17-19 digits")
        return v

    @model_validator(mode="after")
    def validate_no_quotes(self) -> "NotificationConfig":
        """Ensure no configuration values contain quotes."""
        for field_name, field_value in self.model_dump().items():
            if isinstance(field_value, str) and '"' in field_value:
                raise ValueError(
                    f"Configuration value for '{field_name}' in Notifications section contains quotes which are not allowed. "
                    "Please remove all quotes from your configuration."
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
    ignore_tag: Optional[str] = Field(None, alias="IgnoreTag")
    quality_profile_name: Optional[str] = Field(None, alias="QualityProfileName")

    # Application-specific status fields
    movie_status: Optional[str] = Field(None, alias="MovieStatus")
    series_status: Optional[str] = Field(None, alias="SeriesStatus")
    artist_status: Optional[str] = Field(None, alias="ArtistStatus")
    author_status: Optional[str] = Field(None, alias="AuthorStatus")

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return v.rstrip("/")

    @field_validator("count")
    @classmethod
    def validate_count(cls, v: str | int) -> str | int:
        if isinstance(v, str):
            if v.lower() == "max":
                return "max"
            try:
                v = int(v)
            except ValueError:
                raise ValueError("Count must be 'max' or a positive integer")

        if v < 1:
            raise ValueError("Count must be greater than 0")
        return v

    @field_validator("movie_status")
    @classmethod
    def validate_movie_status(cls, v: Optional[str]) -> Optional[str]:
        if v == "in cinemas":
            v = "inCinemas"
        if v and v not in ["tba", "announced", "inCinemas", "released", "deleted"]:
            raise ValueError(
                "MovieStatus must be one of: tba, announced, inCinemas, released, deleted"
            )
        return v

    @field_validator("series_status")
    @classmethod
    def validate_series_status(cls, v: Optional[str]) -> Optional[str]:
        if v and v not in ["continuing", "ended", "upcoming", "deleted"]:
            raise ValueError("SeriesStatus must be one of: continuing, ended, upcoming, deleted")
        return v

    @field_validator("artist_status")
    @classmethod
    def validate_artist_status(cls, v: Optional[str]) -> Optional[str]:
        if v and v not in ["continuing", "ended"]:
            raise ValueError("ArtistStatus must be one of: continuing, ended")
        return v

    @field_validator("author_status")
    @classmethod
    def validate_author_status(cls, v: Optional[str]) -> Optional[str]:
        if v and v not in ["continuing", "ended"]:
            raise ValueError("AuthorStatus must be one of: continuing, ended")
        return v

    @model_validator(mode="after")
    def validate_no_quotes(self) -> "ApplicationConfig":
        """Ensure no configuration values contain quotes."""
        for field_name, field_value in self.model_dump().items():
            if isinstance(field_value, str) and '"' in field_value:
                raise ValueError(
                    f"Configuration value for '{field_name}' contains quotes which are not allowed. "
                    "Please remove all quotes from your configuration."
                )
        return self


def validate_application_name(app_name: str) -> None:
    """Validate that the application name is supported.
    
    Args:
        app_name: Name of the application to validate
        
    Raises:
        ValueError: If application is not supported
    """
    if app_name.lower() not in SUPPORTED_APPS:
        raise ValueError(
            f"{app_name} is not a supported application. "
            f"Supported applications: {', '.join(sorted(SUPPORTED_APPS))}"
        )


def parse_ini_config(config_path: Path) -> dict[str, dict[str, str]]:
    """Parse INI configuration file into nested dictionary.
    
    Also merges General section webhooks into Notifications section for backward compatibility.
    """
    config: dict[str, dict[str, str]] = {}
    current_section = None

    with open(config_path) as f:
        for line in f:
            line = line.strip()

            # Skip empty lines and comments
            if not line or line.startswith(";"):
                continue

            # Section header
            if line.startswith("[") and line.endswith("]"):
                current_section = line[1:-1]
                config[current_section] = {}
                continue

            # Key-value pair
            if "=" in line and current_section:
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()

                # Skip if starts with semicolon (commented out)
                if not key.startswith(";"):
                    config[current_section][key] = value

    # Merge General section webhooks into Notifications
    # Notifications section takes precedence if both are defined
    if "General" in config:
        if "Notifications" not in config:
            config["Notifications"] = {}
        
        # Only copy if not already in Notifications
        for key in ["DiscordWebhook", "NotifiarrPassthroughWebhook", "NotifiarrPassthroughDiscordChannelId"]:
            if key in config["General"] and key not in config["Notifications"]:
                config["Notifications"][key] = config["General"][key]

    return config
