from __future__ import annotations

from modules.dualsense.output_state import ControllerVisualState


def _clamp01(value) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def _byte(value) -> int:
    return max(0, min(255, int(round(value))))


def _lerp_color(a, b, ratio):
    ratio = _clamp01(ratio)
    return tuple(_byte(x + (y - x) * ratio) for x, y in zip(a, b))


def _gear_leds(gear: int) -> int:
    return {
        1: 0x04,
        2: 0x0A,
        3: 0x15,
        4: 0x1B,
    }.get(gear, 0x1F if gear >= 5 else 0)


class LightingController:
    def __init__(self):
        self._lightbar_claimed = False
        self._player_leds_claimed = False

    def update(self, telemetry, settings, now: float) -> ControllerVisualState:
        on = bool(telemetry.get("on", False))
        lightbar = None
        player_leds = None

        if getattr(settings, "enable_tachometer_lightbar", False):
            lightbar = self._tachometer(telemetry, settings, now) if on else (0, 0, 0)
            self._lightbar_claimed = True
        elif self._lightbar_claimed:
            # Clear our last colour exactly once before releasing ownership.
            lightbar = (0, 0, 0)
            self._lightbar_claimed = False

        if getattr(settings, "enable_gear_player_leds", False):
            gear = int(telemetry.get("gear", 0) or 0) if on else 0
            player_leds = _gear_leds(gear)
            self._player_leds_claimed = True
        elif self._player_leds_claimed:
            player_leds = 0
            self._player_leds_claimed = False

        return ControllerVisualState(
            lightbar=lightbar,
            player_leds=player_leds,
        ).normalized()

    @staticmethod
    def _tachometer(telemetry, settings, now):
        max_rpm = max(0.0, float(telemetry.get("max_rpm", 0.0) or 0.0))
        rpm = max(0.0, float(telemetry.get("rpm", 0.0) or 0.0))
        if max_rpm <= 0.0:
            return (0, 0, 0)
        ratio = rpm / max_rpm
        start = _clamp01(getattr(settings, "tachometer_start_ratio", 0.70))
        flash = max(start + 0.01, _clamp01(
            getattr(settings, "tachometer_flash_ratio", 0.93)
        ))
        brightness = _clamp01(getattr(settings, "tachometer_brightness", 0.70))
        start_color = (
            getattr(settings, "tachometer_start_red", 57),
            getattr(settings, "tachometer_start_green", 197),
            getattr(settings, "tachometer_start_blue", 187),
        )
        redline_color = (
            getattr(settings, "tachometer_redline_red", 255),
            getattr(settings, "tachometer_redline_green", 38),
            getattr(settings, "tachometer_redline_blue", 80),
        )
        if ratio < start:
            color = (0, 0, 0)
        elif ratio >= flash:
            rate = max(0.0, float(getattr(settings, "tachometer_flash_rate_hz", 10.0)))
            visible = rate <= 0.0 or int(float(now) * rate * 2.0) % 2 == 0
            color = redline_color if visible else (0, 0, 0)
        else:
            progress = (ratio - start) / max(0.01, flash - start)
            if progress < 0.55:
                color = _lerp_color(start_color, (255, 210, 48), progress / 0.55)
            else:
                color = _lerp_color((255, 210, 48), redline_color, (progress - 0.55) / 0.45)
        return tuple(_byte(channel * brightness) for channel in color)
