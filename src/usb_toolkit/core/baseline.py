# usb_toolkit.core.baseline
#
# Named baseline snapshots and machine-state diffing.
#
# A baseline answers "what is normally plugged into this machine?". Diffing a
# live scan against it reports what appeared, what vanished, and what CHANGED
# — the last being the interesting one for security posture (same VID:PID and
# serial, but suddenly a different interface layout, is a classic firmware-
# reflash tell).
#
# Stable identity: (vid, pid, serial). Bus/address are deliberately excluded —
# the host reassigns them every session, and a baseline must survive replugs
# and reboots. Serial-less devices are matched by (vid, pid, None) and
# compared by instance COUNT, since two identical no-serial mice are
# indistinguishable by design.
#
# Storage: one JSON file per baseline under the app dir, written atomically
# (temp + os.replace). Names are sanitized to a safe filename charset.
#
# Copyright 2026 Leon Priest (7h3v01d) — PETL v1.0.

from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from . import serialize
from .models import UsbDevice

_SAFE_NAME = re.compile(r"[^A-Za-z0-9_\-]+")

StableKey = tuple[int, int, Optional[str]]


def stable_key(dev: UsbDevice) -> StableKey:
    return (dev.vendor_id, dev.product_id, dev.serial)


def _fingerprint(dev: UsbDevice) -> dict:
    """The fields whose change is meaningful across sessions."""
    return {
        "product": dev.product,
        "manufacturer": dev.manufacturer,
        "device_class": dev.device_class,
        "bcd_usb": dev.bcd_usb,
        "interface_classes": sorted(dev.interface_classes),
        "interface_count": sum(1 for _ in dev.iter_interfaces()),
        "endpoint_count": sum(len(i.endpoints) for i in dev.iter_interfaces()),
        "max_power_ma": max((c.max_power_ma for c in dev.configurations), default=0),
    }


@dataclass(frozen=True)
class ChangedDevice:
    device: UsbDevice
    changed_fields: dict[str, tuple[object, object]]  # field -> (baseline, now)


@dataclass(frozen=True)
class BaselineDiff:
    added: list[UsbDevice] = field(default_factory=list)
    removed: list[UsbDevice] = field(default_factory=list)
    changed: list[ChangedDevice] = field(default_factory=list)
    count_changed: list[tuple[StableKey, int, int]] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        return not (self.added or self.removed or self.changed or self.count_changed)


def diff_against_baseline(
    baseline: list[UsbDevice], current: list[UsbDevice]
) -> BaselineDiff:
    base_map: dict[StableKey, list[UsbDevice]] = {}
    for dev in baseline:
        base_map.setdefault(stable_key(dev), []).append(dev)
    curr_map: dict[StableKey, list[UsbDevice]] = {}
    for dev in current:
        curr_map.setdefault(stable_key(dev), []).append(dev)

    added: list[UsbDevice] = []
    removed: list[UsbDevice] = []
    changed: list[ChangedDevice] = []
    count_changed: list[tuple[StableKey, int, int]] = []

    for key, devs in curr_map.items():
        if key not in base_map:
            added.extend(devs)
            continue
        base_devs = base_map[key]
        if len(devs) != len(base_devs):
            count_changed.append((key, len(base_devs), len(devs)))
        # Compare descriptor fingerprints (first instance is representative;
        # identical no-serial units share a fingerprint by definition).
        before = _fingerprint(base_devs[0])
        after = _fingerprint(devs[0])
        delta = {
            k: (before[k], after[k])
            for k in before
            if before[k] != after[k]
        }
        if delta:
            changed.append(ChangedDevice(devs[0], delta))

    for key, devs in base_map.items():
        if key not in curr_map:
            removed.extend(devs)

    return BaselineDiff(added, removed, changed, count_changed)


class BaselineStore:
    """Named baseline snapshots on disk, one JSON file each, atomic writes."""

    def __init__(self, directory: Path) -> None:
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def _path(self, name: str) -> Path:
        safe = _SAFE_NAME.sub("_", name.strip()) or "baseline"
        return self.directory / f"{safe}.json"

    def names(self) -> list[str]:
        return sorted(p.stem for p in self.directory.glob("*.json"))

    def save(self, name: str, devices: list[UsbDevice]) -> Path:
        target = self._path(name)
        meta = {
            "name": target.stem,
            "created": datetime.now(timezone.utc).isoformat(),
            "device_count": len(devices),
        }
        text = serialize.devices_to_json(devices, meta)
        fd, tmp = tempfile.mkstemp(dir=str(self.directory), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(text)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, target)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
        return target

    def load(self, name: str) -> list[UsbDevice]:
        path = self._path(name)
        if not path.is_file():
            raise FileNotFoundError(f"no baseline named {name!r}")
        return serialize.devices_from_json(path.read_text(encoding="utf-8"))

    def meta(self, name: str) -> dict:
        path = self._path(name)
        if not path.is_file():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8")).get("meta", {})
        except (json.JSONDecodeError, OSError):
            return {}

    def delete(self, name: str) -> bool:
        path = self._path(name)
        if path.is_file():
            path.unlink()
            return True
        return False
