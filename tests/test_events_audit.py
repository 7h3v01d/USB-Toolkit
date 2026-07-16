"""Event-diff and audit-chain tests."""

import json

import pytest

from usb_toolkit.core.audit import AuditLog, GENESIS
from usb_toolkit.core.backend import demo_devices
from usb_toolkit.core.events import EventKind, diff_snapshots
from usb_toolkit.core.models import UsbDevice


def _dev(vid, pid, addr):
    return UsbDevice(vendor_id=vid, product_id=pid, device_class=0,
                     device_subclass=0, device_protocol=0, bcd_usb=0x0200,
                     bus=1, address=addr)


def test_diff_detects_connect():
    a = [_dev(1, 1, 4)]
    b = [_dev(1, 1, 4), _dev(2, 2, 5)]
    events = diff_snapshots(a, b)
    assert len(events) == 1
    assert events[0].kind == EventKind.CONNECTED
    assert events[0].device.vendor_id == 2


def test_diff_detects_disconnect():
    a = [_dev(1, 1, 4), _dev(2, 2, 5)]
    b = [_dev(1, 1, 4)]
    events = diff_snapshots(a, b)
    assert len(events) == 1
    assert events[0].kind == EventKind.DISCONNECTED


def test_diff_no_change_is_empty():
    a = demo_devices()
    assert diff_snapshots(a, a) == []


def test_replug_new_address_is_a_fresh_event():
    a = [_dev(1, 1, 4)]
    b = [_dev(1, 1, 9)]  # same device, new host-assigned address
    events = diff_snapshots(a, b)
    kinds = sorted(e.kind.value for e in events)
    assert kinds == ["connected", "disconnected"]


def test_audit_append_and_verify(tmp_path):
    log = AuditLog(tmp_path / "log.jsonl")
    log.append({"kind": "connected", "vid_pid": "046d:c31c"})
    log.append({"kind": "disconnected", "vid_pid": "046d:c31c"})
    result = log.verify()
    assert result.ok
    assert result.records == 2


def test_audit_genesis_prev_hash(tmp_path):
    log = AuditLog(tmp_path / "log.jsonl")
    log.append({"n": 1})
    first = log.records()[0]
    assert first["prev_hash"] == GENESIS


def test_audit_detects_payload_tamper(tmp_path):
    path = tmp_path / "log.jsonl"
    log = AuditLog(path)
    log.append({"n": 1})
    log.append({"n": 2})
    lines = path.read_text().splitlines()
    rec = json.loads(lines[0])
    rec["payload"]["n"] = 999
    lines[0] = json.dumps(rec)
    path.write_text("\n".join(lines) + "\n")
    result = log.verify()
    assert not result.ok
    assert result.broken_line == 1
    assert result.reason == "hash mismatch"


def test_audit_detects_deleted_line(tmp_path):
    path = tmp_path / "log.jsonl"
    log = AuditLog(path)
    for i in range(4):
        log.append({"n": i})
    lines = path.read_text().splitlines()
    del lines[1]  # remove second record -> breaks the chain
    path.write_text("\n".join(lines) + "\n")
    assert not log.verify().ok


def test_audit_is_valid_jsonl(tmp_path):
    # Regression: the original logger produced concatenated arrays; this must
    # be one valid JSON object per line.
    path = tmp_path / "log.jsonl"
    log = AuditLog(path)
    log.append({"a": 1})
    log.append({"b": 2})
    for line in path.read_text().splitlines():
        json.loads(line)  # must not raise


def test_audit_compact_rebuilds_valid_chain(tmp_path):
    log = AuditLog(tmp_path / "log.jsonl")
    log.append({"n": 1})
    log.append({"n": 2})
    log.compact([{"n": 10}, {"n": 20}, {"n": 30}])
    result = log.verify()
    assert result.ok and result.records == 3
