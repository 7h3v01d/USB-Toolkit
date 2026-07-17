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

from .core import libusb_deploy
from .core.backend import default_backend
from .core.ids import UsbIdDatabase
from .ui import theme
from .ui.main_window import MainWindow


def _app_dir() -> Path:
    base = Path.home() / ".usb_toolkit"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _log_path() -> Path:
    return _app_dir() / "usb_handshake.jsonl"


def _assets_dir() -> Path:
    # <project root>/assets, relative to the installed package.
    return Path(__file__).resolve().parent.parent.parent / "assets"


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyleSheet(theme.QSS)

    # Stage libusb-1.0.dll from assets/ (Windows). Failure is non-fatal — the
    # backend falls through to a system libusb or the mock demo set, and the
    # Self-Test tab reports exactly what happened.
    deploy_result = libusb_deploy.deploy(_assets_dir(), _app_dir() / "bin")

    backend = default_backend(deploy_result)
    ids = UsbIdDatabase()
    window = MainWindow(backend, ids, _log_path(), deploy_result=deploy_result)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
