"""Command-line interface for Upgradinatorr."""

import asyncio
from pathlib import Path
from typing import Any, Optional, TypedDict, cast

import rich_click as click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from upgradinatorr.config import (
    ApplicationConfig,
    NotificationConfig,
    parse_ini_config,
)
from upgradinatorr.notifications.discord import send_discord_notification
from upgradinatorr.notifications.notifiarr import send_notifiarr_notification
from upgradinatorr.starr.client import StarrClient, StarrAPIError
from upgradinatorr.starr.media import MediaFilter

console = Console()

# Configure rich-click
click.rich_click.USE_RICH_MARKUP = True
click.rich_click.SHOW_ARGUMENTS = True
click.rich_click.GROUP_ARGUMENTS_OPTIONS = True
click.rich_click.STYLE_ERRORS_SUGGESTION = "magenta italic"


class AppColor(TypedDict):
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


async def process_application(
    app_name: str,
    config: ApplicationConfig,
    notifications: Optional[NotificationConfig] = None,
) -> None:
    """Process a single Starr application.

    Args:
        app_name: Name of the application (radarr, sonarr, etc.)
        config: Application configuration
        notifications: Optional notification configuration
    """
    app_name = app_name.lower()

    console.print(
        Panel(f"[bold cyan]Processing {app_name.title()}[/bold cyan]", border_style="cyan")
    )

    try:
        async with StarrClient(app_name, config.url, config.api_key) as client:
            # Get or create tags
            tag_id = await client.get_or_create_tag(config.tag_name)
            ignore_tag_id = None
            if config.ignore_tag:
                ignore_tag_id = await client.get_or_create_tag(config.ignore_tag)
                if tag_id == ignore_tag_id:
                    raise ValueError(
                        f"Tag '{config.tag_name}' and ignore tag '{config.ignore_tag}' "
                        "cannot be the same"
                    )

            # Get quality profile ID if specified
            quality_profile_id = None
            if config.quality_profile_name:
                quality_profile_id = await client.get_quality_profile_id(
                    config.quality_profile_name
                )

            # Determine status based on app type
            status = None
            if app_name == "radarr":
                status = config.movie_status
            elif app_name == "sonarr":
                status = config.series_status
            elif app_name == "lidarr":
                status = config.artist_status
            elif app_name == "readarr":
                status = config.author_status

            # Get all media
            all_media = await client.get_all_media()

            # Filter media
            media_filter = MediaFilter(
                monitored=config.monitored,
                tag_id=tag_id,
                status=status,
                quality_profile_id=quality_profile_id,
                ignore_tag_id=ignore_tag_id,
            )

            if config.unattended:
                filtered = media_filter.filter_unattended(all_media)
            else:
                filtered = media_filter.filter_attended(all_media)

            # Handle empty results
            if not filtered:
                if config.unattended:
                    # Remove tag from all tagged items and re-filter
                    console.print(
                        "[yellow]No media left to process. Removing tags and re-filtering...[/yellow]"
                    )
                    tagged_media = media_filter.filter_unattended(all_media)
                    if tagged_media:
                        media_ids = [item["id"] for item in tagged_media]
                        await client.remove_tags_from_media(media_ids, tag_id)
                        all_media = await client.get_all_media()
                        filtered = media_filter.filter_attended(all_media)

                    if not filtered:
                        console.print("[yellow]No media to process after tag removal[/yellow]")
                        return
                else:
                    console.print("[yellow]No media found matching criteria[/yellow]")
                    if notifications:
                        await send_completion_notification(
                            app_name, [], notifications, "No media left to search"
                        )
                    return

            console.print(f"[green]Found {len(filtered)} media items matching criteria[/green]")

            # Select random media based on count
            selected = MediaFilter.select_random(filtered, config.count)
            console.print(f"[cyan]Selected {len(selected)} items to search[/cyan]")

            # Start searches
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task(
                    f"Searching {len(selected)} items in {app_name.title()}...",
                    total=None,
                )
                await client.search_media_batch(selected)
                progress.update(task, completed=True)

            # Add tags
            media_ids = [item["id"] for item in selected]
            await client.add_tags_to_media(media_ids, tag_id)

            # Send notifications
            if notifications:
                await send_completion_notification(app_name, selected, notifications)

            console.print(
                Panel(
                    f"[bold green]✓ Successfully processed {len(selected)} items "
                    f"in {app_name.title()}[/bold green]",
                    border_style="green",
                )
            )

    except StarrAPIError as e:
        console.print(f"[red]API Error: {e}[/red]")
        raise
    except Exception as e:
        console.print(f"[red]Unexpected error: {e}[/red]")
        raise


async def send_completion_notification(
    app_name: str,
    media_items: list[dict],
    notifications: NotificationConfig,
    custom_message: Optional[str] = None,
) -> None:
    """Send completion notification."""
    colors = APP_COLORS.get(app_name, APP_COLORS["radarr"])

    if custom_message:
        description = custom_message
    else:
        titles = [MediaFilter.get_media_title(item, app_name) for item in media_items]
        title_list = "\\n".join(f"- {title}" for title in titles[:50])  # Limit to 50

        if len(titles) > 50:
            title_list += f"\\n... and {len(titles) - 50} more"

        description = f"Search started for {len(media_items)} media items:\\n{title_list}"

        if len(description) > 4000:
            description = (
                f"Search started for {len(media_items)} media items.\\n\\n"
                "*The list is too long to display due to Discord's character limit.*"
            )

    # Send Discord notification
    if notifications.discord_webhook:
        await send_discord_notification(
            webhook_url=notifications.discord_webhook,
            title=f"Upgradinatorr - {app_name.title()}",
            description=description,
            color=colors["decimal"],
            thumbnail_url=colors["thumbnail"],
        )

    # Send Notifiarr notification
    if notifications.notifiarr_webhook and notifications.notifiarr_channel_id:
        await send_notifiarr_notification(
            webhook_url=notifications.notifiarr_webhook,
            channel_id=notifications.notifiarr_channel_id,
            app_name=f"Upgradinatorr - {app_name.title()}",
            title=f"Upgradinatorr - {app_name.title()}",
            description=description,
            color=colors["hex"],
            thumbnail_url=colors["thumbnail"],
        )


@click.command()
@click.option(
    "-a",
    "--apps",
    "applications",
    required=True,
    multiple=True,
    help="Starr applications to process (e.g., radarr, sonarr)",
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
@click.version_option(package_name="upgradinatorr", prog_name="upgradinatorr")
def main(
    applications: tuple[str, ...],
    config_file: Path,
    verbose: bool,
) -> None:
    """
    [bold cyan]Upgradinatorr[/bold cyan] - Automated media upgrade search for Starr applications.

    This tool triggers manual searches in Radarr, Sonarr, Lidarr, and Readarr to find
    upgrades for your media, especially useful after modifying Custom Formats.

    [bold]Examples:[/bold]

        upgradinatorr -a radarr -a sonarr

        upgradinatorr -a radarr -c /path/to/config.conf

        upgradinatorr -a lidarr -a readarr --verbose
    """
    console.print(
        Panel.fit(
            "[bold cyan]Upgradinatorr v3.0.0[/bold cyan]\\nMedia Upgrade Automation",
            border_style="cyan",
        )
    )

    if verbose:
        console.print("[dim]Verbose mode enabled[/dim]")

    # Parse configuration
    try:
        config_dict = parse_ini_config(config_file)
    except FileNotFoundError:
        console.print(f"[red]Configuration file not found: {config_file}[/red]")
        raise click.Abort()
    except Exception as e:
        console.print(f"[red]Error parsing configuration: {e}[/red]")
        raise click.Abort()

    # Parse notifications config
    notifications = None
    if "Notifications" in config_dict:
        try:
            notifications = NotificationConfig(**config_dict["Notifications"])
        except Exception as e:
            console.print(f"[yellow]Warning: Invalid notification config: {e}[/yellow]")

    # Process each application
    async def run_all() -> None:
        for app in applications:
            app_lower = app.lower()

            # Find config section (case-insensitive)
            app_config_key = None
            for key in config_dict.keys():
                if key.lower() == app_lower:
                    app_config_key = key
                    break

            if not app_config_key:
                console.print(f"[red]No configuration found for {app}[/red]")
                continue

            try:
                app_config = ApplicationConfig(**cast(dict[str, Any], config_dict[app_config_key]))
                await process_application(app_lower, app_config, notifications)
            except Exception as e:
                console.print(f"[red]Error processing {app}: {e}[/red]")
                if verbose:
                    console.print_exception()
                continue

    try:
        asyncio.run(run_all())
    except KeyboardInterrupt:
        console.print("\\n[yellow]Interrupted by user[/yellow]")
        raise click.Abort()


if __name__ == "__main__":
    main()
