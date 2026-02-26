"""Notifiarr passthrough notifications."""

import logging
from http import HTTPStatus
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)


class NotifiarrNotificationError(Exception):
    """Raised when a Notifiarr notification fails to send."""


async def send_notifiarr_notification(
    webhook_url: str,
    channel_id: str,
    app_name: str,
    title: str,
    description: str,
    color: str,
    thumbnail_url: str | None = None,
    **kwargs: Any,  # noqa: ANN401
) -> None:
    """Send notification via Notifiarr passthrough integration.

    Args:
        webhook_url: Notifiarr webhook URL
        channel_id: Discord channel ID
        app_name: Application name
        title: Notification title
        description: Notification description
        color: Embed color (hex)
        thumbnail_url: Optional thumbnail URL
        **kwargs: Additional notification parameters

    Raises:
        NotifiarrNotificationError: If the webhook request fails.

    """
    payload = {
        "notification": {
            "name": app_name,
            "update": kwargs.get("update", False),
            "event": kwargs.get("event", ""),
        },
        "discord": {
            "color": color,
            "ping": {
                "pingUser": kwargs.get("ping_user"),
                "pingRole": kwargs.get("ping_role"),
            },
            "images": {
                "thumbnail": thumbnail_url,
                "image": kwargs.get("image_url"),
            },
            "text": {
                "title": title,
                "icon": kwargs.get("icon_url"),
                "content": kwargs.get("content"),
                "description": description,
                "fields": kwargs.get("fields"),
                "footer": kwargs.get("footer"),
            },
            "ids": {"channel": int(channel_id)},
        },
    }

    async with (
        aiohttp.ClientSession() as session,
        session.post(
            webhook_url,
            json=payload,
            headers={"Accept": "text/plain"},
        ) as response,
    ):
        if not (HTTPStatus.OK <= response.status < HTTPStatus.MULTIPLE_CHOICES):
            msg = f"Notifiarr webhook returned {response.status}"
            raise NotifiarrNotificationError(
                msg,
            )
        data = await response.json()
        if data.get("result") != "success":
            msg = f"Notifiarr reported failure: {data.get('result')}"
            raise NotifiarrNotificationError(
                msg,
            )

    logger.debug("Notifiarr notification sent")
