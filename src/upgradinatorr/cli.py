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
from upgradinatorr.core import NotificationSender, WorkflowReporter, run_application
from upgradinatorr.media_display import build_media_display_row
from upgradinatorr.notifications.completion import send_completion_notification
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


def create_media_table(media_items: list[dict[str, Any]], app_name: str) -> Table:
    """Create a formatted table for media items."""
    try:
        app_type = get_application_type(app_name)
    except ValueError:
        app_type = app_name.lower()

    app_style = get_app_style(app_name)
    table = Table(box=box.SIMPLE, border_style=app_style, show_header=True, pad_edge=False)

    if app_type == "radarr":
        table.add_column("Title", style="white")
        table.add_column("Year", style="cyan", justify="right")
        table.add_column("Status", style="magenta")
        table.add_column("Monitored", justify="center")
    elif app_type == "sonarr":
        table.add_column("Title", style="white")
        table.add_column("Year", style="cyan", justify="right")
        table.add_column("Status", style="magenta")
        table.add_column("Monitored", justify="center")
        table.add_column("Seasons", justify="right", style="green")
    elif app_type == "lidarr":
        table.add_column("Artist", style="white")
        table.add_column("Status", style="magenta")
        table.add_column("Monitored", justify="center")
    elif app_type == "readarr":
        table.add_column("Author", style="white")
        table.add_column("Status", style="magenta")
        table.add_column("Monitored", justify="center")

    for item in media_items:
        row = build_media_display_row(item, app_type)
        monitored = "Yes" if row.monitored else "No"
        status = row.status

        if status.lower() in ["continuing", "released", "announced"]:
            status = f"[green]{status}[/green]"
        elif status.lower() in ["ended", "missing"]:
            status = f"[red]{status}[/red]"

        if app_type == "radarr":
            table.add_row(
                row.title,
                row.year,
                status,
                monitored,
            )
        elif app_type == "sonarr":
            table.add_row(
                row.title,
                row.year,
                status,
                monitored,
                row.extra.replace("S: ", ""),
            )
        elif app_type in {"lidarr", "readarr"}:
            table.add_row(row.title, status, monitored)

    return table


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


async def process_application(
    app_name: str,
    config: ApplicationConfig,
    notifications: NotificationConfig | None = None,
    *,
    dry_run: bool = False,
    verbose: bool = False,
) -> None:
    """Process a single Starr application."""
    app_name = app_name.lower()
    app_style = get_app_style(app_name)

    console.print()
    console.rule(f"[{app_style}]{app_name.title()}[/{app_style}]")

    meta_parts = [
        f"[dim]{config.url}[/dim]",
        f"count=[dim]'{config.count}'[/dim]",
        f"tag=[dim]'{config.tag_name}'[/dim]",
    ]
    if config.ignore_tag:
        meta_parts.append(f"ignore=[dim]'{config.ignore_tag}'[/dim]")
    if dry_run:
        meta_parts.append("[yellow]dry-run[/yellow]")

    console.print(" · ".join(meta_parts))

    try:
        notification_sender: NotificationSender | None = None
        if notifications:

            async def configured_notification_sender(
                notif_app_name: str,
                media_items: list[dict[str, Any]],
                custom_message: str | None = None,
            ) -> None:
                await send_completion_notification(
                    notif_app_name,
                    media_items,
                    notifications,
                    custom_message,
                    warning_handler=lambda message: console.print(f"[yellow]  {message}[/yellow]"),
                )

            notification_sender = configured_notification_sender

        async with StarrClient(app_name, config.url, config.api_key) as client:
            if verbose:
                console.print(f"[dim]API version: {client.api_version}[/dim]")

            result = await run_application(
                client,
                app_name,
                config,
                dry_run=dry_run,
                verbose=verbose,
                reporter=RichWorkflowReporter(app_style, verbose_enabled=verbose),
                notification_sender=notification_sender,
            )

            if result.selected:
                table = create_media_table(result.selected, app_name)
                console.print(table)
    except StarrAPIError:
        raise
    except Exception:
        logger.exception("Unexpected error processing %s", app_name)
        raise


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

    app_list = []
    for app in applications:
        app_list.extend([a.strip() for a in app.split(",")])
    applications = tuple(app_list)

    try:
        config_dict = parse_ini_config(config_file)
    except Exception as e:
        console.print(f"[red]Error: failed to parse config: {e}[/red]")
        raise click.Abort from e

    notifications = None
    if "Notifications" in config_dict:
        try:
            notifications = NotificationConfig(**config_dict["Notifications"])
        except (ValidationError, ValueError) as e:
            console.print(f"[red]Error: invalid notification config: {e}[/red]")
            raise click.Abort from e
        except Exception as e:
            logger.exception("Unexpected error parsing notification config")
            console.print(f"[red]Error: notification config error: {e}[/red]")
            raise click.Abort from e

    async def run_all() -> None:
        apps_str = ", ".join(applications)
        console.print(f"[dim]{apps_str}[/dim]", justify="center")

        for app in applications:
            app_name = app.strip()
            app_lower = app_name.lower()

            try:
                validate_application_name(app_lower)
            except ValueError as e:
                console.print(f"[red]Error: {e}[/red]")
                raise click.Abort from e

            app_config_key = None
            for key in config_dict:
                if key.lower() == app_lower:
                    app_config_key = key
                    break

            if not app_config_key:
                console.print(f"[red]Error: no config section for '{app}'[/red]")
                raise click.Abort

            try:
                app_config = ApplicationConfig(
                    **cast("dict[str, Any]", config_dict[app_config_key])
                )
                await process_application(
                    app_name, app_config, notifications, dry_run=dry_run, verbose=verbose
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

    try:
        asyncio.run(run_all())
    except KeyboardInterrupt:
        console.print("\n[dim]interrupted[/dim]")
        raise click.Abort from None


if __name__ == "__main__":
    main()
