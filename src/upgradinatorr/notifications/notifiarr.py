"""Notifiarr passthrough notifications."""

import logging
from dataclasses import dataclass, field
from http import HTTPStatus
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)


class NotifiarrNotificationError(Exception):
    """Raised when a Notifiarr notification fails to send."""


@dataclass(slots=True)
class NotifiarrNotificationRequest:
    """Parameters for a Notifiarr passthrough request."""

    webhook_url: str
    channel_id: str
    app_name: str
    title: str
    description: str
    color: str
    thumbnail_url: str | None = None
    extra_fields: dict[str, Any] = field(default_factory=dict)


async def send_notifiarr_notification(request: NotifiarrNotificationRequest) -> None:
    """Send notification via Notifiarr passthrough integration.

    Args:
        request: Notifiarr passthrough request parameters.

    Raises:
        NotifiarrNotificationError: If the webhook request fails.

    """
    payload = {
        "notification": {
            "name": request.app_name,
            "update": request.extra_fields.get("update", False),
            "event": request.extra_fields.get("event", ""),
        },
        "discord": {
            "color": request.color,
            "ping": {
                "pingUser": request.extra_fields.get("ping_user"),
                "pingRole": request.extra_fields.get("ping_role"),
            },
            "images": {
                "thumbnail": request.thumbnail_url,
                "image": request.extra_fields.get("image_url"),
            },
            "text": {
                "title": request.title,
                "icon": request.extra_fields.get("icon_url"),
                "content": request.extra_fields.get("content"),
                "description": request.description,
                "fields": request.extra_fields.get("fields"),
                "footer": request.extra_fields.get("footer"),
            },
            "ids": {"channel": int(request.channel_id)},
        },
    }

    async with (
        aiohttp.ClientSession() as session,
        session.post(
            request.webhook_url,
            json=payload,
            headers={"Accept": "text/plain"},
        ) as response,
    ):
        if not HTTPStatus.OK <= response.status < HTTPStatus.MULTIPLE_CHOICES:
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
