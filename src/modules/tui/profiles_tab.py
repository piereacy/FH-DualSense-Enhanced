"""Profiles tab: manage named Settings snapshots."""
import logging

from rich.markup import escape
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Input, Label, ListItem, ListView, Static

from lang import t
from modules.config import preferences, profiles

log = logging.getLogger("fhds")


class ProfilesTab(Vertical):
    DEFAULT_CSS = """
    ProfilesTab { width: 1fr; height: 1fr; padding: 1 2; }
    ProfilesTab .header { width: 1fr; height: auto; }
    ProfilesTab .header Label { width: auto; padding: 0 1 0 0; text-style: bold; color: $accent; }
    ProfilesTab #profile-active {
        width: 1fr; height: 1; padding: 0 1;
        color: $text-muted; content-align: right middle;
    }
    ProfilesTab #profile-list {
        width: 1fr; height: 1fr; min-height: 5;
        border: round $accent 40%; margin: 0 0 1 0;
    }
    ProfilesTab #profile-list > ListItem { padding: 0 1; }
    ProfilesTab #profile-list > ListItem.--highlight { background: $accent 30%; }
    ProfilesTab .toolbar { width: 1fr; height: auto; margin: 0 0 1 0; }
    ProfilesTab .toolbar Button { width: 1fr; margin: 0 1 0 0; }
    ProfilesTab .toolbar Button:last-of-type { margin: 0; }
    ProfilesTab .save-row { width: 1fr; height: auto; }
    ProfilesTab .save-row Input { width: 1fr; margin: 0 1 0 0; }
    ProfilesTab .save-row Button { width: 12; }
    ProfilesTab #share-section { width: 1fr; height: auto; padding: 1 0 0 0; }
    ProfilesTab #share-section Label { width: 1fr; height: auto; }
    ProfilesTab .share-row { width: 1fr; height: auto; margin: 0 0 1 0; }
    ProfilesTab .share-row Input { width: 1fr; margin: 0 1 0 0; }
    ProfilesTab .share-row Button { width: 18; margin: 0 1 0 0; }
    ProfilesTab .share-row Button:last-of-type { margin: 0; }
    ProfilesTab #profile-path {
        width: 1fr; height: auto; padding: 1 0 0 0;
        color: $text-muted; text-style: italic;
    }
    ProfilesTab #profile-note {
        width: 1fr; height: auto; padding: 1 0 0 0; color: $warning;
    }
    App.-narrow ProfilesTab .toolbar { layout: vertical; }
    App.-narrow ProfilesTab .toolbar Button { width: 1fr; margin: 0 0 1 0; }
    App.-narrow ProfilesTab .save-row { layout: vertical; }
    App.-narrow ProfilesTab .save-row Input { width: 1fr; margin: 0 0 1 0; }
    App.-narrow ProfilesTab .save-row Button { width: 1fr; }
    """

    def __init__(self, settings):
        super().__init__()
        self.settings = settings

    def compose(self) -> ComposeResult:
        with Horizontal(classes="header"):
            yield Label(t("Profiles"))
            yield Static(self._active_text(), id="profile-active")
        yield ListView(id="profile-list")
        with Horizontal(classes="toolbar"):
            yield Button(t("Load"), id="profile-load", variant="primary")
            yield Button(t("Rename"), id="profile-rename")
            yield Button(t("Delete"), id="profile-delete", variant="error")
        with Horizontal(classes="save-row"):
            yield Input(placeholder=t("New profile name"), id="profile-name")
            yield Button(t("Save"), id="profile-save", variant="success")
        yield Static(
            t("Default autosaves and persists across restarts. Save a named profile when you want a reusable snapshot."),
            id="profile-note",
            markup=True,
        )
        with Vertical(id="share-section"):
            yield Label(t("Share profile"))
            with Horizontal(classes="share-row"):
                yield Input(placeholder="FHDS:...", id="share-code")
                yield Button(t("Export & Copy"), id="share-export")
                yield Button(t("Import"), id="share-import", variant="success")
        yield Static(
            t("File: {path}").format(path=preferences.PATH),
            id="profile-path",
            markup=False,
        )

    def on_mount(self):
        self.refresh_list()

    def _active_text(self) -> str:
        store = profiles.load_profiles()
        active = store.get("active") or t("(none)")
        return t("Active: {name}").format(name=f"[b]{escape(str(active))}[/b]")

    def refresh_list(self):
        store = profiles.load_profiles()
        lv = self.query_one("#profile-list", ListView)
        active = store.get("active", "")
        lv.clear()
        for name in profiles.list_profile_names(store):
            visible_name = escape(str(name))
            label = (
                f"{visible_name}  [dim]({t('active')})[/]"
                if name == active
                else visible_name
            )
            lv.append(ListItem(Static(label, markup=True), name=name))
        self.query_one("#profile-active", Static).update(self._active_text())
        if hasattr(self.app, "refresh_profile"):
            self.app.refresh_profile()

    def _selected_name(self) -> str:
        lv = self.query_one("#profile-list", ListView)
        item = lv.highlighted_child
        return item.name if item and item.name else ""

    def _name_input(self) -> Input:
        return self.query_one("#profile-name", Input)

    def _save_from_input(self):
        widget = self._name_input()
        name = widget.value.strip()
        if not name:
            log.warning("Profile name is empty.")
            return
        final = profiles.save_profile(name, self.settings)
        if final and hasattr(self.app, "mark_default_saved"):
            self.app.mark_default_saved()
        widget.value = ""
        self.refresh_list()
        if final and final != name:
            log.info("Saved profile: %s (renamed from %s, name taken)", final, name)
        else:
            log.info("Saved profile: %s", final)

    def on_input_submitted(self, event: Input.Submitted):
        if event.input.id == "profile-name":
            self._save_from_input()

    def on_button_pressed(self, event: Button.Pressed):
        bid = event.button.id
        if bid == "profile-save":
            self._save_from_input()
        elif bid == "profile-load":
            name = self._selected_name()
            if not name:
                log.warning("No profile selected.")
                return
            if profiles.apply_profile(name, self.settings):
                self.app.refresh_setting_widgets()
                self.refresh_list()
                log.info("Loaded profile: %s", name)
        elif bid == "profile-delete":
            name = self._selected_name()
            if not name:
                log.warning("No profile selected.")
                return
            if name == preferences.DEFAULT_PROFILE_NAME:
                log.warning("Default profile cannot be deleted.")
                return
            if profiles.delete_profile(name):
                self.refresh_list()
                log.info("Deleted profile: %s", name)
        elif bid == "profile-rename":
            old = self._selected_name()
            if not old:
                log.warning("No profile selected.")
                return
            if old == preferences.DEFAULT_PROFILE_NAME:
                log.warning("Default profile cannot be renamed.")
                return
            new = self._name_input().value.strip()
            if not new:
                log.warning("Type the new name in the name field first.")
                return
            final = profiles.rename_profile(old, new)
            if not final:
                log.warning("Rename failed.")
                return
            self._name_input().value = ""
            self.refresh_list()
            if final != new:
                log.info("Renamed profile: %s -> %s (name taken)", old, final)
            else:
                log.info("Renamed profile: %s -> %s", old, final)
        elif bid == "share-export":
            self._export_selected()
        elif bid == "share-import":
            self._import_from_field()

    # MARK: share -----------------------------------------------------------

    def _share_input(self) -> Input:
        return self.query_one("#share-code", Input)

    def _notify(self, msg: str, severity: str = "information"):
        self.app.notify(msg, title=t("Share profile"),
                        severity=severity, timeout=4)

    def _export_selected(self):
        name = self._selected_name()
        if not name:
            self._notify(t("No profile selected."), "warning")
            return
        code = profiles.export_profile(name)
        if not code:
            self._notify(t("Export failed."), "error")
            return
        self._share_input().value = code
        try:
            self.app.copy_to_clipboard(code)
            self._notify(
                t("Copied {name} to clipboard.").format(name=escape(str(name)))
            )
        except Exception:
            self._notify(t("Copy failed. Select the code and copy manually."),
                         "warning")
        log.info("Exported profile %s (%d chars)", name, len(code))

    def _import_from_field(self):
        code = self._share_input().value.strip()
        if not code:
            self._notify(t("Paste a code first."), "warning")
            return
        final = profiles.import_profile(code)
        if not final:
            self._notify(t("Invalid share code."), "error")
            return
        self._share_input().value = ""
        self.refresh_list()
        self._notify(t("Imported as {name}.").format(name=escape(str(final))))
        log.info("Imported profile as %s", final)
