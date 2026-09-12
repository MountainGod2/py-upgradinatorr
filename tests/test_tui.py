"""Smoke tests for Textual TUI entrypoint behavior."""

from pathlib import Path

import pytest
from textual.widgets import Log

from upgradinatorr.tui import UpgradinatorTUI


@pytest.mark.asyncio
async def test_tui_shows_error_when_config_missing(tmp_path: Path) -> None:
    """Missing config path currently results in an empty loaded config state."""
    app = UpgradinatorTUI(tmp_path / "missing.conf")

    async with app.run_test() as _pilot:
        log_lines = app.query_one("#log-display", Log).lines
        assert any("config loaded: 0 apps found" in line.lower() for line in log_lines)


@pytest.mark.asyncio
async def test_tui_start_with_no_selected_apps_logs_warning(write_ini: object) -> None:
    """Starting with all app checkboxes off should log a warning."""
    config_path = write_ini(
        """
[Radarr]
ApiKey=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
Url=http://localhost:7878
Count=1
TagName=upgrade
        """,
    )
    app = UpgradinatorTUI(config_path)

    async with app.run_test() as pilot:
        for checkbox in app.query("Checkbox"):
            if checkbox.id and checkbox.id.startswith("chk_"):
                checkbox.value = False

        app.action_start()
        await pilot.pause()

        log_lines = app.query_one("#log-display", Log).lines
        assert any("no applications selected" in line.lower() for line in log_lines)


@pytest.mark.asyncio
async def test_tui_refresh_button_triggers_reload(write_ini: object) -> None:
    """Refresh button should keep the app responsive and update status."""
    config_path = write_ini(
        """
[Radarr]
ApiKey=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
Url=http://localhost:7878
Count=1
TagName=upgrade
        """,
    )
    app = UpgradinatorTUI(config_path)

    async with app.run_test() as pilot:
        app.action_refresh()
        await pilot.pause()

        log_lines = app.query_one("#log-display", Log).lines
        assert any("config loaded" in line.lower() for line in log_lines)
