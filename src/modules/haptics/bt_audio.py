from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass

from ..dualsense.bt_haptics import (
    BT_HAPTICS_FRAMES,
    BT_HAPTICS_SAMPLE_RATE,
    BluetoothPcmQuantizer,
)
from .frame import HapticFrame, SILENT_FRAME
from .pcm import HapticPcmRenderer

try:
    import numpy as np
except (ImportError, OSError):
    np = None

log = logging.getLogger("fhds.haptics.bluetooth")


@dataclass(frozen=True, slots=True)
class BluetoothAudioDiagnosticsSnapshot:
    running: bool
    failed: bool
    frame_count: int
    queue_rejection_count: int
    deadline_miss_count: int
    max_lateness_ms: float


class BluetoothAudioHaptics:
    """Generate 3 kHz stereo haptics and queue them to DualSense HID I/O."""

    def __init__(
        self,
        controller,
        *,
        numpy_module=np,
        renderer: HapticPcmRenderer | None = None,
        monotonic=time.monotonic,
        sleeper=time.sleep,
    ):
        self._controller = controller
        self._np = numpy_module
        self._renderer = renderer
        if self._renderer is None and self._np is not None:
            self._renderer = HapticPcmRenderer(
                numpy_module=self._np,
                sample_rate=BT_HAPTICS_SAMPLE_RATE,
                soft_clip=True,
            )
        self._quantizer = (
            BluetoothPcmQuantizer(numpy_module=self._np)
            if self._np is not None else None
        )
        self._monotonic = monotonic
        self._sleep = sleeper
        self._frame = SILENT_FRAME
        self._frame_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._running = False
        self._failed = False
        self._warned_failure = False
        self._diagnostics_lock = threading.Lock()
        self._frame_count = 0
        self._queue_rejection_count = 0
        self._deadline_miss_count = 0
        self._max_lateness_s = 0.0

    @property
    def running(self) -> bool:
        return self._running

    @property
    def failed(self) -> bool:
        return self._failed

    def diagnostics_snapshot(self) -> BluetoothAudioDiagnosticsSnapshot:
        with self._diagnostics_lock:
            return BluetoothAudioDiagnosticsSnapshot(
                running=self._running,
                failed=self._failed,
                frame_count=self._frame_count,
                queue_rejection_count=self._queue_rejection_count,
                deadline_miss_count=self._deadline_miss_count,
                max_lateness_ms=round(self._max_lateness_s * 1000.0, 3),
            )

    def reset_failure(self) -> None:
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=1.0)
            if thread.is_alive():
                log.error("Bluetooth haptics worker did not stop; reset deferred")
                return
            self._thread = None
            self._running = False
        self._failed = False
        self._warned_failure = False

    def set_frame(self, frame: HapticFrame) -> None:
        with self._frame_lock:
            self._frame = frame

    def start(self) -> bool:
        thread = self._thread
        if thread is not None:
            if thread.is_alive():
                return self._running
            self._thread = None
            self._running = False
        queue = getattr(self._controller, "queue_bt_haptics", None)
        if (
            self._failed
            or self._np is None
            or self._renderer is None
            or not callable(queue)
            or getattr(self._controller, "transport", None) != "bluetooth"
        ):
            return False

        self._stop_event.clear()
        self._running = True
        self._thread = threading.Thread(
            target=self._run,
            name="fhds-bt-haptics",
            daemon=True,
        )
        self._thread.start()
        log.info("Bluetooth HD body haptics started (3000 Hz stereo, report 0x36)")
        return True

    def _run(self) -> None:
        interval = BT_HAPTICS_FRAMES / BT_HAPTICS_SAMPLE_RATE
        deadline = self._monotonic()
        try:
            while not self._stop_event.is_set():
                with self._frame_lock:
                    frame = self._frame
                pcm = self._renderer.render(frame, BT_HAPTICS_FRAMES)
                payload = self._quantizer.quantize(pcm)
                if not self._controller.queue_bt_haptics(payload):
                    with self._diagnostics_lock:
                        self._queue_rejection_count += 1
                    if getattr(self._controller, "transport", None) == "bluetooth":
                        self._failed = True
                        if not self._warned_failure:
                            self._warned_failure = True
                            log.warning(
                                "Bluetooth HD body haptics queue rejected; "
                                "falling back to compatible rumble for this connection."
                            )
                    break

                with self._diagnostics_lock:
                    self._frame_count += 1

                deadline += interval
                now = self._monotonic()
                lateness = max(0.0, now - deadline)
                if lateness > 0.0:
                    with self._diagnostics_lock:
                        self._deadline_miss_count += 1
                        self._max_lateness_s = max(self._max_lateness_s, lateness)
                if deadline < now - interval:
                    deadline = now
                delay = max(0.0, deadline - now)
                if delay > 0.0:
                    # Python 3.13 uses a high-resolution waitable timer on
                    # Windows. threading.Event.wait() rounds this 10.667 ms
                    # interval toward the system's ~15.6 ms scheduler tick.
                    self._sleep(delay)
        except Exception as exc:
            self._failed = True
            if not self._warned_failure:
                self._warned_failure = True
                log.warning("Bluetooth HD body haptics failed: %s", exc)
        finally:
            self._running = False

    def stop(self) -> None:
        thread = self._thread
        if thread is None:
            return
        self._stop_event.set()
        if thread is not threading.current_thread():
            thread.join(timeout=1.0)
        if thread.is_alive():
            log.error("Bluetooth haptics worker did not stop within 1 second")
            return
        self._thread = None
        self._running = False

        queue = getattr(self._controller, "queue_bt_haptics", None)
        if callable(queue) and getattr(self._controller, "transport", None) == "bluetooth":
            try:
                queue(bytes(64))
            except Exception:
                pass
        if self._renderer is not None:
            self._renderer.reset()
        if self._quantizer is not None:
            self._quantizer.reset()
