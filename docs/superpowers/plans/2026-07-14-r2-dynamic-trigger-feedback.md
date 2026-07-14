# Enhanced R2 Dynamic Trigger Feedback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the existing wheelspin and ABS trigger effects with telemetry-driven dynamic intensity, timing stabilization, surface signatures, a GT7-style zoned ABS wall, and profile-scoped advanced tuning.

**Architecture:** Keep `TriggerAnimations` as the state owner and `Controller` as the priority arbiter. Add one small time-based EWMA helper and effect-local latches, emit existing adaptive-trigger frames, and leave USB/Bluetooth/DSX transport boundaries unchanged. Mirror normal and collapsed experimental settings across GUI and TUI.

**Tech Stack:** Python 3.13, dataclasses, pytest, CustomTkinter, Textual, existing DualSense adaptive-trigger protocol and DSX UDP adapter.

## Global Constraints

- Work in `.worktrees/r2-trigger-dynamics` on `feat/r2-trigger-dynamics`.
- Use the approved design in `docs/superpowers/specs/2026-07-14-r2-dynamic-trigger-feedback-design.md`.
- Write a failing test before each production behavior.
- Preserve `Controller` effect priority and transport-independent frame generation.
- Preserve body haptics behavior and the USB/Bluetooth output-report implementation.
- Keep all new tuning fields profile-scoped and GUI/TUI field sets identical.
- Do not change version or release metadata until behavior and hardware verification are complete.

---

### Task 1: Lock Signal Helpers and Settings Defaults

**Files:**
- Create: `tests/forzahorizon/test_effects.py`
- Modify: `src/modules/forzahorizon/effects.py`
- Modify: `src/modules/config/settings.py`
- Modify: `tests/fixtures/community_defaults_2323.json`

- [x] Add telemetry and settings fixtures plus failing tests for a time-based asymmetric EWMA, clamping, and reset.
- [x] Implement the minimal helper using `time.monotonic()` compatible seconds and exponential `dt` mapping.
- [x] Add normal and advanced R2 fields with conservative defaults, and lock those defaults in the community fixture.
- [x] Run `uv run --project src pytest -q tests/forzahorizon/test_effects.py tests/test_community_defaults.py`.

### Task 2: Implement Dynamic Driven-Wheel Wheelspin

**Files:**
- Modify: `tests/forzahorizon/test_effects.py`
- Modify: `src/modules/forzahorizon/effects.py`

- [x] Add failing tests for longitudinal driven-wheel selection and rejection of non-driven or lateral-only slip.
- [x] Add failing tests for throttle gating, low-speed raw rotation and hysteresis.
- [x] Add failing tests for asymmetric attack/release and telemetry-off state reset.
- [x] Add failing tests proving tarmac, water, dirt and gravel retain distinct dynamic frequency bands.
- [x] Implement normalized slip, dominant-wheel surface selection, EWMA, mild G damping, and dynamic amplitude/frequency.
- [x] Run the focused effects tests and `tests/haptics/test_mixer.py` to confirm body haptics did not regress.

### Task 3: Implement GT7-Style ABS Wall

**Files:**
- Modify: `tests/forzahorizon/test_effects.py`
- Modify: `src/modules/forzahorizon/effects.py`
- Modify: `tests/dsx/test_client.py`

- [x] Add failing tests for speed/brake gating and longitudinal slip as the primary ABS signal.
- [x] Add failing tests for weaker combined-slip assistance, dynamic frequency/amplitude, top-three-zone wall, and 100 ms hold.
- [x] Implement zoned `vibrate_zones()` output and the ABS deadline state.
- [x] Add or refine a DSX test proving zoned native output intentionally falls back to dynamic vibration.
- [x] Run `uv run --project src pytest -q tests/forzahorizon/test_effects.py tests/dsx/test_client.py`.

### Task 4: Add Normal and Collapsed Experimental Settings

**Files:**
- Modify: `src/modules/gui/settings_tab.py`
- Modify: `src/modules/gui/system_tab.py`
- Modify: `src/modules/tui/settings_tab.py`
- Modify: `src/modules/tui/system_tab.py`
- Modify: `src/lang/de.py`
- Modify: `src/lang/ja.py`
- Modify: `src/lang/ru.py`
- Modify: `src/lang/tr.py`
- Modify: `src/lang/zh.py`
- Modify: `src/lang/zh_tw.py`
- Modify: `tests/test_haptic_settings.py`

- [x] Add failing AST-level parity tests for `EXPERIMENTAL_SECTIONS`, ranges, profile scope and catalog coverage.
- [x] Move low-level ABS tuning out of the normal section, add wheelspin/ABS sensitivity there, and add all advanced fields to mirrored experimental sections.
- [x] Implement an initially collapsed GUI card and Textual `Collapsible`, each with the warning “不建议自行调节” through localization.
- [x] Ensure System tabs do not render the R2 experimental section.
- [x] Run `uv run --project src pytest -q tests/test_haptic_settings.py`.

### Task 5: Regression, Documentation and Hardware Handoff

**Files:**
- Modify: `docs/PROJECT_STATE.md`
- Modify: `docs/superpowers/specs/2026-07-14-r2-dynamic-trigger-feedback-design.md`
- Modify: `docs/superpowers/plans/2026-07-14-r2-dynamic-trigger-feedback.md`

- [x] Run focused tests after every task and mark completed plan checkboxes.
- [x] Run `uv run --project src pytest -q` and `git diff --check`.
- [x] Audit `git diff --stat`, `git status --short --branch`, settings parity and version metadata.
- [x] Record implemented behavior separately from pending USB, Bluetooth and DSX physical verification in `docs/PROJECT_STATE.md`.
- [ ] Perform phase-separated hardware tests with the user before changing R2 version or publishing a release.
