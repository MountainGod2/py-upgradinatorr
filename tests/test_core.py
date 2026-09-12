"""Unit tests for shared application workflow orchestration."""

from typing import Any

import pytest

from upgradinatorr.config import ApplicationConfig
from upgradinatorr.constants import DRY_RUN_IGNORE_TAG_ID, DRY_RUN_TAG_ID
from upgradinatorr.core import ApplicationRunRequest, NullWorkflowReporter, run_application


class FakeStarrClient:
    """Small in-memory Starr client test double."""

    def __init__(
        self,
        media: list[dict[str, Any]],
        tags: dict[str, int] | None = None,
    ) -> None:
        """Initialize fake API state and captured calls."""
        self._media = media
        self._tags = tags or {}
        self.search_called_with: list[dict[str, Any]] | None = None
        self.tagged_ids: list[int] = []
        self.removed_ids: list[int] = []

    async def get_tag(self, tag_name: str) -> dict[str, Any] | None:
        """Return an existing tag payload by name."""
        if tag_name in self._tags:
            return {"id": self._tags[tag_name], "label": tag_name}
        return None

    async def get_or_create_tag(self, tag_name: str) -> int:
        """Resolve a tag ID, creating one when absent."""
        if tag_name in self._tags:
            return self._tags[tag_name]
        new_id = max(self._tags.values(), default=10) + 1
        self._tags[tag_name] = new_id
        return new_id

    async def get_quality_profile_id(self, profile_name: str) -> int:
        """Return a fixed quality profile ID for tests."""
        del profile_name
        return 99

    async def get_all_media(self) -> list[dict[str, Any]]:
        """Return in-memory media payload."""
        return self._media

    async def remove_tags_from_media(self, media_ids: list[int], tag_id: int) -> None:
        """Track removals and mutate in-memory tag state."""
        self.removed_ids = media_ids
        for item in self._media:
            if item.get("id") in media_ids and tag_id in item.get("tags", []):
                item["tags"].remove(tag_id)

    async def search_media_batch(self, media_items: list[dict[str, Any]]) -> None:
        """Capture search payload for assertions."""
        self.search_called_with = media_items

    async def add_tags_to_media(self, media_ids: list[int], tag_id: int) -> None:
        """Capture tagged IDs for assertions."""
        del tag_id
        self.tagged_ids = media_ids


@pytest.mark.asyncio
async def test_run_application_uses_shared_dry_run_tag_constants() -> None:
    """Dry-run mode should use the canonical sentinel tag IDs."""
    config = ApplicationConfig(
        ApiKey="a" * 32,
        Url="http://localhost:7878",
        Count=1,
        TagName="upgrade",
        IgnoreTag="ignore",
    )
    client = FakeStarrClient(media=[])

    result = await run_application(
        ApplicationRunRequest(
            client=client,
            app_name="radarr",
            config=config,
            dry_run=True,
            reporter=NullWorkflowReporter(),
        )
    )

    assert result.tag_id == DRY_RUN_TAG_ID
    assert result.ignore_tag_id == DRY_RUN_IGNORE_TAG_ID
    assert result.selected == []


@pytest.mark.asyncio
async def test_run_application_validates_tag_ids_in_dry_run() -> None:
    """Dry-run should still reject identical tag and ignore tag IDs."""
    config = ApplicationConfig(
        ApiKey="a" * 32,
        Url="http://localhost:7878",
        Count=1,
        TagName="upgrade",
        IgnoreTag="ignore",
    )
    client = FakeStarrClient(media=[], tags={"upgrade": 123, "ignore": 123})

    with pytest.raises(ValueError, match="cannot be the same"):
        await run_application(
            ApplicationRunRequest(
                client=client,
                app_name="radarr",
                config=config,
                dry_run=True,
                reporter=NullWorkflowReporter(),
            )
        )


@pytest.mark.asyncio
async def test_run_application_notifies_when_no_media_in_attended_mode() -> None:
    """Attended mode should emit the no-media completion notification."""
    config = ApplicationConfig(
        ApiKey="a" * 32,
        Url="http://localhost:7878",
        Count=1,
        TagName="upgrade",
    )
    client = FakeStarrClient(media=[])

    sent_messages: list[tuple[str, list[dict[str, Any]], str | None]] = []

    async def notification_sender(
        app_name: str,
        media_items: list[dict[str, Any]],
        custom_message: str | None = None,
    ) -> bool:
        sent_messages.append((app_name, media_items, custom_message))
        return True

    await run_application(
        ApplicationRunRequest(
            client=client,
            app_name="radarr",
            config=config,
            reporter=NullWorkflowReporter(),
            notification_sender=notification_sender,
        )
    )

    assert sent_messages == [("radarr", [], "No media left to search")]


@pytest.mark.asyncio
async def test_run_application_warns_when_no_media_notification_fails() -> None:
    """The no-media path should warn when the sender reports a failed notification."""
    config = ApplicationConfig(
        ApiKey="a" * 32,
        Url="http://localhost:7878",
        Count=1,
        TagName="upgrade",
    )
    client = FakeStarrClient(media=[])
    warnings: list[str] = []

    class RecordingReporter:
        def status(self, message: str) -> None:
            del message

        def info(self, message: str) -> None:
            del message

        def warning(self, message: str) -> None:
            warnings.append(message)

        def success(self, message: str) -> None:
            del message

        def verbose(self, message: str) -> None:
            del message

    async def notification_sender(
        app_name: str,
        media_items: list[dict[str, Any]],
        custom_message: str | None = None,
    ) -> bool:
        del app_name, media_items, custom_message
        return False

    await run_application(
        ApplicationRunRequest(
            client=client,
            app_name="radarr",
            config=config,
            reporter=RecordingReporter(),
            notification_sender=notification_sender,
        )
    )

    assert warnings == ["notification failed"]
