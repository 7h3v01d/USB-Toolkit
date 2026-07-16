# usb_toolkit.ui.selftest
#
# Backend diagnostics — the old test_usb.py as a panel. Confirms the pyusb +
# libusb backend is present and can enumerate the bus, and reports what the
# usb.ids database resolved to.
#
# Copyright 2026 Leon Priest (7h3v01d) — PETL v1.0.

from __future__ import annotations

from PyQt6.QtCore import pyqtSlot
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..core.backend import UsbBackend
from ..core.ids import UsbIdDatabase
from . import theme


class SelfTestView(QWidget):
    def __init__(self, backend: UsbBackend, ids: UsbIdDatabase, parent=None) -> None:
        super().__init__(parent)
        self._backend = backend
        self._ids = ids
        self._build()
        self.run_test()

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel("BACKEND SELF-TEST")
        title.setObjectName("title")
        header.addWidget(title)
        header.addStretch(1)
        run = QPushButton("Run Test")
        run.setObjectName("primary")
        run.clicked.connect(self.run_test)
        header.addWidget(run)
        outer.addLayout(header)

        self._out = QPlainTextEdit()
        self._out.setReadOnly(True)
        outer.addWidget(self._out, 1)

    @pyqtSlot()
    def run_test(self) -> None:
        lines: list[str] = []
        probe = self._backend.probe()
        mark = "OK  " if probe.ok else "FAIL"
        lines.append(f"[{mark}] backend: {probe.backend_name}")
        lines.append(f"       {probe.detail}")
        lines.append("")

        devices = self._backend.enumerate()
        lines.append(f"[{'OK  ' if devices else '----'}] enumeration: {len(devices)} device(s)")
        for dev in devices:
            vendor = self._ids.vendor(dev.vendor_id) or dev.manufacturer or "?"
            lines.append(f"       {dev.vid_pid}  {vendor}")
        lines.append("")

        if self._ids.available:
            lines.append("[OK  ] usb.ids database loaded")
        else:
            lines.append("[----] usb.ids database not found — names fall back to descriptors")
            lines.append("       place usb.ids in the assets/ folder for vendor resolution")

        self._out.setPlainText("\n".join(lines))
