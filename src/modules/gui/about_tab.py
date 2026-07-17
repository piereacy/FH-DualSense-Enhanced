"""Project attribution and license-required links."""
from __future__ import annotations

import customtkinter as ctk

from lang import t
from modules.about import APP_NAME, ATTRIBUTION, SOURCE_URL, SPONSOR_URL
from modules.config.preferences import _release_version

from . import theme as T
from . import widgets as W


class AboutTab(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self._build()

    def _build(self) -> None:
        W.PageHeader(self, t("About and licenses"), APP_NAME).pack(
            fill="x", pady=(0, T.PAD_MD)
        )

        scroll = W.FastScroll(self)
        scroll.pack(fill="both", expand=True)

        card = W.Card(scroll)
        card.pack(fill="x")
        W.H2(card, f"{APP_NAME} {_release_version() or '?'}").pack(
            anchor="w", padx=T.PAD_MD, pady=(T.PAD_MD, T.PAD_SM)
        )
        W.Body(card, ATTRIBUTION, wraplength=self.app.px(620)).pack(
            anchor="w", fill="x", padx=T.PAD_MD, pady=(0, T.PAD_MD)
        )
        W.GhostButton(
            card,
            text=f"Source: {SOURCE_URL}",
            command=lambda: self.app._open_url(SOURCE_URL),
            anchor="w",
        ).pack(fill="x", padx=T.PAD_MD, pady=(0, T.PAD_XS))
        W.GhostButton(
            card,
            text=f"Sponsor: {SPONSOR_URL}",
            command=lambda: self.app._open_url(SPONSOR_URL),
            anchor="w",
        ).pack(fill="x", padx=T.PAD_MD, pady=(0, T.PAD_MD))
