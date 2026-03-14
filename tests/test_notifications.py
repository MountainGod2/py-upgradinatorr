"""Unit tests for notification sending."""

from http import HTTPStatus

import pytest
from aioresponses import aioresponses

from upgradinatorr.notifications.discord import DiscordNotificationError, send_discord_notification
from upgradinatorr.notifications.notifiarr import (
    NotifiarrNotificationError,
    send_notifiarr_notification,
)


@pytest.mark.asyncio
async def test_send_discord_notification_raises_for_non_2xx(
    mock_aioresponses: aioresponses,
) -> None:
    """Webhook errors should be wrapped in DiscordNotificationError."""
    webhook_url = "https://discord.com/api/webhooks/1/2"
    mock_aioresponses.post(
        webhook_url,
        status=HTTPStatus.BAD_REQUEST,
    )

    with pytest.raises(DiscordNotificationError, match="returned"):
        await send_discord_notification(
            webhook_url=webhook_url,
            title="Title",
            description="Description",
            color=123,
        )


@pytest.mark.asyncio
async def test_send_notifiarr_notification_raises_for_unsuccessful_result(
    mock_aioresponses: aioresponses,
) -> None:
    """A non-success Notifiarr result should raise an explicit error."""
    webhook_url = "https://notifiarr.com/api/v1/notification/passthrough/abc"
    mock_aioresponses.post(
        webhook_url,
        status=HTTPStatus.OK,
        payload={"result": "error"},
    )

    with pytest.raises(NotifiarrNotificationError, match="reported failure"):
        await send_notifiarr_notification(
            webhook_url=webhook_url,
            channel_id="12345678901234567",
            app_name="radarr",
            title="Title",
            description="Description",
            color="FFC230",
        )
