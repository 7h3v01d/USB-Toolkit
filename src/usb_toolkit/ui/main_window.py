# usb_toolkit.ui.main_window
#
# The application shell: four tabs over a shared backend and usb.ids database.
# Live snapshots from the monitor feed the inspector so both stay in sync.
#
# Copyright 2026 Leon Priest (7h3v01d) — PETL v1.0.

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QLabel,
    QMainWindow,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..core.backend import UsbBackend
from ..core.ids import UsbIdDatabase
from ..core.names import NameResolver
from .inspector import InspectorView
from .monitor_view import MonitorView
from .posture import PostureView
from .selftest import SelfTestView
from . import theme

APP_NAME = "USB Toolkit"
APP_VERSION = "1.1.0"


class MainWindow(QMainWindow):
    def __init__(
        self, backend: UsbBackend, ids: UsbIdDatabase, log_path: Path, deploy_result=None
    ) -> None:
        super().__init__()
        self._backend = backend
        self._ids = ids
        self.setWindowTitle(f"{APP_NAME} {APP_VERSION}")
        self.resize(1040, 680)

        self._resolver = NameResolver(ids)

        tabs = QTabWidget()
        self._inspector = InspectorView(backend, ids, self._resolver)
        self._monitor = MonitorView(backend, ids, log_path, self._resolver)
        self._selftest = SelfTestView(backend, ids, deploy_result=deploy_result)
        self._posture = PostureView(backend, ids, log_path.parent / "baselines", self._resolver)

        # Keep the inspector in sync with live monitor snapshots.
        self._monitor.snapshot.connect(self._inspector.set_devices)

        tabs.addTab(self._inspector, "Inspector")
        tabs.addTab(self._monitor, "Monitor")
        tabs.addTab(self._posture, "Posture")
        tabs.addTab(self._selftest, "Self-Test")
        tabs.addTab(self._about(), "About")
        self.setCentralWidget(tabs)

        probe = backend.probe()
        self.statusBar().showMessage(f"{probe.backend_name} — {probe.detail}")

    def _about(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        title = QLabel(f"{APP_NAME}  {APP_VERSION}")
        title.setObjectName("title")
        layout.addWidget(title)
        body = QLabel(
            "Descriptor inspector and handshake-capture monitor for the USB bus.\n\n"
            "Inspector — decode any device's descriptors into human-readable form.\n"
            "Monitor  — record every connect/disconnect to a chain-hashed audit log.\nPosture  — heuristic rogue-device flags, baselines, and drift detection.\n"
            "Self-Test — confirm the pyusb + libusb backend is wired up.\n\n"
            "Copyright 2026 Leon Priest (7h3v01d).\n"
            "Private Evaluation & Testing License (PETL) v1.0 — see LICENSE.txt."
        )
        body.setWordWrap(True)
        layout.addWidget(body)
        return w

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt override)
        self._monitor.shutdown()
        super().closeEvent(event)
