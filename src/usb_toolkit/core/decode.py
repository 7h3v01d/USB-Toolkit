# usb_toolkit.core.decode
#
# Human-readable interpretation of USB descriptors.
#
# This module is the single source of truth for turning raw descriptor codes
# into text. The original scripts had three interpretation bugs, all fixed and
# pinned by tests here:
#
#   1. Device-type classification iterated *configurations* while reading an
#      *interface* field (bInterfaceClass), which raised and silently degraded
#      detection. We now walk configuration -> interface correctly.
#   2. "Speed" was derived from bDeviceProtocol, which is not speed at all.
#      Speed is a link property (libusb speed enum), decoded here separately.
#   3. Max power was read as a *device* field; it is a *configuration* field.
#      It is now reported per configuration.
#
# Copyright 2026 Leon Priest (7h3v01d) — PETL v1.0.

from __future__ import annotations

from .models import Configuration, Endpoint, Interface, UsbDevice

# USB-IF base class codes (bDeviceClass / bInterfaceClass).
_CLASS_NAMES: dict[int, str] = {
    0x00: "Per-Interface",
    0x01: "Audio",
    0x02: "Communications (CDC)",
    0x03: "HID (Human Interface Device)",
    0x05: "Physical",
    0x06: "Image (PTP)",
    0x07: "Printer",
    0x08: "Mass Storage",
    0x09: "Hub",
    0x0A: "CDC-Data",
    0x0B: "Smart Card",
    0x0D: "Content Security",
    0x0E: "Video",
    0x0F: "Personal Healthcare",
    0x10: "Audio/Video",
    0x11: "Billboard",
    0x12: "USB Type-C Bridge",
    0xDC: "Diagnostic Device",
    0xE0: "Wireless Controller",
    0xEF: "Miscellaneous",
    0xFE: "Application Specific",
    0xFF: "Vendor Specific",
}

# libusb_speed enumeration.
_SPEED_NAMES: dict[int, str] = {
    0: "Unknown",
    1: "Low (1.5 Mbps)",
    2: "Full (12 Mbps)",
    3: "High (480 Mbps)",
    4: "SuperSpeed (5 Gbps)",
    5: "SuperSpeed+ (10 Gbps)",
}


def class_name(class_code: int) -> str:
    return _CLASS_NAMES.get(class_code, f"Unknown (0x{class_code:02x})")


def speed_name(speed: int | None) -> str:
    if speed is None:
        return "Unknown (backend did not report)"
    return _SPEED_NAMES.get(speed, f"Unknown (code {speed})")


def usb_version(bcd_usb: int) -> str:
    """Decode bcdUSB (BCD) into a dotted version, e.g. 0x0210 -> '2.10'."""
    major = (bcd_usb >> 8) & 0xFF
    minor = (bcd_usb >> 4) & 0x0F
    sub = bcd_usb & 0x0F
    if sub:
        return f"{major}.{minor}{sub}"
    return f"{major}.{minor}0"


def device_category(device: UsbDevice) -> str:
    """Classify a device by walking configuration -> interface correctly.

    A composite device reports 0x00 at the device level and declares its real
    function(s) per interface, so both the device class and every interface
    class are considered.
    """
    classes = set(device.interface_classes)
    classes.add(device.device_class)

    if 0x08 in classes:
        return "Mass Storage Device"
    if 0x03 in classes:
        return "HID (keyboard, mouse, or dongle)"
    if 0x09 in classes or device.device_class == 0x09:
        return "USB Hub"
    if 0x0E in classes or 0x01 in classes:
        return "Audio/Video Device"
    if 0x07 in classes:
        return "Printer"
    if 0x02 in classes or 0x0A in classes:
        return "Communications Device"
    if 0xFF in classes:
        return "Vendor-Specific (dongle or specialized device)"
    return "Other / Unknown"


def endpoint_summary(ep: Endpoint) -> str:
    return (
        f"0x{ep.address:02x}  {ep.direction:<3}  {ep.transfer_type:<11} "
        f"maxpkt {ep.max_packet_size}B  interval {ep.interval}"
    )


def interface_summary(intf: Interface) -> str:
    return (
        f"Interface {intf.number}: {class_name(intf.interface_class)} "
        f"(subclass 0x{intf.subclass:02x}, protocol 0x{intf.protocol:02x})"
    )


def config_summary(cfg: Configuration) -> str:
    return (
        f"Configuration {cfg.value}: {len(cfg.interfaces)} interface(s), "
        f"max power {cfg.max_power_ma} mA"
    )
