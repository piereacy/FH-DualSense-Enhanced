# DualSense Body Haptics Design

Date: 2026-07-12

Target project: `HamzaYslmn/Forza-Horizon-DualSense-Python`

Reference projects:

- `haritha99ch/HorizonHaptics` at `79fbe2fd7a56e21bd101867dbf14718f2e91ffab`
- `shiftedx/dualsense-command` at `5a5ecfc6bbb29e51afa5e3c55c0b5b64886c080d`

## Goal

Add native DualSense body haptics to Forza-Horizon-DualSense-Python without
regressing its adaptive triggers, reconnect behavior, UI modes, or UDP drain
loop.

The first implementation uses the DualSense USB four-channel audio endpoint for
high-fidelity left and right actuator waveforms. Bluetooth support is part of
the design from the start and uses compatible rumble as a lower-fidelity
fallback. Both transports consume the same telemetry-derived haptic frame.

HorizonHaptics is a reference for effect selection and USB audio routing. It is
not a second runtime process and is not modified by this work. The final code is
implemented inside Forza-Horizon-DualSense-Python.

## Confirmed hardware behavior

The development DualSense has been probed in both transports with hidapi 0.15.0:

- Bluetooth enumerates as bus type 2 and streams 78-byte input reports with
  report ID `0x31`.
- USB enumerates as bus type 1 on the gamepad interface.
- USB exposes a Windows WASAPI output endpoint with four channels at 48 kHz.
- Forza's four `WheelInPuddleDepth` fields are 32-bit floats in the official
  Data Out layout; the existing integer decoding must be corrected for usable
  water-depth effects.
- The observed WASAPI endpoint reports a low output latency of about 3 ms.
- Bluetooth does not expose the four-channel audio endpoint on this Windows
  system.

These observations define the initial transport policy. USB gets audio
haptics, while Bluetooth receives a compatible-rumble downmix through HID.

## Scope

The first complete release includes:

- A transport-neutral body haptic frame and Forza telemetry mixer.
- Engine, road surface, rumble strip, suspension, collision, gear shift,
  puddle, tire slip, and ABS effects.
- USB audio synthesis and routing to DualSense output channels 3 and 4, which
  are zero-based channel indexes 2 and 3.
- Bluetooth compatible-rumble downmix in the existing DualSense HID report.
- Automatic backend selection on connection and transport changes.
- GUI and TUI settings with persistence and translations.
- Automated unit tests and USB and Bluetooth hardware smoke tests.

## Non-goals

- Sending full audio-quality haptics over Bluetooth HID.
- Changing the DSX protocol or adding body haptics to the DSX backend.
- Modifying HorizonHaptics or running it beside this application.
- Replacing the current adaptive-trigger algorithms.
- Capturing or mixing vibration commands from another process.
- Adding manual audio-device selection in the first release. Automatic
  DualSense endpoint discovery is sufficient for the confirmed hardware.

## Architecture

### Transport-neutral frame

Add a small `modules/haptics` package containing an immutable haptic frame:

```python
@dataclass(frozen=True, slots=True)
class HapticFrame:
    left_low: float = 0.0
    left_high: float = 0.0
    right_low: float = 0.0
    right_high: float = 0.0
    engine_hz: float = 0.0
    engine_amplitude: float = 0.0
```

All amplitudes are finite values clamped to `0.0..1.0`. `engine_hz` is zero for
silence and otherwise clamped to the supported engine waveform range. A shared
`SILENT_FRAME` constant represents idle, menu, disconnect, and shutdown state.

### Haptic mixer

`HapticMixer.update(telemetry, settings, now)` is pure with respect to hardware.
It may retain only the previous telemetry values and short event deadlines
required to detect collision jerk, suspension compression, and gear changes.
It returns one `HapticFrame` per parsed packet.

The mixer is independent from NumPy, sounddevice, hidapi, GUI code, and the
adaptive-trigger controller. This makes effect behavior deterministic and
unit-testable.

### Haptic manager

`HapticManager` owns lifecycle and transport selection:

- Disabled setting: hold a silent frame and do not claim HID rumble fields.
- Native DualSense over USB: start the USB audio backend and return no HID
  rumble payload.
- Native DualSense over Bluetooth: stop USB audio and return a compatible
  rumble payload for the next combined HID report.
- Disconnected or unknown transport: stop active output and remain silent.
- DSX backend: remain disabled and log one explanatory message.

The manager observes a read-only transport property exposed by the native
`DualSense` backend. It re-evaluates transport after reconnect, hot-swap, or a
settings change. Backend startup failures are contained inside the manager.

### Atomic trigger and Bluetooth output

Bluetooth rumble must be written in the same HID report as the adaptive trigger
commands. Separate `set_trigger` and `set_rumble` writes could overwrite each
other or double the report rate.

Extend the native writer surface compatibly:

```python
ds.set(left_trigger, right_trigger, rumble=None)
```

Existing callers continue to work because `rumble` defaults to `None`. `None`
means the writer leaves rumble flags and motor bytes unclaimed, preserving the
current output exactly. A rumble object contains normalized low-frequency and
high-frequency amplitudes.

The I/O queue stores triggers and optional compatible rumble as one pending
frame. State-change suppression compares the full encoded state, so a changing
Bluetooth body effect can produce a write even when the triggers are unchanged.
USB audio amplitude updates do not cause extra HID reports.

## Data flow

```text
Forza UDP packet
    -> parse_packet
    -> adaptive-trigger Controller.update
    -> HapticMixer.update
    -> HapticManager route by native transport
        -> USB audio target update
        -> or Bluetooth rumble downmix
    -> one atomic DualSense.set call when HID state changes
```

The existing `recv_latest()` behavior remains unchanged. Audio rendering never
runs on the UDP thread. The UDP loop only publishes the latest immutable frame
to the audio backend.

If no packet arrives for one second, both trigger effects and body haptics are
set to their silent state. Shutdown also sends or renders silence before closing
the HID and audio resources.

`loop.run` creates the mixer and manager once and closes the manager in a
`finally` block. This covers headless, TUI, GUI, game-close, stop-event, and
exception exits without duplicating lifecycle logic across entry points.

## Effect model

The initial mixer uses telemetry fields that the project already parses.

### Engine

Normalize current RPM between idle RPM and maximum RPM. Map this ratio to a
roughly 40 to 120 Hz engine waveform. Amplitude combines a small idle component,
throttle position, and RPM ratio. The waveform is sent equally to both sides,
while directional effects remain independent.

### Road and rumble strips

Per-wheel surface rumble is grouped by side. Front-left and rear-left drive the
left high-frequency layer; front-right and rear-right drive the right layer.
Rumble-strip flags add a stronger textured contribution. A small speed-scaled
asphalt component avoids a completely dead chassis on smooth roads.

### Suspension

Track previous suspension travel per wheel. A sufficiently fast compression
adds a short low-frequency thud on the matching side. The threshold is a
setting-backed constant rather than a literal hidden inside the mixer.

### Collision and smashables

Use acceleration jerk and smashable velocity difference to detect impacts.
Lateral acceleration biases the impact toward the corresponding side. Head-on
or rear impacts feed both sides. Event envelopes decay over a short deadline
instead of relying on one UDP packet.

### Gear shift

A gear change while moving creates a short, centered low-frequency kick. The
event is suppressed during menu telemetry and invalid gear transitions.

### Puddles

Per-wheel puddle depth adds low-frequency drag and a smaller high-frequency
splash component on the matching side.

### Tire slip and ABS

Combined tire slip above a configurable threshold creates a side-specific
low-frequency loss-of-grip effect. Hard braking plus high slip adds a centered
pulse at a stable time-based cadence. It reuses the intent of the current ABS
trigger settings but has its own body-haptic intensity control.

### Mixing and smoothing

Each effect is scaled before summing. Non-finite telemetry values contribute
zero. The final layers are clamped to `0.0..1.0`. Attack and release smoothing
is applied at the audio block boundary so packet jitter cannot create clicks.
Event deadlines use an injected monotonic timestamp to keep tests deterministic.

## USB audio backend

The USB backend uses NumPy and sounddevice:

- Prefer Windows WASAPI.
- Select an output device whose name includes `DualSense` or
  `Wireless Controller` and that exposes at least four output channels.
- Use 48 kHz, float32, and the device's supported four-channel layout.
- Keep headphone channels 1 and 2 silent.
- Route the left actuator to output channel 3 and the right actuator to output
  channel 4.
- Generate low-frequency sine, high-frequency textured tone, and engine
  waveform components in the audio callback.
- Reuse arrays and oscillator state where practical to avoid callback pressure.
- Fill the output buffer with silence whenever the feature is disabled,
  telemetry is stale, or the backend is stopping.

Audio target exchange is protected by a short lock or an atomic snapshot. The
callback never parses telemetry, logs repeatedly, opens devices, or performs
HID writes.

Hardware validation confirmed that the four-channel USB audio endpoint drives
the actuators without an additional HID mode flag. The implementation therefore
does not copy HorizonHaptics' unverified `0x20` output bit. The official Linux
driver assigns that field to speaker-volume control, so setting it here could
change unrelated controller state.

Windows WASAPI is the hardware-validated first target. On Linux, the backend may
select an ALSA device with the same name and channel requirements when
sounddevice and PortAudio are available. If they are unavailable, body haptics
is disabled while the existing Linux trigger path continues unchanged.

## Bluetooth fallback

Bluetooth receives a frequency-priority downmix because compatible rumble has
two amplitude channels rather than four independent audio layers:

- Low-frequency output is `clamp(max(left_low, right_low) +
  0.5 * engine_amplitude)`.
- High-frequency output is `clamp(max(left_high, right_high))`.
- Both values are clamped and converted to `0..255` only in the HID encoder.

This preserves frequency character and strong events but not USB stereo
direction. The limitation is explicit rather than pretending the two rumble
amplitudes can represent four audio layers.

The native DualSense layout dictionaries gain explicit motor offsets. When a
rumble payload is present, the encoder sets the compatible-rumble and
rumble-selection flags and fills the motor bytes. When absent, those bytes and
flags stay zero exactly as before.

The current project's USB and Bluetooth report header, trigger offsets, report
length, and CRC path remain unchanged during the first implementation. Protocol
references use a different Bluetooth common-payload offset in some encoders, so
the existing working trigger layout must not be replaced without a separate
live regression test. The connected controller is used to validate the final
motor flags and offsets.

Full Bluetooth audio haptics is deferred. It can later become another backend
without changing `HapticMixer` or the UDP integration.

## Settings and persistence

Add profile-scoped fields to `modules/config/settings.py`:

- `enable_body_haptics`, default `False`
- `body_haptics_intensity`, default `1.0`
- `engine_haptics_intensity`, default `1.0`
- `road_haptics_intensity`, default `1.0`
- `impact_haptics_intensity`, default `1.0`
- `slip_haptics_intensity`, default `1.0`
- `slip_haptics_threshold`, default `0.8`
- `collision_haptics_jerk_threshold`, default `3.0`
- `collision_haptics_duration_ms`, default `150.0`
- `suspension_haptics_delta_threshold`, default `0.015`

Gear-shift body duration reuses the existing `gear_shift_duration_ms` setting.
Defaults may be tuned after recorded telemetry and hardware validation, but no
numeric threshold is hidden inside the mixer.

These values remain profile-scoped and therefore are not added to
`preferences.GLOBAL_FIELDS`. Transport selection is automatic and is not a
user setting in the first release.

Mirror the new sections in both GUI and TUI settings tables. Add translations
to every existing language module, using clear fallback English if a native
translation needs later refinement. Changes save through the existing
preferences mechanism.

## Error handling

- Missing NumPy or sounddevice: log once, disable USB body haptics, continue
  triggers and telemetry.
- No matching four-channel endpoint: log once with a USB connection hint and
  continue normally.
- Audio callback status: rate-limit diagnostics and always provide a valid
  output buffer.
- Audio stream failure: stop and close the stream, mark USB haptics unavailable,
  and keep the main loop alive.
- HID failure: write silence before closing a usable handle, preserve the last
  desired frame, and requeue it after a successful reconnect.
- Invalid telemetry: discard only the bad contribution or frame, never the
  controller connection.
- DSX selected: body haptics remains inactive and reports the limitation once.

No haptic exception may terminate `loop.run`.

## Dependencies and packaging

Add compatible Python 3.13 versions of `numpy` and `sounddevice` to
`src/pyproject.toml`. Confirm they are included by the ZUV build and Windows
standalone packaging path. USB dependency imports remain guarded so headless or
Bluetooth-only startup can report dependency problems cleanly.

Add the chosen test runner as a development-only dependency rather than a
runtime dependency. A Linux dependency or PortAudio failure must not prevent
the existing trigger-only application from starting, so platform markers or an
optional import path are required where packaging support differs.

HorizonHaptics is MIT licensed. If implementation copies or substantially
adapts its audio synthesis code, preserve its copyright and MIT notice in a
third-party notices file. Prefer independently structured code while retaining
clear attribution for the effect and channel-routing reference.

## Automated tests

Introduce a test directory and use deterministic fakes. Tests cover:

- Silent and disabled mixer output.
- Per-side road, suspension, puddle, and slip routing.
- Engine frequency and amplitude bounds.
- Collision and gear event timing.
- ABS cadence with an injected clock.
- Non-finite input sanitization and final clamping.
- Manager selection for USB, Bluetooth, disconnect, and DSX.
- USB endpoint selection using fake sounddevice metadata.
- Audio callback channel routing and silent stop behavior.
- Existing `ds.set(left, right)` report bytes remain unchanged.
- Rumble flags and motor offsets appear only when a payload is present.
- Bluetooth CRC is recomputed after rumble bytes are written.
- Trigger and rumble state changes are queued atomically.

Tests must be written before each production behavior and observed failing for
the expected reason before implementation.

## Hardware validation

### USB

1. Confirm the selected WASAPI endpoint is four-channel and 48 kHz.
2. Run a low-intensity left-only and right-only actuator pulse.
3. Confirm headphone channels remain silent.
4. Confirm trigger preview still works while audio haptics is active.
5. Feed recorded or emulated telemetry and verify each effect category.
6. Stop telemetry and confirm the actuators become silent within one second.
7. Close the application and confirm no residual audio or trigger effect.

### Bluetooth

1. Switch the same controller to Bluetooth and confirm automatic transport
   detection.
2. Run low and high compatible-rumble pulses at conservative intensity.
3. Confirm the adaptive triggers and rumble coexist in one report.
4. Validate report length, flags, motor bytes, and CRC with unit tests and live
   response.
5. Exercise disconnect and reconnect with a nonzero pending effect.
6. Confirm no motor flags are set when body haptics is disabled.

Hardware tests begin at low intensity and always finish by sending silence.

## Acceptance criteria

- USB gameplay produces responsive, directional body haptics from Forza
  telemetry through the DualSense audio actuators.
- Bluetooth gameplay retains the same effect categories through a documented
  lower-fidelity compatible-rumble downmix.
- Adaptive triggers behave as before on USB and Bluetooth.
- Disabling body haptics produces byte-compatible trigger-only reports.
- Missing audio hardware or dependencies cannot stop the service.
- Stale telemetry, disconnect, backend swap, and shutdown all end in silence.
- GUI, TUI, profiles, headless mode, ZUV packaging, and reconnect behavior have
  regression coverage proportional to the change.

## Implementation order

1. Add deterministic frame, mixer tests, and mixer implementation.
2. Add USB endpoint-selection and callback tests, then the USB audio backend.
3. Add manager lifecycle and loop integration tests.
4. Add atomic rumble payload support to the native HID writer.
5. Add Bluetooth downmix tests and live Bluetooth validation.
6. Add settings, GUI, TUI, translations, packaging, and documentation.
7. Run the full automated suite and both hardware smoke-test checklists.
