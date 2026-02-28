from __future__ import annotations

import platform
import subprocess
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor, QDragEnterEvent, QDropEvent, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app import theme
from app.platforms import PLATFORM_ICONS, PLATFORM_NAMES, tiers_for_platform
from app.splitter import SplitPart


# ---------------------------------------------------------------------------
#  PlatformPicker
# ---------------------------------------------------------------------------


class PlatformPicker(QWidget):
    """Lets the user pick a chat platform and size tier."""

    selection_changed = Signal(int)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._current_tier = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        plat_label = QLabel("PLATFORM")
        plat_label.setObjectName("sectionLabel")
        layout.addWidget(plat_label)

        self._plat_group = QButtonGroup(self)
        self._plat_group.setExclusive(True)
        plat_row = QHBoxLayout()
        plat_row.setSpacing(8)
        for name in PLATFORM_NAMES:
            btn = QPushButton(name)
            btn.setObjectName("platformBtn")
            btn.setCheckable(True)
            btn.setProperty("platform", name)
            icon_path = PLATFORM_ICONS.get(name)
            if icon_path and icon_path.exists():
                btn.setIcon(QIcon(str(icon_path)))
                btn.setIconSize(QSize(20, 20))
            self._plat_group.addButton(btn)
            plat_row.addWidget(btn)
        plat_row.addStretch()
        layout.addLayout(plat_row)

        tier_label = QLabel("SIZE LIMIT")
        tier_label.setObjectName("sectionLabel")
        layout.addWidget(tier_label)

        self._tier_layout = QHBoxLayout()
        self._tier_layout.setSpacing(8)
        layout.addLayout(self._tier_layout)

        self._tier_group = QButtonGroup(self)
        self._tier_group.setExclusive(True)

        self._plat_group.buttonClicked.connect(self._on_platform)
        self._tier_group.buttonClicked.connect(self._on_tier)

        first = self._plat_group.buttons()[0]
        first.setChecked(True)
        self._on_platform(first)

    def _clear_tier_buttons(self):
        for btn in list(self._tier_group.buttons()):
            self._tier_group.removeButton(btn)
            btn.deleteLater()
        while self._tier_layout.count():
            item = self._tier_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _on_platform(self, btn: QPushButton):
        name = btn.property("platform")
        self._clear_tier_buttons()
        tiers = tiers_for_platform(name)
        for i, t in enumerate(tiers):
            tb = QPushButton(t.display_name)
            tb.setObjectName("tierBtn")
            tb.setCheckable(True)
            tb.setProperty("tier_idx", i)
            self._tier_group.addButton(tb)
            self._tier_layout.addWidget(tb)
            if i == 0:
                tb.setChecked(True)
                self._current_tier = t
        self._tier_layout.addStretch()
        if self._current_tier:
            self.selection_changed.emit(self._current_tier.max_size_mb)

    def _on_tier(self, btn: QPushButton):
        plat_btn = self._plat_group.checkedButton()
        if not plat_btn:
            return
        name = plat_btn.property("platform")
        tiers = tiers_for_platform(name)
        idx = btn.property("tier_idx")
        if idx is not None and idx < len(tiers):
            self._current_tier = tiers[idx]
            self.selection_changed.emit(self._current_tier.max_size_mb)

    @property
    def max_size_mb(self) -> int:
        return self._current_tier.max_size_mb if self._current_tier else 25


# ---------------------------------------------------------------------------
#  DropZone
# ---------------------------------------------------------------------------


class DropZone(QWidget):
    """Drag-and-drop area for video files."""

    file_selected = Signal(str)

    SUPPORTED = "Video files (*.mp4 *.mov *.avi *.mkv *.webm *.flv *.wmv *.m4v *.ts *.mts)"

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setMinimumHeight(140)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self._file_path: Optional[str] = None
        self._hovering = False

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._icon_label = QLabel("\U0001f3ac")
        self._icon_label.setStyleSheet("font-size: 32px; background: transparent;")
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._icon_label)

        self._text_label = QLabel("Drop video file here \u2014 or click to browse")
        self._text_label.setStyleSheet(
            f"color: {theme.SUBTEXT0}; font-size: 14px; background: transparent;"
        )
        self._text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._text_label)

        self._file_label = QLabel("")
        self._file_label.setStyleSheet(
            f"color: {theme.BLUE}; font-size: 13px; background: transparent;"
        )
        self._file_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._file_label.hide()
        layout.addWidget(self._file_label)

        self.setCursor(Qt.CursorShape.PointingHandCursor)

    # -- painting --

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        border = QColor(theme.BLUE if self._hovering else theme.SURFACE2)
        pen = QPen(border)
        pen.setWidth(2)
        pen.setStyle(Qt.PenStyle.DashLine)
        p.setPen(pen)
        fill = QColor("#252540" if self._hovering else theme.SURFACE0)
        p.setBrush(fill)
        p.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 12, 12)
        p.end()
        super().paintEvent(event)

    # -- drag & drop --

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            self._hovering = True
            self.update()
            event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        self._hovering = False
        self.update()

    def dropEvent(self, event: QDropEvent):
        self._hovering = False
        self.update()
        urls = event.mimeData().urls()
        if urls:
            self._set_file(urls[0].toLocalFile())

    def mousePressEvent(self, event):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select video file",
            "",
            f"{self.SUPPORTED};;All files (*)",
        )
        if path:
            self._set_file(path)

    def _set_file(self, path: str):
        self._file_path = path
        p = Path(path)
        size_mb = p.stat().st_size / (1024 * 1024)
        self._file_label.setText(f"{p.name}  ({size_mb:.1f} MB)")
        self._file_label.show()
        self._text_label.setText("Drop another file to replace")
        self.file_selected.emit(path)

    @property
    def file_path(self) -> Optional[str]:
        return self._file_path


# ---------------------------------------------------------------------------
#  ResultCard
# ---------------------------------------------------------------------------


class ResultCard(QWidget):
    """Displays a thumbnail preview of one split part."""

    CARD_SIZE = 180

    def __init__(self, part: SplitPart, index: int, parent: QWidget | None = None):
        super().__init__(parent)
        self.part = part
        self.setFixedSize(self.CARD_SIZE, self.CARD_SIZE + 58)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        thumb_label = QLabel()
        thumb_label.setFixedSize(self.CARD_SIZE, self.CARD_SIZE)
        thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        thumb_label.setStyleSheet(
            f"background: {theme.SURFACE0}; border-radius: 8px;"
        )

        if part.thumbnail and part.thumbnail.exists():
            pix = QPixmap(str(part.thumbnail))
            if not pix.isNull():
                pix = pix.scaled(
                    self.CARD_SIZE,
                    self.CARD_SIZE,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                thumb_label.setPixmap(pix)
        else:
            thumb_label.setText("\U0001f3ac")
            thumb_label.setStyleSheet(
                thumb_label.styleSheet() + " font-size: 48px;"
            )

        layout.addWidget(thumb_label)

        info = QHBoxLayout()
        info.setContentsMargins(4, 0, 4, 0)

        text_col = QVBoxLayout()
        text_col.setSpacing(0)

        name_lbl = QLabel(f"Part {index + 1}")
        name_lbl.setStyleSheet(
            f"color: {theme.TEXT}; font-weight: 600; font-size: 12px;"
        )
        text_col.addWidget(name_lbl)

        size_mb = part.size_bytes / (1024 * 1024)
        size_lbl = QLabel(f"{size_mb:.1f} MB")
        size_lbl.setStyleSheet(f"color: {theme.SUBTEXT0}; font-size: 11px;")
        text_col.addWidget(size_lbl)

        info.addLayout(text_col)
        info.addStretch()

        folder_btn = QPushButton("\U0001f4c2")
        folder_btn.setObjectName("folderBtn")
        folder_btn.setFixedSize(28, 28)
        folder_btn.setToolTip("Show in file browser")
        folder_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        folder_btn.clicked.connect(lambda: reveal_in_explorer(part.path))
        info.addWidget(folder_btn)

        layout.addLayout(info)


# ---------------------------------------------------------------------------
#  ResultsPanel
# ---------------------------------------------------------------------------


class ResultsPanel(QWidget):
    """Horizontally scrollable panel of ResultCards."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(0, 0, 0, 0)
        self._outer.setSpacing(8)

        self._label = QLabel("RESULTS")
        self._label.setObjectName("sectionLabel")
        self._label.hide()
        self._outer.addWidget(self._label)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self._scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._scroll.setFixedHeight(ResultCard.CARD_SIZE + 70)
        self._scroll.hide()

        self._inner = QWidget()
        self._inner_layout = QHBoxLayout(self._inner)
        self._inner_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self._inner_layout.setSpacing(12)
        self._scroll.setWidget(self._inner)

        self._outer.addWidget(self._scroll)

    def set_parts(self, parts: list[SplitPart]):
        self._clear()
        for i, part in enumerate(parts):
            self._inner_layout.addWidget(ResultCard(part, i))
        self._label.show()
        self._scroll.show()

    def clear(self):
        self._clear()
        self._label.hide()
        self._scroll.hide()

    def _clear(self):
        while self._inner_layout.count():
            item = self._inner_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()


# ---------------------------------------------------------------------------
#  Utilities
# ---------------------------------------------------------------------------


def reveal_in_explorer(path: Path) -> None:
    """Open the native file browser highlighting *path*."""
    system = platform.system()
    if system == "Darwin":
        subprocess.Popen(["open", "-R", str(path)])
    elif system == "Windows":
        subprocess.Popen(["explorer", "/select,", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path.parent)])
