from __future__ import annotations

import math
from dataclasses import dataclass


def _byte(value) -> int:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return 0
    if not math.isfinite(number):
        return 0
    return max(0, min(255, int(round(number))))


@dataclass(frozen=True, slots=True)
class ControllerVisualState:
    """Optional DualSense visual fields.

    ``None`` means the app does not claim that controller field. Explicit zero
    values mean the feature is enabled and should be switched off for this frame.
    """

    lightbar: tuple[int, int, int] | None = None
    player_leds: int | None = None

    def normalized(self) -> "ControllerVisualState":
        lightbar = None
        if self.lightbar is not None:
            lightbar = tuple(_byte(value) for value in self.lightbar[:3])
            if len(lightbar) != 3:
                raise ValueError("lightbar requires exactly three channels")
        player_leds = None
        if self.player_leds is not None:
            try:
                player_leds = max(0, min(0x1F, int(self.player_leds)))
            except (TypeError, ValueError, OverflowError):
                player_leds = 0
        return ControllerVisualState(lightbar=lightbar, player_leds=player_leds)


NO_VISUAL_CONTROL = ControllerVisualState()

