# usb_toolkit.core.names
#
# One resolver, every view. Layered fallthrough — each device gets the best
# name any source can provide, and "Unknown" is no longer a possible output:
#
#   1. usb.ids product name            (canonical, clean)
#   2. Windows PnP friendly name       (what Device Manager shows; works even
#                                       when libusb can't open the device)
#   3. descriptor strings              (product / manufacturer, when readable)
#   4. vendor + category               ("SanDisk Corp. — Mass Storage Device")
#   5. category alone                  ("Mass Storage Device")
#   6. vid:pid                         (always available)
#
# The PnP map is cached and refreshed on demand (cheap enumeration, but not
# free) — the monitor refreshes it when events arrive so newly-connected
# devices resolve against fresh data.
#
# Copyright 2026 Leon Priest (7h3v01d) — PETL v1.0.

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from . import decode
from .ids import UsbIdDatabase
from .models import UsbDevice
from .win_names import PnpKey, PnpName, pnp_device_names


@dataclass(frozen=True)
class ResolvedName:
    name: str
    source: str  # "usb.ids" | "pnp" | "descriptor" | "vendor+category" | "category" | "vid_pid"
    vendor: Optional[str] = None

    @property
    def display(self) -> str:
        return self.name


class NameResolver:
    """Layered device-name resolution with a refreshable PnP cache."""

    def __init__(
        self,
        ids: UsbIdDatabase,
        pnp_provider: Optional[Callable[[], dict[PnpKey, PnpName]]] = None,
    ) -> None:
        self._ids = ids
        self._pnp_provider = pnp_provider or pnp_device_names
        self._pnp: dict[PnpKey, PnpName] = {}
        self._pnp_by_vidpid: dict[tuple[int, int], PnpName] = {}
        self.refresh_pnp()

    def refresh_pnp(self) -> int:
        """Re-query the PnP layer; returns entry count. Never raises."""
        try:
            self._pnp = self._pnp_provider() or {}
        except Exception:
            self._pnp = {}
        self._pnp_by_vidpid = {}
        for (vid, pid, _serial), entry in self._pnp.items():
            self._pnp_by_vidpid.setdefault((vid, pid), entry)
        return len(self._pnp)

    def _pnp_lookup(self, dev: UsbDevice) -> Optional[PnpName]:
        if dev.serial:
            exact = self._pnp.get((dev.vendor_id, dev.product_id, dev.serial))
            if exact is not None:
                return exact
        return self._pnp_by_vidpid.get((dev.vendor_id, dev.product_id))

    def vendor_name(self, dev: UsbDevice) -> Optional[str]:
        return (
            self._ids.vendor(dev.vendor_id)
            or dev.manufacturer
            or (self._pnp_lookup(dev).manufacturer if self._pnp_lookup(dev) else None)
        )

    def resolve(self, dev: UsbDevice) -> ResolvedName:
        vendor = self.vendor_name(dev)

        ids_product = self._ids.product(dev.vendor_id, dev.product_id)
        if ids_product:
            return ResolvedName(ids_product, "usb.ids", vendor)

        pnp = self._pnp_lookup(dev)
        if pnp is not None:
            return ResolvedName(pnp.name, "pnp", vendor or pnp.manufacturer)

        if dev.product:
            return ResolvedName(dev.product, "descriptor", vendor)
        if dev.manufacturer:
            return ResolvedName(f"{dev.manufacturer} device", "descriptor", dev.manufacturer)

        category = decode.device_category(dev)
        if vendor and category != "Other / Unknown":
            return ResolvedName(f"{vendor} — {category}", "vendor+category", vendor)
        if vendor:
            return ResolvedName(f"{vendor} device", "vendor+category", vendor)
        if category != "Other / Unknown":
            return ResolvedName(category, "category", None)

        return ResolvedName(f"Device {dev.vid_pid}", "vid_pid", None)
