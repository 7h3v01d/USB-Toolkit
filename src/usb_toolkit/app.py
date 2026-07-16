# usb_toolkit.app
#
# Application bootstrap. Selects the real pyusb backend when available and
# falls back to a mock backend (demo devices) so the GUI always runs, even on
# a machine with no libusb installed.
#
# Copyright 2026 Leon Priest (7h3v01d) — PETL v1.0.

from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication

from .core.backend import default_backend
from .core.ids import UsbIdDatabase
from .ui import theme
from .ui.main_window import MainWindow


def _log_path() -> Path:
    base = Path.home() / ".usb_toolkit"
    base.mkdir(parents=True, exist_ok=True)
    return base / "usb_handshake.jsonl"


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyleSheet(theme.QSS)

    backend = default_backend()
    ids = UsbIdDatabase()
    window = MainWindow(backend, ids, _log_path())
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
