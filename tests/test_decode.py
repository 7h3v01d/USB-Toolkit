"""Decode tests — these pin the three original interpretation bugs as fixed."""

from usb_toolkit.core import decode
from usb_toolkit.core.models import (
    Configuration,
    Endpoint,
    Interface,
    UsbDevice,
)


def _mass_storage() -> UsbDevice:
    # Composite: device class 0x00, real function declared on the interface.
    return UsbDevice(
        vendor_id=0x0781, product_id=0x5581,
        device_class=0x00, device_subclass=0, device_protocol=0,
        bcd_usb=0x0300, speed=4,
        configurations=(
            Configuration(1, 500, (
                Interface(0, 0x08, 0x06, 0x50, (Endpoint(0x81, 0x02, 512),)),
            )),
        ),
    )


def test_class_name_known_and_unknown():
    assert decode.class_name(0x08) == "Mass Storage"
    assert "Unknown" in decode.class_name(0x99)


def test_device_category_uses_interface_class_not_config():
    # Bug 1: original code read bInterfaceClass off a configuration and raised.
    dev = _mass_storage()
    assert decode.device_category(dev) == "Mass Storage Device"


def test_device_category_hid():
    dev = UsbDevice(
        vendor_id=1, product_id=1, device_class=0x00, device_subclass=0,
        device_protocol=0, bcd_usb=0x0110,
        configurations=(Configuration(1, 100, (Interface(0, 0x03, 1, 1, ()),)),),
    )
    assert "HID" in decode.device_category(dev)


def test_speed_is_link_property_not_protocol():
    # Bug 2: speed must come from the speed enum, not bDeviceProtocol.
    assert decode.speed_name(4) == "SuperSpeed (5 Gbps)"
    assert decode.speed_name(2) == "Full (12 Mbps)"
    assert "Unknown" in decode.speed_name(None)


def test_usb_version_bcd_decoding():
    assert decode.usb_version(0x0200) == "2.00"
    assert decode.usb_version(0x0110) == "1.10"
    assert decode.usb_version(0x0310) == "3.10"


def test_max_power_is_reported_per_configuration():
    # Bug 3: max power is a configuration field. Model carries it there.
    dev = _mass_storage()
    (cfg,) = dev.configurations
    assert cfg.max_power_ma == 500
    assert "500 mA" in decode.config_summary(cfg)


def test_endpoint_direction_and_type():
    ep_in_bulk = Endpoint(address=0x81, attributes=0x02, max_packet_size=512)
    assert ep_in_bulk.direction == "IN"
    assert ep_in_bulk.transfer_type == "Bulk"
    ep_out_int = Endpoint(address=0x02, attributes=0x03, max_packet_size=8)
    assert ep_out_int.direction == "OUT"
    assert ep_out_int.transfer_type == "Interrupt"
