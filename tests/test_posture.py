"""Posture-pass tests: serialization, baselines + drift, and heuristics."""

import json

from usb_toolkit.core import serialize
from usb_toolkit.core.backend import demo_devices
from usb_toolkit.core.baseline import (
    BaselineStore,
    diff_against_baseline,
    stable_key,
)
from usb_toolkit.core.heuristics import Severity, scan_device, worst_severity
from usb_toolkit.core.ids import UsbIdDatabase
from usb_toolkit.core.models import Configuration, Endpoint, Interface, UsbDevice


def _dev(vid=0x1111, pid=0x2222, serial="S1", classes=(0x03,), power=100,
         speed=2, bcd=0x0200, product="Widget", configs=True):
    interfaces = tuple(
        Interface(i, c, 0, 0, (Endpoint(0x81 + i, 0x03, 8),))
        for i, c in enumerate(classes)
    )
    return UsbDevice(
        vendor_id=vid, product_id=pid, device_class=0x00, device_subclass=0,
        device_protocol=0, bcd_usb=bcd, product=product, serial=serial,
        speed=speed, bus=1, address=4,
        configurations=(Configuration(1, power, interfaces),) if configs else (),
    )


# -- serialization -----------------------------------------------------------

def test_serialize_round_trip_exact():
    for dev in demo_devices():
        assert serialize.from_dict(serialize.to_dict(dev)) == dev


def test_devices_json_round_trip():
    devs = demo_devices()
    text = serialize.devices_to_json(devs, {"note": "test"})
    doc = json.loads(text)
    assert doc["schema"] == serialize.SCHEMA_VERSION
    assert serialize.devices_from_json(text) == devs


def test_csv_has_header_and_rows():
    text = serialize.devices_to_csv(demo_devices())
    lines = text.strip().splitlines()
    assert lines[0].startswith("vid_pid,")
    assert len(lines) == 3  # header + 2 devices
    assert "046d:c31c" in lines[1]


# -- baselines ---------------------------------------------------------------

def test_baseline_save_load_round_trip(tmp_path):
    store = BaselineStore(tmp_path)
    devs = demo_devices()
    store.save("office pc!", devs)  # name gets sanitized
    assert store.names() == ["office_pc_"]
    assert store.load("office pc!") == devs
    meta = store.meta("office pc!")
    assert meta["device_count"] == 2


def test_baseline_delete(tmp_path):
    store = BaselineStore(tmp_path)
    store.save("x", demo_devices())
    assert store.delete("x")
    assert store.names() == []
    assert not store.delete("x")


def test_stable_key_excludes_bus_address():
    a = _dev(serial="S1")
    b = UsbDevice(**{**serialize.to_dict(a), "configurations": a.configurations})
    # rebuild with different bus/address
    moved = serialize.from_dict({**serialize.to_dict(a), "bus": 9, "address": 99})
    assert stable_key(a) == stable_key(moved)


def test_diff_clean_when_only_replugged():
    base = [_dev(serial="S1")]
    moved = serialize.from_dict({**serialize.to_dict(base[0]), "bus": 9, "address": 99})
    assert diff_against_baseline(base, [moved]).clean


def test_diff_detects_added_and_removed():
    base = [_dev(vid=1, pid=1, serial="A")]
    curr = [_dev(vid=2, pid=2, serial="B")]
    result = diff_against_baseline(base, curr)
    assert [d.serial for d in result.added] == ["B"]
    assert [d.serial for d in result.removed] == ["A"]


def test_diff_detects_descriptor_drift():
    # Same identity, but the device now also declares a HID interface —
    # the firmware-reflash tell.
    base = [_dev(serial="S1", classes=(0x08,))]
    curr = [_dev(serial="S1", classes=(0x08, 0x03))]
    result = diff_against_baseline(base, curr)
    assert not result.added and not result.removed
    assert len(result.changed) == 1
    assert "interface_classes" in result.changed[0].changed_fields


def test_diff_counts_serialless_instances():
    mouse = _dev(vid=5, pid=5, serial=None)
    result = diff_against_baseline([mouse], [mouse, mouse])
    assert result.count_changed == [((5, 5, None), 1, 2)]


# -- heuristics ---------------------------------------------------------------

def test_r1_storage_plus_hid_is_red():
    dev = _dev(classes=(0x08, 0x03), serial="S1")
    codes = {f.code: f.severity for f in scan_device(dev)}
    assert codes.get("R1") == Severity.RED


def test_r2_vid_zero_is_red():
    dev = _dev(vid=0x0000)
    assert any(f.code == "R2" and f.severity == Severity.RED for f in scan_device(dev))


def test_r3_hid_plus_vendor_specific_is_amber():
    dev = _dev(classes=(0x03, 0xFF))
    assert any(f.code == "R3" for f in scan_device(dev))


def test_r4_storage_without_serial_is_amber():
    dev = _dev(classes=(0x08,), serial=None)
    assert any(f.code == "R4" for f in scan_device(dev))


def test_r4_not_raised_with_serial():
    dev = _dev(classes=(0x08,), serial="4C531001")
    assert not any(f.code == "R4" for f in scan_device(dev))


def test_r5_unregistered_vid_needs_loaded_db(tmp_path):
    db_file = tmp_path / "usb.ids"
    db_file.write_text("046d  Logitech, Inc.\n\tc31c  Keyboard\n", encoding="utf-8")
    db = UsbIdDatabase(db_file)
    unknown = _dev(vid=0xDEAD)
    assert any(f.code == "R5" for f in scan_device(unknown, db))
    known = _dev(vid=0x046D)
    assert not any(f.code == "R5" for f in scan_device(known, db))
    # Without a database, R5 must NOT fire — no data, no accusation.
    empty_db = UsbIdDatabase(tmp_path / "missing.ids")
    assert not any(f.code == "R5" for f in scan_device(unknown, empty_db))


def test_r6_overbudget_on_usb2_only():
    hog2 = _dev(power=900, speed=2, bcd=0x0200)
    assert any(f.code == "R6" for f in scan_device(hog2))
    hog3 = _dev(power=900, speed=4, bcd=0x0310)
    assert not any(f.code == "R6" for f in scan_device(hog3))


def test_r7_unreadable_configs_is_info():
    dev = _dev(configs=False)
    findings = scan_device(dev)
    assert any(f.code == "R7" and f.severity == Severity.INFO for f in findings)


def test_clean_device_has_no_findings():
    dev = _dev(vid=0x046D, classes=(0x03,), serial="K1", power=90)
    assert scan_device(dev) == []
    assert worst_severity([]) is None


def test_findings_sorted_worst_first():
    dev = _dev(vid=0x0000, classes=(0x08, 0x03), serial=None)
    findings = scan_device(dev)
    sevs = [f.severity for f in findings]
    assert sevs == sorted(sevs, reverse=True)
