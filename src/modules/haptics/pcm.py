from __future__ import annotations

import math

from .frame import HapticFrame, clamp01


class HapticPcmRenderer:
    """Render transport-independent stereo PCM from a :class:`HapticFrame`."""

    def __init__(
        self,
        *,
        numpy_module,
        sample_rate: int,
        smoothing: float = 0.35,
        soft_clip: bool = False,
    ):
        if int(sample_rate) <= 0:
            raise ValueError("sample_rate must be positive")
        self._np = numpy_module
        self.sample_rate = int(sample_rate)
        self.smoothing = float(smoothing)
        self.soft_clip = bool(soft_clip)
        self._levels = [0.0, 0.0, 0.0, 0.0, 0.0]
        self._phase_low = 0.0
        self._phase_high = 0.0
        self._phase_engine = 0.0

    @property
    def levels(self) -> tuple[float, float, float, float, float]:
        return tuple(self._levels)

    def reset(self) -> None:
        self._levels = [0.0, 0.0, 0.0, 0.0, 0.0]
        self._phase_low = 0.0
        self._phase_high = 0.0
        self._phase_engine = 0.0

    def render(self, frame: HapticFrame, frames: int):
        frames = int(frames)
        if frames <= 0:
            raise ValueError("frames must be positive")
        if self._np is None:
            raise RuntimeError("NumPy is required for haptic PCM rendering")

        targets = (
            clamp01(frame.left_low),
            clamp01(frame.left_high),
            clamp01(frame.right_low),
            clamp01(frame.right_high),
            clamp01(frame.engine_amplitude),
        )
        self._levels = [
            current + (target - current) * self.smoothing
            for current, target in zip(self._levels, targets)
        ]
        left_low, left_high, right_low, right_high, engine_amplitude = self._levels

        np_module = self._np
        positions = np_module.arange(frames, dtype=np_module.float64)
        tau = 2.0 * math.pi

        low_step = tau * 65.0 / self.sample_rate
        low_phase = self._phase_low + positions * low_step
        wave_low = np_module.sin(low_phase)
        self._phase_low = (self._phase_low + frames * low_step) % tau

        high_step = tau * 190.0 / self.sample_rate
        high_phase = self._phase_high + positions * high_step
        wave_high = 0.7 * np_module.sin(high_phase) + 0.3 * np_module.sin(high_phase * 1.618)
        self._phase_high = (self._phase_high + frames * high_step) % tau

        try:
            engine_hz = float(frame.engine_hz)
        except (TypeError, ValueError):
            engine_hz = 0.0
        if not math.isfinite(engine_hz):
            engine_hz = 0.0
        engine_hz = max(0.0, engine_hz)
        if engine_hz > 0.0 and engine_amplitude > 0.0:
            engine_step = tau * engine_hz / self.sample_rate
            engine_phase = self._phase_engine + positions * engine_step
            cycles = engine_phase / tau
            wave_engine = 2.0 * (cycles - np_module.floor(cycles + 0.5))
            self._phase_engine = (self._phase_engine + frames * engine_step) % tau
        else:
            wave_engine = np_module.zeros(frames, dtype=np_module.float64)

        left_mix = wave_low * left_low + wave_high * left_high + wave_engine * engine_amplitude
        right_mix = wave_low * right_low + wave_high * right_high + wave_engine * engine_amplitude
        if self.soft_clip:
            # Bluetooth int8 has little headroom. A normalized tanh limiter
            # keeps layered detail instead of flattening every overload to ±127.
            normalizer = math.tanh(1.2)
            left_mix = np_module.tanh(left_mix * 1.2) / normalizer
            right_mix = np_module.tanh(right_mix * 1.2) / normalizer
        pcm = np_module.empty((frames, 2), dtype=np_module.float32)
        pcm[:, 0] = np_module.clip(left_mix, -1.0, 1.0)
        pcm[:, 1] = np_module.clip(right_mix, -1.0, 1.0)
        return pcm
