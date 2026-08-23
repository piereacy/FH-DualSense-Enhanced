"""Textual Haptics Lab panel embedded in the System collapsible."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.css.query import NoMatches
from textual.widgets import Button, Label

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

from .widgets import RangeSlider


class HapticsLabPanel(Vertical):
    DEFAULT_CSS = """
    HapticsLabPanel { width: 1fr; height: auto; padding: 0 1 1 1; }
    HapticsLabPanel Label.section {
        text-style: bold;
        color: $accent;
        padding: 1 0 0 1;
        border-bottom: hkey $accent 30%;
    }
    HapticsLabPanel Label.hint {
        width: 1fr;
        height: auto;
        color: $text-muted;
        padding: 0 1 1 1;
    }
    HapticsLabPanel .lab-row { width: 1fr; height: 3; padding: 0 1; }
    HapticsLabPanel .lab-row Label { width: 24; content-align: left middle; }
    HapticsLabPanel .lab-row RangeSlider { width: 1fr; }
    HapticsLabPanel .lab-scene { width: 1fr; height: auto; min-height: 3; margin: 0 1; }
    HapticsLabPanel #lab-stop { width: 1fr; margin: 1; background: $error 65%; }
    HapticsLabPanel #lab-status { padding: 1; color: $accent; text-style: bold; }
    """

    def __init__(self):
        super().__init__()
        self._intensity = LAB_DEFAULT_INTENSITY
        self._duration_s = LAB_DEFAULT_DURATION_S
        self._status_timer = None

    def compose(self) -> ComposeResult:
        yield Label(t("Preview safety limits"), classes="section")
        yield Label(
            t(
                "The lab never starts virtual Xbox input, Raw Input, or HidHide. "
                "Live game telemetry takes priority, and every preview stops automatically."
            ),
            classes="hint",
            markup=False,
        )
        with Horizontal(classes="lab-row"):
            yield Label(t("Preview intensity"), id="lab-intensity-label")
            yield RangeSlider(
                self._intensity,
                LAB_MIN_INTENSITY,
                LAB_MAX_INTENSITY,
                step=0.01,
                id="lab-intensity",
            )
        with Horizontal(classes="lab-row"):
            yield Label(t("Preview duration"), id="lab-duration-label")
            yield RangeSlider(
                self._duration_s,
                LAB_MIN_DURATION_S,
                LAB_MAX_DURATION_S,
                step=0.25,
                id="lab-duration",
            )
        yield Label(t("Ready for a preview"), id="lab-status", markup=False)
        yield Button(t("Stop all previews"), id="lab-stop")

        for scene in HAPTICS_LAB_SCENES:
            yield Label(t(scene.label), classes="section", markup=False)
            yield Label(t(scene.description), classes="hint", markup=False)
            yield Button(
                t("Play preview"),
                id=f"lab-scene-{scene.key}",
                classes="lab-scene",
            )

    def on_mount(self) -> None:
        self._refresh_state()
        self._status_timer = self.set_interval(0.1, self._refresh_state)

    def on_unmount(self) -> None:
        if self._status_timer is not None:
            self._status_timer.stop()
            self._status_timer = None
        self.stop("shutdown", refresh=False)

    def on_range_slider_changed(self, event: RangeSlider.Changed) -> None:
        if event.slider.id == "lab-intensity":
            self._intensity = event.value
        elif event.slider.id == "lab-duration":
            self._duration_s = event.value
        self._refresh_control_labels()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if button_id == "lab-stop":
            self.stop("user")
            event.stop()
            return
        prefix = "lab-scene-"
        if not button_id.startswith(prefix):
            return
        scene_key = button_id[len(prefix):]
        scene = HAPTICS_LAB_SCENE_BY_KEY.get(scene_key)
        if scene is None or not self._scene_available(scene):
            self._refresh_state()
            event.stop()
            return
        if not self.app._xinput_service.request_preview_runtime(True):
            self._refresh_state()
            event.stop()
            return
        self.app._haptics_lab.start(
            scene_key,
            intensity=self._intensity,
            duration_s=self._duration_s,
        )
        self.app._sync_usb_audio_eligibility()
        self._refresh_state()
        event.stop()

    def _scene_available(self, scene) -> bool:
        app = self.app
        controller = getattr(app, "_ds", None)
        thread = getattr(app, "_thread", None)
        loop_ready = thread is not None and thread.is_alive()
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

    def _refresh_control_labels(self) -> None:
        try:
            self.query_one("#lab-intensity-label", Label).update(
                f"{t('Preview intensity')}: {round(self._intensity * 100)}%"
            )
            self.query_one("#lab-duration-label", Label).update(
                f"{t('Preview duration')}: {self._duration_s:.1f} s"
            )
        except Exception:
            pass

    def _refresh_state(self) -> None:
        if not self.is_mounted:
            return
        self._refresh_control_labels()
        app = self.app
        snapshot = app._haptics_lab.snapshot()
        if not snapshot.active and app._xinput_service.preview_requested:
            app._xinput_service.request_preview_runtime(False)
        controller = getattr(app, "_ds", None)
        thread = getattr(app, "_thread", None)
        loop_ready = thread is not None and thread.is_alive()
        connected = bool(controller and getattr(controller, "connected", False))
        if not loop_ready:
            status = t("Feedback backend is not ready")
        elif not connected and not app._xinput_service.preview_requested:
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
        self.query_one("#lab-status", Label).update(status)
        for scene in HAPTICS_LAB_SCENES:
            self.query_one(f"#lab-scene-{scene.key}", Button).disabled = not self._scene_available(scene)

    def on_hide(self) -> None:
        self.stop("page_hidden")

    def stop(self, reason: str, *, refresh: bool = True) -> None:
        app = self.app
        snapshot = app._haptics_lab.snapshot()
        requested = bool(app._xinput_service.preview_requested)
        if snapshot.active:
            app._haptics_lab.stop(reason)
        if requested:
            app._xinput_service.request_preview_runtime(False)
        if snapshot.active or requested:
            app._sync_usb_audio_eligibility()
        if refresh and self.is_mounted:
            try:
                self._refresh_state()
            except NoMatches:
                # Textual may dispatch Unmount after child controls are pruned.
                pass
