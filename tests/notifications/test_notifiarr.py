"""Unit tests for Notifiarr notification sending."""

from collections.abc import Callable
from http import HTTPStatus

import pytest

from upgradinatorr.notifications.notifiarr import (
    NotifiarrNotificationError,
    send_notifiarr_notification,
)


@pytest.mark.asyncio
async def test_send_notifiarr_notification_raises_for_unsuccessful_result(
    patch_client_session: Callable[..., None],
) -> None:
    """A non-success Notifiarr result should raise an explicit error."""
    patch_client_session(
        "upgradinatorr.notifications.notifiarr.aiohttp.ClientSession",
        status=HTTPStatus.OK,
        payload={"result": "error"},
    )

    with pytest.raises(NotifiarrNotificationError, match="reported failure"):
        await send_notifiarr_notification(
            webhook_url="https://notifiarr.com/api/v1/notification/passthrough/abc",
            channel_id="12345678901234567",
            app_name="radarr",
            title="Title",
            description="Description",
            color="FFC230",
        )
