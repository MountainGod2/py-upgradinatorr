"""Terminal User Interface for Upgradinatorr using Textual."""

import contextlib
import logging
from pathlib import Path
from typing import Any

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import (
    Button,
    Checkbox,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    Log,
)

from upgradinatorr.config import (
    ApplicationConfig,
    NotificationConfig,
    get_application_type,
    parse_ini_config,
    validate_application_name,
)
from upgradinatorr.constants import STATUS_FIELDS
from upgradinatorr.starr.client import StarrAPIError, StarrClient
from upgradinatorr.starr.media import MediaFilter, select_random_media

logger = logging.getLogger(__name__)


class MediaDataTable(DataTable):
    """Custom DataTable for displaying media items."""

    def on_mount(self) -> None:
        """Called when the widget is mounted."""
        self.add_column("App", key="app", width=12)
        self.add_column("Title / Artist", key="title", width=35)
        self.add_column("Year", key="year", width=6)
        self.add_column("Status", key="status", width=12)
        self.add_column("Monitored", key="monitored", width=10)
        self.add_column("Extra", key="extra", width=8)

    def append_media(self, media_items: list[dict[str, Any]], app_name: str, app_type: str) -> None:
        """Append media items to the table without clearing it."""
        for item in media_items:
            monitored = "✓" if item.get("monitored") else "✗"
            status = str(item.get("status", "unknown")).title()

            if app_type == "radarr":
                self.add_row(
                    app_name.title(),
                    item.get("title", "Unknown"),
                    str(item.get("year", "")),
                    status,
                    monitored,
                    "",
                )
            elif app_type == "sonarr":
                seasons = str(
                    item.get("seasonCount", item.get("statistics", {}).get("seasonCount", "?"))
                )
                self.add_row(
                    app_name.title(),
                    item.get("title", "Unknown"),
                    str(item.get("year", "")),
                    status,
                    monitored,
                    f"S: {seasons}",
                )
            elif app_type == "lidarr":
                self.add_row(
                    app_name.title(), item.get("artistName", "Unknown"), "", status, monitored, ""
                )
            elif app_type == "readarr":
                self.add_row(
                    app_name.title(), item.get("authorName", "Unknown"), "", status, monitored, ""
                )


class UpgradinatorTUI(App):
    """Textual TUI for Upgradinatorr."""

    CSS = """
    Screen {
        background: $surface;
    }

    #sidebar {
        width: 35;
        border-right: solid $primary;
        background: $panel;
        padding: 1;
    }

    .panel-title {
        text-style: bold;
        color: $accent;
        padding-bottom: 1;
        margin-top: 1;
        border-bottom: solid $primary;
        width: 100%;
    }

    #app-list {
        height: auto;
        max-height: 12;
        margin-bottom: 1;
    }

    .input-row {
        height: auto;
        align: left middle;
        margin-bottom: 1;
    }

    .input-row Label {
        width: 12;
    }

    #global-count {
        width: 10;
        height: 3;
    }

    #main-content {
        width: 1fr;
        padding: 1;
    }

    #status-display {
        text-style: bold;
        padding: 1;
        background: $panel;
        border: round $primary;
        margin-bottom: 1;
        width: 100%;
    }

    Log {
        height: 1fr;
        border: round $primary;
        background: $panel;
        margin-bottom: 1;
    }

    MediaDataTable {
        height: 1fr;
        border: round $primary;
    }

    #sidebar Button {
        width: 100%;
        margin-top: 1;
    }
    """

    TITLE = "Upgradinatorr"

    def __init__(self, config_file: Path, *args: Any, **kwargs: Any) -> None:  # noqa: ANN401
        """Initialize the TUI application."""
        self.BINDINGS = [
            Binding("q", "quit", "Quit", priority=True),
            Binding("r", "refresh", "Refresh"),
            Binding("s", "start", "Start"),
            Binding("c", "clear_log", "Clear Log"),
        ]
        super().__init__(*args, **kwargs)
        self.config_file = config_file
        self.config_dict: dict[str, Any] = {}
        self.notifications: NotificationConfig | None = None
        self.dry_run = False
        self.verbose = True

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield Header(show_clock=True)

        with Horizontal():
            with Vertical(id="sidebar"):
                yield Label("Applications", classes="panel-title")
                yield VerticalScroll(id="app-list")

                yield Label("Settings", classes="panel-title")
                with Horizontal(classes="input-row"):
                    yield Label("Items/App:")
                    yield Input(
                        placeholder="Auto",
                        id="global-count",
                        tooltip="Leave empty for config default",
                    )

                yield Checkbox("Dry Run", id="dry-run-switch", value=False)
                yield Checkbox("Verbose", id="verbose-switch", value=True)

                yield Button("Start Process", variant="success", id="start-button")
                yield Button("Refresh Config", id="refresh-button")

            with Vertical(id="main-content"):
                yield Label("Ready", id="status-display")
                yield Log(id="log-display", highlight=True)
                yield MediaDataTable(id="media-table", zebra_stripes=True, cursor_type="row")

        yield Footer()

    async def on_mount(self) -> None:
        """Set up the application when mounted."""
        await self.load_config()

    def set_status(self, text: str) -> None:
        """Update the status display."""
        with contextlib.suppress(Exception):
            self.query_one("#status-display", Label).update(text)

    async def load_config(self) -> None:
        """Load configuration from file."""
        log_widget = self.query_one("#log-display", Log)
        self.set_status("Loading config...")

        try:
            log_widget.write_line(f"Loading config from {self.config_file}")
            self.config_dict = parse_ini_config(self.config_file)

            if "Notifications" in self.config_dict:
                self.notifications = NotificationConfig(**self.config_dict["Notifications"])

            app_list = self.query_one("#app-list", VerticalScroll)

            # Clear options safely
            await app_list.query("*").remove()

            app_sections = [
                key for key in self.config_dict if key.lower() not in ["general", "notifications"]
            ]

            valid_apps = 0
            for app_name in app_sections:
                try:
                    validate_application_name(app_name.lower())
                    await app_list.mount(
                        Checkbox(app_name.title(), value=True, id=f"chk_{app_name}")
                    )
                    valid_apps += 1
                except ValueError:
                    log_widget.write_line(f"Skipping invalid app: {app_name}")

            log_widget.write_line(f"Config loaded: {valid_apps} apps found.")
            self.set_status(f"Ready ({valid_apps} available apps)")

        except FileNotFoundError:
            log_widget.write_line(f"Config file not found: {self.config_file}")
            self.set_status("Error: Config not found")
        except Exception as e:
            log_widget.write_line(f"Error loading config: {e}")
            self.set_status("Error: Failed to load config")
            logger.exception("Error loading config")

    @on(Button.Pressed, "#start-button")
    @work(exclusive=True)
    async def on_start_pressed(self) -> None:
        """Handle start button press."""
        selected_apps = [
            chk.id.replace("chk_", "")
            for chk in self.query(Checkbox)
            if chk.id and chk.id.startswith("chk_") and chk.value
        ]

        if not selected_apps:
            self.query_one("#log-display", Log).write_line("No applications selected.")
            self.set_status("No applications selected")
            return

        # Clear just the rows from the table before starting fresh queue
        self.query_one("#media-table", MediaDataTable).clear()

        for app_name in selected_apps:
            await self.process_app(app_name)

        self.set_status("All selected applications processed.")

    @on(Button.Pressed, "#refresh-button")
    async def on_refresh_pressed(self) -> None:
        """Handle refresh button press."""
        await self.load_config()

    @on(Checkbox.Changed, "#dry-run-switch")
    def on_dry_run_switched(self, event: Checkbox.Changed) -> None:
        """Handle dry run switch toggle."""
        self.dry_run = event.value
        self.query_one("#log-display", Log).write_line(
            f"Dry run {'enabled' if self.dry_run else 'disabled'}"
        )

    @on(Checkbox.Changed, "#verbose-switch")
    def on_verbose_switched(self, event: Checkbox.Changed) -> None:
        """Handle verbose switch toggle."""
        self.verbose = event.value
        self.query_one("#log-display", Log).write_line(
            f"Verbose mode {'enabled' if self.verbose else 'disabled'}"
        )

    async def process_app(self, app_name: str) -> None:
        """Process a single application."""
        log_widget = self.query_one("#log-display", Log)
        media_table = self.query_one("#media-table", MediaDataTable)

        log_widget.write_line(f"--- Processing: {app_name.title()} ---")
        self.set_status(f"Processing: {app_name}")

        app_lower = app_name.lower()

        try:
            app_config_key = next(
                (key for key in self.config_dict if key.lower() == app_lower), None
            )

            if not app_config_key:
                log_widget.write_line(f"No config found for '{app_name}'")
                return

            app_config = ApplicationConfig(**self.config_dict[app_config_key])
            app_type = get_application_type(app_lower)

            count_input = self.query_one("#global-count", Input).value
            custom_count = app_config.count
            if count_input and count_input.isdigit():
                custom_count = int(count_input)

            if self.verbose:
                log_widget.write_line(f"  URL: {app_config.url}")
                log_widget.write_line(f"  Tag: {app_config.tag_name} | Items: {custom_count}")

            async with StarrClient(app_lower, app_config.url, app_config.api_key) as client:
                self.set_status(f"{app_name}: Setting up tags...")
                if self.dry_run:
                    tag = await client.get_tag(app_config.tag_name)
                    tag_id = int(tag["id"]) if tag else 9999
                else:
                    tag_id = await client.get_or_create_tag(app_config.tag_name)
                log_widget.write_line(f"Using tag: '{app_config.tag_name}' (ID: {tag_id})")

                ignore_tag_id = None
                if app_config.ignore_tag:
                    if self.dry_run:
                        tag = await client.get_tag(app_config.ignore_tag)
                        ignore_tag_id = int(tag["id"]) if tag else 9998
                    else:
                        ignore_tag_id = await client.get_or_create_tag(app_config.ignore_tag)
                    log_widget.write_line(
                        f"Ignoring tag: '{app_config.ignore_tag}' (ID: {ignore_tag_id})"
                    )

                quality_profile_id = None
                if app_config.quality_profile_name:
                    quality_profile_id = await client.get_quality_profile_id(
                        app_config.quality_profile_name
                    )

                self.set_status(f"{app_name}: Fetching media...")
                all_media = await client.get_all_media()

                status = getattr(app_config, STATUS_FIELDS[app_type], None)
                media_filter = MediaFilter(
                    monitored=app_config.monitored,
                    tag_id=tag_id,
                    status=status,
                    quality_profile_id=quality_profile_id,
                    ignore_tag_id=ignore_tag_id,
                )

                filtered = (
                    media_filter.filter_unattended(all_media)
                    if app_config.unattended
                    else media_filter.filter_attended(all_media)
                )

                if not filtered:
                    log_widget.write_line("No media matched filters.")
                    return

                selected = select_random_media(filtered, custom_count)
                log_widget.write_line(
                    f"Selected {len(selected)} random items out of {len(filtered)} filtered."
                )

                # Show selected items
                media_table.append_media(selected, app_name, app_type)

                if self.dry_run:
                    log_widget.write_line(f"DRY RUN: Would search and tag {len(selected)} items.")
                else:
                    self.set_status(f"{app_name}: Searching and tagging...")
                    await client.search_media_batch(selected)
                    media_ids = [item["id"] for item in selected]
                    await client.add_tags_to_media(media_ids, tag_id)
                    log_widget.write_line(
                        f"Successfully queued search and tagged {len(selected)} items."
                    )

                log_widget.write_line(f"Finished processing {app_name}\n")

        except StarrAPIError as e:
            log_widget.write_line(f"API Error: {e}")
        except Exception as e:
            log_widget.write_line(f"An unexpected error occurred: {e}")
            logger.exception("Error processing app")

    def action_refresh(self) -> None:
        """Refresh configuration."""
        self.run_worker(self.load_config())

    def action_start(self) -> None:
        """Start processing selected apps."""
        self.query_one("#start-button", Button).press()

    def action_clear_log(self) -> None:
        """Clear the log display."""
        self.query_one("#log-display", Log).clear()
        self.query_one("#log-display", Log).write_line("Log cleared.")


def run_tui(config_file: Path = Path("upgradinatorr.conf")) -> None:
    """Run the TUI application."""
    app = UpgradinatorTUI(config_file)
    app.run()


if __name__ == "__main__":
    run_tui()
