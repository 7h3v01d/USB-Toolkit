"""Name-resolution tests: PnP instance-ID parsing and resolver layering.

The SetupAPI call itself can only run on Windows; here the PnP layer is
injected as data so the layering logic is fully exercised. On non-Windows,
pnp_device_names() must return {} and never raise.
"""

from usb_toolkit.core.ids import UsbIdDatabase
from usb_toolkit.core.models import Configuration, Endpoint, Interface, UsbDevice
from usb_toolkit.core.names import NameResolver
from usb_toolkit.core.win_names import PnpName, parse_instance_id, pnp_device_names


def _dev(vid=0x1111, pid=0x2222, serial=None, product=None, manufacturer=None,
         classes=()):
    interfaces = tuple(
        Interface(i, c, 0, 0, (Endpoint(0x81 + i, 0x03, 8),))
        for i, c in enumerate(classes)
    )
    return UsbDevice(
        vendor_id=vid, product_id=pid, device_class=0x00, device_subclass=0,
        device_protocol=0, bcd_usb=0x0200, product=product,
        manufacturer=manufacturer, serial=serial, speed=2, bus=1, address=4,
        configurations=(Configuration(1, 100, interfaces),) if interfaces else (),
    )


def _ids(tmp_path, text=""):
    path = tmp_path / "usb.ids"
    path.write_text(text, encoding="utf-8")
    return UsbIdDatabase(path)


# -- instance-ID parsing ------------------------------------------------------

def test_parse_instance_id_with_serial():
    key = parse_instance_id(r"USB\VID_0781&PID_5581\4C531001")
    assert key == (0x0781, 0x5581, "4C531001")


def test_parse_instance_id_hostgenerated_segment_is_no_serial():
    # Composite children / serial-less devices get '&'-containing segments.
    key = parse_instance_id(r"USB\VID_046D&PID_C31C\5&2A1B3C4D&0&2")
    assert key == (0x046D, 0xC31C, None)


def test_parse_instance_id_lowercase_hex():
    key = parse_instance_id(r"USB\VID_abcd&PID_ef01\XYZ")
    assert key == (0xABCD, 0xEF01, "XYZ")


def test_parse_instance_id_rejects_non_usb():
    assert parse_instance_id(r"PCI\VEN_8086&DEV_1234\3&abc") is None
    assert parse_instance_id("garbage") is None


def test_pnp_query_on_non_windows_is_empty():
    assert pnp_device_names(system="Linux") == {}


# -- resolver layering --------------------------------------------------------

def test_layer1_usbids_product_wins(tmp_path):
    ids = _ids(tmp_path, "0781  SanDisk Corp.\n\t5581  Ultra\n")
    pnp = {(0x0781, 0x5581, "S1"): PnpName("SanDisk Ultra USB Device")}
    r = NameResolver(ids, pnp_provider=lambda: pnp)
    resolved = r.resolve(_dev(vid=0x0781, pid=0x5581, serial="S1"))
    assert resolved.name == "Ultra"
    assert resolved.source == "usb.ids"
    assert resolved.vendor == "SanDisk Corp."


def test_layer2_pnp_when_usbids_misses(tmp_path):
    # This is the exact "Unknown device" scenario from real Windows hardware:
    # VID:PID absent from usb.ids AND string descriptors unreadable.
    ids = _ids(tmp_path)  # empty database
    pnp = {(0xDEAD, 0xBEEF, "S9"): PnpName("Mystery Gadget 3000", "Mystery Corp")}
    r = NameResolver(ids, pnp_provider=lambda: pnp)
    resolved = r.resolve(_dev(vid=0xDEAD, pid=0xBEEF, serial="S9"))
    assert resolved.name == "Mystery Gadget 3000"
    assert resolved.source == "pnp"
    assert resolved.vendor == "Mystery Corp"


def test_pnp_serial_exact_match_preferred(tmp_path):
    ids = _ids(tmp_path)
    pnp = {
        (0xAAAA, 0xBBBB, "S1"): PnpName("Unit One"),
        (0xAAAA, 0xBBBB, "S2"): PnpName("Unit Two"),
    }
    r = NameResolver(ids, pnp_provider=lambda: pnp)
    assert r.resolve(_dev(vid=0xAAAA, pid=0xBBBB, serial="S2")).name == "Unit Two"


def test_pnp_vidpid_fallback_when_serial_unreadable(tmp_path):
    # libusb couldn't read the serial, but PnP knows the device by vid:pid.
    ids = _ids(tmp_path)
    pnp = {(0xAAAA, 0xBBBB, "S1"): PnpName("Known Gadget")}
    r = NameResolver(ids, pnp_provider=lambda: pnp)
    assert r.resolve(_dev(vid=0xAAAA, pid=0xBBBB, serial=None)).name == "Known Gadget"


def test_layer3_descriptor_strings(tmp_path):
    r = NameResolver(_ids(tmp_path), pnp_provider=lambda: {})
    resolved = r.resolve(_dev(product="Widget Pro", manufacturer="ACME"))
    assert resolved.name == "Widget Pro"
    assert resolved.source == "descriptor"


def test_layer4_vendor_plus_category(tmp_path):
    ids = _ids(tmp_path, "0781  SanDisk Corp.\n")  # vendor known, product not
    r = NameResolver(ids, pnp_provider=lambda: {})
    resolved = r.resolve(_dev(vid=0x0781, pid=0x9999, classes=(0x08,)))
    assert resolved.name == "SanDisk Corp. — Mass Storage Device"
    assert resolved.source == "vendor+category"


def test_layer5_category_alone(tmp_path):
    r = NameResolver(_ids(tmp_path), pnp_provider=lambda: {})
    resolved = r.resolve(_dev(classes=(0x03,)))
    assert resolved.name == "HID (keyboard, mouse, or dongle)"
    assert resolved.source == "category"


def test_layer6_vid_pid_is_the_floor(tmp_path):
    r = NameResolver(_ids(tmp_path), pnp_provider=lambda: {})
    resolved = r.resolve(_dev(vid=0x1234, pid=0x5678))
    assert resolved.name == "Device 1234:5678"
    assert resolved.source == "vid_pid"
    # The word "Unknown" must never be the whole answer anymore.
    assert "unknown" not in resolved.name.lower()


def test_refresh_pnp_picks_up_new_entries(tmp_path):
    store = {}
    r = NameResolver(_ids(tmp_path), pnp_provider=lambda: dict(store))
    dev = _dev(vid=0xCAFE, pid=0x0001, serial="X")
    assert r.resolve(dev).source == "vid_pid"
    store[(0xCAFE, 0x0001, "X")] = PnpName("Late Arrival")
    r.refresh_pnp()
    assert r.resolve(dev).name == "Late Arrival"


def test_broken_pnp_provider_degrades(tmp_path):
    def explode():
        raise RuntimeError("setupapi went sideways")
    r = NameResolver(_ids(tmp_path), pnp_provider=explode)
    assert r.resolve(_dev()).source == "vid_pid"  # still resolves
