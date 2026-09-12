"""Shared completion notification helper."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from upgradinatorr.config import NotificationConfig, get_application_type
from upgradinatorr.constants import APP_COLORS, MAX_DISCORD_DESCRIPTION_LENGTH
from upgradinatorr.notifications.discord import (
    DiscordNotificationError,
    DiscordNotificationRequest,
    send_discord_notification,
)
from upgradinatorr.notifications.notifiarr import (
    NotifiarrNotificationError,
    NotifiarrNotificationRequest,
    send_notifiarr_notification,
)
from upgradinatorr.starr.media import get_media_title


@dataclass(slots=True)
class CompletionNotificationRequest:
    """Parameters for sending completion notifications."""

    app_name: str
    media_items: list[dict[str, Any]]
    notifications: NotificationConfig
    custom_message: str | None = None
    warning_handler: Callable[[str], None] | None = None
    enable_discord: bool = True
    enable_notifiarr: bool = True


CompletionNotificationSender = Callable[
    [str, list[dict[str, Any]], str | None],
    Awaitable[bool],
]


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
        f"Search started for {len(media_items)} media items in {app_name.title()}:\n{title_list}"
    )

    if len(description) > MAX_DISCORD_DESCRIPTION_LENGTH:
        return (
            f"Search started for {len(media_items)} media items in {app_name.title()}.\n\n"
            "- *The list of media items is too long to display here due to "
            "Discord's character limit.*"
        )

    return description


def make_notification_sender(
    notifications: NotificationConfig | None,
    warning_handler: Callable[[str], None] | None = None,
    *,
    enable_discord: bool = True,
    enable_notifiarr: bool = True,
) -> CompletionNotificationSender | None:
    """Build a shared notification sender for workflow orchestration."""
    if notifications is None:
        return None

    send_discord = enable_discord and bool(notifications.discord_webhook)
    send_notifiarr = enable_notifiarr and bool(
        notifications.notifiarr_webhook and notifications.notifiarr_channel_id,
    )
    if not send_discord and not send_notifiarr:
        return None

    async def configured_notification_sender(
        app_name: str,
        media_items: list[dict[str, Any]],
        custom_message: str | None = None,
    ) -> bool:
        return await send_completion_notification(
            CompletionNotificationRequest(
                app_name=app_name,
                media_items=media_items,
                notifications=notifications,
                custom_message=custom_message,
                warning_handler=warning_handler,
                enable_discord=send_discord,
                enable_notifiarr=send_notifiarr,
            )
        )

    return configured_notification_sender


async def send_completion_notification(request: CompletionNotificationRequest) -> bool:
    """Send completion notification to configured webhook destinations."""
    app_type = get_application_type(request.app_name)
    colors = APP_COLORS.get(app_type, APP_COLORS["radarr"])
    description = _build_notification_description(
        request.app_name,
        app_type,
        request.media_items,
        request.custom_message,
    )

    sent_count = 0
    successful_count = 0

    if request.enable_discord and request.notifications.discord_webhook:
        sent_count += 1
        try:
            await send_discord_notification(
                DiscordNotificationRequest(
                    webhook_url=request.notifications.discord_webhook,
                    title=f"Upgradinatorr - {request.app_name.title()}",
                    description=description,
                    color=colors["decimal"],
                    thumbnail_url=colors["thumbnail"],
                )
            )
            successful_count += 1
        except DiscordNotificationError as error:
            if request.warning_handler:
                request.warning_handler(f"discord: {error}")

    if (
        request.enable_notifiarr
        and request.notifications.notifiarr_webhook
        and request.notifications.notifiarr_channel_id
    ):
        sent_count += 1
        try:
            await send_notifiarr_notification(
                NotifiarrNotificationRequest(
                    webhook_url=request.notifications.notifiarr_webhook,
                    channel_id=request.notifications.notifiarr_channel_id,
                    app_name=f"Upgradinatorr - {request.app_name.title()}",
                    title=f"Upgradinatorr - {request.app_name.title()}",
                    description=description,
                    color=colors["hex"],
                    thumbnail_url=colors["thumbnail"],
                )
            )
            successful_count += 1
        except NotifiarrNotificationError as error:
            if request.warning_handler:
                request.warning_handler(f"notifiarr: {error}")

    return sent_count > 0 and successful_count > 0
