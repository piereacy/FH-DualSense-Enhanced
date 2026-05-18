"""Logs tab: level cycler, pause toggle, clear, scrolling log view."""
import logging

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Label, Log, Static

log = logging.getLogger("fhds")

LOG_LEVELS = ("WARNING", "INFO", "DEBUG")
DEFAULT_LOG_LEVEL = "INFO"


class LogsTab(Vertical):
    DEFAULT_CSS = """
    LogsTab { width: 1fr; height: 1fr; padding: 0; }
    LogsTab .toolbar { height: 1; width: 1fr; padding: 0 1; background: $boost; }
    LogsTab .toolbar Label.caption { height: 1; color: $text-muted; padding: 0 1 0 0; }
    LogsTab .toolbar Static.sep {
        height: 1; width: 3; color: $text-muted; content-align: center middle;
    }
    LogsTab .toolbar .spacer { width: 1fr; height: 1; }
    LogsTab .toolbar .tb-action {
        height: 1; padding: 0 2; margin: 0 1 0 0;
        color: $text; background: $panel; content-align: center middle;
    }
    LogsTab .toolbar .tb-action:hover { background: $accent 30%; }
    LogsTab .toolbar .tb-action.-active {
        color: $background; background: $accent; text-style: bold;
    }
    LogsTab #log-level { width: 11; color: $accent; text-style: bold; }
    LogsTab #log-pause { width: 9; }
    LogsTab #log-clear { width: 9; }
    LogsTab Log {
        padding: 0 1; height: 1fr; width: 1fr;
        border-top: hkey $foreground 20%;
    }
    """

    def __init__(self):
        super().__init__()
        self._level_idx = LOG_LEVELS.index(DEFAULT_LOG_LEVEL)
        self._paused = False

    def compose(self) -> ComposeResult:
        with Horizontal(classes="toolbar"):
            yield Label("level", classes="caption")
            yield Static(LOG_LEVELS[self._level_idx].lower(), id="log-level", classes="tb-action")
            yield Static("│", classes="sep")
            yield Static("pause", id="log-pause", classes="tb-action")
            yield Static("clear", id="log-clear", classes="tb-action")
            yield Static(classes="spacer")
        yield Log(id="logs", highlight=False, max_lines=2000, auto_scroll=True)

    @property
    def level_name(self) -> str:
        return LOG_LEVELS[self._level_idx]

    @property
    def level(self) -> int:
        return getattr(logging, self.level_name)

    @property
    def paused(self) -> bool:
        return self._paused

    def write(self, msg: str) -> None:
        self.query_one("#logs", Log).write_line(msg)

    def clear(self) -> None:
        self.query_one("#logs", Log).clear()

    def toggle_pause(self) -> None:
        self._paused = not self._paused
        self.query_one("#logs", Log).auto_scroll = not self._paused
        self._refresh_buttons()
        self.app.refresh_status()

    def cycle_level(self) -> None:
        self._level_idx = (self._level_idx + 1) % len(LOG_LEVELS)
        logging.getLogger().setLevel(self.level)
        self._refresh_buttons()
        self.app.refresh_status()
        log.info("Log level: %s", self.level_name)

    def _refresh_buttons(self) -> None:
        self.query_one("#log-level", Static).update(self.level_name.lower())
        pause = self.query_one("#log-pause", Static)
        pause.update("resume" if self._paused else "pause")
        pause.set_class(self._paused, "-active")

    def on_click(self, event):
        widget = getattr(event, "widget", None)
        wid = getattr(widget, "id", None) if widget else None
        if wid == "log-level":
            self.cycle_level()
        elif wid == "log-pause":
            self.toggle_pause()
        elif wid == "log-clear":
            self.clear()
