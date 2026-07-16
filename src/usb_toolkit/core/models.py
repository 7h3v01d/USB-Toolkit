# usb_toolkit.core.models
#
# Backend-agnostic descriptor model.
#
# The UI and all logic operate on these plain dataclasses only. Nothing above
# the backend layer ever imports pyusb, so the entire application is testable
# against a mock backend and immune to libusb availability.
#
# Copyright 2026 Leon Priest (7h3v01d)
# Private Evaluation & Testing License (PETL) v1.0 — see LICENSE.txt.

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterator, Optional


@dataclass(frozen=True)
class Endpoint:
    """A single USB endpoint descriptor."""

    address: int
    attributes: int
    max_packet_size: int
    interval: int = 0

    @property
    def number(self) -> int:
        return self.address & 0x0F

    @property
    def direction(self) -> str:
        return "IN" if (self.address & 0x80) else "OUT"

    @property
    def transfer_type(self) -> str:
        return ("Control", "Isochronous", "Bulk", "Interrupt")[self.attributes & 0x03]


@dataclass(frozen=True)
class Interface:
    """A single USB interface (alt-setting 0) descriptor."""

    number: int
    interface_class: int
    subclass: int
    protocol: int
    endpoints: tuple[Endpoint, ...] = ()


@dataclass(frozen=True)
class Configuration:
    """A USB configuration descriptor."""

    value: int
    max_power_ma: int
    interfaces: tuple[Interface, ...] = ()


@dataclass(frozen=True)
class UsbDevice:
    """A fully-resolved USB device, independent of any backend object.

    All string fields may be ``None`` when the descriptor was absent or the
    string could not be read (common without elevated privileges). Callers must
    treat ``None`` as "unknown", never as an error.
    """

    vendor_id: int
    product_id: int
    device_class: int
    device_subclass: int
    device_protocol: int
    bcd_usb: int
    manufacturer: Optional[str] = None
    product: Optional[str] = None
    serial: Optional[str] = None
    speed: Optional[int] = None          # libusb speed enum, or None if unknown
    bus: Optional[int] = None
    address: Optional[int] = None
    configurations: tuple[Configuration, ...] = ()

    @property
    def vid_pid(self) -> str:
        return f"{self.vendor_id:04x}:{self.product_id:04x}"

    @property
    def identity(self) -> tuple[int, int, Optional[int], Optional[int]]:
        """Stable-per-connection identity: (vid, pid, bus, address).

        Address is assigned by the host at enumeration, so the same physical
        device re-plugged may receive a new address — which is exactly the
        signal the monitor treats as a fresh handshake.
        """
        return (self.vendor_id, self.product_id, self.bus, self.address)

    def iter_interfaces(self) -> Iterator[Interface]:
        for cfg in self.configurations:
            yield from cfg.interfaces

    @property
    def interface_classes(self) -> frozenset[int]:
        return frozenset(i.interface_class for i in self.iter_interfaces())
