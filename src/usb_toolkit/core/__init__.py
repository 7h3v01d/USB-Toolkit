# usb_toolkit.core — backend-agnostic USB inspection core.
# Copyright 2026 Leon Priest (7h3v01d) — PETL v1.0.

from .models import Configuration, Endpoint, Interface, UsbDevice
from .backend import (
    MockBackend,
    ProbeResult,
    PyusbBackend,
    UsbBackend,
    default_backend,
    demo_devices,
)
from .events import DeviceEvent, EventKind, diff_snapshots
from .audit import AuditLog, VerifyResult, GENESIS
from .ids import UsbIdDatabase, DEFAULT_DB
from .libusb_deploy import DeployResult, PeInfo, deploy, parse_pe
from .baseline import BaselineDiff, BaselineStore, ChangedDevice, diff_against_baseline, stable_key
from .heuristics import Finding, Severity, scan_all, scan_device, worst_severity
from .names import NameResolver, ResolvedName
from .win_names import PnpName, parse_instance_id, pnp_device_names
from . import serialize

__all__ = [
    "Configuration",
    "Endpoint",
    "Interface",
    "UsbDevice",
    "MockBackend",
    "ProbeResult",
    "PyusbBackend",
    "UsbBackend",
    "default_backend",
    "demo_devices",
    "DeviceEvent",
    "EventKind",
    "diff_snapshots",
    "AuditLog",
    "VerifyResult",
    "GENESIS",
    "UsbIdDatabase",
    "DEFAULT_DB",
    "DeployResult",
    "PeInfo",
    "deploy",
    "parse_pe",
    "BaselineDiff",
    "BaselineStore",
    "ChangedDevice",
    "diff_against_baseline",
    "stable_key",
    "Finding",
    "Severity",
    "scan_all",
    "scan_device",
    "worst_severity",
    "serialize",
    "NameResolver",
    "ResolvedName",
    "PnpName",
    "parse_instance_id",
    "pnp_device_names",
]
