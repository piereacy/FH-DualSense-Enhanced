import asyncio
import runpy
from pathlib import Path

import pytest

from modules.dualsense.adaptive_trigger import M_OFF
from modules.haptics.lab import (
    HAPTICS_LAB_SCENES,
    LAB_MAX_DURATION_S,
    LAB_MAX_INTENSITY,
    HapticsLab,
    render_haptics_lab_scene,
    scene_supported_by_backend,
)


ROOT = Path(__file__).resolve().parents[2]


def test_every_lab_scene_renders_with_bounded_haptic_channels():
    for scene in HAPTICS_LAB_SCENES:
        output = render_haptics_lab_scene(
            scene.key,
            elapsed_s=0.2,
            duration_s=1.0,
            intensity=999.0,
        )
        for value in (
            output.frame.left_low,
            output.frame.left_high,
            output.frame.right_low,
            output.frame.right_high,
            output.frame.engine_amplitude,
        ):
            assert 0.0 <= value <= LAB_MAX_INTENSITY


def test_directional_collision_preview_does_not_leak_to_other_grip():
    left = render_haptics_lab_scene(
        "collision_left",
        elapsed_s=0.0,
        duration_s=1.0,
        intensity=0.5,
    )
    right = render_haptics_lab_scene(
        "collision_right",
        elapsed_s=0.0,
        duration_s=1.0,
        intensity=0.5,
    )

    assert left.frame.left_low > 0.0
    assert left.frame.right_low == 0.0
    assert right.frame.right_low > 0.0
    assert right.frame.left_low == 0.0


@pytest.mark.parametrize(
    ("scene", "left_active", "right_active"),
    [
        ("abs", True, False),
        ("traction", False, True),
        ("brake_resistance", True, False),
        ("throttle_resistance", False, True),
    ],
)
def test_trigger_preview_ownership_is_explicit(scene, left_active, right_active):
    output = render_haptics_lab_scene(
        scene,
        elapsed_s=0.1,
        duration_s=1.0,
        intensity=0.4,
    )

    assert (output.left_trigger[0] != M_OFF) is left_active
    assert (output.right_trigger[0] != M_OFF) is right_active


def test_lab_clamps_request_and_expires_without_hardware_side_effects():
    now = [10.0]
    lab = HapticsLab(clock=lambda: now[0])

    started = lab.start("engine", intensity=9.0, duration_s=99.0)
    assert started.active is True
    assert started.intensity == LAB_MAX_INTENSITY
    assert started.duration_s == LAB_MAX_DURATION_S
    assert lab.sample() is not None

    now[0] += LAB_MAX_DURATION_S
    completed = lab.snapshot()
    assert completed.active is False
    assert completed.stop_reason == "completed"
    assert lab.sample() is None


def test_live_telemetry_preemption_clears_an_active_preview():
    lab = HapticsLab(clock=lambda: 20.0)
    lab.start("road")

    snapshot = lab.preempt_for_telemetry()

    assert snapshot.active is False
    assert snapshot.stop_reason == "game_telemetry"
    assert lab.sample() is None


def test_unknown_scene_is_rejected_before_state_changes():
    lab = HapticsLab(clock=lambda: 1.0)

    with pytest.raises(ValueError, match="Unknown Haptics Lab scene"):
        lab.start("not-a-scene")

    assert lab.snapshot().active is False


def test_dsx_allows_every_scene_with_an_adaptive_trigger_output():
    for scene in HAPTICS_LAB_SCENES:
        assert scene_supported_by_backend(scene, is_dsx=True) is scene.adaptive_triggers
        assert scene_supported_by_backend(scene, is_dsx=False) is True


def test_all_non_english_catalogs_cover_data_driven_lab_scenes():
    required = {
        "Haptics Lab",
        "Preview one bounded feedback layer at a time without game input forwarding.",
    }
    for scene in HAPTICS_LAB_SCENES:
        required.add(scene.label)
        required.add(scene.description)

    for path in sorted((ROOT / "src/lang").glob("*.py")):
        if path.name in {"__init__.py", "en.py"}:
            continue
        strings = runpy.run_path(str(path))["STRINGS"]
        assert not required - strings.keys(), path.name


def test_haptics_lab_is_only_a_default_collapsed_system_card():
    gui_main = (ROOT / "src/modules/gui/main.py").read_text(encoding="utf-8")
    gui_system = (ROOT / "src/modules/gui/system_tab.py").read_text(encoding="utf-8")
    gui_lab = (ROOT / "src/modules/gui/haptics_lab_tab.py").read_text(encoding="utf-8")
    tui_main = (ROOT / "src/modules/tui/main.py").read_text(encoding="utf-8")
    tui_system = (ROOT / "src/modules/tui/system_tab.py").read_text(encoding="utf-8")

    assert '"Lab": "Haptics Lab"' not in gui_main
    assert "self.haptics_lab_tab =" not in gui_main
    assert "HapticsLabCard" in gui_system
    assert "self._expanded = False" in gui_lab
    assert 'id="tab-haptics-lab"' not in tui_main
    assert 'id="haptics-lab-card"' in tui_system
    assert "collapsed=True" in tui_system
    assert "yield HapticsLabPanel()" in tui_system


def test_tui_haptics_lab_panel_unmounts_after_children_are_pruned():
    from textual.app import App, ComposeResult

    from modules.tui.haptics_lab_tab import HapticsLabPanel

    class XInput:
        preview_requested = False

        def request_preview_runtime(self, _enabled):
            return False

    class LabHarness(App):
        def __init__(self):
            super().__init__()
            self._haptics_lab = HapticsLab()
            self._xinput_service = XInput()
            self._ds = None
            self._thread = None

        def compose(self) -> ComposeResult:
            yield HapticsLabPanel()

        def _sync_usb_audio_eligibility(self):
            raise AssertionError("inactive preview should not sync USB audio")

    async def check():
        app = LabHarness()
        async with app.run_test():
            assert app.query_one(HapticsLabPanel).is_mounted

    asyncio.run(check())
