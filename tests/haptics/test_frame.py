import math

import pytest

from modules.haptics.frame import (
    CompatibleRumble,
    HapticFrame,
    SILENT_FRAME,
    clamp01,
    to_compatible_rumble,
)


def test_silent_frame_has_no_energy():
    assert SILENT_FRAME == HapticFrame()


def test_clamp01_rejects_non_finite_and_clamps_range():
    assert clamp01(float("nan")) == 0.0
    assert clamp01(float("inf")) == 0.0
    assert clamp01(-0.5) == 0.0
    assert clamp01(1.5) == 1.0


def test_compatible_rumble_uses_frequency_priority_downmix():
    frame = HapticFrame(
        left_low=0.4,
        right_low=0.7,
        left_high=0.2,
        right_high=0.6,
        engine_hz=80.0,
        engine_amplitude=0.4,
    )

    rumble = to_compatible_rumble(frame)

    assert rumble == CompatibleRumble(
        low_frequency=pytest.approx(0.9),
        high_frequency=pytest.approx(0.6),
    )


def test_compatible_rumble_clamps_summed_engine_energy():
    frame = HapticFrame(left_low=0.9, engine_amplitude=0.8)

    assert math.isclose(to_compatible_rumble(frame).low_frequency, 1.0)
