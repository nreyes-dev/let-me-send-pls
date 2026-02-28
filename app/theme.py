from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

BASE = "#1e1e2e"
MANTLE = "#181825"
CRUST = "#11111b"
SURFACE0 = "#313244"
SURFACE1 = "#45475a"
SURFACE2 = "#585b70"
OVERLAY0 = "#6c7086"
TEXT = "#cdd6f4"
SUBTEXT0 = "#a6adc8"
SUBTEXT1 = "#bac2de"
BLUE = "#89b4fa"
LAVENDER = "#b4befe"
GREEN = "#a6e3a1"
RED = "#f38ba8"
MAUVE = "#cba6f7"
PEACH = "#fab387"
YELLOW = "#f9e2af"

STYLESHEET = f"""
QWidget {{
    background-color: {BASE};
    color: {TEXT};
    font-size: 13px;
}}

QMainWindow {{
    background-color: {BASE};
}}

QLabel {{
    background: transparent;
}}

QLabel#sectionLabel {{
    color: {SUBTEXT0};
    font-size: 11px;
    font-weight: 600;
}}

QPushButton {{
    background-color: {SURFACE0};
    color: {TEXT};
    border: 1px solid {SURFACE1};
    border-radius: 8px;
    padding: 8px 16px;
    font-weight: 500;
}}

QPushButton:hover {{
    background-color: {SURFACE1};
    border-color: {SURFACE2};
}}

QPushButton:pressed {{
    background-color: {SURFACE2};
}}

QPushButton#platformBtn {{
    padding: 10px 20px;
    font-size: 14px;
    border-radius: 10px;
}}

QPushButton#platformBtn:checked {{
    background-color: {BLUE};
    color: {CRUST};
    border-color: {BLUE};
    font-weight: 700;
}}

QPushButton#tierBtn {{
    padding: 6px 14px;
    font-size: 12px;
    border-radius: 6px;
}}

QPushButton#tierBtn:checked {{
    background-color: {MAUVE};
    color: {CRUST};
    border-color: {MAUVE};
    font-weight: 600;
}}

QPushButton#splitBtn {{
    background-color: {BLUE};
    color: {CRUST};
    font-size: 15px;
    font-weight: 700;
    padding: 12px;
    border: none;
    border-radius: 10px;
}}

QPushButton#splitBtn:hover {{
    background-color: {LAVENDER};
}}

QPushButton#splitBtn:disabled {{
    background-color: {SURFACE1};
    color: {OVERLAY0};
}}

QPushButton#folderBtn {{
    background: transparent;
    border: none;
    padding: 4px;
    border-radius: 4px;
}}

QPushButton#folderBtn:hover {{
    background-color: {SURFACE1};
}}

QLineEdit {{
    background-color: {SURFACE0};
    color: {TEXT};
    border: 1px solid {SURFACE1};
    border-radius: 8px;
    padding: 8px 12px;
    selection-background-color: {BLUE};
    selection-color: {CRUST};
}}

QLineEdit:focus {{
    border-color: {BLUE};
}}

QProgressBar {{
    background-color: {SURFACE0};
    border: none;
    border-radius: 6px;
    height: 12px;
    text-align: center;
    color: transparent;
}}

QProgressBar::chunk {{
    background-color: {BLUE};
    border-radius: 6px;
}}

QScrollArea {{
    background: transparent;
    border: none;
}}

QScrollBar:horizontal {{
    background: {MANTLE};
    height: 8px;
    border-radius: 4px;
}}

QScrollBar::handle:horizontal {{
    background: {SURFACE1};
    border-radius: 4px;
    min-width: 30px;
}}

QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal {{
    width: 0;
}}
"""


def apply_theme(app: QApplication) -> None:
    font = QFont()
    font.setPointSize(13)
    app.setFont(font)
    app.setStyleSheet(STYLESHEET)
