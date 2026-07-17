"""Small modal dialogs used by the Console lifecycle and factory restore."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable

import customtkinter as ctk

from lang import t

from . import theme as T
from . import widgets as W


class _Modal(ctk.CTkToplevel):
    def __init__(self, parent, *, title: str, width: int, height: int):
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.transient(parent)
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.geometry(f"{width}x{height}")
        self.after_idle(self._activate)

    def _activate(self):
        try:
            self.update_idletasks()
            parent = self.master
            x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
            y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 2
            self.geometry(f"+{max(0, x)}+{max(0, y)}")
            self.grab_set()
            self.lift()
            self.focus_force()
        except tk.TclError:
            pass

    def _close(self):
        try:
            self.grab_release()
        except tk.TclError:
            pass
        try:
            self.destroy()
        except tk.TclError:
            pass

    def _cancel(self):
        self._close()


class UnsavedProfileDialog(_Modal):
    """Offer to preserve this session's Default tuning as a named profile."""

    def __init__(
        self,
        parent,
        *,
        suggested_name: str,
        on_save: Callable[[str], bool],
        on_discard: Callable[[], None],
        on_cancel: Callable[[], None],
    ):
        self._on_save = on_save
        self._on_discard = on_discard
        self._on_cancel = on_cancel
        super().__init__(parent, title=t("Save settings before exit?"), width=520, height=275)

        W.H1(self, t("Save your tuning before exit?")).pack(
            anchor="w", padx=T.PAD_LG, pady=(T.PAD_LG, T.PAD_SM)
        )
        W.Body(
            self,
            t("Default already autosaved these changes. Save a named profile to keep a reusable snapshot."),
            wraplength=460,
        ).pack(anchor="w", padx=T.PAD_LG)

        self.entry = ctk.CTkEntry(self)
        self.entry.insert(0, suggested_name)
        self.entry.pack(fill="x", padx=T.PAD_LG, pady=(T.PAD_MD, T.PAD_XS))
        self.entry.bind("<Return>", lambda _event: self._save())
        self.error = W.Warning(self, "")
        self.error.pack(fill="x", padx=T.PAD_LG)

        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.pack(side="bottom", fill="x", padx=T.PAD_LG, pady=T.PAD_LG)
        W.PrimaryButton(
            buttons, t("Save as named profile and exit"), self._save
        ).pack(side="left")
        W.SecondaryButton(
            buttons, t("Exit directly"), self._discard
        ).pack(side="left", padx=T.PAD_SM)
        W.GhostButton(buttons, t("Cancel"), self._cancel).pack(side="right")
        self.after_idle(lambda: (self.entry.focus_set(), self.entry.select_range(0, "end")))

    def _save(self):
        name = self.entry.get().strip()
        if not name:
            self.error.configure(text=t("Profile name cannot be empty."))
            return
        if self._on_save(name):
            self._close()
        else:
            self.error.configure(text=t("Could not save the profile. Please try again."))

    def _discard(self):
        self._on_discard()
        self._close()

    def _cancel(self):
        self._on_cancel()
        self._close()


class FactoryResetDialog(_Modal):
    def __init__(self, parent, *, on_confirm: Callable[[], bool], on_cancel: Callable[[], None]):
        self._on_confirm = on_confirm
        self._on_cancel = on_cancel
        super().__init__(parent, title=t("Restore factory defaults"), width=500, height=235)

        W.H1(self, t("Restore all factory defaults?")).pack(
            anchor="w", padx=T.PAD_LG, pady=(T.PAD_LG, T.PAD_SM)
        )
        W.Body(
            self,
            t("This resets haptics, system settings, language, and Default. Named profiles are kept."),
            wraplength=440,
        ).pack(anchor="w", padx=T.PAD_LG)
        self.error = W.Warning(self, "")
        self.error.pack(fill="x", padx=T.PAD_LG, pady=(T.PAD_SM, 0))

        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.pack(side="bottom", fill="x", padx=T.PAD_LG, pady=T.PAD_LG)
        W.DangerButton(buttons, t("Restore defaults"), self._confirm).pack(side="left")
        W.GhostButton(buttons, t("Cancel"), self._cancel).pack(side="right")

    def _confirm(self):
        if self._on_confirm():
            self._close()
        else:
            self.error.configure(text=t("Could not restore defaults. Check the log and try again."))

    def _cancel(self):
        self._on_cancel()
        self._close()
