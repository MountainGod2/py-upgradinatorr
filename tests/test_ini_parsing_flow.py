"""Integration-style tests for parsing configuration data from disk."""

from collections.abc import Callable
from pathlib import Path

from upgradinatorr.config import parse_ini_config


def test_parse_ini_config_loads_multiple_application_sections(
    write_ini: Callable[[str, str], Path],
) -> None:
    """INI parser should preserve multiple app sections and values."""
    config_file = write_ini(
        """
[Radarr]
ApiKey=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
Url=http://localhost:7878
Count=5
TagName=upgrade

[Sonarr]
ApiKey=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
Url=http://localhost:8989
Count=max
TagName=upgrade
    """,
    )

    parsed = parse_ini_config(config_file)

    assert parsed["Radarr"]["Url"] == "http://localhost:7878"
    assert parsed["Sonarr"]["Count"] == "max"
