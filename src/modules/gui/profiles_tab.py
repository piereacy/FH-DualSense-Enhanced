"""Profiles tab: list, load, save, rename, delete named Settings snapshots."""
import logging
import tkinter as tk

import customtkinter as ctk

from lang import t
from modules.config import preferences, profiles

from . import theme as T
from . import widgets as W

log = logging.getLogger("fhds")


class ProfilesTab(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.settings = app.settings
        self._names: list[str] = []
        self._share_entry: ctk.CTkEntry | None = None
        self._build()
        self._refresh_list()
        app.register_refresh(self._refresh_list)

    def _build(self):
        W.PageHeader(self, t("Profiles"),
                     t("Save and switch named snapshots of your settings.")
                     ).pack(fill="x", pady=(0, T.PAD_MD))

        self._scroll = W.FastScroll(self)
        self._scroll.pack(fill="both", expand=True)

        grid = ctk.CTkFrame(self._scroll, fg_color="transparent", height=330)
        grid.pack(fill="x")
        grid.grid_columnconfigure(0, weight=3, uniform="cols")
        grid.grid_columnconfigure(1, weight=2, uniform="cols")
        grid.grid_rowconfigure(0, weight=1)

        # --- Left card: list + load/rename/delete --------------------------
        left = W.Card(grid)
        left.grid(row=0, column=0, padx=(0, T.PAD_MD // 2), sticky="nsew")

        head = ctk.CTkFrame(left, fg_color="transparent")
        head.pack(fill="x", padx=T.PAD_MD, pady=(T.PAD_MD, T.PAD_SM))
        W.H2(head, t("Saved profiles")).pack(side="left")
        self.lbl_active = ctk.CTkLabel(head, text="",
                                       text_color=T.TEXT_MUTED,
                                       font=ctk.CTkFont(size=T.FS_SMALL))
        self.lbl_active.pack(side="right")

        list_holder = ctk.CTkFrame(left, fg_color=T.BG_INPUT, corner_radius=6)
        list_holder.pack(fill="both", expand=True, padx=T.PAD_MD, pady=(0, T.PAD_SM))
        self.listbox = tk.Listbox(
            list_holder, bg="#1e1f22", fg="#e5e7eb",
            selectbackground=T.ACCENT, selectforeground="white",
            borderwidth=0, highlightthickness=0, activestyle="none",
            font=("Segoe UI", self.app.font_size(11)),
        )
        self.listbox.pack(fill="both", expand=True, padx=4, pady=4)

        actions = ctk.CTkFrame(left, fg_color="transparent")
        actions.pack(fill="x", padx=T.PAD_MD, pady=(0, T.PAD_MD))
        W.PrimaryButton(actions, t("Load"), self._on_load
                        ).pack(side="left", expand=True, fill="x", padx=(0, T.PAD_XS))
        W.SecondaryButton(actions, t("Rename"), self._on_rename
                          ).pack(side="left", expand=True, fill="x", padx=T.PAD_XS)
        W.DangerButton(actions, t("Delete"), self._on_delete
                       ).pack(side="left", expand=True, fill="x", padx=(T.PAD_XS, 0))

        # --- Right card: save new + warning --------------------------------
        right = W.Card(grid)
        right.grid(row=0, column=1, padx=(T.PAD_MD // 2, 0), sticky="nsew")

        W.H2(right, t("Save current settings")).pack(
            anchor="w", padx=T.PAD_MD, pady=(T.PAD_MD, T.PAD_SM))

        self.entry_name = ctk.CTkEntry(right, placeholder_text=t("New profile name"))
        self.entry_name.pack(fill="x", padx=T.PAD_MD, pady=(0, T.PAD_SM))
        self.entry_name.bind("<Return>", lambda _e: self._on_save())

        W.PrimaryButton(right, t("Save profile"), self._on_save
                        ).pack(fill="x", padx=T.PAD_MD, pady=(0, T.PAD_MD))

        W.DangerButton(
            right, t("Restore factory defaults"), self.app.request_factory_reset
        ).pack(fill="x", padx=T.PAD_MD, pady=(0, T.PAD_MD))

        W.Warning(
            right,
            t("Default autosaves and persists across restarts. Save a named profile when you want a reusable snapshot."),
            wrap=self.app.px(320),
        ).pack(fill="x", padx=T.PAD_MD, pady=(0, T.PAD_SM))

        W.Hint(right, t("File: {path}").format(path=preferences.PATH),
               wrap=self.app.px(320)
               ).pack(fill="x", padx=T.PAD_MD, pady=(0, T.PAD_MD))

        # --- Share card (spans full width) ---------------------------------
        share = W.Card(self._scroll)
        share.pack(fill="x", pady=(T.PAD_MD, 0))
        W.H2(share, t("Share profile")).pack(
            anchor="w", padx=T.PAD_MD, pady=(T.PAD_MD, T.PAD_XS))
        W.Hint(share,
               t("Export the selected profile as a short code (copied to your "
                 "clipboard), or paste a code below and import it."),
               wrap=self.app.px(640),
               ).pack(anchor="w", padx=T.PAD_MD, pady=(0, T.PAD_SM))

        self._share_entry = ctk.CTkEntry(share, placeholder_text="FHDS:...")
        self._share_entry.pack(fill="x", padx=T.PAD_MD, pady=(0, T.PAD_SM))

        row = ctk.CTkFrame(share, fg_color="transparent")
        row.pack(fill="x", padx=T.PAD_MD, pady=(0, T.PAD_MD))
        W.PrimaryButton(row, t("Export & Copy"), self._on_export
                        ).pack(side="left", padx=(0, T.PAD_XS))
        W.PrimaryButton(row, t("Import"), self._on_import
                        ).pack(side="left", padx=T.PAD_XS)

    # MARK: list helpers ----------------------------------------------------

    def _refresh_list(self):
        store = profiles.load_profiles()
        active = store.get("active", "")
        self.lbl_active.configure(
            text=t("Active: {name}").format(name=active or t("(none)"))
        )
        self.listbox.delete(0, "end")
        names = profiles.list_profile_names(store)
        for name in names:
            label = f"{name}   ({t('active')})" if name == active else name
            self.listbox.insert("end", label)
        if active in names:
            idx = names.index(active)
            self.listbox.selection_clear(0, "end")
            self.listbox.selection_set(idx)
            self.listbox.activate(idx)
        self._names = names
        if hasattr(self.app, "refresh_profile"):
            self.app.refresh_profile()

    def _selected_name(self) -> str:
        sel = self.listbox.curselection()
        if not sel:
            return ""
        idx = sel[0]
        return self._names[idx] if idx < len(self._names) else ""

    def _name_input(self) -> str:
        return self.entry_name.get().strip()

    # MARK: actions ---------------------------------------------------------

    def _on_save(self):
        name = self._name_input()
        if not name:
            log.warning("Profile name is empty.")
            return
        final = profiles.save_profile(name, self.settings)
        if final:
            self.app.mark_default_saved()
        self.entry_name.delete(0, "end")
        self._refresh_list()
        if final and final != name:
            log.info("Saved profile: %s (renamed from %s, name taken)", final, name)
        else:
            log.info("Saved profile: %s", final)

    def _on_load(self):
        name = self._selected_name()
        if not name:
            log.warning("No profile selected.")
            return
        if profiles.apply_profile(name, self.settings):
            self.app.refresh_setting_widgets()
            self._refresh_list()
            log.info("Loaded profile: %s", name)

    def _on_delete(self):
        name = self._selected_name()
        if not name:
            log.warning("No profile selected.")
            return
        if name == preferences.DEFAULT_PROFILE_NAME:
            log.warning("Default profile cannot be deleted.")
            return
        if profiles.delete_profile(name):
            self._refresh_list()
            log.info("Deleted profile: %s", name)

    def _on_rename(self):
        old = self._selected_name()
        if not old:
            log.warning("No profile selected.")
            return
        if old == preferences.DEFAULT_PROFILE_NAME:
            log.warning("Default profile cannot be renamed.")
            return
        new = self._name_input()
        if not new:
            log.warning("Type the new name in the name field first.")
            return
        final = profiles.rename_profile(old, new)
        if not final:
            log.warning("Rename failed.")
            return
        self.entry_name.delete(0, "end")
        self._refresh_list()
        if final != new:
            log.info("Renamed profile: %s -> %s (name taken)", old, final)
        else:
            log.info("Renamed profile: %s -> %s", old, final)

    # MARK: share -----------------------------------------------------------

    def _on_export(self):
        name = self._selected_name()
        if not name:
            self.app.toast(t("No profile selected."))
            return
        code = profiles.export_profile(name)
        if not code:
            self.app.toast(t("Export failed."))
            return
        if self._share_entry is not None:
            self._share_entry.delete(0, "end")
            self._share_entry.insert(0, code)
        try:
            self.app.root.clipboard_clear()
            self.app.root.clipboard_append(code)
            self.app.root.update()
            self.app.toast(t("Copied {name} to clipboard.").format(name=name))
        except tk.TclError:
            self.app.toast(t("Copy failed. Select the code and copy manually."))
        log.info("Exported profile %s (%d chars)", name, len(code))

    def _on_import(self):
        if self._share_entry is None:
            return
        code = self._share_entry.get().strip()
        if not code:
            self.app.toast(t("Paste a code first."))
            return
        final = profiles.import_profile(code)
        if not final:
            self.app.toast(t("Invalid share code."))
            return
        self._share_entry.delete(0, "end")
        self._refresh_list()
        self.app.toast(t("Imported as {name}.").format(name=final))
        log.info("Imported profile as %s", final)
