"""Project attribution and license-required links."""
from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Button, Label

from modules.about import APP_NAME, ATTRIBUTION, SOURCE_URL, SPONSOR_URL
from modules.config.preferences import _release_version


class AboutTab(VerticalScroll):
    DEFAULT_CSS = """
    AboutTab { width: 1fr; height: 1fr; padding: 1 2; }
    AboutTab .about-title { text-style: bold; color: $accent; padding: 1; }
    AboutTab .about-copy { width: 1fr; height: auto; padding: 1; }
    AboutTab .about-link { width: 1fr; margin: 0 1 1 1; }
    """

    def compose(self) -> ComposeResult:
        yield Label(
            f"{APP_NAME} {_release_version() or '?'}",
            classes="about-title",
        )
        yield Label(ATTRIBUTION, classes="about-copy")
        yield Button(f"Source: {SOURCE_URL}", id="about-source", classes="about-link")
        yield Button(f"Sponsor: {SPONSOR_URL}", id="about-sponsor", classes="about-link")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "about-source":
            self.app._open_url(SOURCE_URL)
        elif event.button.id == "about-sponsor":
            self.app._open_url(SPONSOR_URL)
