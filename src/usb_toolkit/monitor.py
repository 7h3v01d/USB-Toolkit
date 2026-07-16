# usb_toolkit.monitor
#
# Background USB monitor. Polls the backend on an interval, diffs snapshots and
# emits connect/disconnect events on the Qt main thread.
#
# Follows the house threading discipline:
#   * QThread subclass, not moveToThread.
#   * A module-level _worker_refs set holds a strong reference to every live
#     worker so Python's GC cannot collect a running QThread mid-flight.
#   * @pyqtSlot on the thread entry point.
#   * Cooperative stop via a flag checked each loop; join on shutdown.
#
# Copyright 2026 Leon Priest (7h3v01d) — PETL v1.0.

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import QThread, pyqtSignal, pyqtSlot

from .core.backend import UsbBackend
from .core.events import DeviceEvent, diff_snapshots
from .core.models import UsbDevice

# Strong references to every live worker — GC safety for running QThreads.
_worker_refs: set["MonitorWorker"] = set()


class MonitorWorker(QThread):
    """Polls ``backend`` every ``interval_ms`` and reports device deltas."""

    event_detected = pyqtSignal(object)   # DeviceEvent
    snapshot_ready = pyqtSignal(list)     # list[UsbDevice]
    error = pyqtSignal(str)

    def __init__(self, backend: UsbBackend, interval_ms: int = 1000, parent=None) -> None:
        super().__init__(parent)
        self._backend = backend
        self._interval_ms = max(200, int(interval_ms))
        self._running = False
        _worker_refs.add(self)

    @pyqtSlot()
    def run(self) -> None:  # QThread entry point
        self._running = True
        try:
            previous: Optional[list[UsbDevice]] = None
            while self._running:
                current = self._backend.enumerate()
                self.snapshot_ready.emit(current)
                if previous is not None:
                    for event in diff_snapshots(previous, current):
                        if not self._running:
                            break
                        self.event_detected.emit(event)
                previous = current
                # Sleep in small slices so stop() is responsive.
                waited = 0
                while self._running and waited < self._interval_ms:
                    self.msleep(50)
                    waited += 50
        except Exception as exc:  # never let the thread die silently
            self.error.emit(str(exc))
        finally:
            self._running = False

    def stop(self) -> None:
        """Request a cooperative stop and wait for the loop to exit."""
        self._running = False
        self.wait(3000)
        _worker_refs.discard(self)
