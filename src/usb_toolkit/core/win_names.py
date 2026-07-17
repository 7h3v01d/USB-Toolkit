# usb_toolkit.core.win_names
#
# Windows PnP device names via SetupAPI — the same source Device Manager uses.
#
# Why this exists: libusb on Windows usually cannot OPEN a device that is
# already claimed by a native driver (HID, storage, ...), so string
# descriptors come back unreadable and devices show as "Unknown". Windows,
# however, already knows every device's name from enumeration. This module
# reads it — pure ctypes over setupapi.dll, registry-property reads only,
# nothing is opened, written, or executed. Deny-first: any failure at any
# stage yields an empty result, never an exception.
#
# The join key is parsed out of the PnP device instance ID, e.g.
#     USB\VID_0781&PID_5581\4C531001
# -> (0x0781, 0x5581, "4C531001").  The third path segment is the serial when
# the device provides one; composite children and serial-less devices get a
# host-generated segment containing '&', which we treat as no-serial.
#
# Copyright 2026 Leon Priest (7h3v01d) — PETL v1.0.

from __future__ import annotations

import platform
import re
from dataclasses import dataclass
from typing import Optional

_INSTANCE_RE = re.compile(
    r"USB\\VID_([0-9A-Fa-f]{4})&PID_([0-9A-Fa-f]{4})(?:\\(.*))?$"
)

# SetupAPI constants.
_DIGCF_PRESENT = 0x00000002
_DIGCF_ALLCLASSES = 0x00000004
_SPDRP_DEVICEDESC = 0x00000000
_SPDRP_MFG = 0x0000000B
_SPDRP_FRIENDLYNAME = 0x0000000C
_INVALID_HANDLE = -1


@dataclass(frozen=True)
class PnpName:
    name: str                 # FriendlyName if present, else DeviceDesc
    manufacturer: Optional[str] = None


PnpKey = tuple[int, int, Optional[str]]  # (vid, pid, serial-or-None)


def parse_instance_id(instance_id: str) -> Optional[PnpKey]:
    """Parse 'USB\\VID_xxxx&PID_xxxx\\serial' into a join key.

    Segments containing '&' are host-generated placeholders for serial-less
    or composite-child devices and are treated as no-serial.
    """
    match = _INSTANCE_RE.match(instance_id.strip())
    if not match:
        return None
    vid = int(match.group(1), 16)
    pid = int(match.group(2), 16)
    serial = match.group(3)
    if serial is not None:
        serial = serial.strip()
        if not serial or "&" in serial:
            serial = None
    return (vid, pid, serial)


def pnp_device_names(system: Optional[str] = None) -> dict[PnpKey, PnpName]:
    """Return names for every present USB device, keyed by (vid, pid, serial).

    Non-Windows platforms and every failure mode return {}.
    """
    system = system or platform.system()
    if system != "Windows":
        return {}
    try:
        return _query_setupapi()
    except Exception:
        return {}


def _query_setupapi() -> dict[PnpKey, PnpName]:
    import ctypes
    from ctypes import wintypes

    setupapi = ctypes.windll.setupapi  # type: ignore[attr-defined]

    class SP_DEVINFO_DATA(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("ClassGuid", ctypes.c_byte * 16),
            ("DevInst", wintypes.DWORD),
            ("Reserved", ctypes.POINTER(ctypes.c_ulong)),
        ]

    devs = setupapi.SetupDiGetClassDevsW(
        None, "USB", None, _DIGCF_PRESENT | _DIGCF_ALLCLASSES
    )
    if devs == _INVALID_HANDLE:
        return {}

    result: dict[PnpKey, PnpName] = {}
    try:
        index = 0
        info = SP_DEVINFO_DATA()
        info.cbSize = ctypes.sizeof(SP_DEVINFO_DATA)
        buf = ctypes.create_unicode_buffer(1024)
        raw = ctypes.create_string_buffer(2048)

        def _prop(prop: int) -> Optional[str]:
            needed = wintypes.DWORD(0)
            ok = setupapi.SetupDiGetDeviceRegistryPropertyW(
                devs, ctypes.byref(info), prop, None,
                raw, ctypes.sizeof(raw), ctypes.byref(needed),
            )
            if not ok:
                return None
            try:
                text = ctypes.wstring_at(raw)
            except Exception:
                return None
            text = text.strip()
            return text or None

        while setupapi.SetupDiEnumDeviceInfo(devs, index, ctypes.byref(info)):
            index += 1
            if not setupapi.SetupDiGetDeviceInstanceIdW(
                devs, ctypes.byref(info), buf, ctypes.sizeof(buf) // 2, None
            ):
                continue
            key = parse_instance_id(buf.value)
            if key is None:
                continue
            name = _prop(_SPDRP_FRIENDLYNAME) or _prop(_SPDRP_DEVICEDESC)
            if not name:
                continue
            mfg = _prop(_SPDRP_MFG)
            # First name wins; the parent device tends to enumerate before
            # its composite children and carries the better name.
            result.setdefault(key, PnpName(name, mfg))
    finally:
        setupapi.SetupDiDestroyDeviceInfoList(devs)
    return result
