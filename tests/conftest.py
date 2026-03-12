"""Shared pytest configuration for test discovery."""

import sys
from pathlib import Path
from typing import Protocol, Self

import pytest

# Ensure local src/ package imports work without installing the project.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))


class PatchClientSession(Protocol):
    """Callable signature for patching aiohttp ClientSession in tests."""

    def __call__(
        self,
        module_client_session_path: str,
        *,
        status: int,
        payload: dict[str, object] | None = None,
    ) -> None:
        """Patch a module's aiohttp ClientSession factory with a fake implementation."""


class WriteIni(Protocol):
    """Callable signature for writing temporary INI config files."""

    def __call__(self, content: str, filename: str = "upgradinatorr.conf") -> Path:
        """Write INI content to a temporary file and return that file path."""


@pytest.fixture
def patch_client_session(monkeypatch: pytest.MonkeyPatch) -> PatchClientSession:
    """Patch an aiohttp ClientSession with a configurable fake response."""

    class _FakeResponse:
        def __init__(self, status: int, payload: dict[str, object] | None = None) -> None:
            self.status = status
            self._payload = payload

        async def __aenter__(self) -> Self:
            return self

        async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
            return None

        async def json(self) -> dict[str, object]:
            if self._payload is None:
                return {}
            return self._payload

    class _FakeSession:
        def __init__(self, status: int, payload: dict[str, object] | None = None) -> None:
            self._status = status
            self._payload = payload

        async def __aenter__(self) -> Self:
            return self

        async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
            return None

        def post(self, *_args: object, **_kwargs: object) -> _FakeResponse:
            return _FakeResponse(self._status, self._payload)

    def _patch(
        module_client_session_path: str,
        *,
        status: int,
        payload: dict[str, object] | None = None,
    ) -> None:
        monkeypatch.setattr(
            module_client_session_path,
            lambda: _FakeSession(status, payload),
        )

    return _patch


@pytest.fixture
def write_ini(tmp_path: Path) -> WriteIni:
    """Create an INI file and return the created path."""

    def _write(content: str, filename: str = "upgradinatorr.conf") -> Path:
        config_file = tmp_path / filename
        config_file.write_text(content.strip(), encoding="utf-8")
        return config_file

    return _write
