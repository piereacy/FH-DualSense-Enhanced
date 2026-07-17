"""All tunables in one place. Forces 0-255, frequencies in Hz."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Settings:
    # MARK: UDP
    udp_host: str = "127.0.0.1"               # bind address for Forza Data Out
    udp_port: int = 5300                      # match Forza HUD setting
    udp_timeout: float = 0.5                  # socket recv timeout (s)
    udp_forward: bool = False                 # mirror raw packets to udp_forward_to (off by default)
    udp_forward_to: str = "127.0.0.1:5301"    # host:port targets (comma-separated) when udp_forward is on

    # MARK: Pedal shared
    pedal_value_max: int = 255                # raw pedal byte range. DO NOT CHANGE
    wall_zones: int = 2                       # firmware end-wall depth; 1=top zone only, 9=full travel

    # MARK: L2 brake resistance
    # Rigid curve: 0..wall_engage_at maps baseline..max_force, then firmware wall at 100%.
    enable_brake_resistance: bool = True
    brake_deadzone: int = 0                   # community-informed baseline
    brake_baseline_force: int = 0             # force at deadzone exit
    brake_max_force: int = 5                  # peak force just before the wall
    brake_curve: float = 5.0                  # parabolic exponent; higher = softer mid, harder near wall
    brake_wall_engage_at: int = 250           # byte that triggers firmware wall. DO NOT CHANGE
    brake_wall_release_at: int = 200          # hysteresis exit byte. DO NOT CHANGE
    enable_brake_static_wall: bool = False    # optional fixed wall mid-travel
    brake_static_wall_at: int = 128           # pedal byte where the static wall sits
    brake_static_wall_force: int = 255        # static wall strength

    # MARK: L2 handbrake bonus
    enable_handbrake_bonus: bool = False
    handbrake_bonus: int = 0                  # flat extra force while handbrake is engaged

    # MARK: L2 ABS pulse
    # GT7-style wall: lower zones pulse while the top zones stay maxed.
    enable_abs: bool = True
    abs_brake_threshold: int = 255            # min brake byte to arm
    abs_min_speed_kmh: float = 6.0            # low-speed gate only; does not scale intensity
    abs_slip_ratio_threshold: float = 0.3     # per-wheel slip trigger
    abs_combined_slip_threshold: float = 0.3  # combined slip trigger
    abs_sensitivity: float = 1.0              # normal UI sensitivity multiplier
    abs_combined_slip_weight: float = 0.35    # combined slip stays auxiliary
    abs_slip_full_scale: float = 2.0           # slip mapped to maximum pulse
    abs_freq_min: int = 20                    # pulse frequency at threshold
    abs_freq: int = 60                        # maximum pulse frequency
    abs_amp_min: int = 32                     # pulse amplitude at threshold
    abs_amp: int = 90                         # maximum pulse amplitude
    abs_hold_ms: float = 100.0                # anti-stutter hold deadline
    abs_wall_zones: int = 3                   # top zones remain a maximum wall

    # MARK: R2 throttle resistance
    # Light rigid curve: 0..wall_engage_at maps baseline..max_force, then firmware wall at 100%.
    enable_throttle_resistance: bool = True
    accel_deadzone: int = 0                   # community-informed baseline
    throttle_baseline_force: int = 0          # force at deadzone exit
    throttle_max_force: int = 1               # peak force just before the wall (lighter than brake)
    throttle_curve: float = 5.0               # parabolic exponent; higher = softer early, firmer near wall
    throttle_wall_engage_at: int = 250        # byte that triggers firmware wall. DO NOT CHANGE
    throttle_wall_release_at: int = 200       # hysteresis exit byte. DO NOT CHANGE

    # MARK: R4 optional throttle dynamics
    enable_boost_resistance: bool = False
    boost_resistance_threshold: float = 0.5
    boost_resistance_force: int = 18
    enable_gforce_resistance: bool = False
    gforce_lateral_weight: float = 0.25
    gforce_longitudinal_weight: float = 1.0
    gforce_full_scale: float = 1.5
    gforce_resistance_force: int = 28
    gforce_attack_ms: float = 70.0
    gforce_release_ms: float = 180.0

    # MARK: R2 trigger redline warning
    enable_rev_limiter: bool = False
    rev_limit_ratio: float = 0.93             # fraction of max_rpm to fire at
    rev_limit_freq: int = 30                  # adaptive-trigger vibration frequency
    rev_limit_amp: int = 12                   # adaptive-trigger vibration strength
    rev_limit_hold_ms: float = 120.0          # anti-stutter hold after falling below the ratio

    # MARK: Body haptics redline warning
    # Fuel-cut pulse with independent left/right grip routing.
    enable_grip_redline_haptics: bool = True
    grip_redline_left: bool = True
    grip_redline_right: bool = False
    grip_redline_ratio: float = 0.93
    grip_redline_release_ratio: float = 0.90
    grip_redline_freq: int = 10
    grip_redline_amp: int = 220
    grip_redline_gain: float = 1.5
    grip_redline_duty_cycle: float = 0.70
    grip_redline_low_ratio: float = 0.45
    grip_redline_attack_strength: float = 0.65
    grip_redline_attack_duration_ms: float = 120.0
    grip_redline_background_duck: float = 0.30

    # MARK: Shared trigger traction/grip feedback
    # Braking routes longitudinal grip to L2; accelerator or both pedals route
    # it to R2. Near zero speed, accelerator-driven rotation preserves burnouts.
    enable_wheelspin_buzz: bool = True
    wheelspin_amp: int = 90
    wheelspin_sensitivity: float = 1.0
    wheelspin_slip_threshold: float = 0.6
    wheelspin_hysteresis: float = 0.15         # fraction of the active threshold
    wheelspin_slip_full_scale: float = 3.0
    wheelspin_attack_ms: float = 40.0
    wheelspin_release_ms: float = 125.0
    wheelspin_g_damping: float = 0.25
    wheelspin_burnout_rotation_threshold: float = 30.0
    wheelspin_burnout_rotation_full_scale: float = 120.0
    wheelspin_tarmac_freq_min: int = 90
    wheelspin_tarmac_freq_max: int = 180
    wheelspin_water_freq_min: int = 80
    wheelspin_water_freq_max: int = 150
    wheelspin_dirt_freq_min: int = 30
    wheelspin_dirt_freq_max: int = 70
    wheelspin_gravel_freq_min: int = 12
    wheelspin_gravel_freq_max: int = 30

    # MARK: R2 idle buzz
    # Engine-idle oscillation while stopped and accelerator pressed under ~25%.
    # Single chug pattern: vibrate amp toggles between low and high every half-period.
    enable_idle_buzz: bool = True
    idle_max_speed_kmh: float = 5.0           # only while car is essentially stopped
    idle_accel_max: int = 64                  # upper byte (~25% of 255): idle fades out past this press
    idle_freq: int = 30                       # base vibrate Hz
    idle_amp_low: int = 1                     # quiet half of the cycle
    idle_amp_high: int = 60                   # loud half of the cycle
    idle_period_s: float = 0.5                # full cycle length (sec)

    # MARK: Gear shift
    # One short burst on up/downshift while moving.
    enable_gear_shift: bool = False           # buzz on R2
    enable_gear_shift_brake: bool = False     # also buzz on L2 via the wall
    gear_shift_freq: int = 10
    gear_shift_amp: int = 10
    gear_shift_duration_ms: float = 100.0     # burst length

    # MARK: Body haptics gear shift
    # Optional centered grip thump, independent from the adaptive triggers.
    enable_grip_gear_shift_haptics: bool = False
    grip_gear_shift_strength: float = 0.8
    grip_gear_shift_duration_ms: float = 100.0

    # MARK: R4 optional trigger events and idle road texture
    enable_collision_trigger_l2: bool = False
    enable_collision_trigger_r2: bool = False
    collision_trigger_freq: int = 2
    collision_trigger_amp: int = 220
    collision_trigger_duration_ms: float = 90.0
    enable_trigger_surface_l2: bool = False
    enable_trigger_surface_r2: bool = False
    trigger_surface_freq: int = 10
    trigger_surface_amp: int = 18
    trigger_rumble_strip_freq: int = 25
    trigger_rumble_strip_amp: int = 110

    # MARK: Body haptics
    # USB and Bluetooth consume the same normalized HapticFrame. Only their
    # existing transport/synthesis paths differ.
    enable_body_haptics: bool = True
    body_haptics_intensity: float = 0.5
    engine_haptics_intensity: float = 0.5
    road_haptics_intensity: float = 0.7
    impact_haptics_intensity: float = 2.0
    slip_haptics_intensity: float = 1.0
    slip_haptics_threshold: float = 0.8
    collision_haptics_jerk_threshold: float = 3.0
    collision_haptics_duration_ms: float = 150.0
    collision_haptics_cooldown_ms: float = 250.0
    collision_haptics_rebound_ratio: float = 0.45
    collision_haptics_weak_side_ratio: float = 0.35
    collision_background_duck: float = 0.20
    suspension_haptics_delta_threshold: float = 0.015

    # MARK: R4 optional controller lighting
    enable_tachometer_lightbar: bool = False
    tachometer_start_ratio: float = 0.70
    tachometer_flash_ratio: float = 0.93
    tachometer_flash_rate_hz: float = 10.0
    tachometer_brightness: float = 0.70
    tachometer_start_red: int = 57
    tachometer_start_green: int = 197
    tachometer_start_blue: int = 187
    tachometer_redline_red: int = 255
    tachometer_redline_green: int = 38
    tachometer_redline_blue: int = 80
    enable_gear_player_leds: bool = False

    # MARK: System - startup pulse
    enable_startup_pulse: bool = True
    startup_pulse_force: int = 150            # one-shot force test on connect

    # MARK: System - reconnect
    # Off by default for HidHide compatibility. On = USB unplug/replug recovers without restart.
    enable_reconnect: bool = False
    reconnect_interval_s: float = 5.0         # retry cadence when disconnected

    # MARK: System - controller selection
    # Lock to a specific DualSense by serial. Empty = auto (first found).
    # Soft lock: falls back to first-found if the locked one is missing.
    # USB and BT report different serials for the same controller.
    controller_lock_serial: str = ""

    # MARK: System - updates
    check_for_updates: bool = True            # built-in updater checks GitHub in the background
    auto_download_updates: bool = False       # download only; installation still requires confirmation

    # MARK: System - FH6 installation
    # Validated Windows Steam game root. Discovery is read-only; archive swaps are button-only.
    fh6_install_path: str = ""

    # MARK: System - DSX
    # When on, triggers go to DualSenseX over UDP instead of HID. Lets DSX (Steam)
    # own the controller without HID fighting it. Toggling restarts the backend.
    use_dsx: bool = False
    dsx_host: str = "127.0.0.1"               # match the host in DSX settings
    dsx_port: int = 6969                      # match the port in DSX settings

    # MARK: System - language
    # Module name in `lang/` (en, tr, zh, zh_tw, ja). Unknown codes fall back to English.
    language: str = "en"

    # MARK: System - application behavior
    # Closes when the game process disappears; telemetry-lost is a fallback for Task Manager kills.
    exit_on_game_close: bool = True
    minimize_to_tray: bool = True
    game_process_name_contains: tuple = ("forza",)   # substring match, case-insensitive
    game_poll_interval_s: float = 2.0                # psutil scan cadence
    telemetry_lost_exit_s: float = 60.0              # quit if no packets for this long after first packet
