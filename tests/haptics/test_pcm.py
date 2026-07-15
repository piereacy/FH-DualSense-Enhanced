import numpy as np

from modules.haptics.frame import HapticFrame, SILENT_FRAME
from modules.haptics.pcm import HapticPcmRenderer


def test_renderer_keeps_left_and_right_channels_isolated():
    left = HapticPcmRenderer(numpy_module=np, sample_rate=3000)
    right = HapticPcmRenderer(numpy_module=np, sample_rate=3000)

    left_pcm = left.render(HapticFrame(left_low=1.0), 32)
    right_pcm = right.render(HapticFrame(right_high=1.0), 32)

    assert left_pcm.shape == (32, 2)
    assert np.any(left_pcm[:, 0] != 0.0)
    assert np.all(left_pcm[:, 1] == 0.0)
    assert np.all(right_pcm[:, 0] == 0.0)
    assert np.any(right_pcm[:, 1] != 0.0)


def test_renderer_uses_same_block_smoothing_at_usb_and_bluetooth_rates():
    usb = HapticPcmRenderer(numpy_module=np, sample_rate=48_000)
    bluetooth = HapticPcmRenderer(numpy_module=np, sample_rate=3_000)
    frame = HapticFrame(left_low=1.0)

    usb.render(frame, 512)
    bluetooth.render(frame, 32)

    assert usb.levels == bluetooth.levels
    assert usb.levels[0] == 0.35


def test_renderer_preserves_phase_between_blocks_and_reset_clears_state():
    continuous = HapticPcmRenderer(numpy_module=np, sample_rate=3000)
    split = HapticPcmRenderer(numpy_module=np, sample_rate=3000)
    frame = HapticFrame(engine_hz=83.0, engine_amplitude=0.6)

    whole = continuous.render(frame, 64)
    parts = np.concatenate((split.render(frame, 32), split.render(frame, 32)))

    assert np.allclose(whole[:32], parts[:32])
    assert not np.allclose(whole[32:], parts[32:])  # smoothing is per 10.667 ms block

    split.reset()
    assert split.levels == (0.0, 0.0, 0.0, 0.0, 0.0)
    assert np.all(split.render(SILENT_FRAME, 32) == 0.0)


def test_renderer_rejects_invalid_frame_count():
    renderer = HapticPcmRenderer(numpy_module=np, sample_rate=3000)

    try:
        renderer.render(SILENT_FRAME, 0)
    except ValueError as exc:
        assert "frames" in str(exc)
    else:
        raise AssertionError("render() accepted a zero frame count")
