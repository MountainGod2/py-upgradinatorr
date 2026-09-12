"""Unit tests for configuration validation logic."""

from collections.abc import Callable
from pathlib import Path

import pytest

from upgradinatorr.config import (
    ApplicationConfig,
    NotificationConfig,
    get_application_type,
    parse_ini_config,
)


@pytest.mark.parametrize(
    ("instance_name", "expected_type"),
    [
        ("Radarr4K", "radarr"),
        ("My-Sonarr", "sonarr"),
        ("READARR", "readarr"),
    ],
)
def test_get_application_type_normalizes_instance_name(
    instance_name: str,
    expected_type: str,
) -> None:
    """Names with suffixes/prefixes still resolve to a supported app type."""
    assert get_application_type(instance_name) == expected_type


def test_get_application_type_rejects_unknown() -> None:
    """Unknown app names raise a helpful error."""
    with pytest.raises(ValueError, match="not a supported application"):
        get_application_type("bazarr")


def test_application_config_count_accepts_max() -> None:
    """Count can be configured using the literal max value."""
    config = ApplicationConfig(
        ApiKey="a" * 32,
        Url="http://localhost:7878/",
        Count="max",
        TagName="upgrade",
    )
    assert config.count == "max"
    assert config.url == "http://localhost:7878"


def test_application_config_rejects_bad_url() -> None:
    """URL must include an accepted scheme."""
    with pytest.raises(ValueError, match="URL must start"):
        ApplicationConfig(
            ApiKey="a" * 32,
            Url="localhost:7878",
            Count=1,
            TagName="upgrade",
        )


def test_notification_config_rejects_channel_id_format() -> None:
    """Channel ID must be a discord-style snowflake string."""
    with pytest.raises(ValueError, match="17-19 digits"):
        NotificationConfig(NotifiarrPassthroughDiscordChannelId="123")


def test_parse_ini_config_merges_general_to_notifications(
    write_ini: Callable[[str], Path],
) -> None:
    """General section webhook values should merge into Notifications."""
    config_file = write_ini(
        """
[General]
DiscordWebhook=https://discord.com/api/webhooks/11111111111111111/abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_ab

[Notifications]
NotifiarrPassthroughDiscordChannelId=12345678901234567
        """,
    )

    parsed = parse_ini_config(config_file)

    assert parsed["Notifications"]["DiscordWebhook"].startswith("https://discord.com/api/webhooks/")
    assert parsed["Notifications"]["NotifiarrPassthroughDiscordChannelId"] == "12345678901234567"
