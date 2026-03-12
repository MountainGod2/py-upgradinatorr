"""Unit tests for constant mappings."""

from upgradinatorr.config import SUPPORTED_APPS
from upgradinatorr.constants import APP_COLORS, STATUS_FIELDS


def test_all_supported_apps_have_color_and_status_mapping() -> None:
    """Every supported app should be represented consistently in constants."""
    assert set(APP_COLORS) >= SUPPORTED_APPS
    assert set(STATUS_FIELDS) >= SUPPORTED_APPS
