# usb_toolkit.core.heuristics
#
# Suspicion heuristics — descriptor-level tells that a device may not be what
# it claims. These are HEURISTICS, not verdicts: every finding carries a code,
# a severity, and a plain-language explanation of why it matters, and the UI
# presents them as flags to investigate, never as accusations.
#
# Severity ladder:
#   RED   — the classic attack signatures; investigate before trusting.
#   AMBER — irregular; legitimate hardware sometimes does this, but it's
#           exactly where cheap clones and implants also live.
#   INFO  — visibility gaps worth knowing about, not suspicion.
#
# Rules:
#   R1 RED   storage + HID composite       (BadUSB tell: "flash drive" that
#                                            can also type keystrokes)
#   R2 RED   VID 0x0000                    (no legitimate vendor ships this)
#   R3 AMBER HID + vendor-specific combo   (keystroke access plus an opaque
#                                            channel)
#   R4 AMBER mass storage with no serial   (the MSC spec requires a unique
#                                            serial; clones often omit it)
#   R5 AMBER unregistered VID              (not in usb.ids — only when the
#                                            database is actually loaded)
#   R6 AMBER over-budget power draw        (>500 mA config on a USB 2.0 link)
#   R7 INFO  no readable configuration     (descriptors blocked — often just
#                                            missing privileges)
#
# Copyright 2026 Leon Priest (7h3v01d) — PETL v1.0.

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Optional

from .ids import UsbIdDatabase
from .models import UsbDevice


class Severity(IntEnum):
    INFO = 0
    AMBER = 1
    RED = 2


@dataclass(frozen=True)
class Finding:
    code: str
    severity: Severity
    title: str
    detail: str


def _has(dev: UsbDevice, cls: int) -> bool:
    return cls in dev.interface_classes


def scan_device(dev: UsbDevice, ids: Optional[UsbIdDatabase] = None) -> list[Finding]:
    """Run every rule against one device. Deterministic order, worst first."""
    findings: list[Finding] = []

    storage = _has(dev, 0x08)
    hid = _has(dev, 0x03)
    vendor_specific = _has(dev, 0xFF) or dev.device_class == 0xFF

    # R1 — storage + HID composite.
    if storage and hid:
        findings.append(Finding(
            "R1", Severity.RED,
            "Storage device with keyboard capability",
            "This device declares BOTH a mass-storage interface and a HID "
            "interface. A flash drive that can also send keystrokes is the "
            "signature BadUSB pattern. Verify this is a known multifunction "
            "device (e.g. a security key) before trusting it.",
        ))

    # R2 — VID 0x0000.
    if dev.vendor_id == 0x0000:
        findings.append(Finding(
            "R2", Severity.RED,
            "Vendor ID 0x0000",
            "No registered vendor ships VID 0x0000. This is typical of "
            "uninitialized or deliberately blanked firmware.",
        ))

    # R3 — HID + vendor-specific.
    if hid and vendor_specific:
        findings.append(Finding(
            "R3", Severity.AMBER,
            "HID combined with vendor-specific interface",
            "Keystroke-capable AND carrying an opaque vendor channel. Common "
            "in legitimate gaming/peripheral dongles — and in implants. Worth "
            "confirming the vendor.",
        ))

    # R4 — storage with no serial.
    if storage and not dev.serial:
        findings.append(Finding(
            "R4", Severity.AMBER,
            "Mass-storage device without a serial number",
            "The mass-storage class spec requires a unique serial. Missing "
            "serials are common on cheap clones and re-flashed controllers.",
        ))

    # R5 — unregistered VID (only when the database is genuinely loaded).
    if ids is not None and ids.available and dev.vendor_id != 0x0000:
        if ids.vendor(dev.vendor_id) is None:
            findings.append(Finding(
                "R5", Severity.AMBER,
                "Vendor ID not in the public registry",
                f"VID 0x{dev.vendor_id:04x} does not appear in usb.ids. "
                "Recently registered vendors are sometimes missing, but so "
                "are made-up IDs.",
            ))

    # R6 — power draw beyond the USB 2.0 budget.
    max_power = max((c.max_power_ma for c in dev.configurations), default=0)
    usb3 = (dev.speed or 0) >= 4 or dev.bcd_usb >= 0x0300
    if max_power > 500 and not usb3:
        findings.append(Finding(
            "R6", Severity.AMBER,
            f"Requests {max_power} mA on a USB 2.0 link",
            "The USB 2.0 budget is 500 mA per port. Over-budget requests can "
            "brown-out hubs or indicate a descriptor copied from different "
            "hardware.",
        ))

    # R7 — nothing readable below the device descriptor.
    if not dev.configurations:
        findings.append(Finding(
            "R7", Severity.INFO,
            "Configuration descriptors unreadable",
            "Interface-level checks could not run for this device. Usually a "
            "privilege issue (try running elevated), not suspicion.",
        ))

    findings.sort(key=lambda f: (-f.severity, f.code))
    return findings


def scan_all(
    devices: list[UsbDevice], ids: Optional[UsbIdDatabase] = None
) -> dict[tuple, list[Finding]]:
    """Scan every device; keyed by device identity for UI joins."""
    return {dev.identity: scan_device(dev, ids) for dev in devices}


def worst_severity(findings: list[Finding]) -> Optional[Severity]:
    return max((f.severity for f in findings), default=None)
