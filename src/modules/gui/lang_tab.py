"""Language tab: pick UI language. Restart-to-apply."""
import logging
import tkinter as tk

import customtkinter as ctk

from lang import available, set_language, t
from modules.config import preferences

from . import theme as T
from . import widgets as W

log = logging.getLogger("fhds")


class LangTab(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.settings = app.settings
        self._codes: list[str] = []
        self._build()
        self._refresh()

    def _build(self):
        W.PageHeader(self, t("Language"),
                     t("Restart the app to apply your choice.")
                     ).pack(fill="x", pady=(0, T.PAD_MD))

        card = W.Card(self)
        card.pack(fill="both", expand=True)

        W.H2(card, t("Available languages")).pack(anchor="w",
                                                  padx=T.PAD_MD,
                                                  pady=(T.PAD_MD, T.PAD_SM))

        holder = ctk.CTkFrame(card, fg_color=T.BG_INPUT, corner_radius=6)
        holder.pack(fill="both", expand=True, padx=T.PAD_MD, pady=(0, T.PAD_SM))
        self.listbox = tk.Listbox(
            holder, bg="#1e1f22", fg="#e5e7eb",
            selectbackground=T.ACCENT, selectforeground="white",
            borderwidth=0, highlightthickness=0, activestyle="none",
            font=(self.app.ui_font_family, self.app.font_size(11)),
        )
        self.listbox.pack(fill="both", expand=True, padx=4, pady=4)
        self.listbox.bind("<<ListboxSelect>>", self._on_select)
        self.listbox.bind("<Double-Button-1>", self._on_select)

        self.lbl_note = W.Warning(card, "", wrap=self.app.px(640))
        self.lbl_note.pack(fill="x", padx=T.PAD_MD, pady=(0, T.PAD_MD))

    def _refresh(self):
        self.listbox.delete(0, "end")
        self._codes = []
        active = self.settings.language
        for i, (code, name) in enumerate(available()):
            self._codes.append(code)
            mark = f"   ({t('active')})" if code == active else ""
            self.listbox.insert("end", f"{name}{mark}")
            if code == active:
                self.listbox.selection_clear(0, "end")
                self.listbox.selection_set(i)

    def _on_select(self, _event=None):
        sel = self.listbox.curselection()
        if not sel:
            return
        code = self._codes[sel[0]]
        if code == self.settings.language:
            return
        self.settings.language = code
        preferences.save(self.settings)
        set_language(code)
        self._refresh()
        self.lbl_note.configure(text=t("Restart the app to apply the new language."))
        log.info("language = %s", code)
