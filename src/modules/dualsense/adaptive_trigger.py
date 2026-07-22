"""DualSense adaptive trigger effect primitives (game-agnostic).

Every public function returns a `(mode_byte, params_tuple)` HID frame ready
to hand to `DualSense.set(left, right)`. No game-specific logic lives here.
"""
import math
import time

# --- Raw mode/effect bytes ---

M_OFF            = 0x05  # reset to neutral
M_VIBRATE        = 0x06  # Simple_Vibration (single zone buzz)
M_RIGID          = 0x01  # Static_Resistance
M_RIGID_ZONES    = 0x21  # Feedback: per-zone resistance (10 slots)
M_VIBRATE_ZONES  = 0x26  # Vibration: per-zone amplitude + frequency

# Hidden firmware effects - unique behavior, may be removed someday
M_BOW            = 0x22  # resist start..end then snap back
M_GALLOP         = 0x23  # rhythmic two-foot pulse
M_MACHINE        = 0x27  # oscillate between two amplitudes
M_WEAPON_SIMPLE  = 0x02  # Simple_Weapon
M_WEAPON         = 0x25  # resist start..end with snap release

# Limited leftovers - stricter param ranges, no clear use case
M_RIGID_LIMITED  = 0x11
M_WEAPON_LIMITED = 0x12

RAW_MAX = 255


def _clamp(v, hi=RAW_MAX):
    try:
        value = float(v)
    except (TypeError, ValueError, OverflowError):
        return 0
    if not math.isfinite(value):
        return 0
    return max(0, min(hi, round(value)))


def _pack_zones(strengths):
    """Build the 6-byte (active-mask, 3-bit-per-zone strengths) payload shared
    by rigid_zones and vibrate_zones. Strengths are 0..8; 0 = inactive."""
    active = packed = 0
    for i, s in enumerate(strengths[:10]):
        if s > 0:
            active |= 1 << i
            packed |= (s - 1) << (3 * i)
    return (
        active & 0xFF, (active >> 8) & 0xFF,
        packed & 0xFF, (packed >> 8) & 0xFF,
        (packed >> 16) & 0xFF, (packed >> 24) & 0xFF,
    )


# --- Effect primitives (raw HID frames) -----------------------------------

def off():
    return (M_OFF, ())

def rigid(force):
    return (M_RIGID, (0, _clamp(force)))

def vibrate(freq, amp):
    return (M_VIBRATE, (_clamp(freq), _clamp(amp)))

def vibrate_zones(amp, freq, wall_zones):
    """Per-zone vibrate: lower zones buzz at `amp` (1-8), top `wall_zones` stay maxed."""
    a = max(1, min(8, int(amp)))
    w = max(1, min(9, int(wall_zones)))
    strengths = [a] * (10 - w) + [8] * w
    return (M_VIBRATE_ZONES, _pack_zones(strengths) + (0, 0, _clamp(freq), 0))

def rigid_zones(zones):
    """Per-zone resistance: 10 per-zone strengths (0-8). Zero = inactive."""
    strengths = [max(0, min(8, int(s))) for s in zones[:10]]
    return (M_RIGID_ZONES, _pack_zones(strengths) + (0, 0, 0, 0))

def weapon(start, end, strength):
    """Weapon: resist between start..end zones, snap on release. start 2-7, end start+1..8, strength 1-8."""
    s = max(2, min(7, int(start)))
    e = max(s + 1, min(8, int(end)))
    f = max(1, min(8, int(strength)))
    zones = (1 << s) | (1 << e)
    return (M_WEAPON, (zones & 0xFF, (zones >> 8) & 0xFF, f - 1))

def bow(start, end, strength, snap_force):
    """Bow: resist start..end then snap. start 0-8, end start+1..8, both forces 1-8."""
    s = max(0, min(8, int(start)))
    e = max(s + 1, min(8, int(end)))
    f = max(1, min(8, int(strength)))
    sf = max(1, min(8, int(snap_force)))
    zones = (1 << s) | (1 << e)
    pair = ((f - 1) & 0x07) | (((sf - 1) & 0x07) << 3)
    return (M_BOW, (zones & 0xFF, (zones >> 8) & 0xFF, pair & 0xFF, (pair >> 8) & 0xFF))

def gallop(start, end, first_foot, second_foot, freq):
    """Galloping: two-foot pulse. start 0-8, end start+1..9, firstFoot 0-6, secondFoot ff+1..7, freq Hz."""
    s = max(0, min(8, int(start)))
    e = max(s + 1, min(9, int(end)))
    ff = max(0, min(6, int(first_foot)))
    sf = max(ff + 1, min(7, int(second_foot)))
    zones = (1 << s) | (1 << e)
    pair = (sf & 0x07) | ((ff & 0x07) << 3)
    return (M_GALLOP, (zones & 0xFF, (zones >> 8) & 0xFF, pair & 0xFF, _clamp(freq)))

def machine(start, end, amp_a, amp_b, freq, period):
    """Machine: oscillate between two amplitudes. start 0-8, end start+1..9, amps 0-7, freq Hz, period (0.1s units)."""
    s = max(0, min(8, int(start)))
    e = max(s + 1, min(9, int(end)))
    a = max(0, min(7, int(amp_a)))
    b = max(0, min(7, int(amp_b)))
    zones = (1 << s) | (1 << e)
    pair = (a & 0x07) | ((b & 0x07) << 3)
    return (M_MACHINE, (zones & 0xFF, (zones >> 8) & 0xFF, pair & 0xFF, _clamp(freq), _clamp(period)))

def weapon_simple(start_position, end_position, strength):
    """Simple_Weapon (0x02): resist between two raw byte positions then snap. All params 0-255 raw bytes."""
    return (M_WEAPON_SIMPLE, (_clamp(start_position), _clamp(end_position), _clamp(strength)))

def rigid_limited(position, strength):
    """Rigid_Limited (0x11): static resistance starting at raw `position`. position 0-255, strength capped 0-10."""
    return (M_RIGID_LIMITED, (_clamp(position), max(0, min(10, int(strength)))))

def weapon_limited(start_position, end_position, strength):
    """Weapon_Limited (0x12): resist between raw byte positions then snap.
    start_position must be >= 0x10; end_position must be in start..start+100; strength 0-10."""
    s = max(0x10, _clamp(start_position))
    e = max(s, min(s + 100, _clamp(end_position)))
    return (M_WEAPON_LIMITED, (s, e, max(0, min(10, int(strength)))))

def vibrate_simple(position, amplitude, frequency):
    """Simple_Vibration (0x06): buzz past `position`. Bytes [freq, amp, position] (raw 0-255)."""
    return (M_VIBRATE, (_clamp(frequency), _clamp(amplitude), _clamp(position)))

def feedback_slope(start_position, end_position, start_strength, end_strength):
    """Linear-ramp resistance from start..end zones. start 0-8, end start+1..9, strengths 1-8."""
    sp = max(0, min(8, int(start_position)))
    ep = max(sp + 1, min(9, int(end_position)))
    ss = max(1, min(8, int(start_strength)))
    es = max(1, min(8, int(end_strength)))
    slope = (es - ss) / (ep - sp)
    zones = [0] * 10
    for i in range(sp, 10):
        zones[i] = round(ss + slope * (i - sp)) if i <= ep else es
    return rigid_zones(zones)


# --- Standalone preview ---------------------------------------------------
# Run: `python -m modules.dualsense.adaptive_trigger` from src/.
# Pick an effect by number; it plays on BOTH triggers for ~3s then resets.

EFFECTS = [
    ("off",                          off()),
    ("rigid(180)",                   rigid(180)),
    ("rigid(255)",                   rigid(255)),
    ("vibrate(20, 180)",             vibrate(20, 180)),
    ("vibrate_simple(0,180,20)",     vibrate_simple(0, 180, 20)),
    ("vibrate_zones(6, 20, 3)",      vibrate_zones(6, 20, 3)),
    ("rigid_zones [top 2 maxed]",    rigid_zones([0]*8 + [8]*2)),
    ("rigid_zones [mid bump]",       rigid_zones([0,0,0,0,0,8,8,8,0,0])),
    ("feedback_slope(0,9,1,8)",      feedback_slope(0, 9, 1, 8)),
    ("weapon(4, 7, 8)",              weapon(4, 7, 8)),
    ("bow(1, 5, 3, 8)",              bow(1, 5, 3, 8)),
    ("gallop(2, 8, 1, 4, 5)",        gallop(2, 8, 1, 4, 5)),
    ("machine(1, 8, 2, 7, 8, 5)",    machine(1, 8, 2, 7, 8, 5)),
    ("weapon_simple(0x70,0xa0,0xff)", weapon_simple(0x70, 0xa0, 0xff)),
    ("rigid_limited(0, 10) [weak by design]", rigid_limited(0, 10)),
    ("weapon_limited(0x20,0x80,10)", weapon_limited(0x20, 0x80, 10)),
]

PREVIEW_HOLD_S = 3.0


def _preview():
    try:
        from .main import DualSense
    except ImportError:
        import os
        import sys
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        from modules.dualsense.main import DualSense
    ds = DualSense(enable_startup_pulse=False)
    ds.open()
    print("Waiting for DualSense...")
    for _ in range(50):
        if ds.connected:
            break
        time.sleep(0.1)
    if not ds.connected:
        print("No controller found.")
        ds.close()
        return
    print("Connected. Effects:")
    for i, (label, _) in enumerate(EFFECTS):
        print(f"  {i:2}: {label}")
    print("   a: play all in sequence")
    print("   q: quit")
    try:
        while True:
            choice = input("\nPick # / a / q: ").strip().lower()
            if choice in ("q", "quit", "exit"):
                break
            if choice == "a":
                for label, frame in EFFECTS:
                    print(f"  {label}")
                    ds.set(frame, frame)
                    time.sleep(PREVIEW_HOLD_S)
                ds.set(off(), off())
                continue
            if not choice.isdigit() or not (0 <= int(choice) < len(EFFECTS)):
                print("Invalid.")
                continue
            label, frame = EFFECTS[int(choice)]
            print(f"Playing: {label}  ({PREVIEW_HOLD_S}s)")
            ds.set(frame, frame)
            time.sleep(PREVIEW_HOLD_S)
            ds.set(off(), off())
    except KeyboardInterrupt:
        pass
    finally:
        ds.set(off(), off())
        time.sleep(0.1)
        ds.close()
        print("Done.")


if __name__ == "__main__":
    _preview()
