# usb_toolkit.ui.monitor_view
#
# Real-time handshake capture. Start/stop a background poller; every connect
# and disconnect is written to the chain-hashed audit log and shown live.
#
# Copyright 2026 Leon Priest (7h3v01d) — PETL v1.0.

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..core.audit import AuditLog
from ..core.backend import UsbBackend
from ..core.events import DeviceEvent, EventKind
from ..core.ids import UsbIdDatabase
from ..core.names import NameResolver
from ..core.models import UsbDevice
from ..monitor import MonitorWorker
from . import theme


class MonitorView(QWidget):
    snapshot = pyqtSignal(list)  # forwards live snapshots to the inspector

    def __init__(
        self,
        backend: UsbBackend,
        ids: UsbIdDatabase,
        log_path: Path,
        resolver: NameResolver,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._backend = backend
        self._ids = ids
        self._resolver = resolver
        self._log = AuditLog(log_path)
        self._worker: MonitorWorker | None = None
        self._build()

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel("HANDSHAKE CAPTURE")
        title.setObjectName("title")
        header.addWidget(title)
        header.addStretch(1)
        self._status = QLabel("stopped")
        self._status.setObjectName("dim")
        header.addWidget(self._status)
        self._start_btn = QPushButton("Start")
        self._start_btn.setObjectName("primary")
        self._start_btn.clicked.connect(self._toggle)
        header.addWidget(self._start_btn)
        verify = QPushButton("Verify Log")
        verify.clicked.connect(self._verify)
        header.addWidget(verify)
        outer.addLayout(header)

        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["Time (UTC)", "Event", "Device", "VID:PID"])
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        outer.addWidget(self._table, 1)

        self._log_label = QLabel(f"Audit log: {self._log.path}")
        self._log_label.setObjectName("dim")
        outer.addWidget(self._log_label)

    # -- lifecycle ----------------------------------------------------------

    @pyqtSlot()
    def _toggle(self) -> None:
        if self._worker is None:
            self._start()
        else:
            self._stop()

    def _start(self) -> None:
        self._worker = MonitorWorker(self._backend, interval_ms=1000)
        self._worker.event_detected.connect(self._on_event)
        self._worker.snapshot_ready.connect(self.snapshot)
        self._worker.error.connect(self._on_error)
        self._worker.start()
        self._start_btn.setText("Stop")
        self._start_btn.setObjectName("danger")
        self._start_btn.setStyleSheet("")  # re-poll object-name based QSS
        self._status.setText("monitoring")

    def _stop(self) -> None:
        if self._worker is not None:
            self._worker.stop()
            self._worker = None
        self._start_btn.setText("Start")
        self._start_btn.setObjectName("primary")
        self._status.setText("stopped")

    def shutdown(self) -> None:
        self._stop()

    # -- events -------------------------------------------------------------

    @pyqtSlot(object)
    def _on_event(self, event: DeviceEvent) -> None:
        dev: UsbDevice = event.device
        # A device that just enumerated may only now have a PnP name — refresh
        # the cache so the freshest Windows-side name is available.
        self._resolver.refresh_pnp()
        resolved = self._resolver.resolve(dev)
        name = resolved.name
        payload = {
            "kind": event.kind.value,
            "timestamp": event.timestamp,
            "vid_pid": dev.vid_pid,
            "product": name,
            "name_source": resolved.source,
            "serial": dev.serial,
            "bus": dev.bus,
            "address": dev.address,
        }
        self._log.append(payload)

        row = self._table.rowCount()
        self._table.insertRow(row)
        color = Qt.GlobalColor.green if event.kind == EventKind.CONNECTED else Qt.GlobalColor.red
        cells = [event.timestamp, event.kind.value.upper(), name, dev.vid_pid]
        for col, text in enumerate(cells):
            item = QTableWidgetItem(text)
            if col == 1:
                item.setForeground(color)
            self._table.setItem(row, col, item)
        self._table.scrollToBottom()

        # Race fix: at the instant of connection Windows may not have finished
        # naming the device, and its string descriptors may not be readable
        # yet. If the name came from a weak layer, take a second look shortly
        # after — same treatment the Inspector effectively gets by being
        # opened later.
        if event.kind == EventKind.CONNECTED and resolved.source in (
            "category", "vid_pid", "vendor+category"
        ):
            QTimer.singleShot(
                2500, lambda r=row, d=dev: self._reresolve_row(r, d)
            )

    def _reresolve_row(self, row: int, dev: UsbDevice) -> None:
        """Second-chance naming for a captured connect event (GUI thread)."""
        if row >= self._table.rowCount():
            return
        self._resolver.refresh_pnp()
        # Prefer the device's CURRENT descriptors — strings often become
        # readable a moment after enumeration completes.
        fresh = dev
        for candidate in self._backend.enumerate():
            if candidate.identity == dev.identity:
                fresh = candidate
                break
        resolved = self._resolver.resolve(fresh)
        item = self._table.item(row, 2)
        if item is not None and resolved.name != item.text() and resolved.source not in (
            "category", "vid_pid"
        ):
            item.setText(resolved.name)

    @pyqtSlot(str)
    def _on_error(self, message: str) -> None:
        self._status.setText(f"error: {message}")

    @pyqtSlot()
    def _verify(self) -> None:
        result = self._log.verify()
        if result.ok:
            QMessageBox.information(
                self, "Audit Log", f"Chain intact.\n{result.records} record(s) verified."
            )
        else:
            QMessageBox.critical(
                self,
                "Audit Log",
                f"Chain BROKEN at line {result.broken_line}: {result.reason}.",
            )
