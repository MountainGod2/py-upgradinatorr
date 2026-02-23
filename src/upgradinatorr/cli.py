"""Command-line interface for Upgradinatorr."""

import asyncio
from pathlib import Path
from typing import Any, Optional, TypedDict, cast

import rich_click as click
from rich import box
from rich.console import Console
from rich.table import Table

from upgradinatorr.config import (
    ApplicationConfig,
    NotificationConfig,
    parse_ini_config,
    validate_application_name,
)
from upgradinatorr.notifications.discord import send_discord_notification
from upgradinatorr.notifications.notifiarr import send_notifiarr_notification
from upgradinatorr.starr.client import StarrClient, StarrAPIError
from upgradinatorr.starr.media import MediaFilter

console = Console(width=100)

click.rich_click.USE_RICH_MARKUP = True
click.rich_click.SHOW_ARGUMENTS = True
click.rich_click.GROUP_ARGUMENTS_OPTIONS = True
click.rich_click.STYLE_ERRORS_SUGGESTION = "magenta italic"
click.rich_click.STYLE_OPTIONS_TABLE_BOX = "SIMPLE"


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


def get_app_style(app_name: str) -> str:
    """Get the color style for an application."""
    app_color = APP_COLORS.get(app_name.lower())
    if app_color:
        return f"#{app_color['hex']}"
    return "#FFFFFF"


def create_media_table(media_items: list[dict[str, Any]], app_name: str, title: str) -> Table:
    """Create a formatted table for media items."""
    app_style = get_app_style(app_name)
    table = Table(title=title, box=box.SIMPLE, border_style=app_style)

    if app_name == "radarr":
        table.add_column("Title", style="white")
        table.add_column("Year", style="cyan", justify="right")
        table.add_column("Status", style="magenta")
        table.add_column("Monitored", justify="center")
    elif app_name == "sonarr":
        table.add_column("Title", style="white")
        table.add_column("Year", style="cyan", justify="right")
        table.add_column("Status", style="magenta")
        table.add_column("Monitored", justify="center")
        table.add_column("Seasons", justify="right", style="green")
    elif app_name == "lidarr":
        table.add_column("Artist", style="white")
        table.add_column("Status", style="magenta")
        table.add_column("Monitored", justify="center")
    elif app_name == "readarr":
        table.add_column("Author", style="white")
        table.add_column("Status", style="magenta")
        table.add_column("Monitored", justify="center")

    for item in media_items:
        monitored = "✓" if item.get("monitored") else "✗"
        status = str(item.get("status", "unknown")).title()

        if status.lower() in ["continuing", "released", "announced"]:
            status = f"[green]{status}[/green]"
        elif status.lower() in ["ended", "missing"]:
            status = f"[red]{status}[/red]"

        if app_name == "radarr":
            table.add_row(
                item.get("title", "Unknown"),
                str(item.get("year", "")),
                status,
                monitored,
            )
        elif app_name == "sonarr":
            seasons = str(
                item.get("seasonCount", item.get("statistics", {}).get("seasonCount", "?"))
            )
            table.add_row(
                item.get("title", "Unknown"),
                str(item.get("year", "")),
                status,
                monitored,
                seasons,
            )
        elif app_name == "lidarr":
            table.add_row(item.get("artistName", "Unknown"), status, monitored)
        elif app_name == "readarr":
            table.add_row(item.get("authorName", "Unknown"), status, monitored)

    return table


async def process_application(
    app_name: str,
    config: ApplicationConfig,
    notifications: Optional[NotificationConfig] = None,
    dry_run: bool = False,
    verbose: bool = False,
) -> None:
    """Process a single Starr application.

    Args:
        app_name: Name of the application (radarr, sonarr, etc.)
        config: Application configuration
        notifications: Optional notification configuration
        dry_run: If True, run in dry-run mode
        verbose: If True, enable verbose output
    """
    app_name = app_name.lower()
    app_style = get_app_style(app_name)

    console.print()
    console.rule(f"[{app_style}]{app_name.title()}[/{app_style}]")
    if dry_run:
        console.print("[yellow]DRY RUN MODE[/yellow]", justify="center")

    summary_parts = [
        f"URL: [dim]{config.url}[/dim]",
        f"Count: [dim]{config.count}[/dim]",
        f"Tag: [dim]{config.tag_name}[/dim]",
    ]

    if config.ignore_tag:
        summary_parts.append(f"Ignore: [dim]{config.ignore_tag}[/dim]")

    console.print(" | ".join(summary_parts))
    console.print()

    if verbose:
        console.print(f"[dim]Validating {app_name.title()} configuration...[/dim]")

    try:
        async with StarrClient(app_name, config.url, config.api_key) as client:
            if verbose:
                console.print(f"[dim]Retrieved API version: {client.api_version}[/dim]")

            with console.status(f"[{app_style}]Checking tags...", spinner="dots"):
                if dry_run:
                    tag = await client.get_tag(config.tag_name)
                    if tag:
                        tag_id = int(tag["id"])
                        if verbose:
                            console.print(
                                f"[dim]Found tag '{config.tag_name}' with ID: {tag_id}[/dim]"
                            )
                    else:
                        console.print(f"[yellow]- Would create tag '{config.tag_name}'[/yellow]")
                        tag_id = -1
                else:
                    tag_id = await client.get_or_create_tag(config.tag_name)
                    if verbose:
                        console.print(f"[dim]Tag '{config.tag_name}' has ID: {tag_id}[/dim]")

                ignore_tag_id = None
                if config.ignore_tag:
                    if dry_run:
                        tag = await client.get_tag(config.ignore_tag)
                        if tag:
                            ignore_tag_id = int(tag["id"])
                            if verbose:
                                console.print(
                                    f"[dim]Found ignore tag '{config.ignore_tag}' with ID: {ignore_tag_id}[/dim]"
                                )
                        else:
                            console.print(
                                f"[yellow]- Would create ignore tag '{config.ignore_tag}'[/yellow]"
                            )
                            ignore_tag_id = -2
                    else:
                        ignore_tag_id = await client.get_or_create_tag(config.ignore_tag)
                        if verbose:
                            console.print(
                                f"[dim]Ignore tag '{config.ignore_tag}' has ID: {ignore_tag_id}[/dim]"
                            )

                    if tag_id == ignore_tag_id:
                        raise ValueError(
                            f"Tag '{config.tag_name}' and ignore tag '{config.ignore_tag}' "
                            "cannot be the same"
                        )

            quality_profile_id = None
            if config.quality_profile_name:
                with console.status(f"[{app_style}]Checking quality profile...", spinner="dots"):
                    quality_profile_id = await client.get_quality_profile_id(
                        config.quality_profile_name
                    )
                    if verbose:
                        console.print(
                            f"[dim]Quality profile '{config.quality_profile_name}' has ID: {quality_profile_id}[/dim]"
                        )

            status = None
            if app_name == "radarr":
                status = config.movie_status
            elif app_name == "sonarr":
                status = config.series_status
            elif app_name == "lidarr":
                status = config.artist_status
            elif app_name == "readarr":
                status = config.author_status

            with console.status(
                f"[{app_style}]Retrieving media from {app_name.title()}...", spinner="bouncingBall"
            ) as status_spinner:
                all_media = await client.get_all_media()
                if verbose:
                    console.print(
                        f"[dim]Retrieved a total of {len(all_media)} media items from {app_name.title()}[/dim]"
                    )

                status_spinner.update(f"Filtering {len(all_media)} items...")

                media_filter = MediaFilter(
                    monitored=config.monitored,
                    tag_id=tag_id,
                    status=status,
                    quality_profile_id=quality_profile_id,
                    ignore_tag_id=ignore_tag_id,
                )

                if config.unattended:
                    if verbose:
                        console.print(
                            f"[dim]Filtering media to only include media with the tag '{config.tag_name}'[/dim]"
                        )
                    filtered = media_filter.filter_unattended(all_media)
                else:
                    if verbose:
                        console.print(
                            f"[dim]Filtering media to only include media without the tag '{config.tag_name}' and that are monitored[/dim]"
                        )
                    filtered = media_filter.filter_attended(all_media)

                if verbose:
                    console.print(
                        f"[dim]Filtered media based on configuration values, found {len(filtered)} media items to process for {app_name.title()}[/dim]"
                    )

                if not filtered:
                    if config.unattended:
                        console.print(
                            "[yellow]No media left to process. Removing tags and re-filtering...[/yellow]"
                        )
                        tagged_media = media_filter.filter_unattended(all_media)
                        if tagged_media:
                            media_ids = [item["id"] for item in tagged_media]
                            if dry_run:
                                console.print(
                                    f"[yellow]- Would remove tag from {len(media_ids)} items[/yellow]"
                                )
                                for item in all_media:
                                    if (
                                        item.get("id") in media_ids
                                        and "tags" in item
                                        and tag_id in item["tags"]
                                    ):
                                        item["tags"].remove(tag_id)
                            else:
                                await client.remove_tags_from_media(media_ids, tag_id)
                                all_media = await client.get_all_media()
                            filtered = media_filter.filter_attended(all_media)

                        if not filtered:
                            console.print("[yellow]No media to process after tag removal[/yellow]")
                            return
                    else:
                        console.print(
                            f"[yellow]No {app_name} media found matching criteria[/yellow]"
                        )
                        if notifications:
                            await send_completion_notification(
                                app_name, [], notifications, "No media left to search"
                            )
                        return

            console.print(
                f"[{app_style}]Found {len(filtered)} candidates matching criteria[/{app_style}]"
            )

            selected = MediaFilter.select_random(filtered, config.count)

            if selected:
                table = create_media_table(selected, app_name, f"Selected Items ({len(selected)})")
                console.print(table)
            else:
                console.print("[yellow]No items selected[/yellow]")

            if dry_run:
                console.print(
                    f"[yellow]- Would search {len(selected)} items in {app_name.title()}[/yellow]"
                )
            else:
                with console.status(f"[{app_style}]Triggering searches...", spinner="dots"):
                    await client.search_media_batch(selected)
                console.print(
                    f"[{app_style}]✓ Search triggered for {len(selected)} items[/{app_style}]"
                )

            media_ids = [item["id"] for item in selected]
            if dry_run:
                console.print(
                    f"[yellow]- Would add tag to {len(media_ids)} items in {app_name.title()}[/yellow]"
                )
            else:
                with console.status(f"[{app_style}]Updating tags...", spinner="dots"):
                    await client.add_tags_to_media(media_ids, tag_id)
                console.print(
                    f"[green]✓ Added tag '{config.tag_name}' to {len(media_ids)} items[/green]"
                )

            if notifications:
                if dry_run:
                    console.print("[yellow]- Would send completion notification[/yellow]")
                else:
                    with console.status("Sending notifications...", spinner="dots"):
                        await send_completion_notification(app_name, selected, notifications)
                    console.print("[green]✓ Notifications sent[/green]")

            if not dry_run:
                console.print(
                    f"[bold green]✓ Successfully processed {len(selected)} items in {app_name.title()}[/bold green]"
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

    if notifications.discord_webhook:
        await send_discord_notification(
            webhook_url=notifications.discord_webhook,
            title=f"Upgradinatorr - {app_name.title()}",
            description=description,
            color=colors["decimal"],
            thumbnail_url=colors["thumbnail"],
        )

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
@click.option(
    "--dry-run",
    is_flag=True,
    help="Run in dry-run mode (do not make changes)",
)
@click.version_option(package_name="upgradinatorr", prog_name="upgradinatorr")
def main(
    applications: tuple[str, ...],
    config_file: Path,
    verbose: bool,
    dry_run: bool,
) -> None:
    """
    [bold cyan]Upgradinatorr[/bold cyan] - Automated media upgrade search for Starr applications.

    This tool triggers manual searches in Radarr, Sonarr, Lidarr, and Readarr to find
    upgrades for your media, especially useful after modifying Custom Formats.

    [bold]Examples:[/bold]

        upgradinatorr -a radarr -a sonarr

        upgradinatorr -a radarr -c /path/to/config.conf

        upgradinatorr -a lidarr -a readarr --verbose

        upgradinatorr -a radarr --dry-run
    """
    console.rule("[bold cyan]Upgradinatorr[/bold cyan]")

    if verbose:
        console.print("[dim]Verbose mode enabled[/dim]", justify="center")
    if dry_run:
        console.print("[yellow]Running in DRY-RUN mode[/yellow]", justify="center")

    try:
        config_dict = parse_ini_config(config_file)
    except FileNotFoundError:
        console.print(f"[red]Configuration file not found: {config_file}[/red]")
        raise click.Abort()
    except Exception as e:
        console.print(f"[red]Error parsing configuration: {e}[/red]")
        raise click.Abort()

    notifications = None
    if "Notifications" in config_dict:
        try:
            notifications = NotificationConfig(**config_dict["Notifications"])
        except Exception as e:
            console.print(f"[yellow]Warning: Invalid notification config: {e}[/yellow]")

    async def run_all() -> None:
        console.print(
            f"\n[bold]Processing {len(applications)} application(s):[/bold] {', '.join(applications)}"
        )

        for app in applications:
            app_lower = app.lower()

            try:
                validate_application_name(app_lower)
            except ValueError as e:
                console.print(f"[red]✗ {e}[/red]")
                continue

            app_config_key = None
            for key in config_dict.keys():
                if key.lower() == app_lower:
                    app_config_key = key
                    break

            if not app_config_key:
                console.print(f"[red]✗ No configuration found for {app}[/red]")
                continue

            try:
                app_config = ApplicationConfig(**cast(dict[str, Any], config_dict[app_config_key]))
                await process_application(app_lower, app_config, notifications, dry_run, verbose)
            except Exception as e:
                console.print(f"[red]✗ Error processing {app}: {e}[/red]")
                if verbose:
                    console.print_exception()
                continue

        console.print()
        console.print("[bold green]All tasks completed![/bold green]")

    try:
        asyncio.run(run_all())
    except KeyboardInterrupt:
        console.print("\\n[yellow]Interrupted by user[/yellow]")
        raise click.Abort()


if __name__ == "__main__":
    main()
