"""Modal screens shared by TUI lifecycle actions."""

from __future__ import annotations

from collections.abc import Callable

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static

from lang import t


class UnsavedProfileScreen(ModalScreen[str | None]):
    """Offer to preserve Default tuning as a reusable named profile."""

    BINDINGS = [("escape", "cancel", "Cancel")]
    DEFAULT_CSS = """
    UnsavedProfileScreen {
        align: center middle;
        background: $background 70%;
    }
    UnsavedProfileScreen > #profile-exit-dialog {
        width: 72;
        height: auto;
        max-width: 95%;
        padding: 1 2;
        border: round $accent;
        background: $surface;
    }
    UnsavedProfileScreen #profile-exit-heading {
        width: 1fr;
        height: auto;
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }
    UnsavedProfileScreen #profile-exit-detail {
        width: 1fr;
        height: auto;
        color: $text-muted;
        margin-bottom: 1;
    }
    UnsavedProfileScreen #profile-exit-error {
        width: 1fr;
        height: auto;
        color: $error;
    }
    UnsavedProfileScreen #profile-exit-buttons {
        width: 1fr;
        height: auto;
        margin-top: 1;
    }
    UnsavedProfileScreen #profile-exit-buttons Button {
        width: 1fr;
        margin-right: 1;
    }
    UnsavedProfileScreen #profile-exit-buttons Button:last-of-type {
        margin-right: 0;
    }
    """

    def __init__(self, *, suggested_name: str, on_save: Callable[[str], bool]):
        super().__init__()
        self._suggested_name = suggested_name
        self._on_save = on_save

    def compose(self) -> ComposeResult:
        with Vertical(id="profile-exit-dialog"):
            yield Label(t("Save your tuning before exit?"), id="profile-exit-heading")
            yield Static(
                t(
                    "Default already autosaved these changes. Save a named profile to keep a reusable snapshot."
                ),
                id="profile-exit-detail",
            )
            yield Input(value=self._suggested_name, id="profile-exit-name")
            yield Static("", id="profile-exit-error")
            with Horizontal(id="profile-exit-buttons"):
                yield Button(
                    t("Save as named profile and exit"),
                    id="profile-exit-save",
                    variant="success",
                )
                yield Button(t("Exit directly"), id="profile-exit-discard")
                yield Button(t("Cancel"), id="profile-exit-cancel")

    def on_mount(self) -> None:
        field = self.query_one("#profile-exit-name", Input)
        field.focus()
        field.selection = (0, len(field.value))

    def _save(self) -> None:
        name = self.query_one("#profile-exit-name", Input).value.strip()
        error = self.query_one("#profile-exit-error", Static)
        if not name:
            error.update(t("Profile name cannot be empty."))
            return
        if not self._on_save(name):
            error.update(t("Could not save the profile. Please try again."))
            return
        self.dismiss("exit")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "profile-exit-name":
            self._save()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "profile-exit-save":
            self._save()
        elif event.button.id == "profile-exit-discard":
            self.dismiss("exit")
        elif event.button.id == "profile-exit-cancel":
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)
