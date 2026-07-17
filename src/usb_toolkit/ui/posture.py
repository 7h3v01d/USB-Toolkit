# usb_toolkit.ui.posture
#
# Security posture: heuristics scan of the live device set, baseline
# management, and drift detection — with JSON/CSV export.
#
# Copyright 2026 Leon Priest (7h3v01d) — PETL v1.0.

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..core import heuristics, serialize
from ..core.backend import UsbBackend
from ..core.baseline import BaselineStore, diff_against_baseline
from ..core.heuristics import Severity
from ..core.ids import UsbIdDatabase
from ..core.names import NameResolver
from ..core.models import UsbDevice
from . import theme

_SEV_COLOR = {
    Severity.RED: QColor(theme.RED),
    Severity.AMBER: QColor(theme.AMBER),
    Severity.INFO: QColor(theme.TEXT_DIM),
}
_SEV_LABEL = {Severity.RED: "RED", Severity.AMBER: "AMBER", Severity.INFO: "INFO"}


class PostureView(QWidget):
    def __init__(
        self,
        backend: UsbBackend,
        ids: UsbIdDatabase,
        baseline_dir: Path,
        resolver: NameResolver,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._backend = backend
        self._ids = ids
        self._resolver = resolver
        self._store = BaselineStore(baseline_dir)
        self._devices: list[UsbDevice] = []
        self._build()
        self.rescan()

    # -- layout ---------------------------------------------------------

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel("SECURITY POSTURE")
        title.setObjectName("title")
        header.addWidget(title)
        header.addStretch(1)
        self._summary = QLabel("")
        self._summary.setObjectName("dim")
        header.addWidget(self._summary)
        scan_btn = QPushButton("Rescan")
        scan_btn.setObjectName("primary")
        scan_btn.clicked.connect(self.rescan)
        header.addWidget(scan_btn)
        outer.addLayout(header)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Baseline:"))
        self._baseline_combo = QComboBox()
        self._baseline_combo.setMinimumWidth(180)
        controls.addWidget(self._baseline_combo)
        save_btn = QPushButton("Save Baseline")
        save_btn.clicked.connect(self._save_baseline)
        controls.addWidget(save_btn)
        diff_btn = QPushButton("Diff Against Baseline")
        diff_btn.setObjectName("primary")
        diff_btn.clicked.connect(self._run_diff)
        controls.addWidget(diff_btn)
        controls.addStretch(1)
        export_json = QPushButton("Export JSON")
        export_json.clicked.connect(lambda: self._export("json"))
        controls.addWidget(export_json)
        export_csv = QPushButton("Export CSV")
        export_csv.clicked.connect(lambda: self._export("csv"))
        controls.addWidget(export_csv)
        outer.addLayout(controls)

        split = QSplitter(Qt.Orientation.Vertical)

        self._findings = QTreeWidget()
        self._findings.setColumnCount(3)
        self._findings.setHeaderLabels(["Device / Finding", "Severity", "Detail"])
        self._findings.setColumnWidth(0, 340)
        self._findings.setColumnWidth(1, 90)
        split.addWidget(self._findings)

        self._diff = QTreeWidget()
        self._diff.setColumnCount(2)
        self._diff.setHeaderLabels(["Baseline Drift", "Detail"])
        self._diff.setColumnWidth(0, 340)
        split.addWidget(self._diff)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 2)
        outer.addWidget(split, 1)

        self._refresh_baseline_names()

    # -- scan + findings --------------------------------------------------

    @pyqtSlot()
    def rescan(self) -> None:
        self._devices = self._backend.enumerate()
        self._findings.clear()
        red = amber = 0
        for dev in self._devices:
            found = heuristics.scan_device(dev, self._ids)
            name = self._resolver.resolve(dev).name
            worst = heuristics.worst_severity(found)
            node = QTreeWidgetItem(
                self._findings,
                [f"{name}  [{dev.vid_pid}]",
                 _SEV_LABEL.get(worst, "CLEAN") if worst is not None else "CLEAN",
                 f"{len(found)} finding(s)" if found else "no findings"],
            )
            if worst is not None:
                node.setForeground(1, _SEV_COLOR[worst])
            else:
                node.setForeground(1, QColor(theme.PHOSPHOR))
            for f in found:
                child = QTreeWidgetItem(node, [f"{f.code}  {f.title}", _SEV_LABEL[f.severity], f.detail])
                child.setForeground(1, _SEV_COLOR[f.severity])
                if f.severity == Severity.RED:
                    red += 1
                elif f.severity == Severity.AMBER:
                    amber += 1
            node.setExpanded(worst is not None and worst >= Severity.AMBER)
        self._summary.setText(
            f"{len(self._devices)} device(s) — {red} red, {amber} amber"
        )

    # -- baselines ---------------------------------------------------------

    def _refresh_baseline_names(self) -> None:
        current = self._baseline_combo.currentText()
        self._baseline_combo.clear()
        self._baseline_combo.addItems(self._store.names())
        if current:
            idx = self._baseline_combo.findText(current)
            if idx >= 0:
                self._baseline_combo.setCurrentIndex(idx)

    @pyqtSlot()
    def _save_baseline(self) -> None:
        name, ok = QInputDialog.getText(
            self, "Save Baseline", "Baseline name:", text="this-machine"
        )
        if not ok or not name.strip():
            return
        self._devices = self._backend.enumerate()
        path = self._store.save(name, self._devices)
        self._refresh_baseline_names()
        idx = self._baseline_combo.findText(path.stem)
        if idx >= 0:
            self._baseline_combo.setCurrentIndex(idx)
        QMessageBox.information(
            self, "Baseline",
            f"Saved {len(self._devices)} device(s) to baseline '{path.stem}'.",
        )

    @pyqtSlot()
    def _run_diff(self) -> None:
        name = self._baseline_combo.currentText()
        self._diff.clear()
        if not name:
            QTreeWidgetItem(self._diff, ["No baseline selected", "save one first"])
            return
        try:
            base = self._store.load(name)
        except (FileNotFoundError, ValueError, KeyError) as exc:
            QTreeWidgetItem(self._diff, ["Baseline unreadable", str(exc)])
            return
        current = self._backend.enumerate()
        self._devices = current
        result = diff_against_baseline(base, current)

        meta = self._store.meta(name)
        header = QTreeWidgetItem(
            self._diff,
            [f"vs '{name}'", f"captured {meta.get('created', '?')}, "
                             f"{meta.get('device_count', '?')} device(s)"],
        )
        header.setForeground(0, QColor(theme.TEAL))

        if result.clean:
            ok = QTreeWidgetItem(self._diff, ["CLEAN", "machine matches baseline"])
            ok.setForeground(0, QColor(theme.PHOSPHOR))
            return

        for dev in result.added:
            item = QTreeWidgetItem(
                self._diff,
                [f"ADDED  {self._resolver.resolve(dev).name} [{dev.vid_pid}]",
                 f"serial {dev.serial or '—'}"],
            )
            item.setForeground(0, QColor(theme.AMBER))
        for dev in result.removed:
            item = QTreeWidgetItem(
                self._diff,
                [f"REMOVED  {self._resolver.resolve(dev).name} [{dev.vid_pid}]",
                 f"serial {dev.serial or '—'}"],
            )
            item.setForeground(0, QColor(theme.TEXT_DIM))
        for change in result.changed:
            dev = change.device
            item = QTreeWidgetItem(
                self._diff,
                [f"CHANGED  {self._resolver.resolve(dev).name} [{dev.vid_pid}]",
                 "descriptor drift — expand"],
            )
            item.setForeground(0, QColor(theme.RED))
            for fld, (before, after) in change.changed_fields.items():
                QTreeWidgetItem(item, [f"  {fld}", f"{before!r} → {after!r}"])
            item.setExpanded(True)
        for key, before, after in result.count_changed:
            vid, pid, serial = key
            QTreeWidgetItem(
                self._diff,
                [f"COUNT  {vid:04x}:{pid:04x} (serial {serial or '—'})",
                 f"{before} instance(s) → {after}"],
            )

    # -- export --------------------------------------------------------------

    def _export(self, kind: str) -> None:
        if not self._devices:
            self._devices = self._backend.enumerate()
        suffix = "json" if kind == "json" else "csv"
        path, _ = QFileDialog.getSaveFileName(
            self, f"Export {suffix.upper()}",
            f"usb-inventory.{suffix}", f"{suffix.upper()} files (*.{suffix})",
        )
        if not path:
            return
        if kind == "json":
            text = serialize.devices_to_json(
                self._devices, {"exported_by": "USB Toolkit"}
            )
        else:
            text = serialize.devices_to_csv(self._devices)
        try:
            Path(path).write_text(text, encoding="utf-8")
        except OSError as exc:
            QMessageBox.critical(self, "Export", f"Write failed: {exc}")
            return
        QMessageBox.information(
            self, "Export", f"Exported {len(self._devices)} device(s) to\n{path}"
        )
