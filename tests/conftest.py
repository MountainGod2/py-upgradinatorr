"""Shared pytest configuration for test discovery."""

import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Protocol

import pytest
import stamina
from aioresponses import aioresponses

# Ensure local src/ package imports work without installing the project.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))


class WriteIni(Protocol):
    """Callable signature for writing temporary INI config files."""

    def __call__(self, content: str, filename: str = "upgradinatorr.conf") -> Path:
        """Write INI content to a temporary file and return that file path."""


@pytest.fixture
def mock_aioresponses() -> Iterator[aioresponses]:
    """Mock aiohttp requests."""
    with aioresponses() as m:
        yield m


@pytest.fixture(autouse=True, scope="session")
def setup_stamina_testing() -> Iterator[None]:
    """Configure stamina to act immediately and avoid backoffs in tests."""
    stamina.set_testing(True)
    yield
    stamina.set_testing(False)


@pytest.fixture
def write_ini(tmp_path: Path) -> WriteIni:
    """Create an INI file and return the created path."""

    def _write(content: str, filename: str = "upgradinatorr.conf") -> Path:
        config_file = tmp_path / filename
        config_file.write_text(content.strip(), encoding="utf-8")
        return config_file

    return _write
