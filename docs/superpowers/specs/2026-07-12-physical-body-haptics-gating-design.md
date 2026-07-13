# Physical Body Haptics Gating Design

## Scope

This change refines the body haptics implemented locally in
`Forza-Horizon-DualSense-Python`. `HorizonHaptics` remains the reference for
layered USB audio haptics. The target stays a single program with both USB and
Bluetooth support. Adaptive trigger behavior is outside this change.

All work remains local. The user authorized integration as a local commit on
`main`; pushing, opening a pull request, or any other remote write remains out
of scope.

## Problem

The current mixer copies the reference engine curve, including a fixed `0.08`
engine amplitude whenever valid RPM telemetry is present. Therefore a vehicle
that is stationary, has no throttle input, and is sitting at idle RPM still
drives both grips continuously.

A global speed gate is not a valid fix. It would also suppress real stationary
events such as revving the engine, spinning driven wheels, being hit by another
vehicle, or compressing the suspension.

The desired model is:

`body haptic output = material signature multiplied by physical excitation`

Road material determines the character of tire contact feedback. Rolling,
slip, wheelspin, water displacement, suspension motion, or impact determines
whether energy exists and how strong it is. Material alone must not create a
continuous vibration while nothing is moving or changing.

## Reference Boundary

The following `HorizonHaptics` source separation is retained:

- engine vibration with a 40 to 120 Hz RPM mapping;
- directional surface texture in the high-frequency channels;
- puddle drag in low-frequency channels plus splash texture in high-frequency
  channels;
- directional tire slip in low-frequency channels;
- ABS pulses;
- suspension thuds, gear kicks, and directional collisions.

The reference activation conditions are not copied blindly. In particular,
its unconditional idle engine floor and ungated stationary surface values are
the source of non-physical continuous output.

## Derived Physical State

### Rolling state

The mixer owns a small hysteresis state to reject telemetry jitter around zero:

- enter rolling at `speed >= 0.5 km/h`;
- remain rolling until `speed <= 0.2 km/h`;
- reset rolling state only when body haptics are disabled, telemetry leaves the
  race, UDP telemetry is lost, or the mixer is explicitly reset.

The rolling state controls tire-road contact sources only. It never gates the
entire haptic frame.

### Engine activity

The engine is active when any of these conditions is true:

- the vehicle is rolling;
- raw accelerator input is greater than `1`;
- current RPM is more than `max(100 RPM, 5 percent of idle RPM)` above idle.

When active, the existing reference curve remains:

- frequency: 40 Hz at idle to 120 Hz at redline;
- amplitude: `0.08 + throttle * 0.25 + rpm_ratio * 0.10`, followed by the
  existing engine and master intensity settings.

When inactive, both engine frequency and amplitude are zero. This makes a true
stationary idle silent while preserving a stationary throttle blip and the RPM
falloff after the driver releases the throttle.

### Low-speed wheelspin

Near zero vehicle speed, Forza combined-slip values are not reliable. The body
haptics mixer reuses the target project's existing trigger-domain rules:

- below `5 km/h`, require accelerator input at or above the configured
  accelerator dead zone;
- select driven wheels from `drive_train`;
- treat an individual driven wheel as spinning only when its absolute raw wheel
  rotation speed exceeds `30 rad/s`;
- scale grip energy continuously with rotation above that threshold rather than
  producing a fixed on/off buzz.

At `5 km/h` and above, directional `tire_combined_slip` and the existing slip
threshold remain authoritative.

### Excited tire contacts

A wheel has tire-road excitation when either:

- the vehicle is rolling; or
- that driven wheel is confirmed as low-speed wheelspin.

Surface rumble, rumble-strip geometry, and puddle depth contribute only for an
excited wheel. This gives the following behavior:

- a parked tire resting on gravel, a rumble strip, or in water is not a source
  of continuous energy;
- normal driving retains directional road texture;
- a stationary burnout activates only the spinning driven wheels;
- tarmac, dirt, gravel, rumble-strip, and water telemetry continue to produce
  distinct low/high-frequency mixtures during rolling or wheelspin.

The target project's existing wheelspin surface thresholds define the material
profile rather than introducing unrelated categories:

- surface rumble at or below `0.10` is tarmac-like and stays primarily in the
  high-frequency texture channel;
- values above `0.10` are loose dirt and add a modest low-frequency component;
- values above `0.30` are gravel or rocks and add a stronger low-frequency
  component while retaining granular high-frequency texture;
- puddle depth keeps the reference water mix of low-frequency drag and
  high-frequency splash.

This is not a generic speed-scaled rumble. Material telemetry still selects the
texture, and the actual contact motion supplies its energy.

## Source Activation Matrix

| Source | Activation rule | Stationary behavior |
|---|---|---|
| Engine | Rolling, throttle input, or RPM clearly above idle | Revving remains active; true idle is silent |
| Surface texture | Per-wheel excited contact | Silent without rolling or driven-wheel spin |
| Rumble strip | Per-wheel excited contact plus strip geometry | A burnout on a strip remains active |
| Puddle | Per-wheel excited contact plus puddle depth | Wheelspin in water retains drag and splash |
| Tire slip | Combined slip at speed; driven raw wheel rotation at low speed | Burnout remains directional and drivetrain-aware |
| Collision and smashable | Jerk or velocity-difference event | Always allowed |
| Suspension | Per-wheel suspension delta event | Always allowed |
| Gear kick | Existing gear change and speed above `3 km/h` | Not armed while parked |
| ABS | Brake threshold, configured minimum speed, and slip | Not armed from zero-speed slip noise |

Collision and suspension remain chassis impulses. They are not suppressed by
stationary road rules. Concurrent tire contact texture is layered only when a
wheel has actual contact excitation, so road material remains meaningful
without becoming a permanent background vibration.

## State Handling

Stationary telemetry must not call `reset()` and must not return early. The
mixer continues updating acceleration, suspension, gear, collision-envelope,
and shift state so real stationary impacts remain detectable and later movement
does not create stale deltas.

The existing reset behavior for disabled haptics, menus, lost telemetry, and
shutdown remains unchanged.

## USB and Bluetooth

The mixer produces the same physical `HapticFrame` for both transports:

- USB streams the four low/high channels and engine oscillator to the DualSense
  audio endpoint;
- Bluetooth converts the same frame to compatible low/high motor output;
- adaptive trigger frames continue through the existing atomic controller
  update and are not gated by body-haptics state.

## Game Vibration Setting

The new logic does not use the Forza vibration option as an activation gate.
Direct engine, collision, suspension, wheel-rotation, puddle, and strip signals
remain telemetry-driven. Some `surface_rumble` values may still vary with the
game option, so the documentation should describe disabling game vibration as
a conditional conflict-avoidance step rather than as a requirement for body
haptics to work.

## Regression Tests

The implementation must first add tests that fail against the current mixer:

1. True stationary idle produces `SILENT_FRAME`.
2. Stationary revving produces engine output but no tire-road texture without
   wheel motion.
3. A stationary burnout uses only the driven wheels and works when combined
   slip is zero.
4. The same burnout produces distinct frames for tarmac, dirt, gravel, and
   water telemetry.
5. Parked stale surface, puddle, rumble-strip, and combined-slip values do not
   create continuous output without physical excitation.
6. Moving surface texture remains directional.
7. A stationary collision and suspension change still produce their event
   impulses.
8. ABS is silent below its minimum speed and remains active above it.
9. Stopping and starting around the hysteresis thresholds does not chatter or
   create a false collision, suspension, or gear event.

After the focused tests pass, run the complete suite, Ruff over the changed
scope, compile checks, packaging tests, and USB/Bluetooth transport regressions.

## Acceptance Criteria

- No continuous grip vibration at true stationary idle.
- Stationary revving follows throttle and RPM.
- Stationary burnouts remain directional and road-material-aware.
- Road materials remain distinct whenever tire contact has physical excitation.
- Stationary collision and suspension events remain available.
- USB and Bluetooth behavior share the same mixer rules.
- Adaptive trigger output is unchanged.
- Git integration is limited to a local `main` commit; no remote write occurs.

## Implementation Verification

- Focused verification passed: mixer `36 passed` and DualSense `15 passed`.
- Complete automated verification passed: `88 passed`; scoped Ruff,
  `compileall`, and `git diff --check` all exited 0.
- A fresh PyInstaller EXE built from `packaging/windows/fhds.spec`; `--help`
  exited 0, and archive inspection confirmed PortAudio, NumPy runtime files,
  and `docs\THIRD_PARTY_NOTICES.md`.
- The verified EXE is `37,834,629` bytes with SHA-256
  `F040573B0116D7E41AE9B6CE08F2E51E76F4BB569461EEC2A4058FF3E403B33C`.
- Two controlled USB probe runs used the production mixer and manager paths.
  Both exited 0, opened the DualSense audio endpoint, emitted all five
  technical phase frames with silent transitions, and reached final
  silence/audio-stream close.
- The user waived further phase-by-phase sensation grading after those two
  successful technical runs and accepted the implementation for local
  integration. Final-code evaluation reproduced the same full-excitation phase
  frames; deterministic tests additionally cover the proportional stationary
  material ramp and Bluetooth release-frame race. No remote operation was
  performed.
