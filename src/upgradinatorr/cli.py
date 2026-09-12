"""Command-line interface for Upgradinatorr."""

import asyncio
import logging
from pathlib import Path
from typing import Any, cast

import rich_click as click
from pydantic import ValidationError
from rich import box
from rich.console import Console
from rich.table import Table

from upgradinatorr.config import (
    ApplicationConfig,
    NotificationConfig,
    get_application_type,
    parse_ini_config,
    validate_application_name,
)
from upgradinatorr.constants import (
    APP_COLORS,
)
from upgradinatorr.core import (
    ApplicationRunRequest,
    WorkflowReporter,
    run_application,
)
from upgradinatorr.media_display import build_media_display_row
from upgradinatorr.notifications.completion import (
    make_notification_sender,
)
from upgradinatorr.starr.client import StarrAPIError, StarrClient

console = Console(width=100)
logger = logging.getLogger(__name__)

click.rich_click.USE_RICH_MARKUP = True
click.rich_click.SHOW_ARGUMENTS = True
click.rich_click.GROUP_ARGUMENTS_OPTIONS = True
click.rich_click.STYLE_ERRORS_SUGGESTION = "magenta italic"
click.rich_click.STYLE_OPTIONS_TABLE_BOX = "SIMPLE"


def get_app_style(app_name: str) -> str:
    """Get the color style for an application."""
    try:
        app_type = get_application_type(app_name)
    except ValueError:
        app_type = app_name.lower()

    app_color = APP_COLORS.get(app_type)
    if app_color:
        return f"#{app_color['hex']}"
    return "#FFFFFF"


def _get_app_type(app_name: str) -> str:
    try:
        return get_application_type(app_name)
    except ValueError:
        return app_name.lower()


def _add_media_columns(table: Table, app_type: str) -> None:
    if app_type in {"radarr", "sonarr"}:
        table.add_column("Title", style="white")
        table.add_column("Year", style="cyan", justify="right")
        table.add_column("Status", style="magenta")
        table.add_column("Monitored", justify="center")
        if app_type == "sonarr":
            table.add_column("Seasons", justify="right", style="green")
        return

    if app_type == "lidarr":
        table.add_column("Artist", style="white")
        table.add_column("Status", style="magenta")
        table.add_column("Monitored", justify="center")
        return

    if app_type == "readarr":
        table.add_column("Author", style="white")
        table.add_column("Status", style="magenta")
        table.add_column("Monitored", justify="center")


def _style_status(status: str) -> str:
    normalized = status.lower()
    if normalized in {"continuing", "released", "announced"}:
        return f"[green]{status}[/green]"
    if normalized in {"ended", "missing"}:
        return f"[red]{status}[/red]"
    return status


def create_media_table(media_items: list[dict[str, Any]], app_name: str) -> Table:
    """Create a formatted table for media items."""
    app_type = _get_app_type(app_name)

    app_style = get_app_style(app_name)
    table = Table(box=box.SIMPLE, border_style=app_style, show_header=True, pad_edge=False)

    _add_media_columns(table, app_type)

    for item in media_items:
        row = build_media_display_row(item, app_type)
        monitored = "Yes" if row.monitored else "No"
        status = _style_status(row.status)

        if app_type == "sonarr":
            table.add_row(row.title, row.year, status, monitored, row.extra.replace("S: ", ""))
        elif app_type in {"radarr", "lidarr", "readarr"}:
            values = [row.title, status, monitored]
            if app_type == "radarr":
                values.insert(1, row.year)
            table.add_row(*values)

    return table


def _normalize_applications(applications: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(
        app_name.strip()
        for application_group in applications
        for app_name in application_group.split(",")
        if app_name.strip()
    )


def _load_notifications(config_dict: dict[str, Any]) -> NotificationConfig | None:
    if "Notifications" not in config_dict:
        return None

    try:
        return NotificationConfig(**config_dict["Notifications"])
    except (ValidationError, ValueError) as e:
        console.print(f"[red]Error: invalid notification config: {e}[/red]")
        raise click.Abort from e
    except Exception as e:
        logger.exception("Unexpected error parsing notification config")
        console.print(f"[red]Error: notification config error: {e}[/red]")
        raise click.Abort from e


async def _process_cli_application(
    app_name: str,
    config_dict: dict[str, Any],
    notifications: NotificationConfig | None,
    *,
    verbose: bool,
    dry_run: bool,
) -> None:
    app_lower = app_name.lower()

    validate_application_name(app_lower)

    app_config_key = next((key for key in config_dict if key.lower() == app_lower), None)
    if not app_config_key:
        console.print(f"[red]Error: no config section for '{app_name}'[/red]")
        raise click.Abort

    app_config = ApplicationConfig(**cast("dict[str, Any]", config_dict[app_config_key]))
    app_style = get_app_style(app_name)

    notification_sender = make_notification_sender(
        notifications,
        warning_handler=lambda message: console.print(f"[yellow]  {message}[/yellow]"),
    )

    async with StarrClient(app_lower, app_config.url, app_config.api_key) as client:
        if verbose:
            console.print(f"[dim]API version: {client.api_version}[/dim]")

        result = await run_application(
            ApplicationRunRequest(
                client=client,
                app_name=app_lower,
                config=app_config,
                dry_run=dry_run,
                verbose=verbose,
                reporter=RichWorkflowReporter(app_style, verbose_enabled=verbose),
                notification_sender=notification_sender,
            )
        )

        if result.selected:
            table = create_media_table(result.selected, app_name)
            console.print(table)


async def _run_cli(
    applications: tuple[str, ...],
    config_dict: dict[str, Any],
    notifications: NotificationConfig | None,
    *,
    verbose: bool,
    dry_run: bool,
) -> None:
    apps_str = ", ".join(applications)
    console.print(f"[dim]{apps_str}[/dim]", justify="center")

    for app in applications:
        try:
            await _process_cli_application(
                app,
                config_dict,
                notifications,
                verbose=verbose,
                dry_run=dry_run,
            )
        except (StarrAPIError, ValidationError, ValueError) as e:
            console.print(f"[red]Error: {app}: {e}[/red]")
            if verbose:
                console.print_exception()
            raise click.Abort from e
        except Exception as e:
            logger.exception("Unexpected error processing %s", app)
            console.print(f"[red]Error: {app}: unexpected error - {e}[/red]")
            if verbose:
                console.print_exception()
            raise click.Abort from e

    console.print()


class RichWorkflowReporter(WorkflowReporter):
    """Render workflow events for CLI output."""

    def __init__(self, app_style: str, *, verbose_enabled: bool) -> None:
        """Store rendering style and verbosity flags."""
        self.app_style = app_style
        self.verbose_enabled = verbose_enabled

    def status(self, message: str) -> None:
        """Render a workflow status update."""
        console.print(f"[{self.app_style}]{message}[/{self.app_style}]")

    def info(self, message: str) -> None:
        """Render an informational workflow message."""
        console.print(f"[dim]{message}[/dim]")

    def warning(self, message: str) -> None:
        """Render a warning workflow message."""
        console.print(f"[yellow]  {message}[/yellow]")

    def success(self, message: str) -> None:
        """Render a successful workflow message."""
        console.print(f"[green]Success:[/green] {message}")

    def verbose(self, message: str) -> None:
        """Render a verbose workflow message when enabled."""
        if self.verbose_enabled:
            console.print(f"[dim]{message}[/dim]")


@click.command()
@click.option(
    "-a",
    "--apps",
    "applications",
    required=True,
    multiple=True,
    help=("Config section names to process (e.g., radarr,radarr4k or sonarr-main)"),
)
@click.option(
    "-c",
    "--config",
    "config_file",
    type=click.Path(exists=True, path_type=Path),
    default=Path("upgradinatorr.conf"),
    help="Path to configuration file",
)
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    help="Enable verbose output",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Simulate run without making changes",
)
@click.version_option(package_name="upgradinatorr", prog_name="upgradinatorr")
def main(
    applications: tuple[str, ...],
    config_file: Path,
    verbose: bool,  # noqa: FBT001
    dry_run: bool,  # noqa: FBT001
) -> None:
    """[bold cyan]Upgradinatorr[/bold cyan] - Automated media upgrade search for Starr applications.

    Triggers manual searches in Radarr, Sonarr, Lidarr, and Readarr to find
    upgrades for your media, especially useful after modifying Custom Formats.

    [bold]Examples:[/bold]

        upgradinatorr -a radarr,radarr4k

        upgradinatorr -a radarr -c /path/to/config.conf

        upgradinatorr -a lidarr,readarr --verbose

        upgradinatorr -a radarr --dry-run
    """
    console.rule("[bold cyan]Upgradinatorr[/bold cyan]")

    applications = _normalize_applications(applications)

    try:
        config_dict = parse_ini_config(config_file)
    except Exception as e:
        console.print(f"[red]Error: failed to parse config: {e}[/red]")
        raise click.Abort from e

    notifications = _load_notifications(config_dict)

    try:
        asyncio.run(
            _run_cli(
                applications,
                config_dict,
                notifications,
                verbose=verbose,
                dry_run=dry_run,
            )
        )
    except KeyboardInterrupt:
        console.print("\n[dim]interrupted[/dim]")
        raise click.Abort from None


if __name__ == "__main__":
    main()
