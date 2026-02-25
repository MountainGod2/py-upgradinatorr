"""Command-line interface for Upgradinatorr."""

import asyncio
from pathlib import Path
from typing import Any, TypedDict, cast

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
from upgradinatorr.notifications.discord import DiscordNotificationError, send_discord_notification
from upgradinatorr.notifications.notifiarr import (
    NotifiarrNotificationError,
    send_notifiarr_notification,
)
from upgradinatorr.starr.client import StarrAPIError, StarrClient
from upgradinatorr.starr.media import MediaFilter

console = Console(width=100)

click.rich_click.USE_RICH_MARKUP = True
click.rich_click.SHOW_ARGUMENTS = True
click.rich_click.GROUP_ARGUMENTS_OPTIONS = True
click.rich_click.STYLE_ERRORS_SUGGESTION = "magenta italic"
click.rich_click.STYLE_OPTIONS_TABLE_BOX = "SIMPLE"

MAX_NOTIFICATION_ITEMS = 50
MAX_DISCORD_DESCRIPTION_LENGTH = 4000


class AppColor(TypedDict):
    """Color configuration for an application."""

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


def create_media_table(media_items: list[dict[str, Any]], app_name: str) -> Table:
    """Create a formatted table for media items."""
    app_style = get_app_style(app_name)
    table = Table(box=box.SIMPLE, border_style=app_style, show_header=True, pad_edge=False)

    if app_name == "radarr":
        table.add_column("Title", style="white")
        table.add_column("Year", style="cyan", justify="right")
        table.add_column("Status", style="magenta")
        table.add_column("Mon", justify="center")
    elif app_name == "sonarr":
        table.add_column("Title", style="white")
        table.add_column("Year", style="cyan", justify="right")
        table.add_column("Status", style="magenta")
        table.add_column("Mon", justify="center")
        table.add_column("Seasons", justify="right", style="green")
    elif app_name == "lidarr":
        table.add_column("Artist", style="white")
        table.add_column("Status", style="magenta")
        table.add_column("Mon", justify="center")
    elif app_name == "readarr":
        table.add_column("Author", style="white")
        table.add_column("Status", style="magenta")
        table.add_column("Mon", justify="center")

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
                item.get("seasonCount", item.get("statistics", {}).get("seasonCount", "?")),
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


def validate_tag_ids(tag_name: str, tag_id: int, ignore_tag: str, ignore_tag_id: int) -> None:
    """Validate that tag and ignore tag are not the same.

    Args:
        tag_name: Name of the primary tag
        tag_id: ID of the primary tag
        ignore_tag: Name of the ignore tag
        ignore_tag_id: ID of the ignore tag

    Raises:
        ValueError: If tag_id and ignore_tag_id are the same
    """
    if tag_id == ignore_tag_id:
        msg = f"tag '{tag_name}' and ignore tag '{ignore_tag}' cannot be the same"
        raise ValueError(msg)


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
        f"count=[dim]{config.count}[/dim]",
        f"tag=[dim]{config.tag_name}[/dim]",
    ]
    if config.ignore_tag:
        meta_parts.append(f"ignore=[dim]{config.ignore_tag}[/dim]")
    if dry_run:
        meta_parts.append("[yellow]dry-run[/yellow]")

    console.print(" · ".join(meta_parts))

    try:
        async with StarrClient(app_name, config.url, config.api_key) as client:
            if verbose:
                console.print(f"[dim]API version: {client.api_version}[/dim]")

            with console.status(f"[{app_style}]Fetching tags...", spinner="dots"):
                if dry_run:
                    tag = await client.get_tag(config.tag_name)
                    if tag:
                        tag_id = int(tag["id"])
                    else:
                        console.print(f"[yellow]  would create tag '{config.tag_name}'[/yellow]")
                        tag_id = -1
                else:
                    tag_id = await client.get_or_create_tag(config.tag_name)

                if verbose:
                    console.print(f"[dim]tag '{config.tag_name}' → id={tag_id}[/dim]")

                ignore_tag_id = None
                if config.ignore_tag:
                    if dry_run:
                        tag = await client.get_tag(config.ignore_tag)
                        if tag:
                            ignore_tag_id = int(tag["id"])
                        else:
                            console.print(
                                f"[yellow]  would create ignore tag '{config.ignore_tag}'[/yellow]",
                            )
                            ignore_tag_id = -2
                    else:
                        ignore_tag_id = await client.get_or_create_tag(config.ignore_tag)

                    if verbose:
                        console.print(
                            f"[dim]ignore tag '{config.ignore_tag}' → id={ignore_tag_id}[/dim]",
                        )

                    validate_tag_ids(config.tag_name, tag_id, config.ignore_tag, ignore_tag_id)

            quality_profile_id = None
            if config.quality_profile_name:
                with console.status(f"[{app_style}]Checking quality profile...", spinner="dots"):
                    quality_profile_id = await client.get_quality_profile_id(
                        config.quality_profile_name,
                    )
                    if verbose:
                        console.print(
                            f"[dim]quality profile '{config.quality_profile_name}' "
                            f"→ id={quality_profile_id}[/dim]",
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
                f"[{app_style}]Fetching media...",
                spinner="dots",
            ) as status_spinner:
                all_media = await client.get_all_media()
                status_spinner.update(f"[{app_style}]Filtering {len(all_media)} items...")

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

                if verbose:
                    console.print(
                        f"[dim]{len(all_media)} total → {len(filtered)} match filter[/dim]",
                    )

                if not filtered:
                    if config.unattended:
                        console.print("[dim]No untagged media — cycling tags...[/dim]")
                        tagged_media = media_filter.filter_unattended(all_media)
                        if tagged_media:
                            media_ids = [item["id"] for item in tagged_media]
                            if dry_run:
                                console.print(
                                    f"[yellow]  would remove tag from "
                                    f"{len(media_ids)} items[/yellow]",
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
                            console.print("[dim]Nothing to process[/dim]")
                            return
                    else:
                        console.print(f"[dim]No {app_name} media matched — skipping[/dim]")
                        if notifications:
                            await send_completion_notification(
                                app_name,
                                [],
                                notifications,
                                "No media left to search",
                            )
                        return

            selected = MediaFilter.select_random(filtered, config.count)

            console.print(
                f"[{app_style}]{len(filtered)} candidates[/{app_style}]  "
                f"→  [bold]{len(selected)} selected[/bold]",
            )

            if selected:
                table = create_media_table(selected, app_name)
                console.print(table)

            if dry_run:
                console.print(f"[yellow]  would search {len(selected)} items[/yellow]")
                console.print(f"[yellow]  would tag {len(selected)} items[/yellow]")
                if notifications:
                    console.print("[yellow]  would send notification[/yellow]")
            else:
                with console.status(f"[{app_style}]Searching...", spinner="dots"):
                    await client.search_media_batch(selected)
                console.print(f"[green]✓[/green] search queued for {len(selected)} items")

                media_ids = [item["id"] for item in selected]
                with console.status(f"[{app_style}]Tagging...", spinner="dots"):
                    await client.add_tags_to_media(media_ids, tag_id)
                console.print(f"[green]✓[/green] tagged {len(media_ids)} items")

                if notifications:
                    with console.status("Notifying...", spinner="dots"):
                        await send_completion_notification(app_name, selected, notifications)
                    console.print("[green]✓[/green] notification sent")

    except StarrAPIError as e:
        console.print(f"[red]✗ API error: {e}[/red]")
        raise
    except Exception as e:
        console.print(f"[red]✗ {e}[/red]")
        raise


async def send_completion_notification(
    app_name: str,
    media_items: list[dict[str, Any]],
    notifications: NotificationConfig,
    custom_message: str | None = None,
) -> None:
    """Send completion notification."""
    colors = APP_COLORS.get(app_name, APP_COLORS["radarr"])

    if custom_message:
        description = custom_message
    else:
        titles = [MediaFilter.get_media_title(item, app_name) for item in media_items]
        title_list = "\n".join(f"- {title}" for title in titles[:50])

        if len(titles) > MAX_NOTIFICATION_ITEMS:
            title_list += f"\n... and {len(titles) - 50} more"

        description = f"Search started for {len(media_items)} media items:\n{title_list}"

        if len(description) > MAX_DISCORD_DESCRIPTION_LENGTH:
            description = (
                f"Search started for {len(media_items)} media items.\n\n"
                f"*The list is too long to display due to Discord's character limit.*"
            )

    if notifications.discord_webhook:
        try:
            await send_discord_notification(
                webhook_url=notifications.discord_webhook,
                title=f"Upgradinatorr - {app_name.title()}",
                description=description,
                color=colors["decimal"],
                thumbnail_url=colors["thumbnail"],
            )
        except DiscordNotificationError as e:
            console.print(f"[yellow]  discord: {e}[/yellow]")

    if notifications.notifiarr_webhook and notifications.notifiarr_channel_id:
        try:
            await send_notifiarr_notification(
                webhook_url=notifications.notifiarr_webhook,
                channel_id=notifications.notifiarr_channel_id,
                app_name=f"Upgradinatorr - {app_name.title()}",
                title=f"Upgradinatorr - {app_name.title()}",
                description=description,
                color=colors["hex"],
                thumbnail_url=colors["thumbnail"],
            )
        except NotifiarrNotificationError as e:
            console.print(f"[yellow]  notifiarr: {e}[/yellow]")


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

        upgradinatorr -a radarr,sonarr

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
    except FileNotFoundError as e:
        console.print(f"[red]✗ config file not found: {config_file}[/red]")
        raise click.Abort from e
    except Exception as e:
        console.print(f"[red]✗ failed to parse config: {e}[/red]")
        raise click.Abort from e

    notifications = None
    if "Notifications" in config_dict:
        try:
            notifications = NotificationConfig(**config_dict["Notifications"])
        except Exception as e:  # noqa: BLE001 - Don't fail on invalid notification config
            console.print(f"[yellow]  invalid notification config: {e}[/yellow]")

    async def run_all() -> None:
        apps_str = ", ".join(applications)
        console.print(f"[dim]{apps_str}[/dim]", justify="center")

        for app in applications:
            app_lower = app.lower()

            try:
                validate_application_name(app_lower)
            except ValueError as e:
                console.print(f"[red]✗ {e}[/red]")
                continue

            app_config_key = None
            for key in config_dict:
                if key.lower() == app_lower:
                    app_config_key = key
                    break

            if not app_config_key:
                console.print(f"[red]✗ no config section for '{app}'[/red]")
                continue

            try:
                app_config = ApplicationConfig(
                    **cast("dict[str, Any]", config_dict[app_config_key])
                )
                await process_application(
                    app_lower, app_config, notifications, dry_run=dry_run, verbose=verbose
                )
            except Exception as e:  # noqa: BLE001 - Continue processing other apps on error
                console.print(f"[red]✗ {app}: {e}[/red]")
                if verbose:
                    console.print_exception()
                continue

        console.print()

    try:
        asyncio.run(run_all())
    except KeyboardInterrupt:
        console.print("\n[dim]interrupted[/dim]")
        raise click.Abort from None


if __name__ == "__main__":
    main()
