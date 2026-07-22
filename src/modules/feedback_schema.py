"""Transport-neutral UI grouping for trigger and grip feedback settings.

GUI and TUI render these immutable definitions independently.  Keeping the
classification here prevents a setting from drifting onto a different output
device page in one frontend only.
"""

TRIGGER_SWITCH_SECTIONS = (
    ("L2 - Brake", (
        ("enable_gear_shift_brake", "Shift thump", None, None, ""),
        ("enable_abs", "ABS rumble", None, None, ""),
        ("enable_brake_static_wall", "Static brake wall", None, None, ""),
        ("enable_brake_resistance", "Brake stiffness", None, None, ""),
        ("enable_handbrake_bonus", "Handbrake stiffness bonus", None, None, ""),
    )),
    ("R2 - Throttle", (
        ("enable_gear_shift", "Shift thump", None, None, ""),
        ("enable_idle_buzz", "Idle buzz", None, None, ""),
        ("enable_rev_limiter", "R2 trigger redline vibration", None, None, ""),
        ("enable_throttle_resistance", "Throttle stiffness", None, None, ""),
    )),
    ("Shared trigger feedback", (
        ("enable_wheelspin_buzz", "Tire grip trigger feedback", None, None, ""),
    )),
)

GRIP_SWITCH_SECTIONS = (
    ("Body haptics", (
        ("enable_body_haptics", "Enable body haptics", None, None,
         "Uses the same haptic mix over USB and Bluetooth; only the transport path differs. "
         "Disable in-game vibration to prevent competing or doubled grip output."),
    )),
    ("Grip feedback", (
        ("enable_grip_gear_shift_haptics", "Grip gear-shift thump", None, None, ""),
    )),
    ("Redline feedback", (
        ("enable_grip_redline_haptics", "Grip redline vibration", None, None, ""),
        ("grip_redline_left", "Left grip", None, None, ""),
        ("grip_redline_right", "Right grip", None, None, ""),
    )),
)

TRIGGER_SETTING_SECTIONS = (
    ("Pedal dead zones", (
        ("accel_deadzone", "Gas trigger dead zone", 0, 255, ""),
        ("brake_deadzone", "Brake trigger dead zone", 0, 255, ""),
    )),
    ("Left trigger - Brake force", (
        ("brake_baseline_force", "Resting stiffness", 0, 255, ""),
        ("brake_max_force", "Hard-press stiffness", 0, 255, ""),
        ("brake_curve", "Stiffness curve shape", 0.1, 20.0, ""),
        ("handbrake_bonus", "Handbrake extra stiffness", 0, 255, ""),
    )),
    ("Left trigger - Static wall (optional)", (
        ("brake_static_wall_at", "Wall position on the trigger", 0, 255, ""),
        ("brake_static_wall_force", "Wall hardness", 0, 255, ""),
    )),
    ("Right trigger - Gas force", (
        ("throttle_baseline_force", "Resting stiffness", 0, 255, ""),
        ("throttle_max_force", "Hard-press stiffness", 0, 255, ""),
        ("throttle_curve", "Stiffness curve shape", 0.1, 20.0, ""),
    )),
    ("ABS (anti-lock brake) rumble", (
        ("abs_amp", "Rumble strength", 0, 255, ""),
        ("abs_sensitivity", "Sensitivity", 0.1, 3.0, ""),
    )),
    ("R2 trigger redline vibration", (
        ("rev_limit_ratio", "Trigger near redline at", 0.0, 1.0, ""),
        ("rev_limit_freq", "Trigger vibration frequency (Hz)", 1, 255, ""),
        ("rev_limit_amp", "Trigger vibration strength", 0, 255, ""),
        ("rev_limit_hold_ms", "Trigger hold time (ms)", 0.0, 1000.0, ""),
    )),
    ("Tire grip trigger feedback", (
        ("wheelspin_amp", "Tire grip trigger strength", 0, 255, ""),
        ("wheelspin_sensitivity", "Sensitivity", 0.1, 3.0, ""),
    )),
    ("Idle buzz", (
        ("idle_amp_high", "Idle strength", 0, 255, ""),
    )),
    ("R2 trigger gear-shift thump", (
        ("gear_shift_freq", "Thump speed (Hz)", 0, 255, ""),
        ("gear_shift_amp", "Thump strength", 0, 255, ""),
        ("gear_shift_duration_ms", "Thump length (ms)", 0.0, 2000.0, ""),
    )),
)

GRIP_SETTING_SECTIONS = (
    ("Grip redline vibration", (
        ("grip_redline_ratio", "Grip trigger near redline at", 0.0, 1.0, ""),
        ("grip_redline_freq", "Grip pulse rate (Hz)", 1, 20, ""),
        ("grip_redline_amp", "Grip pulse strength", 0, 255, ""),
        ("grip_redline_duty_cycle", "Grip pulse width", 0.20, 0.85, ""),
        ("grip_redline_attack_strength", "Grip entry impact", 0.0, 1.0, ""),
    )),
    ("Grip gear-shift thump", (
        ("grip_gear_shift_strength", "Grip thump strength", 0.0, 2.0, ""),
        ("grip_gear_shift_duration_ms", "Grip thump length (ms)", 0.0, 2000.0, ""),
    )),
    ("Body haptics tuning", (
        ("body_haptics_intensity", "Master intensity", 0.0, 2.0, ""),
        ("engine_haptics_intensity", "Engine intensity", 0.0, 2.0, ""),
        ("road_haptics_intensity", "Road texture intensity", 0.0, 2.0, ""),
        ("impact_haptics_intensity", "Impact and suspension intensity", 0.0, 2.0, ""),
        ("slip_haptics_intensity", "Slip and ABS intensity", 0.0, 2.0, ""),
        ("slip_haptics_threshold", "Slip threshold", 0.0, 5.0, ""),
    )),
)

TRIGGER_EXPERIMENTAL_SECTIONS = (
    ("Experimental dynamic resistance", (
        ("enable_boost_resistance", "Turbo boost resistance", None, None, ""),
        ("boost_resistance_threshold", "Boost activation threshold", 0.0, 10.0, ""),
        ("boost_resistance_force", "Boost extra resistance", 0, 255, ""),
        ("enable_gforce_resistance", "G-force resistance", None, None, ""),
        ("gforce_resistance_force", "G-force extra resistance", 0, 255, ""),
        ("gforce_lateral_weight", "Lateral G weight", 0.0, 2.0, ""),
        ("gforce_longitudinal_weight", "Longitudinal G weight", 0.0, 2.0, ""),
        ("gforce_full_scale", "G force at maximum resistance", 0.1, 5.0, ""),
        ("gforce_attack_ms", "G-force attack smoothing (ms)", 1.0, 500.0, ""),
        ("gforce_release_ms", "G-force release smoothing (ms)", 1.0, 1000.0, ""),
    )),
    ("Experimental collision trigger feedback", (
        ("enable_collision_trigger_l2", "L2 collision trigger jolt", None, None, ""),
        ("enable_collision_trigger_r2", "R2 collision trigger jolt", None, None, ""),
        ("collision_trigger_freq", "Collision trigger frequency (Hz)", 0, 255, ""),
        ("collision_trigger_amp", "Collision trigger strength", 0, 255, ""),
        ("collision_trigger_duration_ms", "Collision trigger duration (ms)", 0.0, 500.0, ""),
    )),
    ("Experimental road texture trigger feedback", (
        ("enable_trigger_surface_l2", "L2 idle road texture", None, None, ""),
        ("enable_trigger_surface_r2", "R2 idle road texture", None, None, ""),
        ("trigger_surface_freq", "Road texture frequency (Hz)", 0, 255, ""),
        ("trigger_surface_amp", "Road texture strength", 0, 255, ""),
        ("trigger_rumble_strip_freq", "Rumble strip frequency (Hz)", 0, 255, ""),
        ("trigger_rumble_strip_amp", "Rumble strip strength", 0, 255, ""),
    )),
    ("ABS advanced tuning", (
        ("abs_brake_threshold", "Minimum brake input", 0, 255, ""),
        ("abs_min_speed_kmh", "Minimum speed (km/h)", 0.0, 500.0, ""),
        ("abs_slip_ratio_threshold", "Longitudinal slip threshold", 0.0, 10.0, ""),
        ("abs_combined_slip_threshold", "Combined slip threshold", 0.0, 10.0, ""),
        ("abs_combined_slip_weight", "Combined slip influence", 0.0, 1.0, ""),
        ("abs_slip_full_scale", "Slip at maximum feedback", 0.1, 10.0, ""),
        ("abs_freq_min", "Minimum frequency (Hz)", 0, 255, ""),
        ("abs_freq", "Maximum frequency (Hz)", 0, 255, ""),
        ("abs_amp_min", "Minimum strength", 0, 255, ""),
        ("abs_hold_ms", "Feedback hold (ms)", 0.0, 500.0, ""),
        ("abs_wall_zones", "Top wall zones", 1, 9, ""),
    )),
    ("Tire grip trigger advanced tuning", (
        ("wheelspin_slip_threshold", "Longitudinal slip threshold", 0.0, 10.0, ""),
        ("wheelspin_hysteresis", "Slip hysteresis", 0.0, 0.9, ""),
        ("wheelspin_slip_full_scale", "Slip at maximum feedback", 0.1, 10.0, ""),
        ("wheelspin_attack_ms", "Attack smoothing (ms)", 1.0, 500.0, ""),
        ("wheelspin_release_ms", "Release smoothing (ms)", 1.0, 1000.0, ""),
        ("wheelspin_g_damping", "G-force damping", 0.0, 1.0, ""),
        ("wheelspin_burnout_rotation_threshold", "Burnout rotation threshold", 0.0, 300.0, ""),
        ("wheelspin_burnout_rotation_full_scale", "Burnout rotation at maximum feedback", 1.0, 1000.0, ""),
        ("wheelspin_tarmac_freq_min", "Tarmac minimum frequency (Hz)", 0, 255, ""),
        ("wheelspin_tarmac_freq_max", "Tarmac maximum frequency (Hz)", 0, 255, ""),
        ("wheelspin_water_freq_min", "Water minimum frequency (Hz)", 0, 255, ""),
        ("wheelspin_water_freq_max", "Water maximum frequency (Hz)", 0, 255, ""),
        ("wheelspin_dirt_freq_min", "Dirt minimum frequency (Hz)", 0, 255, ""),
        ("wheelspin_dirt_freq_max", "Dirt maximum frequency (Hz)", 0, 255, ""),
        ("wheelspin_gravel_freq_min", "Gravel minimum frequency (Hz)", 0, 255, ""),
        ("wheelspin_gravel_freq_max", "Gravel maximum frequency (Hz)", 0, 255, ""),
    )),
)

GRIP_EXPERIMENTAL_SECTIONS = (
    ("Grip redline advanced tuning", (
        ("grip_redline_release_ratio", "Grip release below redline at", 0.0, 1.0, ""),
        ("grip_redline_gain", "Grip signal gain", 0.0, 2.0, ""),
        ("grip_redline_low_ratio", "Low-frequency pulse ratio", 0.0, 1.0, ""),
        ("grip_redline_background_duck", "Redline background level", 0.0, 1.0, ""),
        ("grip_redline_attack_duration_ms", "Grip entry impact duration (ms)", 0.0, 500.0, ""),
    )),
    ("Collision haptics advanced tuning", (
        ("collision_haptics_jerk_threshold", "Collision jerk threshold", 0.0, 50.0, ""),
        ("collision_haptics_duration_ms", "Collision duration (ms)", 0.0, 1000.0, ""),
        ("collision_haptics_cooldown_ms", "Collision cooldown (ms)", 0.0, 2000.0, ""),
        ("collision_haptics_rebound_ratio", "Collision rebound strength", 0.0, 1.0, ""),
        ("collision_haptics_weak_side_ratio", "Collision weak-side strength", 0.0, 1.0, ""),
        ("collision_background_duck", "Collision background level", 0.0, 1.0, ""),
    )),
)


def field_names(*section_groups) -> tuple[str, ...]:
    return tuple(
        field[0]
        for sections in section_groups
        for _title, fields in sections
        for field in fields
    )
