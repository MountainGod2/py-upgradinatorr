"""Unit tests for notification sending."""

from http import HTTPStatus
from unittest.mock import AsyncMock

import pytest
from aioresponses import aioresponses

from upgradinatorr.config import NotificationConfig
from upgradinatorr.notifications.completion import (
    CompletionNotificationRequest,
    make_notification_sender,
    send_completion_notification,
)
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

DISCORD_WEBHOOK = (
    "https://discord.com/api/webhooks/123456789012345678/"
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_abcd"
)
NOTIFIARR_WEBHOOK = (
    "https://notifiarr.com/api/v1/notification/passthrough/12345678-1234-1234-1234-123456789abc"
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
            DiscordNotificationRequest(
                webhook_url=webhook_url,
                title="Title",
                description="Description",
                color=123,
            )
        )


@pytest.mark.asyncio
async def test_send_completion_notification_handles_notifiarr_errors_best_effort(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Notifiarr errors should be reported as warnings and not re-raised."""
    warnings: list[str] = []

    mock_discord = AsyncMock(return_value=None)
    mock_notifiarr = AsyncMock(side_effect=NotifiarrNotificationError("boom"))
    monkeypatch.setattr(
        "upgradinatorr.notifications.completion.send_discord_notification",
        mock_discord,
    )
    monkeypatch.setattr(
        "upgradinatorr.notifications.completion.send_notifiarr_notification",
        mock_notifiarr,
    )

    sent = await send_completion_notification(
        CompletionNotificationRequest(
            app_name="radarr",
            media_items=[{"title": "Movie"}],
            notifications=NotificationConfig(
                DiscordWebhook=DISCORD_WEBHOOK,
                NotifiarrPassthroughWebhook=NOTIFIARR_WEBHOOK,
                NotifiarrPassthroughDiscordChannelId="12345678901234567",
            ),
            warning_handler=warnings.append,
        )
    )

    assert sent
    assert warnings == ["notifiarr: boom"]


@pytest.mark.asyncio
async def test_make_notification_sender_returns_none_when_all_channels_disabled() -> None:
    """Factory should return no sender if no channels are enabled."""
    notifications = NotificationConfig(
        DiscordWebhook=DISCORD_WEBHOOK,
        NotifiarrPassthroughWebhook=NOTIFIARR_WEBHOOK,
        NotifiarrPassthroughDiscordChannelId="12345678901234567",
    )

    sender = make_notification_sender(
        notifications,
        enable_discord=False,
        enable_notifiarr=False,
    )

    assert sender is None


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
            NotifiarrNotificationRequest(
                webhook_url=webhook_url,
                channel_id="12345678901234567",
                app_name="radarr",
                title="Title",
                description="Description",
                color="FFC230",
            )
        )
