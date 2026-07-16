# usb_toolkit.core.events
#
# Snapshot diffing. Given two enumerations, report what was plugged and what
# was unplugged. The original monitor only ever detected additions and re-logged
# every device on each change; this computes a clean add/remove delta.
#
# Copyright 2026 Leon Priest (7h3v01d) — PETL v1.0.

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from .models import UsbDevice


class EventKind(str, Enum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"


@dataclass(frozen=True)
class DeviceEvent:
    kind: EventKind
    device: UsbDevice
    timestamp: str  # ISO-8601 UTC

    @staticmethod
    def now(kind: EventKind, device: UsbDevice) -> "DeviceEvent":
        return DeviceEvent(kind, device, datetime.now(timezone.utc).isoformat())


def diff_snapshots(previous: list[UsbDevice], current: list[UsbDevice]) -> list[DeviceEvent]:
    """Return connect/disconnect events between two enumerations.

    Identity is (vid, pid, bus, address). Connections are reported before
    disconnections so a re-plug (new address) reads naturally in the log.
    """
    prev_map = {d.identity: d for d in previous}
    curr_map = {d.identity: d for d in current}

    events: list[DeviceEvent] = []
    for identity, device in curr_map.items():
        if identity not in prev_map:
            events.append(DeviceEvent.now(EventKind.CONNECTED, device))
    for identity, device in prev_map.items():
        if identity not in curr_map:
            events.append(DeviceEvent.now(EventKind.DISCONNECTED, device))
    return events
