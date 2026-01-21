"""Upgradinatorr - Media upgrade automation for Starr applications."""

from importlib.metadata import version

__version__ = version("upgradinatorr")
__author__ = "MountainGod2"

from upgradinatorr.config import ApplicationConfig, NotificationConfig

__all__ = ["ApplicationConfig", "NotificationConfig"]
