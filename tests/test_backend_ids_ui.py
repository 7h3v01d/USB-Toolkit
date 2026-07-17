"""Backend, usb.ids resolver, and headless UI construction tests."""

import os

import pytest

from usb_toolkit.core.backend import (
    MockBackend,
    PyusbBackend,
    default_backend,
    demo_devices,
)
from usb_toolkit.core.ids import UsbIdDatabase

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


# -- backend ---------------------------------------------------------------

def test_mock_backend_probe_and_enumerate():
    be = MockBackend(demo_devices())
    assert be.probe().ok
    assert len(be.enumerate()) == 2


def test_mock_plug_unplug():
    be = MockBackend([])
    (kbd, flash) = demo_devices()
    be.plug(kbd)
    assert len(be.enumerate()) == 1
    be.unplug(kbd.identity)
    assert be.enumerate() == []


def test_pyusb_backend_never_raises_without_devices():
    # No libusb / no devices in the sandbox — must degrade, not explode.
    be = PyusbBackend()
    probe = be.probe()
    assert probe.backend_name == "PyusbBackend"
    assert isinstance(be.enumerate(), list)


def test_default_backend_returns_a_backend():
    be = default_backend()
    assert hasattr(be, "enumerate")
    assert isinstance(be.enumerate(), list)


# -- usb.ids ---------------------------------------------------------------

def test_ids_missing_database_degrades(tmp_path):
    db = UsbIdDatabase(tmp_path / "nope.ids")
    assert not db.available
    assert db.vendor(0x046D) is None
    assert db.product(0x046D, 0xC31C) is None


def test_ids_parses_vendor_and_product(tmp_path):
    path = tmp_path / "usb.ids"
    path.write_text(
        "# comment\n"
        "046d  Logitech, Inc.\n"
        "\tc31c  Keyboard K120\n"
        "0781  SanDisk Corp.\n"
        "\t5581  Ultra\n",
        encoding="utf-8",
    )
    db = UsbIdDatabase(path)
    assert db.available
    assert db.vendor(0x046D) == "Logitech, Inc."
    assert db.product(0x046D, 0xC31C) == "Keyboard K120"
    assert db.vendor(0x0781) == "SanDisk Corp."
    assert db.product(0x9999, 0x0000) is None


# -- UI (headless) ---------------------------------------------------------

@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def test_main_window_builds(qapp, tmp_path):
    from usb_toolkit.ui.main_window import MainWindow
    be = MockBackend(demo_devices())
    win = MainWindow(be, UsbIdDatabase(), tmp_path / "log.jsonl")
    assert win.centralWidget().count() == 5  # Inspector, Monitor, Posture, Self-Test, About
    win.close()


def test_inspector_populates(qapp):
    from usb_toolkit.ui.inspector import InspectorView
    from usb_toolkit.core.names import NameResolver
    be = MockBackend(demo_devices())
    ids = UsbIdDatabase()
    view = InspectorView(be, ids, NameResolver(ids, pnp_provider=lambda: {}))
    assert view._list.count() == 2


def test_selftest_runs(qapp):
    from usb_toolkit.ui.selftest import SelfTestView
    be = MockBackend(demo_devices())
    view = SelfTestView(be, UsbIdDatabase())
    assert "backend" in view._out.toPlainText().lower()
