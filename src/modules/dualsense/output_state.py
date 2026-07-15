from __future__ import annotations

from dataclasses import dataclass


def _byte(value) -> int:
    return max(0, min(255, int(round(float(value)))))


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
            player_leds = max(0, min(0x1F, int(self.player_leds)))
        return ControllerVisualState(lightbar=lightbar, player_leds=player_leds)


NO_VISUAL_CONTROL = ControllerVisualState()

