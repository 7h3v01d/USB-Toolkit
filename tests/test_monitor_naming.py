"""Monitor second-chance naming tests.

Reproduces the field report: a device captured at the instant of connection
resolves weakly (strings unreadable, PnP not yet registered), while the same
device inspected moments later has a full name. The monitor row must upgrade.
"""

import os
import tempfile
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from usb_toolkit.core.backend import MockBackend
from usb_toolkit.core.events import DeviceEvent, EventKind
from usb_toolkit.core.ids import UsbIdDatabase
from usb_toolkit.core.models import Configuration, Endpoint, Interface, UsbDevice
from usb_toolkit.core.names import NameResolver
from usb_toolkit.core.win_names import PnpName


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def _bare_device():
    """As captured at connect instant: no strings readable."""
    return UsbDevice(
        vendor_id=0xCAFE, product_id=0x0042, device_class=0x00,
        device_subclass=0, device_protocol=0, bcd_usb=0x0200,
        manufacturer=None, product=None, serial=None, speed=2, bus=1, address=7,
        configurations=(Configuration(1, 100, (
            Interface(0, 0x03, 0, 0, (Endpoint(0x81, 3, 8),)),)),),
    )


def _named_device():
    """Same device moments later: strings now readable."""
    bare = _bare_device()
    return UsbDevice(**{**bare.__dict__, "product": "Macro Pad Mk II",
                        "manufacturer": "DeskForge"})


def _empty_ids(tmp_path):
    return UsbIdDatabase(tmp_path / "missing.ids")


def _make_view(tmp_path, backend, resolver):
    from usb_toolkit.ui.monitor_view import MonitorView
    return MonitorView(backend, _empty_ids(tmp_path),
                       Path(tempfile.mkdtemp()) / "log.jsonl", resolver)


def test_weak_name_row_upgrades_from_fresh_descriptors(qapp, tmp_path):
    backend = MockBackend([_bare_device()])
    resolver = NameResolver(_empty_ids(tmp_path), pnp_provider=lambda: {})
    view = _make_view(tmp_path, backend, resolver)

    view._on_event(DeviceEvent.now(EventKind.CONNECTED, _bare_device()))
    assert view._table.item(0, 2).text() == "HID (keyboard, mouse, or dongle)"

    # Strings become readable — the re-enumeration now returns a named device.
    backend.set_devices([_named_device()])
    view._reresolve_row(0, _bare_device())
    assert view._table.item(0, 2).text() == "Macro Pad Mk II"


def test_weak_name_row_upgrades_from_late_pnp(qapp, tmp_path):
    pnp_store = {}
    backend = MockBackend([_bare_device()])
    resolver = NameResolver(_empty_ids(tmp_path),
                            pnp_provider=lambda: dict(pnp_store))
    view = _make_view(tmp_path, backend, resolver)

    view._on_event(DeviceEvent.now(EventKind.CONNECTED, _bare_device()))
    # Windows names the device just after our capture.
    pnp_store[(0xCAFE, 0x0042, None)] = PnpName("DeskForge Macro Pad")
    view._reresolve_row(0, _bare_device())
    assert view._table.item(0, 2).text() == "DeskForge Macro Pad"


def test_reresolve_never_downgrades(qapp, tmp_path):
    # A row already strongly named must not be overwritten by a weak result.
    backend = MockBackend([_bare_device()])  # fresh scan yields only weak data
    pnp_store = {(0xCAFE, 0x0042, None): PnpName("DeskForge Macro Pad")}
    resolver = NameResolver(_empty_ids(tmp_path),
                            pnp_provider=lambda: dict(pnp_store))
    view = _make_view(tmp_path, backend, resolver)
    view._on_event(DeviceEvent.now(EventKind.CONNECTED, _bare_device()))
    assert view._table.item(0, 2).text() == "DeskForge Macro Pad"

    pnp_store.clear()  # PnP data vanishes; re-resolve would yield category
    view._reresolve_row(0, _bare_device())
    assert view._table.item(0, 2).text() == "DeskForge Macro Pad"


def test_reresolve_out_of_range_row_is_safe(qapp, tmp_path):
    backend = MockBackend([])
    resolver = NameResolver(_empty_ids(tmp_path), pnp_provider=lambda: {})
    view = _make_view(tmp_path, backend, resolver)
    view._reresolve_row(99, _bare_device())  # must not raise
