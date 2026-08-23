"""Default-collapsed Haptics Lab card backed by the shared output loop."""

from __future__ import annotations

import customtkinter as ctk

from lang import t
from modules.haptics.lab import (
    HAPTICS_LAB_SCENE_BY_KEY,
    HAPTICS_LAB_SCENES,
    LAB_DEFAULT_DURATION_S,
    LAB_DEFAULT_INTENSITY,
    LAB_MAX_DURATION_S,
    LAB_MAX_INTENSITY,
    LAB_MIN_DURATION_S,
    LAB_MIN_INTENSITY,
    scene_supported_by_backend,
)

from . import theme as T
from . import widgets as W


class HapticsLabCard(W.Card):
    """Compact System-page card; expanded controls never become a nav page."""

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self._intensity = LAB_DEFAULT_INTENSITY
        self._duration_s = LAB_DEFAULT_DURATION_S
        self._intensity_value: ctk.CTkLabel | None = None
        self._duration_value: ctk.CTkLabel | None = None
        self._status: ctk.CTkLabel | None = None
        self._scene_buttons: dict[str, ctk.CTkButton] = {}
        self._expanded = False
        self._page_visible = False
        self._toggle_button: ctk.CTkButton | None = None
        self._body: ctk.CTkFrame | None = None
        self._poll_after = None
        self._build()

    def _build(self):
        self._toggle_button = W.GhostButton(
            self,
            text=f"▶ {t('Haptics Lab')}",
            command=self._toggle,
            anchor="w",
        )
        self._toggle_button.pack(fill="x", padx=T.PAD_SM, pady=(T.PAD_SM, 0))
        W.Hint(
            self,
            t(
                "Preview one bounded feedback layer at a time without game input forwarding."
            ),
            wrap=self.app.px(640),
        ).pack(fill="x", padx=T.PAD_MD, pady=(0, T.PAD_SM))

        self._body = ctk.CTkFrame(self, fg_color="transparent")
        W.H2(self._body, t("Preview safety limits")).pack(
            anchor="w",
            padx=T.PAD_MD,
            pady=(T.PAD_XS, T.PAD_SM),
        )
        W.Hint(
            self._body,
            t(
                "The lab never starts virtual Xbox input, Raw Input, or HidHide. "
                "Live game telemetry takes priority, and every preview stops automatically."
            ),
            wrap=self.app.px(680),
        ).pack(fill="x", padx=T.PAD_MD, pady=(0, T.PAD_SM))

        intensity_row = W.FieldRow(self._body, t("Preview intensity"))
        intensity_row.pack(fill="x", padx=T.PAD_MD, pady=T.PAD_XS)
        self._intensity_value = W.Body(intensity_row.controls, "")
        self._intensity_value.pack(side="right", padx=(T.PAD_SM, 0))
        intensity_slider = ctk.CTkSlider(
            intensity_row.controls,
            from_=LAB_MIN_INTENSITY,
            to=LAB_MAX_INTENSITY,
            number_of_steps=55,
            command=self._set_intensity,
        )
        intensity_slider.pack(side="left", fill="x", expand=True)
        intensity_slider.set(self._intensity)

        duration_row = W.FieldRow(self._body, t("Preview duration"))
        duration_row.pack(fill="x", padx=T.PAD_MD, pady=T.PAD_XS)
        self._duration_value = W.Body(duration_row.controls, "")
        self._duration_value.pack(side="right", padx=(T.PAD_SM, 0))
        duration_slider = ctk.CTkSlider(
            duration_row.controls,
            from_=LAB_MIN_DURATION_S,
            to=LAB_MAX_DURATION_S,
            number_of_steps=11,
            command=self._set_duration,
        )
        duration_slider.pack(side="left", fill="x", expand=True)
        duration_slider.set(self._duration_s)

        footer = ctk.CTkFrame(self._body, fg_color="transparent")
        footer.pack(fill="x", padx=T.PAD_MD, pady=(T.PAD_SM, T.PAD_MD))
        self._status = W.Body(footer, t("Ready for a preview"))
        self._status.pack(side="left", fill="x", expand=True)
        W.DangerButton(
            footer,
            t("Stop all previews"),
            self._stop,
            width=170,
        ).pack(side="right")

        for scene in HAPTICS_LAB_SCENES:
            card = ctk.CTkFrame(
                self._body,
                fg_color=T.BG_INPUT,
                corner_radius=6,
            )
            card.pack(fill="x", padx=T.PAD_SM, pady=(0, T.PAD_SM))
            button = W.SecondaryButton(
                card,
                t("Play preview"),
                lambda key=scene.key: self._play(key),
                width=150,
            )
            button.pack(side="right", padx=T.PAD_MD, pady=T.PAD_MD)
            text = ctk.CTkFrame(card, fg_color="transparent")
            text.pack(side="left", fill="x", expand=True, padx=T.PAD_MD, pady=T.PAD_MD)
            W.H2(text, t(scene.label)).pack(anchor="w")
            W.Hint(text, t(scene.description), wrap=self.app.px(560)).pack(
                fill="x",
                pady=(T.PAD_XS, 0),
            )
            self._scene_buttons[scene.key] = button

        self._set_intensity(self._intensity)
        self._set_duration(self._duration_s)
        self._refresh_lab_state()

    @property
    def expanded(self) -> bool:
        return self._expanded

    def _toggle(self):
        self._set_expanded(not self._expanded)

    def _set_expanded(self, expanded: bool):
        expanded = bool(expanded)
        if self._body is None or self._toggle_button is None:
            return
        if expanded == self._expanded:
            return
        self._expanded = expanded
        marker = "▼" if expanded else "▶"
        self._toggle_button.configure(text=f"{marker} {t('Haptics Lab')}")
        if expanded:
            self._body.pack(fill="x", padx=T.PAD_SM, pady=(0, T.PAD_SM))
            self._refresh_lab_state()
            self._schedule_poll()
        else:
            self._body.pack_forget()
            self._cancel_poll()
            self._stop("card_collapsed")

    def _set_intensity(self, value):
        self._intensity = max(LAB_MIN_INTENSITY, min(LAB_MAX_INTENSITY, float(value)))
        if self._intensity_value is not None:
            self._intensity_value.configure(text=f"{round(self._intensity * 100)}%")

    def _set_duration(self, value):
        self._duration_s = max(LAB_MIN_DURATION_S, min(LAB_MAX_DURATION_S, float(value)))
        if self._duration_value is not None:
            self._duration_value.configure(text=f"{self._duration_s:.1f} s")

    def _play(self, scene_key: str):
        scene = HAPTICS_LAB_SCENE_BY_KEY[scene_key]
        if not self._scene_available(scene):
            self._refresh_lab_state()
            return
        if not self.app._xinput_service.request_preview_runtime(True):
            self._refresh_lab_state()
            return
        self.app._haptics_lab.start(
            scene_key,
            intensity=self._intensity,
            duration_s=self._duration_s,
        )
        self.app._sync_usb_audio_eligibility()
        self._refresh_lab_state()

    def _stop(self, reason: str = "user"):
        snapshot = self.app._haptics_lab.snapshot()
        requested = bool(self.app._xinput_service.preview_requested)
        if snapshot.active:
            self.app._haptics_lab.stop(reason)
        if requested:
            self.app._xinput_service.request_preview_runtime(False)
        if snapshot.active or requested:
            self.app._sync_usb_audio_eligibility()
        self._refresh_lab_state()

    def _scene_available(self, scene) -> bool:
        controller = self.app._ds
        loop_ready = self.app._thread is not None and self.app._thread.is_alive()
        available = bool(
            controller
            and (
                bool(getattr(controller, "connected", False))
                or bool(getattr(controller, "is_dsx", False))
            )
        )
        if (
            not loop_ready
            or controller is None
            or not available
        ):
            return False
        if not scene_supported_by_backend(
            scene,
            is_dsx=bool(getattr(controller, "is_dsx", False)),
        ):
            return False
        return True

    def _refresh_lab_state(self):
        snapshot = self.app._haptics_lab.snapshot()
        controller = self.app._ds
        connected = bool(controller and getattr(controller, "connected", False))
        preview_requested = self.app._xinput_service.preview_requested
        loop_ready = self.app._thread is not None and self.app._thread.is_alive()
        if not loop_ready:
            status = t("Feedback backend is not ready")
        elif not connected and not preview_requested:
            status = t("Connect a DualSense to use the lab")
        elif snapshot.active:
            label = HAPTICS_LAB_SCENE_BY_KEY[snapshot.scene].label
            status = t("Playing {scene} - {seconds:.1f} s remaining").format(
                scene=t(label),
                seconds=snapshot.remaining_s,
            )
        elif snapshot.stop_reason == "completed":
            status = t("Preview complete")
        elif bool(getattr(controller, "is_dsx", False)):
            status = t("DSX mode supports adaptive-trigger previews only")
        else:
            status = t("Ready for a preview")
        if self._status is not None and self._status.cget("text") != status:
            self._status.configure(text=status)
        for key, button in self._scene_buttons.items():
            state = "normal" if self._scene_available(HAPTICS_LAB_SCENE_BY_KEY[key]) else "disabled"
            button.configure(state=state)

    def _poll(self):
        self._poll_after = None
        if self.app._tearing_down or not self._page_visible or not self._expanded:
            return
        if (
            not self.app._haptics_lab.snapshot().active
            and self.app._xinput_service.preview_requested
        ):
            self.app._xinput_service.request_preview_runtime(False)
        self._refresh_lab_state()
        self._poll_after = self.after(100, self._poll)

    def _schedule_poll(self):
        if self._poll_after is None and self._page_visible and self._expanded:
            self._poll_after = self.after(100, self._poll)

    def _cancel_poll(self):
        if self._poll_after is None:
            return
        try:
            self.after_cancel(self._poll_after)
        except Exception:
            pass
        self._poll_after = None

    def on_show(self):
        self._page_visible = True
        self._refresh_lab_state()
        self._schedule_poll()

    def on_hide(self):
        self._page_visible = False
        self._cancel_poll()
        self._stop("page_hidden")
