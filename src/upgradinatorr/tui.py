"""Terminal User Interface for Upgradinatorr using Textual."""

import contextlib
import logging
from pathlib import Path
from typing import Any, ClassVar

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
    parse_ini_config,
    validate_application_name,
)
from upgradinatorr.core import (
    ApplicationRunRequest,
    NotificationSender,
    WorkflowReporter,
    run_application,
)
from upgradinatorr.media_display import build_media_display_row
from upgradinatorr.notifications.completion import (
    CompletionNotificationRequest,
    send_completion_notification,
)
from upgradinatorr.starr.client import StarrAPIError, StarrClient

logger = logging.getLogger(__name__)


class MediaDataTable(DataTable[str]):
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
            row = build_media_display_row(item, app_type)
            monitored = "✓" if row.monitored else "✗"
            self.add_row(
                app_name.title(),
                row.title,
                row.year,
                row.status,
                monitored,
                row.extra,
            )


class TuiWorkflowReporter(WorkflowReporter):
    """Render shared workflow events in Textual widgets."""

    def __init__(self, app: "UpgradinatorTUI", app_name: str, *, verbose_enabled: bool) -> None:
        """Store UI widget context and verbosity flags."""
        self._app = app
        self._app_name = app_name
        self._verbose_enabled = verbose_enabled

    def status(self, message: str) -> None:
        """Render a status update in the status label."""
        self._app.set_status(f"{self._app_name}: {message}")

    def info(self, message: str) -> None:
        """Render an informational message to the log widget."""
        self._app.query_one("#log-display", Log).write_line(message)

    def warning(self, message: str) -> None:
        """Render a warning message to the log widget."""
        self._app.query_one("#log-display", Log).write_line(f"Warning: {message}")

    def success(self, message: str) -> None:
        """Render a success message to the log widget."""
        self._app.query_one("#log-display", Log).write_line(f"Success: {message}")

    def verbose(self, message: str) -> None:
        """Render verbose output when verbose mode is enabled."""
        if self._verbose_enabled:
            self._app.query_one("#log-display", Log).write_line(f"Detail: {message}")


class UpgradinatorTUI(App[None]):
    """Textual TUI for Upgradinatorr."""

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        Binding("q", "quit", "Quit", priority=True),
        Binding("r", "refresh", "Refresh"),
        Binding("s", "start", "Start"),
        Binding("c", "clear_log", "Clear Log"),
    ]

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
        super().__init__(*args, **kwargs)
        self.config_file = config_file
        self.config_dict: dict[str, Any] = {}
        self.notifications: NotificationConfig | None = None
        self.notify_discord_enabled = False
        self.notify_notifiarr_enabled = False
        self._suppress_notification_logs = False
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
                yield Label("Notifications", classes="panel-title")
                yield Vertical(id="notification-method-list")

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

    def _get_notification_config_availability(self) -> tuple[bool, bool]:
        """Return config availability for Discord and Notifiarr channels."""
        notifications = self.notifications
        if notifications is None:
            return False, False

        has_discord = bool(notifications.discord_webhook)
        has_notifiarr = bool(
            notifications.notifiarr_webhook and notifications.notifiarr_channel_id,
        )
        return has_discord, has_notifiarr

    def _notification_summary(self) -> str:
        """Build a short summary of active notification settings."""
        has_discord, has_notifiarr = self._get_notification_config_availability()
        if not has_discord and not has_notifiarr:
            return "No notification methods configured"

        if not self.notify_discord_enabled and not self.notify_notifiarr_enabled:
            return "All notification methods disabled"

        methods: list[str] = []
        if has_discord:
            discord_state = "on" if self.notify_discord_enabled else "off"
            methods.append(f"Discord notifications {discord_state}")
        if has_notifiarr:
            notifiarr_state = "on" if self.notify_notifiarr_enabled else "off"
            methods.append(f"Notifiarr notifications {notifiarr_state}")

        return ", ".join(methods)

    def _get_notification_switch(self, switch_id: str) -> Checkbox | None:
        """Return a notification checkbox if it is currently mounted."""
        for widget in self.query(f"#{switch_id}"):
            if isinstance(widget, Checkbox):
                return widget
        return None

    async def _rebuild_notification_method_switches(self) -> None:
        """Mount only notification method switches that are configured."""
        has_discord, has_notifiarr = self._get_notification_config_availability()
        method_list = self.query_one("#notification-method-list", Vertical)

        await method_list.query("*").remove()

        if has_discord:
            await method_list.mount(
                Checkbox("Discord", id="notify-discord-switch", value=self.notify_discord_enabled),
            )
        if has_notifiarr:
            await method_list.mount(
                Checkbox(
                    "Notifiarr",
                    id="notify-notifiarr-switch",
                    value=self.notify_notifiarr_enabled,
                ),
            )

    def _apply_notification_switch_states(self) -> None:
        """Sync notification checkbox values and disabled state from current settings."""
        has_discord, has_notifiarr = self._get_notification_config_availability()

        if not has_discord:
            self.notify_discord_enabled = False
        if not has_notifiarr:
            self.notify_notifiarr_enabled = False

        discord_switch = self._get_notification_switch("notify-discord-switch")
        notifiarr_switch = self._get_notification_switch("notify-notifiarr-switch")

        self._suppress_notification_logs = True
        if discord_switch and discord_switch.value != self.notify_discord_enabled:
            discord_switch.value = self.notify_discord_enabled
        if notifiarr_switch and notifiarr_switch.value != self.notify_notifiarr_enabled:
            notifiarr_switch.value = self.notify_notifiarr_enabled
        self._suppress_notification_logs = False

        if discord_switch:
            discord_switch.disabled = not has_discord
        if notifiarr_switch:
            notifiarr_switch.disabled = not has_notifiarr

    def _resolve_app_config(self, app_name: str) -> tuple[str | None, ApplicationConfig | None]:
        app_lower = app_name.lower()
        app_config_key = next((key for key in self.config_dict if key.lower() == app_lower), None)
        if not app_config_key:
            return None, None

        return app_config_key, ApplicationConfig(**self.config_dict[app_config_key])

    def _resolve_count(self, app_config: ApplicationConfig) -> int | str | None:
        count_input = self.query_one("#global-count", Input).value
        custom_count = app_config.count
        if count_input and count_input.isdigit():
            custom_count = int(count_input)
        return custom_count

    def _build_notification_sender(
        self,
        log_widget: Log,
        notifications: NotificationConfig | None,
    ) -> NotificationSender | None:
        if notifications is None:
            if self.verbose:
                log_widget.write_line("Detail: no notification methods configured; skipping send")
            return None

        send_discord = self.notify_discord_enabled and bool(notifications.discord_webhook)
        send_notifiarr = self.notify_notifiarr_enabled and bool(
            notifications.notifiarr_webhook and notifications.notifiarr_channel_id,
        )

        def log_notification_warning(message: str) -> None:
            """Write notification warnings to the TUI log."""
            log_widget.write_line(f"Warning: {message}")

        if not send_discord and not send_notifiarr:
            if self.verbose:
                log_widget.write_line("Detail: notifications disabled; no methods are active")
            return None

        async def configured_notification_sender(
            notif_app_name: str,
            media_items: list[dict[str, Any]],
            custom_message: str | None = None,
        ) -> None:
            await send_completion_notification(
                CompletionNotificationRequest(
                    app_name=notif_app_name,
                    media_items=media_items,
                    notifications=notifications,
                    custom_message=custom_message,
                    warning_handler=log_notification_warning,
                    enable_discord=send_discord,
                    enable_notifiarr=send_notifiarr,
                )
            )

        return configured_notification_sender

    async def load_config(self) -> None:
        """Load configuration from file."""
        log_widget = self.query_one("#log-display", Log)
        self.set_status("Loading config...")

        try:
            log_widget.write_line(f"Loading config from {self.config_file}")
            self.config_dict = parse_ini_config(self.config_file)

            if "Notifications" in self.config_dict:
                self.notifications = NotificationConfig(**self.config_dict["Notifications"])
            else:
                self.notifications = None

            has_discord, has_notifiarr = self._get_notification_config_availability()
            self.notify_discord_enabled = has_discord
            self.notify_notifiarr_enabled = has_notifiarr
            await self._rebuild_notification_method_switches()
            self._apply_notification_switch_states()

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
                    log_widget.write_line(f"Warning: skipping invalid app '{app_name}'")

            log_widget.write_line(f"Config loaded: {valid_apps} apps found.")
            log_widget.write_line(self._notification_summary())
            self.set_status(f"Ready ({valid_apps} available apps)")

        except FileNotFoundError:
            log_widget.write_line(f"Error: config file not found at {self.config_file}")
            self.set_status("Error: Config not found")
        except Exception as e:
            log_widget.write_line(f"Error: failed to load config: {e}")
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
            self.query_one("#log-display", Log).write_line("Warning: no applications selected")
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

    @on(Checkbox.Changed, "#notify-discord-switch")
    def on_notify_discord_switched(self, event: Checkbox.Changed) -> None:
        """Handle Discord notification switch toggle."""
        self.notify_discord_enabled = event.value
        if not self._suppress_notification_logs:
            self.query_one("#log-display", Log).write_line(self._notification_summary())

    @on(Checkbox.Changed, "#notify-notifiarr-switch")
    def on_notify_notifiarr_switched(self, event: Checkbox.Changed) -> None:
        """Handle Notifiarr notification switch toggle."""
        self.notify_notifiarr_enabled = event.value
        if not self._suppress_notification_logs:
            self.query_one("#log-display", Log).write_line(self._notification_summary())

    async def process_app(self, app_name: str) -> None:
        """Process a single application."""
        log_widget = self.query_one("#log-display", Log)
        media_table = self.query_one("#media-table", MediaDataTable)

        log_widget.write_line(f"--- Processing: {app_name.title()} ---")
        self.set_status(f"Processing: {app_name}")

        app_lower = app_name.lower()

        try:
            app_config_key, app_config = self._resolve_app_config(app_name)
            if not app_config_key:
                log_widget.write_line(f"No config found for '{app_name}'")
                return

            if app_config is None:
                log_widget.write_line(f"No config found for '{app_name}'")
                return

            custom_count = self._resolve_count(app_config)

            if self.verbose:
                log_widget.write_line(f"Detail: URL {app_config.url}")
                log_widget.write_line(
                    f"Detail: tag '{app_config.tag_name}' | items {custom_count}",
                )

            notification_sender = self._build_notification_sender(log_widget, self.notifications)

            async with StarrClient(app_lower, app_config.url, app_config.api_key) as client:
                reporter = TuiWorkflowReporter(
                    self,
                    app_name,
                    verbose_enabled=self.verbose,
                )
                result = await run_application(
                    ApplicationRunRequest(
                        client=client,
                        app_name=app_lower,
                        config=app_config,
                        count=custom_count,
                        dry_run=self.dry_run,
                        verbose=self.verbose,
                        reporter=reporter,
                        notification_sender=notification_sender,
                    )
                )

                if not result.selected:
                    log_widget.write_line("No media matched filters.")
                    return

                media_table.append_media(result.selected, app_name, result.app_type)

                log_widget.write_line(f"Finished processing {app_name}\n")

        except StarrAPIError as e:
            log_widget.write_line(f"Error: API error: {e}")
        except Exception as e:
            log_widget.write_line(f"Error: unexpected error: {e}")
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
