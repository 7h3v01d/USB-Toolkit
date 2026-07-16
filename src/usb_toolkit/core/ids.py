# usb_toolkit.core.ids
#
# Vendor / product name resolution from the public "usb.ids" database
# (the same format shipped with usbutils / http://www.linux-usb.org/usb.ids).
#
# Deny-first / degrade-gracefully: if the database is missing or malformed, the
# resolver simply returns None for every lookup. It never raises to the caller
# and never fabricates a name.
#
# Copyright 2026 Leon Priest (7h3v01d) — PETL v1.0.

from __future__ import annotations

from pathlib import Path
from typing import Optional


class UsbIdDatabase:
    """Lazy, forgiving parser for the usb.ids vendor/product table.

    File format (tab-indented):

        VVVV  Vendor Name
        \tPPPP  Product Name
    """

    def __init__(self, path: Optional[Path] = None) -> None:
        self._vendors: dict[int, str] = {}
        self._products: dict[tuple[int, int], str] = {}
        self._loaded = False
        self._path = path

    @property
    def available(self) -> bool:
        self._ensure_loaded()
        return bool(self._vendors)

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        path = self._path or _default_path()
        if path is None or not path.is_file():
            return
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return
        current_vendor: Optional[int] = None
        for line in text.splitlines():
            if not line or line.startswith("#"):
                continue
            if line.startswith("\t\t"):
                continue  # interface entry — not needed here
            if line.startswith("\t"):
                if current_vendor is None:
                    continue
                body = line[1:]
                pid_hex, _, name = body.partition("  ")
                pid = _parse_hex(pid_hex.strip())
                if pid is not None and name.strip():
                    self._products[(current_vendor, pid)] = name.strip()
            else:
                # A top-level line that isn't a vendor (class 'C', 'AT', etc.)
                # ends the vendor context.
                vid_hex, _, name = line.partition("  ")
                vid = _parse_hex(vid_hex.strip())
                if vid is not None and name.strip() and " " not in vid_hex.strip():
                    current_vendor = vid
                    self._vendors[vid] = name.strip()
                else:
                    current_vendor = None

    def vendor(self, vendor_id: int) -> Optional[str]:
        self._ensure_loaded()
        return self._vendors.get(vendor_id)

    def product(self, vendor_id: int, product_id: int) -> Optional[str]:
        self._ensure_loaded()
        return self._products.get((vendor_id, product_id))


def _parse_hex(token: str) -> Optional[int]:
    try:
        return int(token, 16)
    except (ValueError, TypeError):
        return None


def _default_path() -> Optional[Path]:
    candidate = Path(__file__).resolve().parent.parent.parent.parent / "assets" / "usb.ids"
    return candidate


# Process-wide default instance for convenience.
DEFAULT_DB = UsbIdDatabase()
