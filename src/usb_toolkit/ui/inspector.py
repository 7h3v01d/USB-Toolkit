# usb_toolkit.ui.inspector
#
# WhatsUSB, reimagined as a panel: a device list on the left, a full descriptor
# walkthrough on the right. All human-readable text comes from core.decode, so
# the descriptor-interpretation bugs are fixed once for every view.
#
# Copyright 2026 Leon Priest (7h3v01d) — PETL v1.0.

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..core import decode
from ..core.backend import UsbBackend
from ..core.ids import UsbIdDatabase
from ..core.models import UsbDevice
from . import theme


class InspectorView(QWidget):
    def __init__(self, backend: UsbBackend, ids: UsbIdDatabase, parent=None) -> None:
        super().__init__(parent)
        self._backend = backend
        self._ids = ids
        self._devices: list[UsbDevice] = []
        self._build()
        self.refresh()

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel("DEVICE INSPECTOR")
        title.setObjectName("title")
        header.addWidget(title)
        header.addStretch(1)
        self._count = QLabel("")
        self._count.setObjectName("dim")
        header.addWidget(self._count)
        refresh = QPushButton("Rescan")
        refresh.setObjectName("primary")
        refresh.clicked.connect(self.refresh)
        header.addWidget(refresh)
        outer.addLayout(header)

        split = QSplitter(Qt.Orientation.Horizontal)
        self._list = QListWidget()
        self._list.setMinimumWidth(280)
        self._list.currentRowChanged.connect(self._on_select)
        split.addWidget(self._list)

        self._detail = QTreeWidget()
        self._detail.setColumnCount(2)
        self._detail.setHeaderLabels(["Field", "Value"])
        self._detail.setColumnWidth(0, 240)
        split.addWidget(self._detail)
        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 1)
        outer.addWidget(split, 1)

    # -- data ---------------------------------------------------------------

    @pyqtSlot()
    def refresh(self) -> None:
        self._devices = self._backend.enumerate()
        self._list.clear()
        for dev in self._devices:
            vendor = self._ids.vendor(dev.vendor_id) or dev.manufacturer or "Unknown vendor"
            product = self._ids.product(dev.vendor_id, dev.product_id) or dev.product or dev.vid_pid
            item = QListWidgetItem(f"{vendor}\n  {product}  [{dev.vid_pid}]")
            self._list.addItem(item)
        self._count.setText(f"{len(self._devices)} device(s)")
        if self._devices:
            self._list.setCurrentRow(0)
        else:
            self._detail.clear()

    def set_devices(self, devices: list[UsbDevice]) -> None:
        """Allow the monitor tab to push a fresh snapshot in."""
        current = self._list.currentRow()
        self._devices = devices
        self.refresh_from_cache(current)

    def refresh_from_cache(self, keep_row: int = 0) -> None:
        self._list.clear()
        for dev in self._devices:
            vendor = self._ids.vendor(dev.vendor_id) or dev.manufacturer or "Unknown vendor"
            product = self._ids.product(dev.vendor_id, dev.product_id) or dev.product or dev.vid_pid
            self._list.addItem(QListWidgetItem(f"{vendor}\n  {product}  [{dev.vid_pid}]"))
        self._count.setText(f"{len(self._devices)} device(s)")
        if 0 <= keep_row < len(self._devices):
            self._list.setCurrentRow(keep_row)
        elif self._devices:
            self._list.setCurrentRow(0)

    @pyqtSlot(int)
    def _on_select(self, row: int) -> None:
        self._detail.clear()
        if not (0 <= row < len(self._devices)):
            return
        dev = self._devices[row]
        vendor = self._ids.vendor(dev.vendor_id)
        product = self._ids.product(dev.vendor_id, dev.product_id)

        ident = self._section("Identity")
        self._row(ident, "VID:PID", dev.vid_pid)
        self._row(ident, "Vendor (usb.ids)", vendor or "—")
        self._row(ident, "Product (usb.ids)", product or "—")
        self._row(ident, "Manufacturer", dev.manufacturer or "Unknown")
        self._row(ident, "Product string", dev.product or "Unknown")
        self._row(ident, "Serial", dev.serial or "Unknown")

        link = self._section("Link")
        self._row(link, "Category", decode.device_category(dev))
        self._row(link, "Device class", decode.class_name(dev.device_class))
        self._row(link, "USB version", decode.usb_version(dev.bcd_usb))
        self._row(link, "Speed", decode.speed_name(dev.speed))
        self._row(link, "Bus / Address", f"{dev.bus} / {dev.address}")

        for cfg in dev.configurations:
            cnode = self._section(decode.config_summary(cfg))
            self._row(cnode, "Max power", f"{cfg.max_power_ma} mA")
            for intf in cfg.interfaces:
                inode = QTreeWidgetItem(cnode, [decode.interface_summary(intf), ""])
                for ep in intf.endpoints:
                    QTreeWidgetItem(inode, ["Endpoint", decode.endpoint_summary(ep)])
        self._detail.expandAll()

    # -- helpers ------------------------------------------------------------

    def _section(self, title: str) -> QTreeWidgetItem:
        node = QTreeWidgetItem(self._detail, [title, ""])
        node.setForeground(0, Qt.GlobalColor.cyan)
        return node

    def _row(self, parent: QTreeWidgetItem, field: str, value: str) -> None:
        QTreeWidgetItem(parent, [field, value])
