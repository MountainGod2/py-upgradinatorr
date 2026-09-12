"""Discord webhook notifications."""

import logging
from dataclasses import dataclass
from http import HTTPStatus

import aiohttp

logger = logging.getLogger(__name__)


class DiscordNotificationError(Exception):
    """Raised when a Discord notification fails to send."""


@dataclass(slots=True)
class DiscordNotificationRequest:
    """Parameters for a Discord webhook request."""

    webhook_url: str
    title: str
    description: str
    color: int
    thumbnail_url: str | None = None
    username: str = "Upgradinatorr"
    avatar_url: str = "https://www.python.org/static/community_logos/python-logo.png"


async def send_discord_notification(request: DiscordNotificationRequest) -> None:
    """Send notification to Discord via webhook.

    Args:
        request: Discord webhook request parameters.

    Raises:
        DiscordNotificationError: If the webhook request fails.

    """
    payload = {
        "username": request.username,
        "avatar_url": request.avatar_url,
        "embeds": [
            {
                "title": request.title,
                "description": request.description,
                "color": request.color,
                "thumbnail": {"url": request.thumbnail_url} if request.thumbnail_url else None,
            },
        ],
    }

    async with (
        aiohttp.ClientSession() as session,
        session.post(request.webhook_url, json=payload) as response,
    ):
        if not HTTPStatus.OK <= response.status < HTTPStatus.MULTIPLE_CHOICES:
            msg = f"Discord webhook returned {response.status}"
            raise DiscordNotificationError(
                msg,
            )

    logger.debug("Discord notification sent")
