"""Unit tests for Discord notification sending."""

from collections.abc import Callable
from http import HTTPStatus

import pytest

from upgradinatorr.notifications.discord import DiscordNotificationError, send_discord_notification


@pytest.mark.asyncio
async def test_send_discord_notification_raises_for_non_2xx(
    patch_client_session: Callable[..., None],
) -> None:
    """Webhook errors should be wrapped in DiscordNotificationError."""
    patch_client_session(
        "upgradinatorr.notifications.discord.aiohttp.ClientSession",
        status=HTTPStatus.BAD_REQUEST,
    )

    with pytest.raises(DiscordNotificationError, match="returned"):
        await send_discord_notification(
            webhook_url="https://discord.com/api/webhooks/1/2",
            title="Title",
            description="Description",
            color=123,
        )
