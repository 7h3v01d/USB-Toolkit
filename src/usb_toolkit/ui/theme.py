# usb_toolkit.ui.theme
#
# Dark-industrial palette and stylesheet. Obsidian ground, teal primary,
# phosphor / amber / red status, JetBrains Mono, flat zero-radius controls.
#
# Copyright 2026 Leon Priest (7h3v01d) — PETL v1.0.

from __future__ import annotations

OBSIDIAN = "#0b0f14"
PANEL = "#111820"
PANEL_HI = "#182230"
LINE = "#243040"
TEAL = "#2fd6c3"
PHOSPHOR = "#4be08a"
AMBER = "#ffb454"
RED = "#ff5c66"
TEXT = "#cdd6e0"
TEXT_DIM = "#7d8b9c"

FONT = "JetBrains Mono, Consolas, 'Courier New', monospace"

QSS = f"""
* {{
    font-family: {FONT};
    font-size: 12px;
    color: {TEXT};
}}
QMainWindow, QWidget {{
    background-color: {OBSIDIAN};
}}
QTabWidget::pane {{
    border: 1px solid {LINE};
    background: {OBSIDIAN};
}}
QTabBar::tab {{
    background: {PANEL};
    color: {TEXT_DIM};
    padding: 8px 18px;
    border: 1px solid {LINE};
    border-bottom: none;
    margin-right: 2px;
}}
QTabBar::tab:selected {{
    background: {PANEL_HI};
    color: {TEAL};
    border-top: 2px solid {TEAL};
}}
QTabBar::tab:hover {{
    color: {TEXT};
}}
QTreeWidget, QTableWidget, QTextEdit, QPlainTextEdit, QListWidget {{
    background: {PANEL};
    border: 1px solid {LINE};
    selection-background-color: {PANEL_HI};
    selection-color: {TEAL};
}}
QHeaderView::section {{
    background: {PANEL_HI};
    color: {TEXT_DIM};
    padding: 6px;
    border: none;
    border-right: 1px solid {LINE};
    text-transform: uppercase;
    letter-spacing: 1px;
}}
QTreeWidget::item {{ padding: 3px; }}
QTreeWidget::item:selected {{ color: {TEAL}; }}
QPushButton {{
    background: {PANEL_HI};
    color: {TEXT};
    border: 1px solid {LINE};
    padding: 8px 16px;
    border-radius: 0px;
    text-transform: uppercase;
    letter-spacing: 1px;
}}
QPushButton:hover {{
    border: 1px solid {TEAL};
    color: {TEAL};
}}
QPushButton:pressed {{
    background: {OBSIDIAN};
}}
QPushButton:disabled {{
    color: {TEXT_DIM};
    border: 1px solid {LINE};
}}
QPushButton#primary {{
    border: 1px solid {TEAL};
    color: {TEAL};
}}
QPushButton#danger:hover {{
    border: 1px solid {RED};
    color: {RED};
}}
QLabel#title {{
    color: {TEAL};
    font-size: 15px;
    letter-spacing: 2px;
    text-transform: uppercase;
}}
QLabel#dim {{ color: {TEXT_DIM}; }}
QStatusBar {{
    background: {PANEL};
    color: {TEXT_DIM};
    border-top: 1px solid {LINE};
}}
QScrollBar:vertical {{
    background: {OBSIDIAN};
    width: 12px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {LINE};
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{ background: {TEAL}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QSplitter::handle {{ background: {LINE}; }}
"""
