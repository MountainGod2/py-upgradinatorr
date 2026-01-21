"""Notification services for Upgradinatorr."""

from upgradinatorr.notifications.discord import send_discord_notification
from upgradinatorr.notifications.notifiarr import send_notifiarr_notification

__all__ = ["send_discord_notification", "send_notifiarr_notification"]
