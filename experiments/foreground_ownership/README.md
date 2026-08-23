# Foreground ownership experiment (not shipped in R11)

This directory preserves the Windows-only experiment that tied physical
DualSense ownership to the foreground FH4/FH5/FH6 process. It is deliberately
outside `src/`, has no package initializer, and must not be imported by runtime
code, tests, or the PyInstaller specification used for R11.

R11 uses the regular backend lifetime: while FH-DualSense-Enhanced is running,
its native backend may enumerate and hold the selected physical DualSense.
Switching to the desktop or another game does not release that handle. No R10
backup build or R11 listener build is part of the current pull request or
release plan.

Preserved material:

- `reference/xinput_service_with_foreground_gate.py` — the complete gated
  service implementation, including the detector and child-generation logic.
- `reference/process_watch_with_foreground.py` — the Win32 foreground PID and
  exact executable lookup.
- `reference/passive_detection.py` — handle-free Configuration Manager and
  Bluetooth presence detection used while the gate was closed.
- `reference_tests/test_passive_detection.py` — the matching reference tests.
- `integration/dualsense_runtime_gate_removal.patch` — the exact production
  integration removed from the native DualSense worker for R11. Removed lines
  preserve the runtime gate, deferred startup pulse, passive waiting state, and
  candidate-open race checks.

These files are archival reference code, not a supported executable path. A
future release may revive the experiment only by moving reviewed code back into
`src/`, restoring focused tests, and explicitly adding it to that release's
architecture and packaging contract.
