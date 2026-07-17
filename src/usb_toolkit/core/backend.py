# usb_toolkit.core.backend
#
# The one place that touches pyusb / libusb. Everything above this line speaks
# only in usb_toolkit.core.models dataclasses.
#
#   UsbBackend   - abstract interface (enumerate() -> list[UsbDevice], probe()).
#   PyusbBackend - the real backend; converts pyusb objects to models, reading
#                  string descriptors defensively (missing/blocked -> None).
#   MockBackend  - a deterministic in-memory backend for tests and for running
#                  the GUI on a machine with no libusb / no devices.
#
# Copyright 2026 Leon Priest (7h3v01d) — PETL v1.0.

from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import Optional

from .models import Configuration, Endpoint, Interface, UsbDevice


@dataclass(frozen=True)
class ProbeResult:
    """Outcome of a backend self-test."""

    ok: bool
    backend_name: str
    detail: str


class UsbBackend(abc.ABC):
    """Abstract source of USB device descriptors."""

    @abc.abstractmethod
    def probe(self) -> ProbeResult:
        """Verify the backend can talk to the bus. Never raises."""

    @abc.abstractmethod
    def enumerate(self) -> list[UsbDevice]:
        """Return every visible device as a model. Never raises; returns []."""


class MockBackend(UsbBackend):
    """Deterministic backend backed by an in-memory device list.

    Tests and the offline demo drive the whole application through this.
    """

    def __init__(self, devices: Optional[list[UsbDevice]] = None) -> None:
        self._devices: list[UsbDevice] = list(devices or [])

    def set_devices(self, devices: list[UsbDevice]) -> None:
        self._devices = list(devices)

    def plug(self, device: UsbDevice) -> None:
        self._devices.append(device)

    def unplug(self, identity: tuple) -> None:
        self._devices = [d for d in self._devices if d.identity != identity]

    def probe(self) -> ProbeResult:
        return ProbeResult(True, "MockBackend", f"{len(self._devices)} simulated device(s)")

    def enumerate(self) -> list[UsbDevice]:
        return list(self._devices)


class PyusbBackend(UsbBackend):
    """Real backend over pyusb + libusb.

    When ``dll_path`` is supplied (a staged, PE-validated libusb-1.0.dll), it
    is handed to pyusb by explicit path via ``find_library`` — PATH is never
    consulted or mutated for it.
    """

    def __init__(self, dll_path=None) -> None:
        self._usb = None
        self._util = None
        self._dll_path = str(dll_path) if dll_path else None
        self._import_error: Optional[str] = None
        try:
            import usb.core as _core  # noqa: WPS433 (deliberate late import)
            import usb.util as _util

            self._usb = _core
            self._util = _util
        except Exception as exc:  # ImportError or backend init failure
            self._import_error = str(exc)

    def _libusb_backend(self):
        """Build the libusb1 backend, preferring the staged DLL. Never raises."""
        try:
            import usb.backend.libusb1 as libusb1

            if self._dll_path:
                backend = libusb1.get_backend(find_library=lambda _name: self._dll_path)
                if backend is not None:
                    return backend, "staged libusb-1.0.dll"
            backend = libusb1.get_backend()
            if backend is not None:
                return backend, "system libusb-1.0"
        except Exception:
            pass
        return None, "no libusb backend"

    def probe(self) -> ProbeResult:
        if self._usb is None:
            return ProbeResult(False, "PyusbBackend", f"pyusb unavailable: {self._import_error}")
        try:
            backend, backend_label = self._libusb_backend()
            found = self._usb.find(find_all=True, backend=backend)
            count = sum(1 for _ in found) if found is not None else 0
            if backend is None:
                return ProbeResult(
                    True,
                    "PyusbBackend",
                    f"default backend, {count} device(s) — install libusb-1.0 for full access",
                )
            return ProbeResult(True, "PyusbBackend", f"{backend_label}, {count} device(s)")
        except Exception as exc:
            return ProbeResult(False, "PyusbBackend", f"bus error: {exc}")

    def enumerate(self) -> list[UsbDevice]:
        if self._usb is None:
            return []
        try:
            backend, _ = self._libusb_backend()
            raw = self._usb.find(find_all=True, backend=backend)
            if raw is None:
                return []
            return [self._to_model(dev) for dev in raw]
        except Exception:
            return []

    # -- conversion ---------------------------------------------------------

    def _string(self, dev, index: int) -> Optional[str]:
        """Read a string descriptor, returning None on any failure."""
        if not index:
            return None
        try:
            value = self._util.get_string(dev, index)
            return value or None
        except Exception:
            return None

    def _speed(self, dev) -> Optional[int]:
        try:
            return int(dev.speed)
        except Exception:
            return None

    def _to_model(self, dev) -> UsbDevice:
        configs: list[Configuration] = []
        try:
            for cfg in dev:
                interfaces: list[Interface] = []
                for intf in cfg:
                    endpoints = tuple(
                        Endpoint(
                            address=ep.bEndpointAddress,
                            attributes=ep.bmAttributes,
                            max_packet_size=ep.wMaxPacketSize,
                            interval=getattr(ep, "bInterval", 0),
                        )
                        for ep in intf
                    )
                    interfaces.append(
                        Interface(
                            number=intf.bInterfaceNumber,
                            interface_class=intf.bInterfaceClass,
                            subclass=intf.bInterfaceSubClass,
                            protocol=intf.bInterfaceProtocol,
                            endpoints=endpoints,
                        )
                    )
                configs.append(
                    Configuration(
                        value=cfg.bConfigurationValue,
                        # bMaxPower is expressed in 2 mA units.
                        max_power_ma=getattr(cfg, "bMaxPower", 0) * 2,
                        interfaces=tuple(interfaces),
                    )
                )
        except Exception:
            # A permission-blocked device still yields its device-level fields.
            configs = []

        return UsbDevice(
            vendor_id=dev.idVendor,
            product_id=dev.idProduct,
            device_class=dev.bDeviceClass,
            device_subclass=dev.bDeviceSubClass,
            device_protocol=dev.bDeviceProtocol,
            bcd_usb=getattr(dev, "bcdUSB", 0),
            manufacturer=self._string(dev, dev.iManufacturer),
            product=self._string(dev, dev.iProduct),
            serial=self._string(dev, dev.iSerialNumber),
            speed=self._speed(dev),
            bus=getattr(dev, "bus", None),
            address=getattr(dev, "address", None),
            configurations=tuple(configs),
        )


def default_backend(deploy_result=None) -> UsbBackend:
    """Return the real backend if pyusb imports, else a mock so the GUI still runs.

    ``deploy_result`` is an optional libusb_deploy.DeployResult; when it
    succeeded, its staged DLL path is handed to the backend.
    """
    dll_path = None
    if deploy_result is not None and getattr(deploy_result, "ok", False):
        dll_path = deploy_result.dll_path
    backend = PyusbBackend(dll_path=dll_path)
    if backend._usb is None:  # noqa: SLF001 (module-internal factory)
        return MockBackend(demo_devices())
    return backend


def demo_devices() -> list[UsbDevice]:
    """A small, realistic device set for offline demos and tests."""
    keyboard = UsbDevice(
        vendor_id=0x046D, product_id=0xC31C,
        device_class=0x00, device_subclass=0x00, device_protocol=0x00,
        bcd_usb=0x0110, manufacturer="Logitech", product="USB Keyboard",
        serial=None, speed=2, bus=1, address=4,
        configurations=(
            Configuration(
                value=1, max_power_ma=90,
                interfaces=(
                    Interface(
                        number=0, interface_class=0x03, subclass=0x01, protocol=0x01,
                        endpoints=(Endpoint(address=0x81, attributes=0x03, max_packet_size=8, interval=10),),
                    ),
                ),
            ),
        ),
    )
    flash = UsbDevice(
        vendor_id=0x0781, product_id=0x5581,
        device_class=0x00, device_subclass=0x00, device_protocol=0x00,
        bcd_usb=0x0310, manufacturer="SanDisk", product="Ultra USB 3.0",
        serial="4C531001", speed=4, bus=2, address=7,
        configurations=(
            Configuration(
                value=1, max_power_ma=224,
                interfaces=(
                    Interface(
                        number=0, interface_class=0x08, subclass=0x06, protocol=0x50,
                        endpoints=(
                            Endpoint(address=0x81, attributes=0x02, max_packet_size=1024),
                            Endpoint(address=0x02, attributes=0x02, max_packet_size=1024),
                        ),
                    ),
                ),
            ),
        ),
    )
    return [keyboard, flash]
