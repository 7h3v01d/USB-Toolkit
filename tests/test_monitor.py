"""Monitor worker tests — lifecycle, event emission, GC-safety refs."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from usb_toolkit.core.backend import MockBackend, demo_devices
from usb_toolkit.core.models import UsbDevice
from usb_toolkit import monitor as monitor_mod
from usb_toolkit.monitor import MonitorWorker, _worker_refs


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def _dongle():
    return UsbDevice(vendor_id=0x1234, product_id=0x5678, device_class=0x03,
                     device_subclass=0, device_protocol=0, bcd_usb=0x0200,
                     product="Test Dongle", speed=2, bus=3, address=9)


def test_worker_registers_strong_ref(qapp):
    be = MockBackend(demo_devices())
    worker = MonitorWorker(be, interval_ms=200)
    assert worker in _worker_refs
    worker.stop()
    assert worker not in _worker_refs


def test_worker_emits_connect_event(qapp):
    from PyQt6.QtCore import QCoreApplication, QTimer

    be = MockBackend(demo_devices())
    worker = MonitorWorker(be, interval_ms=200)
    seen = []
    worker.event_detected.connect(lambda e: seen.append(e))

    worker.start()
    QTimer.singleShot(250, lambda: be.plug(_dongle()))

    # Pump the event loop briefly to collect the signal.
    import time
    deadline = time.time() + 3.0
    while time.time() < deadline and not seen:
        QCoreApplication.processEvents()
        time.sleep(0.05)

    worker.stop()
    assert any(e.device.vendor_id == 0x1234 for e in seen)


def test_worker_stop_is_idempotent(qapp):
    be = MockBackend([])
    worker = MonitorWorker(be, interval_ms=200)
    worker.start()
    worker.stop()
    worker.stop()  # must not raise or hang
    assert not worker.isRunning()
