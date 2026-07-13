# DualSense Body Haptics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add high-fidelity USB body haptics and a Bluetooth compatible-rumble fallback to `HamzaYslmn/Forza-Horizon-DualSense-Python` while preserving adaptive triggers and trigger-only output when disabled.

**Architecture:** A pure `HapticMixer` converts Forza telemetry into an immutable transport-neutral `HapticFrame`. `HapticManager` routes that frame to a four-channel USB audio stream or converts it to a Bluetooth `CompatibleRumble` payload that is encoded atomically with trigger effects by the existing HID writer.

**Tech Stack:** Python 3.13, pytest, NumPy, sounddevice, hidapi, CustomTkinter, Textual, PyInstaller, ZUV.

## Global Constraints

- Target only `work/hamza`, the local clone of `HamzaYslmn/Forza-Horizon-DualSense-Python`.
- Do not push, open a PR, create a remote branch, or merge any branch.
- Do not create additional implementation commits unless the user explicitly requests them.
- Preserve `DualSense.set(left, right)` behavior byte-for-byte when body haptics is disabled.
- Keep `recv_latest()` and state-change HID writes.
- Keep DSX trigger behavior unchanged; body haptics remains inactive in DSX mode.
- USB uses four-channel 48 kHz float32 audio with haptics on zero-based channels 2 and 3.
- Bluetooth uses the existing report layout and CRC path, with live hardware validation before completion.
- All tunables live in `src/modules/config/settings.py`.
- Body-haptics tunables remain profile-scoped and are not added to `GLOBAL_FIELDS`.
- No em dash character in source, tests, docs, or user-facing text.
- Every production behavior follows a witnessed red-green TDD cycle.
- Hardware tests start at low intensity and finish by sending silence.

---

## File Structure

Create:

- `pytest.ini`: make `src` importable from repository-root test commands.
- `tests/haptics/test_frame.py`: frame validation and Bluetooth downmix behavior.
- `tests/haptics/test_mixer.py`: deterministic telemetry-to-haptic effect tests.
- `tests/haptics/test_audio.py`: endpoint selection and audio callback routing.
- `tests/haptics/test_manager.py`: transport routing and lifecycle tests.
- `tests/dualsense/test_output_report.py`: USB and Bluetooth report regression tests.
- `tests/dualsense/test_reconnect_output.py`: pending-frame resend and disconnect silence tests.
- `tests/dsx/test_client.py`: DSX call-shape compatibility test.
- `tests/test_loop_haptics.py`: loop integration, idle reset, and cleanup tests.
- `tests/forzahorizon/test_udp_listener.py`: puddle-depth protocol regression test.
- `src/modules/haptics/__init__.py`: public haptics exports.
- `src/modules/haptics/frame.py`: immutable haptic and compatible-rumble values.
- `src/modules/haptics/mixer.py`: pure Forza body-effect mixer.
- `src/modules/haptics/audio.py`: USB audio endpoint and real-time synthesis.
- `src/modules/haptics/manager.py`: runtime backend selection and lifecycle.
- `docs/THIRD_PARTY_NOTICES.md`: HorizonHaptics MIT attribution if synthesis code is substantially adapted.

Modify:

- `src/modules/dualsense/main.py`: transport property, motor offsets, and atomic rumble.
- `src/modules/dsx/client.py`: accept and ignore the native-only rumble argument.
- `src/modules/loop.py`: mixer and manager integration with guaranteed cleanup.
- `src/modules/forzahorizon/udp_listener.py`: decode puddle depths as float32.
- `src/modules/config/settings.py`: body-haptics settings and thresholds.
- `src/modules/gui/settings_tab.py`: GUI controls.
- `src/modules/tui/settings_tab.py`: matching TUI controls.
- `src/lang/{de,ja,ru,tr,zh,zh_tw}.py`: translated labels and hints.
- `src/pyproject.toml`: NumPy, sounddevice, and pytest metadata.
- `packaging/windows/fhds.spec`: audio dependency collection if PyInstaller needs it.
- `packaging/linux/fhds.spec`: audio dependency and third-party notice collection.
- `packaging/windows/build_exe.bat`: include NumPy and sounddevice in local builds.
- `.github/workflows/release.yml`: include packaging dependencies without running or pushing the workflow.
- `README.md` and `docs/ReadmeZH.md`: usage, USB/BT behavior, and limitations.

---

### Task 1: Haptic values and Bluetooth downmix

**Files:**

- Create: `pytest.ini`
- Create: `tests/haptics/test_frame.py`
- Create: `src/modules/haptics/__init__.py`
- Create: `src/modules/haptics/frame.py`

**Interfaces:**

- Produces: `HapticFrame`, `SILENT_FRAME`, `CompatibleRumble`, `clamp01`, and `to_compatible_rumble(frame)`.
- Consumes: only Python standard-library types.

- [x] **Step 1: Add the test harness and failing frame tests**

```ini
[pytest]
pythonpath = src
testpaths = tests
```

```python
import math

from modules.haptics.frame import (
    CompatibleRumble,
    HapticFrame,
    SILENT_FRAME,
    clamp01,
    to_compatible_rumble,
)


def test_silent_frame_has_no_energy():
    assert SILENT_FRAME == HapticFrame()


def test_clamp01_rejects_non_finite_and_clamps_range():
    assert clamp01(float("nan")) == 0.0
    assert clamp01(float("inf")) == 0.0
    assert clamp01(-0.5) == 0.0
    assert clamp01(1.5) == 1.0


def test_compatible_rumble_uses_frequency_priority_downmix():
    frame = HapticFrame(
        left_low=0.4,
        right_low=0.7,
        left_high=0.2,
        right_high=0.6,
        engine_hz=80.0,
        engine_amplitude=0.4,
    )
    assert to_compatible_rumble(frame) == CompatibleRumble(
        low_frequency=0.9,
        high_frequency=0.6,
    )


def test_compatible_rumble_clamps_summed_engine_energy():
    frame = HapticFrame(left_low=0.9, engine_amplitude=0.8)
    assert math.isclose(to_compatible_rumble(frame).low_frequency, 1.0)
```

- [x] **Step 2: Run the tests and verify RED**

Run:

```powershell
work\probe-venv\Scripts\python.exe -m pip install pytest
work\probe-venv\Scripts\python.exe -m pytest work\hamza\tests\haptics\test_frame.py -q
```

Expected: collection fails because `modules.haptics.frame` does not exist.

- [x] **Step 3: Implement the minimal immutable values**

```python
from __future__ import annotations

import math
from dataclasses import dataclass


def clamp01(value: float) -> float:
    value = float(value)
    if not math.isfinite(value):
        return 0.0
    return max(0.0, min(1.0, value))


@dataclass(frozen=True, slots=True)
class HapticFrame:
    left_low: float = 0.0
    left_high: float = 0.0
    right_low: float = 0.0
    right_high: float = 0.0
    engine_hz: float = 0.0
    engine_amplitude: float = 0.0


@dataclass(frozen=True, slots=True)
class CompatibleRumble:
    low_frequency: float = 0.0
    high_frequency: float = 0.0


SILENT_FRAME = HapticFrame()


def to_compatible_rumble(frame: HapticFrame) -> CompatibleRumble:
    return CompatibleRumble(
        low_frequency=clamp01(max(frame.left_low, frame.right_low) + 0.5 * frame.engine_amplitude),
        high_frequency=clamp01(max(frame.left_high, frame.right_high)),
    )
```

Export these names from `src/modules/haptics/__init__.py`.

- [x] **Step 4: Verify GREEN and inspect the local diff**

Run:

```powershell
work\probe-venv\Scripts\python.exe -m pytest work\hamza\tests\haptics\test_frame.py -q
git -C work\hamza diff --check
```

Expected: four tests pass, and `git diff --check` exits 0.

---

### Task 2: Deterministic Forza haptic mixer

**Files:**

- Create: `tests/haptics/test_mixer.py`
- Create: `src/modules/haptics/mixer.py`
- Modify: `src/modules/config/settings.py`
- Modify: `src/modules/haptics/__init__.py`

**Interfaces:**

- Consumes: `Mapping[str, object]` telemetry, `Settings`, and an explicit monotonic `now`.
- Produces: `HapticMixer.update(telemetry, settings, now) -> HapticFrame` and `HapticMixer.reset()`.

- [x] **Step 1: Add failing baseline, engine, and directional tests**

Create a `_telemetry(**overrides)` helper containing every key used by the mixer with race-on, stationary, zero-energy defaults. Add tests asserting:

```python
def test_menu_telemetry_is_silent_and_resets_state(settings):
    mixer = HapticMixer()
    assert mixer.update(_telemetry(on=False), settings, now=1.0) == SILENT_FRAME


def test_engine_maps_idle_to_redline_frequency(settings):
    mixer = HapticMixer()
    idle = mixer.update(_telemetry(rpm=1000.0, idle_rpm=1000.0, max_rpm=9000.0), settings, now=1.0)
    redline = mixer.update(_telemetry(rpm=9000.0, idle_rpm=1000.0, max_rpm=9000.0), settings, now=2.0)
    assert idle.engine_hz == 40.0
    assert redline.engine_hz == 120.0
    assert redline.engine_amplitude > idle.engine_amplitude


def test_road_and_puddle_energy_stays_on_matching_side(settings):
    frame = HapticMixer().update(
        _telemetry(surface_rumble_fl=0.6, wheel_in_puddle_fl=1),
        settings,
        now=1.0,
    )
    assert frame.left_high > frame.right_high
    assert frame.left_low > frame.right_low


def test_suspension_compression_creates_left_thud(settings):
    mixer = HapticMixer()
    mixer.update(_telemetry(suspension_travel_meters_fl=0.10), settings, now=1.0)
    frame = mixer.update(_telemetry(suspension_travel_meters_fl=0.08), settings, now=1.02)
    assert frame.left_low > frame.right_low


def test_slip_and_abs_are_clamped(settings):
    frame = HapticMixer().update(
        _telemetry(tire_combined_slip_rr=9.0, brake=255), settings, now=2.0
    )
    assert 0.0 <= frame.right_low <= 1.0
    assert 0.0 <= frame.left_low <= 1.0
```

- [x] **Step 2: Run mixer tests and verify RED**

Run:

```powershell
work\probe-venv\Scripts\python.exe -m pytest work\hamza\tests\haptics\test_mixer.py -q
```

Expected: collection fails because `modules.haptics.mixer` does not exist.

- [x] **Step 3: Add settings with exact defaults**

Append the body-haptics fields to `Settings`:

```python
enable_body_haptics: bool = False
body_haptics_intensity: float = 1.0
engine_haptics_intensity: float = 1.0
road_haptics_intensity: float = 1.0
impact_haptics_intensity: float = 1.0
slip_haptics_intensity: float = 1.0
slip_haptics_threshold: float = 0.8
collision_haptics_jerk_threshold: float = 3.0
collision_haptics_duration_ms: float = 150.0
suspension_haptics_delta_threshold: float = 0.015
```

- [x] **Step 4: Implement the mixer effect model**

Implement `HapticMixer` with these exact rules:

- Return `SILENT_FRAME` and call `reset()` when `on` is false or the feature is disabled.
- Sanitize every numeric input through a finite-float helper.
- RPM ratio is `(rpm - idle_rpm) / (max_rpm - idle_rpm)`, clamped to `0..1`.
- Engine frequency is `40 + ratio * 80`.
- Engine amplitude is `(0.08 + accel / 255 * 0.25 + ratio * 0.1) * engine_haptics_intensity`.
- Side surface high energy is the average of front and rear values multiplied by `1.5`.
- Speed above 10.8 km/h adds `min(1, (speed / 3.6 - 3) / 80) * 0.12` to both high layers.
- A nonzero rumble-strip field adds `0.35` to its side.
- A nonzero puddle integer is normalized to `0..1`, adding `0.6 * depth` low and `0.3 * depth` high.
- Slip energy is `max(0, side_slip - threshold) * 0.5 * slip_intensity`.
- A suspension drop larger than the configured threshold adds `1.0` low to that side.
- Acceleration jerk above its threshold arms a decaying collision event for the configured duration.
- Smashable velocity difference above `3.0` arms the same event.
- Gear changes between positive gears while moving above 3 km/h arm a centered `0.8` kick for `gear_shift_duration_ms`.
- Hard brake above 100 plus slip above threshold adds a 15 Hz time-based centered pulse.
- Apply per-category intensity before master intensity, then clamp every output layer.

- [x] **Step 5: Add non-finite, collision, gear, and reset tests**

Add focused tests proving NaN becomes zero, collision direction follows `accel_x`, gear kick persists for its deadline, and `reset()` prevents an old suspension or gear state from firing after a menu frame.

- [x] **Step 6: Verify GREEN**

Run:

```powershell
work\probe-venv\Scripts\python.exe -m pytest work\hamza\tests\haptics\test_frame.py work\hamza\tests\haptics\test_mixer.py -q
```

Expected: all frame and mixer tests pass.

---

### Task 3: USB four-channel audio backend

**Files:**

- Create: `tests/haptics/test_audio.py`
- Create: `src/modules/haptics/audio.py`
- Modify: `src/pyproject.toml`
- Modify: `src/modules/haptics/__init__.py`

**Interfaces:**

- Consumes: `HapticFrame`, injectable sounddevice module, and injectable NumPy module.
- Produces: `UsbAudioHaptics.start() -> bool`, `set_frame(frame)`, `stop()`, `running`, and pure `find_dualsense_output_device(devices, hostapis, platform)`.

- [x] **Step 1: Write failing endpoint-selection tests**

Add tests with plain dictionaries proving Windows selects the four-channel WASAPI DualSense endpoint, ignores microphone and stereo endpoints, and returns `None` when no candidate exists. Add a Linux test that prefers an ALSA candidate.

- [x] **Step 2: Verify RED**

Run:

```powershell
work\probe-venv\Scripts\python.exe -m pytest work\hamza\tests\haptics\test_audio.py -q
```

Expected: collection fails because `modules.haptics.audio` does not exist.

- [x] **Step 3: Implement endpoint selection and lazy dependencies**

Implement module-level guarded imports:

```python
try:
    import numpy as np
    import sounddevice as sd
except ImportError:
    np = None
    sd = None
```

`find_dualsense_output_device` must require at least four output channels, a name containing `dualsense` or `wireless controller`, and WASAPI on Windows or ALSA on Linux.

- [x] **Step 4: Write failing callback routing tests**

Construct `UsbAudioHaptics` with fake dependencies, call its callback with a zeroed `(64, 4)` float32 array, and assert:

```python
assert np.all(out[:, 0] == 0.0)
assert np.all(out[:, 1] == 0.0)
assert np.any(out[:, 2] != 0.0)
assert np.any(out[:, 3] != 0.0)
```

Add left-only and right-only tests and a stopped-state test that fills all channels with zero.

- [x] **Step 5: Implement real-time synthesis**

Use a 48 kHz float32 stream. Generate a 65 Hz low sine, a textured 180 to 200 Hz high layer, and a phase-continuous engine waveform. Smooth target amplitudes toward current amplitudes once per block, clear all channels, and write only indexes 2 and 3. `start()` returns false and logs once on dependency, endpoint, or stream failure. `stop()` first publishes `SILENT_FRAME`, then stops and closes the stream.

- [x] **Step 6: Verify GREEN and dependency import**

Run:

```powershell
work\probe-venv\Scripts\python.exe -m pytest work\hamza\tests\haptics\test_audio.py -q
work\probe-venv\Scripts\python.exe -c "import sys; sys.path.insert(0, r'work/hamza/src'); from modules.haptics.audio import UsbAudioHaptics; print(UsbAudioHaptics.__name__)"
```

Expected: audio tests pass and the import prints `UsbAudioHaptics`.

---

### Task 4: Atomic HID rumble and transport reporting

**Files:**

- Create: `tests/dualsense/test_output_report.py`
- Modify: `src/modules/dualsense/main.py`

**Interfaces:**

- Consumes: `CompatibleRumble | None` through `DualSense.set(left, right, rumble=None)`.
- Produces: `DualSense.transport -> "usb" | "bluetooth" | None`.

- [x] **Step 1: Capture failing trigger-only regression tests**

Instantiate `DualSense` without opening hardware, select `USB` and `BT` layouts directly, and assert the current report IDs, lengths, trigger flags, trigger offsets, and Bluetooth CRC. Save expected trigger-only bytes before modifying production code.

- [x] **Step 2: Run and verify the baseline tests pass**

Run:

```powershell
work\probe-venv\Scripts\python.exe -m pytest work\hamza\tests\dualsense\test_output_report.py -q
```

Expected: trigger-only characterization tests pass against current code.

- [x] **Step 3: Add failing rumble tests**

Add tests asserting:

- USB motor bytes are at indexes 3 and 4.
- BT motor bytes are at indexes 4 and 5 for the preserved project layout.
- A `CompatibleRumble(0.5, 0.25)` sets compatible-rumble flags and encoded amplitudes.
- `rumble=None` leaves flags and motor bytes unchanged.
- BT CRC changes and matches recomputation after motor fields are written.
- Transport reports USB or Bluetooth only while a device handle is connected.

- [x] **Step 4: Verify RED**

Run the same test file. Expected: new tests fail because the signature, motor layout entries, rumble flags, and transport property do not exist.

- [x] **Step 5: Implement minimal HID extensions**

Add `motor_r` and `motor_l` to both layout dictionaries. Store the pending rumble under the existing lock. Preserve the current BT report header and trigger offsets. Set compatible-rumble flags only when rumble is not `None`; encode high frequency to right and low frequency to left. Do not add HorizonHaptics' unverified USB `0x20` mode bit because the Linux driver defines it as speaker-volume control and direct four-channel audio already opens successfully. Recompute CRC after all fields are populated.

- [x] **Step 6: Verify GREEN and full report regression**

Run:

```powershell
work\probe-venv\Scripts\python.exe -m pytest work\hamza\tests\dualsense\test_output_report.py -q
```

Expected: old trigger-only and new haptics report tests all pass.

---

### Task 5: Manager and loop integration

**Files:**

- Create: `tests/haptics/test_manager.py`
- Create: `tests/test_loop_haptics.py`
- Create: `src/modules/haptics/manager.py`
- Modify: `src/modules/haptics/__init__.py`
- Modify: `src/modules/loop.py`

**Interfaces:**

- Consumes: native or DSX backend, `Settings`, `HapticFrame`, and an injectable audio factory.
- Produces: `HapticManager.route(frame) -> CompatibleRumble | None`, `silence()`, and `close()`.

- [x] **Step 1: Write failing manager routing tests**

Use a fake controller with `transport` and `connected` fields. Assert:

- Disabled settings return `None` and stop audio.
- USB starts audio once, publishes the frame, and returns `None`.
- Bluetooth stops audio and returns `to_compatible_rumble(frame)`.
- Disconnect returns `None` and silences every output.
- A fake with `is_dsx=True` remains disabled.
- Repeated routes do not repeatedly start or stop the backend.

- [x] **Step 2: Verify manager tests RED**

Expected: collection fails because `HapticManager` does not exist.

- [x] **Step 3: Implement the manager and verify GREEN**

Keep transport state inside `HapticManager`; create the audio object lazily only for USB. Catch and rate-limit backend exceptions. `close()` must call `silence()` and stop audio.

- [x] **Step 4: Write failing loop integration tests**

Use fake listener, controller, manager factory, and stop event to prove one parsed packet updates triggers and haptics, Bluetooth rumble is passed in the same `ds.set` call, a one-second idle sends trigger off plus manager silence, and `manager.close()` executes when the loop exits.

- [x] **Step 5: Integrate into `loop.run`**

Create `HapticMixer` and `HapticManager` once. On each valid packet, compute the trigger pair and haptic frame, route it, and compare `(left, right, rumble)` for HID state-change writes. For USB, haptic frames update audio without generating HID writes unless trigger state changes. Wrap the loop in `try/finally` and close the manager.

- [x] **Step 6: Verify GREEN**

Run:

```powershell
work\probe-venv\Scripts\python.exe -m pytest work\hamza\tests\haptics\test_manager.py work\hamza\tests\test_loop_haptics.py -q
```

Expected: all manager and loop integration tests pass.

---

### Task 6: Settings surfaces and translations

**Files:**

- Modify: `src/modules/gui/settings_tab.py`
- Modify: `src/modules/tui/settings_tab.py`
- Modify: `src/lang/{de,ja,ru,tr,zh,zh_tw}.py`
- Modify: `tests/haptics/test_mixer.py`

**Interfaces:**

- Consumes: exact settings fields added in Task 2.
- Produces: matching GUI and TUI sections with live persistence.

- [x] **Step 1: Add failing settings-table parity tests**

Parse or import both `SETTING_SECTIONS` lists and assert they contain the same body-haptics attributes in the same order, all attributes exist on `Settings`, and none appears in `GLOBAL_FIELDS`.

- [x] **Step 2: Verify RED**

Expected: tests fail because the UI tables do not contain body-haptics fields.

- [x] **Step 3: Add matching GUI and TUI sections**

Add a `Body haptics` section containing the enable switch, master, engine, road, impact, slip intensity, and slip threshold controls. Keep engineering thresholds in `Settings` but out of the normal UI unless hardware tuning proves users need them.

- [x] **Step 4: Add translations**

Add keys for the section, each label, and the USB/BT automatic-output hint to every non-English catalog. Preserve each file's existing UTF-8 encoding and syntax.

- [x] **Step 5: Verify GREEN and catalog imports**

Run all settings parity tests, then import every `src/lang/*.py` module with `py_compile`.

---

### Task 7: Packaging, notices, and user documentation

**Files:**

- Modify: `src/pyproject.toml`
- Modify: `packaging/windows/fhds.spec`
- Modify: `packaging/windows/build_exe.bat`
- Modify: `.github/workflows/release.yml`
- Create: `docs/THIRD_PARTY_NOTICES.md`
- Modify: `README.md`
- Modify: `docs/ReadmeZH.md`

**Interfaces:**

- Produces: installable runtime dependencies and documented USB/BT behavior.

- [x] **Step 1: Add dependency metadata**

Add compatible Python 3.13 NumPy and sounddevice runtime dependencies and pytest as a development dependency. Add NumPy and sounddevice to Windows PyInstaller build inputs and hidden imports only where PyInstaller analysis requires it.

- [x] **Step 2: Add attribution**

Document HorizonHaptics copyright, MIT license text, source URL, and pinned reference commit in `docs/THIRD_PARTY_NOTICES.md` if implementation substantially adapts its synthesis or effect code.

- [x] **Step 3: Update English and Chinese usage documentation**

Document:

- Body haptics default off.
- USB provides high-fidelity four-channel audio haptics.
- Bluetooth automatically falls back to compatible rumble.
- Bluetooth output is lower fidelity and not stereo-equivalent.
- DSX mode does not receive this feature in the first release.
- Missing audio devices do not disable adaptive triggers.

- [x] **Step 4: Verify metadata and imports**

Run TOML parsing, Python compilation, batch-file text inspection, and all automated tests. Run `git diff --check` and scan new files for an em dash.

---

### Task 8: Hardware validation and final audit

**Files:**

- No production files unless a hardware failure first receives a failing automated regression test.

**Interfaces:**

- Consumes: completed local implementation and the connected DualSense.
- Produces: fresh automated, USB, Bluetooth, and packaging evidence.

- [x] **Step 1: Run the full automated suite**

Run:

```powershell
work\probe-venv\Scripts\python.exe -m pytest work\hamza\tests -q
work\probe-venv\Scripts\python.exe -m compileall -q work\hamza\src
git -C work\hamza diff --check
```

Expected: zero failures, zero compilation errors, and clean diff checks.

- [x] **Step 2: Run conservative USB channel tests**

With USB connected, select the confirmed four-channel WASAPI endpoint. Send a short low-intensity left pulse, silence, right pulse, and silence. Confirm correct side response, silent headphone channels, trigger preview coexistence, and clean shutdown.

- [x] **Step 3: Run USB telemetry tests**

Use the project's emulation or recorded deterministic frames to validate engine, road, collision, suspension, gear, puddle, slip, ABS, stale telemetry silence, and application exit silence.

- [x] **Step 4: Switch to Bluetooth and run compatible-rumble tests**

Verify automatic transport detection, short conservative low and high pulses, adaptive trigger coexistence, CRC correctness, body-haptics disable behavior, and reconnect with a previously nonzero frame. Always send silence before closing the HID handle.

- [x] **Step 5: Run packaging smoke checks**

Build or analyze the ZUV bundle and Windows PyInstaller target locally. Start the resulting artifact, confirm imports and controller enumeration, then close it without publishing the artifact.

- [x] **Step 6: Requirement-by-requirement completion audit**

Compare current code and fresh evidence against every scope item and acceptance criterion in `docs/superpowers/specs/2026-07-12-dualsense-body-haptics-design.md`. Record any missing or indirect evidence as incomplete and continue implementation until all explicit requirements are proven.
