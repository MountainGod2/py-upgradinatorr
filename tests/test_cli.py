"""Smoke tests for CLI entrypoint behavior."""

from pathlib import Path
from typing import Any

from click.testing import CliRunner

from upgradinatorr.cli import main
from upgradinatorr.core import ApplicationRunResult


class FakeStarrClient:
    """Minimal async context manager used by CLI smoke tests."""

    def __init__(self, _app_name: str, _url: str, _api_key: str) -> None:
        self.api_version = "v3"

    async def __aenter__(self) -> "FakeStarrClient":
        return self

    async def __aexit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc: BaseException | None,
        _tb: Any,
    ) -> None:
        return


def test_cli_fails_when_config_file_is_missing() -> None:
    """Click should fail fast when the config path does not exist."""
    runner = CliRunner()

    result = runner.invoke(main, ["-a", "radarr", "-c", "missing.conf"])

    assert result.exit_code != 0
    assert "does not exist" in result.output


def test_cli_rejects_invalid_application_name(write_ini: Any) -> None:
    """Unsupported app names should abort without making API calls."""
    config_path = write_ini(
        """
[Bazarr]
ApiKey=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
Url=http://localhost:6767
Count=1
TagName=upgrade
        """,
    )

    runner = CliRunner()
    result = runner.invoke(main, ["-a", "bazarr", "-c", str(config_path)])

    assert result.exit_code != 0
    assert "not a supported application" in result.output


def test_cli_dry_run_passes_flag_to_workflow(
    monkeypatch: Any,
    write_ini: Any,
) -> None:
    """Dry-run option should flow into the shared workflow request."""
    config_path = write_ini(
        """
[Radarr]
ApiKey=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
Url=http://localhost:7878
Count=1
TagName=upgrade
        """,
    )

    captured_dry_run: list[bool] = []

    async def fake_run_application(request: Any) -> ApplicationRunResult:
        captured_dry_run.append(request.dry_run)
        return ApplicationRunResult(
            app_name="radarr",
            app_type="radarr",
            tag_id=1,
            ignore_tag_id=None,
            quality_profile_id=None,
            total_media=0,
            filtered_count=0,
            selected=[],
        )

    monkeypatch.setattr("upgradinatorr.cli.StarrClient", FakeStarrClient)
    monkeypatch.setattr("upgradinatorr.cli.run_application", fake_run_application)

    runner = CliRunner()
    result = runner.invoke(main, ["-a", "radarr", "-c", str(config_path), "--dry-run"])

    assert result.exit_code == 0
    assert captured_dry_run == [True]
