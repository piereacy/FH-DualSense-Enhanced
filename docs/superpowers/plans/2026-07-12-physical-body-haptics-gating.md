# Physical Body Haptics Gating Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace unconditional stationary grip vibration with per-source physical activation while preserving stationary revving, drivetrain-aware burnouts, road-material texture, impacts, USB, Bluetooth, and adaptive triggers.

**Architecture:** Keep `HapticMixer` as the single transport-independent source of `HapticFrame`. Add rolling hysteresis and per-wheel contact excitation inside the mixer, reuse the target project's low-speed drivetrain and wheel-rotation rules, and leave `HapticManager` plus the DualSense transport code unchanged. Tests drive each behavior before production changes.

**Tech Stack:** Python 3.13, pytest, dataclasses, NumPy/sounddevice downstream, existing Forza Data Out parser, existing DualSense HID and audio backends.

## Global Constraints

- Work only in the local `work/hamza` repository.
- Do not run `git add`, `git commit`, merge, push, create a branch, or create a pull request.
- Keep one FH-DualSense program; HorizonHaptics is a behavioral reference only.
- Preserve USB high-fidelity audio and Bluetooth compatible rumble.
- Preserve adaptive trigger output and the atomic `ds.set(left, right, rumble)` path.
- True stationary idle must be silent, but stationary revving, burnouts, collisions, and suspension impulses must remain active.
- Road material determines texture only when rolling, wheelspin, or another real contact excitation supplies energy.
- Do not add new user settings unless a failing test demonstrates that an existing setting cannot express the approved behavior.

---

## File Map

- Modify `src/modules/haptics/mixer.py`: derive rolling, engine, per-wheel contact, burnout, surface, slip, and ABS activation.
- Modify `tests/haptics/test_mixer.py`: lock the approved physical state matrix and preserve event behavior.
- Modify `src/modules/gui/settings_tab.py`: soften the in-game vibration guidance.
- Modify `src/modules/tui/settings_tab.py`: mirror the GUI wording.
- Modify `src/lang/de.py`, `src/lang/ja.py`, `src/lang/ru.py`, `src/lang/tr.py`, `src/lang/zh.py`, `src/lang/zh_tw.py`: translate the revised guidance.
- Modify `tests/test_haptic_settings.py`: require the revised localized label.
- Modify `README.md` and `docs/ReadmeZH.md`: document per-source activation and conditional game-vibration guidance.
- Modify `docs/superpowers/specs/2026-07-12-physical-body-haptics-gating-design.md`: mark implementation verification results after completion.

---

### Task 1: True Idle and Engine Activity

**Files:**
- Modify: `tests/haptics/test_mixer.py`
- Modify: `src/modules/haptics/mixer.py`

**Interfaces:**
- Consumes: `HapticMixer.update(telemetry: Mapping[str, object], settings, now: float) -> HapticFrame`
- Produces: `_rolling: bool`, `_update_rolling(speed_kmh: float) -> bool`, and engine output that is zero only at true stationary idle.

- [x] **Step 1: Make ordinary effect fixtures represent a moving vehicle**

Change `_telemetry()` defaults to include the wheel-state fields needed by later tests and make its default speed `50.0` so existing road, slip, collision, and suspension tests do not accidentally describe a parked car:

```python
        "wheel_rotation_speed_fl": 0.0,
        "wheel_rotation_speed_fr": 0.0,
        "wheel_rotation_speed_rl": 0.0,
        "wheel_rotation_speed_rr": 0.0,
        "drive_train": 2,
        "speed": 50.0,
```

- [x] **Step 2: Add the failing idle test and the revving guard test**

```python
def test_true_stationary_idle_is_silent(settings):
    frame = HapticMixer().update(
        _telemetry(speed=0.0, rpm=1000.0, idle_rpm=1000.0, accel=0),
        settings,
        now=1.0,
    )

    assert frame == SILENT_FRAME


def test_stationary_revving_produces_engine_only(settings):
    frame = HapticMixer().update(
        _telemetry(
            speed=0.0,
            rpm=7000.0,
            accel=220,
            surface_rumble_fl=1.0,
            wheel_on_rumble_strip_fr=1,
            wheel_in_puddle_rr=1.0,
        ),
        settings,
        now=1.0,
    )

    assert frame.engine_hz > 40.0
    assert frame.engine_amplitude > 0.0
    assert frame.left_low == 0.0
    assert frame.left_high == 0.0
    assert frame.right_low == 0.0
    assert frame.right_high == 0.0
```

- [x] **Step 3: Run the tests and verify the correct red result**

Run:

```powershell
..\probe-venv\Scripts\python.exe -m pytest -q tests/haptics/test_mixer.py::test_true_stationary_idle_is_silent tests/haptics/test_mixer.py::test_stationary_revving_produces_engine_only
```

Expected: the idle test fails because the current frame contains `engine_hz=40.0` and `engine_amplitude=0.08`; the revving test also fails because ungated surface and puddle channels are nonzero.

- [x] **Step 4: Add rolling hysteresis and engine activation**

Add constants and state in `mixer.py`:

```python
_ROLLING_ENTER_KMH = 0.5
_ROLLING_EXIT_KMH = 0.2
_ENGINE_ACCEL_ACTIVITY = 1.0
_ENGINE_RPM_ACTIVITY_MIN = 100.0
_ENGINE_RPM_ACTIVITY_RATIO = 0.05


def reset(self) -> None:
    self._rolling = False
    # Preserve all existing reset assignments below this line.


def _update_rolling(self, speed_kmh: float) -> bool:
    if self._rolling:
        self._rolling = speed_kmh > _ROLLING_EXIT_KMH
    else:
        self._rolling = speed_kmh >= _ROLLING_ENTER_KMH
    return self._rolling
```

At the start of `update()`, after the enable/menu guard, derive `speed_kmh`, `rolling`, and raw accelerator once. Replace the unconditional engine block with:

```python
speed_kmh = max(0.0, _number(telemetry.get("speed")))
rolling = self._update_rolling(speed_kmh)
accel_raw = max(0.0, _number(telemetry.get("accel")))

rpm = _number(telemetry.get("rpm"))
idle_rpm = _number(telemetry.get("idle_rpm"))
max_rpm = _number(telemetry.get("max_rpm"))
rpm_margin = max(_ENGINE_RPM_ACTIVITY_MIN, idle_rpm * _ENGINE_RPM_ACTIVITY_RATIO)
engine_active = rolling or accel_raw > _ENGINE_ACCEL_ACTIVITY or rpm > idle_rpm + rpm_margin

if engine_active and max_rpm > idle_rpm:
    rpm_ratio = clamp01((rpm - idle_rpm) / (max_rpm - idle_rpm))
    engine_hz = 40.0 + rpm_ratio * 80.0
    throttle = clamp01(accel_raw / 255.0)
    engine_amplitude = (
        0.08 + throttle * 0.25 + rpm_ratio * 0.1
    ) * _setting(settings, "engine_haptics_intensity", 1.0)
else:
    rpm_ratio = 0.0
    engine_hz = 0.0
    engine_amplitude = 0.0
```

Do not return early when `rolling` is false.

- [x] **Step 5: Temporarily gate existing tire-contact sources by rolling**

Until Task 2 adds wheelspin contacts, ensure surface, strip, puddle, asphalt, and ordinary combined-slip contributions execute only when `rolling` is true. Keep collision, suspension, gear state, and engine outside this condition.

- [x] **Step 6: Run focused and complete mixer tests**

Run:

```powershell
..\probe-venv\Scripts\python.exe -m pytest -q tests/haptics/test_mixer.py
```

Expected: all mixer tests pass after existing effect tests use moving telemetry.

- [x] **Step 7: Preserve the local working tree without committing**

Run only:

```powershell
git diff --check -- src/modules/haptics/mixer.py tests/haptics/test_mixer.py
```

Expected: exit code 0. Do not stage or commit.

---

### Task 2: Drivetrain-Aware Burnout and Material Texture

**Files:**
- Modify: `tests/haptics/test_mixer.py`
- Modify: `src/modules/haptics/mixer.py`

**Interfaces:**
- Consumes: `rolling`, raw per-wheel rotation, `drive_train`, `accel_deadzone`, and existing road/slip intensity settings.
- Produces: per-wheel `spin_strength: dict[str, float]` and `contact_active: dict[str, bool]` used by surface, strip, puddle, and slip layers.

- [x] **Step 1: Add failing burnout and stale-material tests**

```python
def test_stationary_burnout_uses_only_driven_wheel_rotation(settings):
    mixer = HapticMixer()
    front_noise = mixer.update(
        _telemetry(
            speed=0.0,
            drive_train=1,
            accel=255,
            rpm=7000.0,
            wheel_rotation_speed_fl=120.0,
            tire_combined_slip_fl=9.0,
        ),
        settings,
        now=1.0,
    )
    rear_spin = mixer.update(
        _telemetry(
            speed=0.0,
            drive_train=1,
            accel=255,
            rpm=7000.0,
            wheel_rotation_speed_rr=120.0,
        ),
        settings,
        now=1.1,
    )

    assert front_noise.left_low == 0.0
    assert front_noise.right_low == 0.0
    assert rear_spin.right_low > rear_spin.left_low


def test_stationary_burnout_keeps_material_signatures(settings):
    common = dict(
        speed=0.0,
        drive_train=1,
        accel=255,
        rpm=7000.0,
        wheel_rotation_speed_rr=120.0,
    )
    tarmac = HapticMixer().update(_telemetry(**common), settings, now=1.0)
    dirt = HapticMixer().update(
        _telemetry(**common, surface_rumble_rr=0.2), settings, now=1.0
    )
    gravel = HapticMixer().update(
        _telemetry(**common, surface_rumble_rr=0.4), settings, now=1.0
    )
    water = HapticMixer().update(
        _telemetry(**common, wheel_in_puddle_rr=1.0), settings, now=1.0
    )

    assert dirt.right_high > tarmac.right_high
    assert gravel.right_high > dirt.right_high
    assert gravel.right_low > dirt.right_low > tarmac.right_low
    assert water.right_high > tarmac.right_high
    assert water.right_low > tarmac.right_low
    assert len({tarmac, dirt, gravel, water}) == 4


def test_stationary_stale_contact_telemetry_is_silent(settings):
    frame = HapticMixer().update(
        _telemetry(
            speed=0.0,
            accel=0,
            rpm=1000.0,
            surface_rumble_fl=1.0,
            wheel_on_rumble_strip_fr=1,
            wheel_in_puddle_rl=1.0,
            tire_combined_slip_rr=9.0,
        ),
        settings,
        now=1.0,
    )

    assert frame == SILENT_FRAME
```

- [x] **Step 2: Run the new tests and verify red**

Run:

```powershell
..\probe-venv\Scripts\python.exe -m pytest -q tests/haptics/test_mixer.py -k "burnout or stale_contact"
```

Expected: burnout tests fail because low-speed raw wheel rotation is not yet converted to body haptics; the stale-contact test protects the Task 1 rolling gate.

- [x] **Step 3: Derive per-wheel spin strength and contact excitation**

Import the existing domain constants rather than inventing a second threshold:

```python
from modules.forzahorizon.effects import (
    BURNOUT_ROT_THRESHOLD,
    DRIVEN_WHEELS,
    LOW_SPEED_KMH,
)
```

After deriving `speed_kmh`, `rolling`, and `accel_raw`, add:

```python
spin_strength = {wheel: 0.0 for wheel in _WHEELS}
if speed_kmh < LOW_SPEED_KMH and accel_raw >= max(
    1.0, _setting(settings, "accel_deadzone", 50.0)
):
    drive_train = int(_number(telemetry.get("drive_train"), -1.0))
    driven = DRIVEN_WHEELS.get(drive_train, _WHEELS)
    full_scale = BURNOUT_ROT_THRESHOLD * 4.0
    for wheel in driven:
        rotation = abs(_number(telemetry.get(f"wheel_rotation_speed_{wheel}")))
        spin_strength[wheel] = clamp01(
            (rotation - BURNOUT_ROT_THRESHOLD)
            / (full_scale - BURNOUT_ROT_THRESHOLD)
        )

contact_active = {
    wheel: rolling or spin_strength[wheel] > 0.0
    for wheel in _WHEELS
}
```

- [x] **Step 4: Apply contact activation and material profiles per wheel**

Reuse the surface thresholds already used by `forzahorizon/effects.py` and map
them to the body's low/high actuator bands:

```python
def _surface_components(value: float) -> tuple[float, float]:
    value = max(0.0, _number(value))
    high = value * 0.75
    if value > 0.30:
        low = value * 0.45
    elif value > 0.10:
        low = value * 0.20
    else:
        low = 0.0
    return low, high


for wheel in _WHEELS:
    if not contact_active[wheel]:
        continue
    side = "left" if wheel in ("fl", "rl") else "right"
    surface_low, surface_high = _surface_components(
        telemetry.get(f"surface_rumble_{wheel}")
    )
    if side == "left":
        left_low += surface_low * road_scale
        left_high += surface_high * road_scale
    else:
        right_low += surface_low * road_scale
        right_high += surface_high * road_scale
```

Use `contact_active` for strip detection and for selecting puddle depth. Preserve the existing strip amplitude and puddle low/high ratios. Asphalt hum remains rolling-only.

- [x] **Step 5: Split high-speed slip from low-speed wheelspin**

Keep combined-slip values for ABS and at-speed slip. For the ordinary slip layer use:

```python
if speed_kmh < LOW_SPEED_KMH:
    slip_left = max(spin_strength["fl"], spin_strength["rl"])
    slip_right = max(spin_strength["fr"], spin_strength["rr"])
    left_low += slip_left * 0.5 * slip_scale
    right_low += slip_right * 0.5 * slip_scale
else:
    slip_left = max(combined_slips["fl"], combined_slips["rl"])
    slip_right = max(combined_slips["fr"], combined_slips["rr"])
    left_low += max(0.0, slip_left - slip_threshold) * 0.5 * slip_scale
    right_low += max(0.0, slip_right - slip_threshold) * 0.5 * slip_scale
```

- [x] **Step 6: Add and pass rolling hysteresis coverage**

```python
def test_rolling_hysteresis_prevents_zero_speed_chatter(settings):
    mixer = HapticMixer()
    assert mixer.update(
        _telemetry(speed=0.3, rpm=1000.0, surface_rumble_fl=0.6),
        settings,
        now=1.0,
    ) == SILENT_FRAME

    started = mixer.update(
        _telemetry(speed=0.5, surface_rumble_fl=0.6), settings, now=1.1
    )
    held = mixer.update(
        _telemetry(speed=0.3, surface_rumble_fl=0.6), settings, now=1.2
    )
    stopped = mixer.update(
        _telemetry(speed=0.2, rpm=1000.0, surface_rumble_fl=0.6),
        settings,
        now=1.3,
    )

    assert started.left_high > 0.0
    assert held.left_high > 0.0
    assert stopped == SILENT_FRAME
```

Run:

```powershell
..\probe-venv\Scripts\python.exe -m pytest -q tests/haptics/test_mixer.py
```

Expected: all mixer tests pass.

- [x] **Step 7: Preserve the local working tree without committing**

Run `git diff --check -- src/modules/haptics/mixer.py tests/haptics/test_mixer.py` and expect exit code 0. Do not stage or commit.

---

### Task 3: Preserve Impacts and Correct ABS Activation

**Files:**
- Modify: `tests/haptics/test_mixer.py`
- Modify: `src/modules/haptics/mixer.py`

**Interfaces:**
- Consumes: existing jerk, smashable, suspension, gear, brake, and combined-slip telemetry.
- Produces: stationary chassis impulses plus speed-qualified ABS pulses.

- [x] **Step 1: Add stationary impact guard tests**

```python
def test_stationary_collision_remains_directional(settings):
    mixer = HapticMixer()
    mixer.update(_telemetry(speed=0.0, rpm=1000.0), settings, now=1.0)
    frame = mixer.update(
        _telemetry(speed=0.0, rpm=1000.0, accel_x=10.0), settings, now=1.01
    )

    assert frame.left_low > frame.right_low > 0.0
    assert frame.engine_amplitude == 0.0


def test_stationary_suspension_thud_remains_directional(settings):
    mixer = HapticMixer()
    mixer.update(
        _telemetry(speed=0.0, rpm=1000.0, suspension_travel_meters_fl=0.10),
        settings,
        now=1.0,
    )
    frame = mixer.update(
        _telemetry(speed=0.0, rpm=1000.0, suspension_travel_meters_fl=0.08),
        settings,
        now=1.02,
    )

    assert frame.left_low > frame.right_low
    assert frame.engine_amplitude == 0.0
```

Run both tests before further production edits. Expected: PASS, proving the implementation has not introduced the rejected whole-frame stationary gate.

- [x] **Step 2: Add the failing ABS speed test**

```python
def test_abs_requires_configured_minimum_speed(settings):
    mixer = HapticMixer()
    stopped = mixer.update(
        _telemetry(
            speed=0.0,
            rpm=1000.0,
            brake=255,
            tire_combined_slip_fl=9.0,
        ),
        settings,
        now=2.0,
    )
    moving = mixer.update(
        _telemetry(
            speed=settings.abs_min_speed_kmh,
            brake=255,
            tire_combined_slip_fl=9.0,
        ),
        settings,
        now=2.0,
    )

    assert stopped == SILENT_FRAME
    assert moving.left_low > 0.0
    assert moving.right_low > 0.0
```

Run the test and expect the stopped assertion to fail against the current hard-coded ABS rule.

- [x] **Step 3: Qualify ABS with existing settings**

Use combined slip, not low-speed burnout strength:

```python
brake_threshold = max(1.0, _setting(settings, "abs_brake_threshold", 100.0))
abs_min_speed = _setting(settings, "abs_min_speed_kmh", 15.0)
abs_slip_threshold = _setting(settings, "abs_combined_slip_threshold", 1.0)
combined_left = max(combined_slips["fl"], combined_slips["rl"])
combined_right = max(combined_slips["fr"], combined_slips["rr"])
if (
    brake >= brake_threshold
    and speed_kmh >= abs_min_speed
    and max(combined_left, combined_right) > abs_slip_threshold
    and int(now * 15.0) % 2 == 0
):
    left_low += 0.5 * slip_scale
    right_low += 0.5 * slip_scale
```

- [x] **Step 4: Run event and full mixer tests**

Run:

```powershell
..\probe-venv\Scripts\python.exe -m pytest -q tests/haptics/test_mixer.py
```

Expected: all tests pass, including stationary impact guards and ABS comparison.

- [x] **Step 5: Preserve the local working tree without committing**

Run `git diff --check -- src/modules/haptics/mixer.py tests/haptics/test_mixer.py` and expect exit code 0. Do not stage or commit.

---

### Task 4: Correct User Guidance Without Changing Runtime Activation

**Files:**
- Modify: `tests/test_haptic_settings.py`
- Modify: `src/modules/gui/settings_tab.py`
- Modify: `src/modules/tui/settings_tab.py`
- Modify: `src/lang/de.py`
- Modify: `src/lang/ja.py`
- Modify: `src/lang/ru.py`
- Modify: `src/lang/tr.py`
- Modify: `src/lang/zh.py`
- Modify: `src/lang/zh_tw.py`
- Modify: `README.md`
- Modify: `docs/ReadmeZH.md`

**Interfaces:**
- Consumes: the shared English translation key used by GUI and TUI setting sections.
- Produces: conditional conflict guidance that does not claim body haptics depend on the in-game vibration option.

- [x] **Step 1: Change the expected label first**

Replace the old warning in `BODY_LABELS` with:

```python
"Automatically uses high-fidelity USB audio or Bluetooth compatible rumble. "
"Disable in-game vibration only if you feel competing or doubled output."
```

Run:

```powershell
..\probe-venv\Scripts\python.exe -m pytest -q tests/test_haptic_settings.py
```

Expected: FAIL because GUI, TUI, and non-English catalogs still use the old key.

- [x] **Step 2: Update GUI, TUI, and every non-English catalog**

Use the exact new English key in both setting tabs. Replace the corresponding key/value in all six catalogs with a natural translation that retains both facts: USB/Bluetooth selection is automatic, and disabling in-game vibration is conditional on felt conflict or doubled output.

- [x] **Step 3: Update README guidance**

Document these exact behavioral distinctions in both English and Chinese documentation:

- true stationary idle is silent;
- stationary revving and drivetrain-aware burnouts remain active;
- road material is applied only with rolling or wheelspin excitation;
- body haptics do not require the Forza vibration option;
- disable the option only when native/Steam output competes with or doubles the synthesized output.

- [x] **Step 4: Run settings, translation, and whitespace checks**

Run:

```powershell
..\probe-venv\Scripts\python.exe -m pytest -q tests/test_haptic_settings.py
git diff --check -- src/modules/gui/settings_tab.py src/modules/tui/settings_tab.py src/lang README.md docs/ReadmeZH.md
```

Expected: test pass and `git diff --check` exit code 0.

- [x] **Step 5: Preserve the local working tree without committing**

Do not stage or commit the documentation and translations.

---

### Task 5: Full Verification, Build, and USB Hardware Check

**Files:**
- Modify: `docs/superpowers/specs/2026-07-12-physical-body-haptics-gating-design.md`
- Create outside repository: `outputs/FH-DualSense-v1.6.2-physical-haptics-local.exe`
- Create outside repository: `outputs/physical-haptics-verification.md`

**Interfaces:**
- Consumes: completed source, tests, packaging spec, connected USB DualSense, and user confirmation.
- Produces: verified local executable and evidence summary without Git integration.

- [x] **Step 1: Run focused and complete automated verification**

Run:

```powershell
..\probe-venv\Scripts\python.exe -m pytest -q tests/haptics/test_mixer.py
..\probe-venv\Scripts\python.exe -m pytest -q
& 'C:\ProgramData\anaconda3\Scripts\ruff.exe' check src/modules/haptics tests/haptics/test_mixer.py tests/test_haptic_settings.py
..\probe-venv\Scripts\python.exe -m compileall -q src tests packaging
git diff --check
```

Expected: focused tests pass, complete suite passes with the new test count, Ruff passes over changed code, compile succeeds, and diff check exits 0.

- [x] **Step 2: Build a new local executable**

Use the existing Windows PyInstaller spec in a new build directory so the previous known-good executable is preserved. Verify `--help` exits 0 and the archive still contains PortAudio, NumPy, and `docs\\THIRD_PARTY_NOTICES.md`.

- [x] **Step 3: Run a controlled USB physical sequence after notifying the user**

Use production mixer and manager paths with telemetry frames for five labeled phases, silencing between phases:

1. true stationary idle, expected no grip vibration;
2. stationary revving, expected centered engine vibration;
3. stationary rear-wheel-drive burnout on tarmac, expected driven-side slip plus engine;
4. the same burnout with rough/water material inputs, expected a distinct texture;
5. moving directional road texture, expected left/right material direction.

Keep each active phase short, send `SILENT_FRAME` between phases, preserve trigger output, and close the audio stream in `finally`.

- [x] **Step 4: Ask the user for phase-by-phase physical confirmation**

Record whether idle is silent, rev follows RPM, burnout is directional, material changes are distinguishable, and moving surface direction is correct. If a phase is wrong, return to the corresponding focused test before tuning.

- [x] **Step 5: Refresh local deliverables and verification evidence**

Copy the verified executable and updated design to `outputs`, calculate SHA-256, and create `outputs/physical-haptics-verification.md` with automated results, hardware observations, known baseline lint warnings, and the untouched local Git state.

- [x] **Step 6: Final local-only audit**

Run:

```powershell
git status --short --branch
git diff --check
```

Expected: implementation remains modified/untracked in the local working tree, `main` remains ahead only by the earlier design commit, and no remote operation has occurred.
