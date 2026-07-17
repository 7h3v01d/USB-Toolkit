# usb_toolkit.core.serialize
#
# UsbDevice <-> plain dict, for baselines and exports. Round-trip is exact:
# from_dict(to_dict(dev)) == dev, pinned by tests. CSV export flattens to one
# row per device for spreadsheet use.
#
# Copyright 2026 Leon Priest (7h3v01d) — PETL v1.0.

from __future__ import annotations

import csv
import io
import json
from typing import Any

from .models import Configuration, Endpoint, Interface, UsbDevice
from . import decode

SCHEMA_VERSION = 1


def to_dict(dev: UsbDevice) -> dict[str, Any]:
    return {
        "vendor_id": dev.vendor_id,
        "product_id": dev.product_id,
        "device_class": dev.device_class,
        "device_subclass": dev.device_subclass,
        "device_protocol": dev.device_protocol,
        "bcd_usb": dev.bcd_usb,
        "manufacturer": dev.manufacturer,
        "product": dev.product,
        "serial": dev.serial,
        "speed": dev.speed,
        "bus": dev.bus,
        "address": dev.address,
        "configurations": [
            {
                "value": cfg.value,
                "max_power_ma": cfg.max_power_ma,
                "interfaces": [
                    {
                        "number": intf.number,
                        "interface_class": intf.interface_class,
                        "subclass": intf.subclass,
                        "protocol": intf.protocol,
                        "endpoints": [
                            {
                                "address": ep.address,
                                "attributes": ep.attributes,
                                "max_packet_size": ep.max_packet_size,
                                "interval": ep.interval,
                            }
                            for ep in intf.endpoints
                        ],
                    }
                    for intf in cfg.interfaces
                ],
            }
            for cfg in dev.configurations
        ],
    }


def from_dict(data: dict[str, Any]) -> UsbDevice:
    return UsbDevice(
        vendor_id=data["vendor_id"],
        product_id=data["product_id"],
        device_class=data["device_class"],
        device_subclass=data["device_subclass"],
        device_protocol=data["device_protocol"],
        bcd_usb=data["bcd_usb"],
        manufacturer=data.get("manufacturer"),
        product=data.get("product"),
        serial=data.get("serial"),
        speed=data.get("speed"),
        bus=data.get("bus"),
        address=data.get("address"),
        configurations=tuple(
            Configuration(
                value=cfg["value"],
                max_power_ma=cfg["max_power_ma"],
                interfaces=tuple(
                    Interface(
                        number=intf["number"],
                        interface_class=intf["interface_class"],
                        subclass=intf["subclass"],
                        protocol=intf["protocol"],
                        endpoints=tuple(
                            Endpoint(
                                address=ep["address"],
                                attributes=ep["attributes"],
                                max_packet_size=ep["max_packet_size"],
                                interval=ep.get("interval", 0),
                            )
                            for ep in intf.get("endpoints", [])
                        ),
                    )
                    for intf in cfg.get("interfaces", [])
                ),
            )
            for cfg in data.get("configurations", [])
        ),
    )


def devices_to_json(devices: list[UsbDevice], meta: dict | None = None) -> str:
    doc = {
        "schema": SCHEMA_VERSION,
        "meta": meta or {},
        "devices": [to_dict(d) for d in devices],
    }
    return json.dumps(doc, indent=2, ensure_ascii=False)


def devices_from_json(text: str) -> list[UsbDevice]:
    doc = json.loads(text)
    return [from_dict(d) for d in doc.get("devices", [])]


def devices_to_csv(devices: list[UsbDevice]) -> str:
    """One row per device — the spreadsheet-friendly flat view."""
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(
        [
            "vid_pid", "manufacturer", "product", "serial", "category",
            "device_class", "usb_version", "speed", "bus", "address",
            "interface_classes", "max_power_ma",
        ]
    )
    for dev in devices:
        classes = ";".join(
            f"0x{c:02x}" for c in sorted(dev.interface_classes)
        )
        max_power = max((c.max_power_ma for c in dev.configurations), default="")
        writer.writerow(
            [
                dev.vid_pid,
                dev.manufacturer or "",
                dev.product or "",
                dev.serial or "",
                decode.device_category(dev),
                f"0x{dev.device_class:02x}",
                decode.usb_version(dev.bcd_usb),
                decode.speed_name(dev.speed),
                dev.bus if dev.bus is not None else "",
                dev.address if dev.address is not None else "",
                classes,
                max_power,
            ]
        )
    return buf.getvalue()
