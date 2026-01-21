"""Discord webhook notifications."""

from typing import Optional

import aiohttp
from rich.console import Console

console = Console()


async def send_discord_notification(
    webhook_url: str,
    title: str,
    description: str,
    color: int,
    thumbnail_url: Optional[str] = None,
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
            }
        ],
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(webhook_url, json=payload) as response:
            if response.status in range(200, 300):
                console.log("[green]Discord notification sent successfully[/green]")
            else:
                console.log(f"[red]Failed to send Discord notification: {response.status}[/red]")
