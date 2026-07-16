"""At-a-glance status and shortcuts shared by all R4 GUI shells."""
from __future__ import annotations

import customtkinter as ctk

from lang import t
from modules.config import profiles
from modules.update.presentation import localized_status

from . import theme as T
from . import widgets as W


class OverviewTab(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.settings = app.settings
        self._build()
        app.register_refresh(self.refresh)

    def _build(self):
        W.PageHeader(
            self, t("Overview"),
            t("Controller, telemetry, profile, and update status at a glance."),
        ).pack(fill="x", pady=(0, T.PAD_MD))

        scroll = W.FastScroll(self)
        scroll.pack(fill="both", expand=True)

        status = ctk.CTkFrame(scroll, fg_color="transparent")
        status.pack(fill="x")
        for col in range(2):
            status.grid_columnconfigure(col, weight=1, uniform="overview")

        _, self.controller_value, self.controller_hint = self._status_card(
            status, 0, t("DualSense"), t("Waiting"), t("USB or Bluetooth")
        )
        _, self.telemetry_value, self.telemetry_hint = self._status_card(
            status, 1, t("Forza telemetry"), t("Waiting for packets"), t("UDP data out")
        )
        _, self.profile_value, _ = self._status_card(
            status, 2, t("Active profile"), "-", t("Changes save instantly")
        )
        _, self.update_value, self.update_hint = self._status_card(
            status, 3, t("Updates"), t("Update status: idle"), t("Built-in updater")
        )

        quick = W.Card(scroll)
        quick.pack(fill="x", pady=(T.PAD_MD, 0))
        W.H2(quick, t("Quick access")).pack(
            anchor="w", padx=T.PAD_MD, pady=(T.PAD_MD, T.PAD_SM)
        )
        row = ctk.CTkFrame(quick, fg_color="transparent")
        row.pack(fill="x", padx=T.PAD_MD, pady=(0, T.PAD_MD))
        row.grid_columnconfigure((0, 1), weight=1, uniform="quick")
        W.PrimaryButton(
            row, text=t("Driving feedback"), command=lambda: self.app._select_nav("Driving")
        ).grid(row=0, column=0, sticky="ew", padx=(0, T.PAD_XS), pady=(0, T.PAD_XS))
        W.SecondaryButton(
            row, text=t("Grip haptics"), command=lambda: self.app._select_nav("Haptics")
        ).grid(row=0, column=1, sticky="ew", padx=(T.PAD_XS, 0), pady=(0, T.PAD_XS))
        W.SecondaryButton(
            row, text=t("System and updates"), command=lambda: self.app._select_nav("System")
        ).grid(row=1, column=0, sticky="ew", padx=(0, T.PAD_XS), pady=(T.PAD_XS, 0))
        W.DangerButton(
            row, text=t("Restore defaults"), command=self.app.request_factory_reset
        ).grid(row=1, column=1, sticky="ew", padx=(T.PAD_XS, 0), pady=(T.PAD_XS, 0))

        note = W.Card(scroll)
        note.pack(fill="x", pady=(T.PAD_MD, 0))
        W.H2(note, t("R4 workspace")).pack(
            anchor="w", padx=T.PAD_MD, pady=(T.PAD_MD, T.PAD_SM)
        )
        W.Hint(
            note,
            t("Miku Console uses the shared settings, haptic engine, and controller backend."),
            wrap=self.app.px(760),
        ).pack(fill="x", padx=T.PAD_MD, pady=(0, T.PAD_MD))

    @staticmethod
    def _status_card(parent, index, title, value, hint):
        row, column = divmod(index, 2)
        card = W.Card(parent)
        card.grid(row=row, column=column, sticky="nsew",
                  padx=(0 if column == 0 else T.PAD_SM // 2,
                        T.PAD_SM // 2 if column == 0 else 0),
                  pady=(0 if row == 0 else T.PAD_SM // 2,
                        T.PAD_SM // 2 if row == 0 else 0))
        W.Hint(card, title).pack(anchor="w", padx=T.PAD_MD, pady=(T.PAD_MD, T.PAD_XS))
        value_label = ctk.CTkLabel(
            card, text=value, anchor="w", text_color=T.TEXT,
            font=ctk.CTkFont(size=T.FS_H1, weight="bold"),
        )
        value_label.pack(fill="x", padx=T.PAD_MD)
        hint_label = W.Hint(card, hint)
        hint_label.pack(anchor="w", padx=T.PAD_MD, pady=(T.PAD_XS, T.PAD_MD))
        return card, value_label, hint_label

    def refresh(self):
        ds = getattr(self.app, "_ds", None)
        if ds is not None and ds.connected:
            self.controller_value.configure(text=t("Connected"))
            self.controller_hint.configure(
                text=t("Transport: {transport}").format(
                    transport=(ds.transport or "?").upper()
                )
            )
        else:
            self.controller_value.configure(text=t("Waiting"))
            self.controller_hint.configure(text=t("USB or Bluetooth"))

        listener = getattr(self.app, "_listener", None)
        if listener is not None and not getattr(listener, "lost", False):
            self.telemetry_value.configure(text=t("Listening"))
        else:
            self.telemetry_value.configure(text=t("Waiting for packets"))
        self.telemetry_hint.configure(
            text=t("UDP port {port}").format(port=self.settings.udp_port)
        )
        self.profile_value.configure(text=profiles.active_name())
        snapshot = self.app._update_service.snapshot()
        self.update_value.configure(text=localized_status(snapshot, t))
        self.update_hint.configure(
            text=t("Windows EXE") if self.app._update_service.supported
            else t("Unavailable in this runtime")
        )
