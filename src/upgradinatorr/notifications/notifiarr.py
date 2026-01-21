"""Notifiarr passthrough notifications."""

from typing import Any, Optional

import aiohttp
from rich.console import Console

console = Console()


async def send_notifiarr_notification(
    webhook_url: str,
    channel_id: str,
    app_name: str,
    title: str,
    description: str,
    color: str,
    thumbnail_url: Optional[str] = None,
    **kwargs: Any,
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

    async with aiohttp.ClientSession() as session:
        async with session.post(
            webhook_url, json=payload, headers={"Accept": "text/plain"}
        ) as response:
            if response.status == 200:
                data = await response.json()
                if data.get("result") == "success":
                    console.log("[green]Notifiarr notification sent successfully[/green]")
                else:
                    console.log("[red]Notifiarr notification failed[/red]")
            else:
                console.log(f"[red]Failed to send Notifiarr notification: {response.status}[/red]")
