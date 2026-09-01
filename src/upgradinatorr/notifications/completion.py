"""Shared completion notification helper."""

from collections.abc import Callable
from typing import Any

from upgradinatorr.config import NotificationConfig, get_application_type
from upgradinatorr.constants import APP_COLORS, MAX_DISCORD_DESCRIPTION_LENGTH
from upgradinatorr.notifications.discord import DiscordNotificationError, send_discord_notification
from upgradinatorr.notifications.notifiarr import (
    NotifiarrNotificationError,
    send_notifiarr_notification,
)
from upgradinatorr.starr.media import get_media_title


def _build_notification_description(
    app_name: str,
    app_type: str,
    media_items: list[dict[str, Any]],
    custom_message: str | None,
) -> str:
    if custom_message:
        return custom_message

    titles = [get_media_title(item, app_type) for item in media_items]
    title_list = "\n".join(f"- {title}" for title in titles)

    description = (
        f"Search started for {len(media_items)} media items in {app_name.title()}:\n"
        f"{title_list}"
    )

    if len(description) > MAX_DISCORD_DESCRIPTION_LENGTH:
        return (
            f"Search started for {len(media_items)} media items in {app_name.title()}.\n\n"
            "- *The list of media items is too long to display here due to "
            "Discord's character limit.*"
        )

    return description


async def send_completion_notification(
    app_name: str,
    media_items: list[dict[str, Any]],
    notifications: NotificationConfig,
    custom_message: str | None = None,
    warning_handler: Callable[[str], None] | None = None,
    *,
    enable_discord: bool = True,
    enable_notifiarr: bool = True,
) -> None:
    """Send completion notification to configured webhook destinations."""
    app_type = get_application_type(app_name)
    colors = APP_COLORS.get(app_type, APP_COLORS["radarr"])
    description = _build_notification_description(app_name, app_type, media_items, custom_message)

    if enable_discord and notifications.discord_webhook:
        try:
            await send_discord_notification(
                webhook_url=notifications.discord_webhook,
                title=f"Upgradinatorr - {app_name.title()}",
                description=description,
                color=colors["decimal"],
                thumbnail_url=colors["thumbnail"],
            )
        except DiscordNotificationError as error:
            if warning_handler:
                warning_handler(f"discord: {error}")

    if enable_notifiarr and notifications.notifiarr_webhook and notifications.notifiarr_channel_id:
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
        except NotifiarrNotificationError as error:
            if warning_handler:
                warning_handler(f"notifiarr: {error}")
            raise
