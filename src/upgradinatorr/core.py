"""Shared application workflow orchestration for CLI and TUI."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Protocol

from upgradinatorr.config import ApplicationConfig, get_application_type
from upgradinatorr.constants import DRY_RUN_IGNORE_TAG_ID, DRY_RUN_TAG_ID, STATUS_FIELDS
from upgradinatorr.starr.client import StarrClientProtocol
from upgradinatorr.starr.media import MediaFilter, select_random_media


class WorkflowReporter(Protocol):
    """Reporter interface for workflow progress and outcomes."""

    def status(self, message: str) -> None:
        """Report an in-progress step."""

    def info(self, message: str) -> None:
        """Report informational output."""

    def warning(self, message: str) -> None:
        """Report warnings."""

    def success(self, message: str) -> None:
        """Report successful operations."""

    def verbose(self, message: str) -> None:
        """Report verbose diagnostics."""


NotificationSender = Callable[
    [str, list[dict[str, Any]], str | None],
    Awaitable[bool],
]


@dataclass(slots=True)
class ApplicationRunRequest:
    """Inputs required to run the shared application workflow."""

    client: StarrClientProtocol
    app_name: str
    config: ApplicationConfig
    count: int | str | None = None
    dry_run: bool = False
    verbose: bool = False
    reporter: WorkflowReporter | None = None
    notification_sender: NotificationSender | None = None


@dataclass(slots=True)
class UnattendedModeRequest:
    """Inputs required to cycle unattended tags."""

    workflow: ApplicationRunRequest
    reporter: WorkflowReporter
    tag_id: int
    ignore_tag_id: int | None
    quality_profile_id: int | None
    all_media: list[dict[str, Any]]


class NullWorkflowReporter:
    """No-op reporter for callers that do not need progress output."""

    def status(self, message: str) -> None:  # noqa: ARG002
        """Ignore status messages."""
        return

    def info(self, message: str) -> None:  # noqa: ARG002
        """Ignore informational messages."""
        return

    def warning(self, message: str) -> None:  # noqa: ARG002
        """Ignore warning messages."""
        return

    def success(self, message: str) -> None:  # noqa: ARG002
        """Ignore success messages."""
        return

    def verbose(self, message: str) -> None:  # noqa: ARG002
        """Ignore verbose messages."""
        return


@dataclass(slots=True)
class ApplicationRunResult:
    """Result payload returned by the shared application workflow."""

    app_name: str
    app_type: str
    tag_id: int
    ignore_tag_id: int | None
    quality_profile_id: int | None
    total_media: int
    filtered_count: int
    selected: list[dict[str, Any]]
    cycled_unattended_tags: bool = False


def validate_tag_ids(tag_name: str, tag_id: int, ignore_tag: str, ignore_tag_id: int) -> None:
    """Validate that tag and ignore tag are not the same."""
    if tag_id == ignore_tag_id:
        msg = f"tag '{tag_name}' and ignore tag '{ignore_tag}' cannot be the same"
        raise ValueError(msg)


async def _setup_tags(
    client: StarrClientProtocol,
    config: ApplicationConfig,
    reporter: WorkflowReporter,
    *,
    dry_run: bool,
    verbose: bool,
) -> tuple[int, int | None]:
    if dry_run:
        tag = await client.get_tag(config.tag_name)
        if tag:
            tag_id = int(tag["id"])
        else:
            reporter.warning(f"would create tag '{config.tag_name}'")
            tag_id = DRY_RUN_TAG_ID
    else:
        tag_id = await client.get_or_create_tag(config.tag_name)

    if verbose:
        reporter.verbose(f"tag '{config.tag_name}' -> id={tag_id}")

    ignore_tag_id = None
    if config.ignore_tag:
        if dry_run:
            tag = await client.get_tag(config.ignore_tag)
            if tag:
                ignore_tag_id = int(tag["id"])
            else:
                reporter.warning(f"would create ignore tag '{config.ignore_tag}'")
                ignore_tag_id = DRY_RUN_IGNORE_TAG_ID
        else:
            ignore_tag_id = await client.get_or_create_tag(config.ignore_tag)

        if verbose:
            reporter.verbose(f"ignore tag '{config.ignore_tag}' -> id={ignore_tag_id}")

        if ignore_tag_id is None:
            msg = "ignore_tag_id was not resolved"
            raise RuntimeError(msg)
        validate_tag_ids(config.tag_name, tag_id, config.ignore_tag, ignore_tag_id)

    return tag_id, ignore_tag_id


async def _setup_quality_profile(
    client: StarrClientProtocol,
    config: ApplicationConfig,
    reporter: WorkflowReporter,
    *,
    verbose: bool,
) -> int | None:
    if not config.quality_profile_name:
        return None

    quality_profile_id = await client.get_quality_profile_id(config.quality_profile_name)
    if verbose:
        reporter.verbose(
            f"quality profile '{config.quality_profile_name}' -> id={quality_profile_id}",
        )

    return quality_profile_id


def _build_media_filter(
    app_name: str,
    config: ApplicationConfig,
    tag_id: int,
    ignore_tag_id: int | None,
    quality_profile_id: int | None,
) -> MediaFilter:
    app_type = get_application_type(app_name)
    status = getattr(config, STATUS_FIELDS[app_type], None)
    return MediaFilter(
        monitored=config.monitored,
        tag_id=tag_id,
        status=status,
        quality_profile_id=quality_profile_id,
        ignore_tag_id=ignore_tag_id,
    )


async def _handle_unattended_mode(
    request: UnattendedModeRequest,
) -> tuple[list[dict[str, Any]], bool]:
    request.reporter.info("No untagged media; cycling tags...")

    media_filter = _build_media_filter(
        request.workflow.app_name,
        request.workflow.config,
        request.tag_id,
        request.ignore_tag_id,
        request.quality_profile_id,
    )
    tagged_media = media_filter.filter_unattended(request.all_media)

    if not tagged_media:
        request.reporter.warning(
            "No media currently has the unattended tag "
            f"'{request.workflow.config.tag_name}' in {request.workflow.app_name.title()}. "
            "This is usually a configuration issue; if unexpected, open an issue at "
            "https://github.com/mountaingod2/upgradinatorr/issues",
        )
        return [], False

    media_ids = [item["id"] for item in tagged_media]
    if request.workflow.dry_run:
        request.reporter.warning(f"would remove tag from {len(media_ids)} items")
        for item in request.all_media:
            if item.get("id") in media_ids and "tags" in item and request.tag_id in item["tags"]:
                item["tags"].remove(request.tag_id)
        updated_media = request.all_media
    else:
        await request.workflow.client.remove_tags_from_media(media_ids, request.tag_id)
        updated_media = await request.workflow.client.get_all_media()

    return media_filter.filter_attended(updated_media), True


async def _process_selected_media(
    request: ApplicationRunRequest,
    reporter: WorkflowReporter,
    selected: list[dict[str, Any]],
    tag_id: int,
) -> None:
    if request.dry_run:
        reporter.warning(f"would search {len(selected)} items")
        reporter.warning(f"would tag {len(selected)} items")
        if request.notification_sender:
            reporter.warning("would send notification")
        return

    reporter.status("Searching...")
    await request.client.search_media_batch(selected)
    reporter.success(f"search queued for {len(selected)} items")

    media_ids = [item["id"] for item in selected]
    reporter.status("Tagging...")
    await request.client.add_tags_to_media(media_ids, tag_id)
    reporter.success(f"tagged {len(media_ids)} items")

    if request.notification_sender:
        reporter.status("Notifying...")
        notification_sent = await request.notification_sender(request.app_name, selected, None)
        if notification_sent:
            reporter.success("notification sent")
        else:
            reporter.warning("notification failed")


async def run_application(request: ApplicationRunRequest) -> ApplicationRunResult:
    """Run the full workflow for one configured Starr application."""
    request.app_name = request.app_name.lower()
    app_type = get_application_type(request.app_name)
    active_reporter = request.reporter or NullWorkflowReporter()

    active_reporter.status("Setting up tags...")
    tag_id, ignore_tag_id = await _setup_tags(
        request.client,
        request.config,
        active_reporter,
        dry_run=request.dry_run,
        verbose=request.verbose,
    )

    active_reporter.status("Checking quality profile...")
    quality_profile_id = await _setup_quality_profile(
        request.client,
        request.config,
        active_reporter,
        verbose=request.verbose,
    )

    active_reporter.status("Fetching media...")
    all_media = await request.client.get_all_media()
    media_filter = _build_media_filter(
        request.app_name,
        request.config,
        tag_id,
        ignore_tag_id,
        quality_profile_id,
    )

    filtered = (
        media_filter.filter_unattended(all_media)
        if request.config.unattended
        else media_filter.filter_attended(all_media)
    )

    if request.verbose:
        active_reporter.verbose(f"{len(all_media)} total -> {len(filtered)} match filter")

    cycled_unattended_tags = False
    if not filtered:
        if request.config.unattended:
            filtered, cycled_unattended_tags = await _handle_unattended_mode(
                UnattendedModeRequest(
                    workflow=request,
                    reporter=active_reporter,
                    tag_id=tag_id,
                    ignore_tag_id=ignore_tag_id,
                    quality_profile_id=quality_profile_id,
                    all_media=all_media,
                )
            )
            if not filtered:
                active_reporter.info("No media left to process in unattended mode")
                return ApplicationRunResult(
                    app_name=request.app_name,
                    app_type=app_type,
                    tag_id=tag_id,
                    ignore_tag_id=ignore_tag_id,
                    quality_profile_id=quality_profile_id,
                    total_media=len(all_media),
                    filtered_count=0,
                    selected=[],
                    cycled_unattended_tags=cycled_unattended_tags,
                )
        else:
            active_reporter.info(f"No {request.app_name} media matched; skipping")
            if request.notification_sender:
                notification_sent = await request.notification_sender(
                    request.app_name,
                    [],
                    "No media left to search",
                )
                if not notification_sent:
                    active_reporter.warning("notification failed")
            return ApplicationRunResult(
                app_name=request.app_name,
                app_type=app_type,
                tag_id=tag_id,
                ignore_tag_id=ignore_tag_id,
                quality_profile_id=quality_profile_id,
                total_media=len(all_media),
                filtered_count=0,
                selected=[],
                cycled_unattended_tags=False,
            )

    selected_count = request.count if request.count is not None else request.config.count
    selected = select_random_media(filtered, selected_count)

    active_reporter.info(f"{len(filtered)} candidates -> {len(selected)} selected")

    await _process_selected_media(request, active_reporter, selected, tag_id)

    return ApplicationRunResult(
        app_name=request.app_name,
        app_type=app_type,
        tag_id=tag_id,
        ignore_tag_id=ignore_tag_id,
        quality_profile_id=quality_profile_id,
        total_media=len(all_media),
        filtered_count=len(filtered),
        selected=selected,
        cycled_unattended_tags=cycled_unattended_tags,
    )
