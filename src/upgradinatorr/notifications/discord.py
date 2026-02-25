"""Discord webhook notifications."""

import logging

import aiohttp

logger = logging.getLogger(__name__)

# HTTP status code range for successful responses
HTTP_SUCCESS_MIN = 200
HTTP_SUCCESS_MAX = 300


class DiscordNotificationError(Exception):
    """Raised when a Discord notification fails to send."""


async def send_discord_notification(
    webhook_url: str,
    title: str,
    description: str,
    color: int,
    thumbnail_url: str | None = None,
    username: str = "Upgradinatorr",
    avatar_url: str = "https://gh.notifiarr.com/images/icons/powershell.png",
) -> None:
    """Send notification to Discord via webhook.

    Args:
        webhook_url: Discord webhook URL
        title: Message title
        description: Message description
        color: Embed color (decimal)
        thumbnail_url: Optional thumbnail URL
        username: Webhook username
        avatar_url: Webhook avatar URL

    Raises:
        DiscordNotificationError: If the webhook request fails.

    """
    payload = {
        "username": username,
        "avatar_url": avatar_url,
        "embeds": [
            {
                "title": title,
                "description": description,
                "color": color,
                "thumbnail": {"url": thumbnail_url} if thumbnail_url else None,
            },
        ],
    }

    async with (
        aiohttp.ClientSession() as session,
        session.post(webhook_url, json=payload) as response,
    ):
        if not (HTTP_SUCCESS_MIN <= response.status < HTTP_SUCCESS_MAX):
            msg = f"Discord webhook returned {response.status}"
            raise DiscordNotificationError(
                msg,
            )

    logger.debug("Discord notification sent")
