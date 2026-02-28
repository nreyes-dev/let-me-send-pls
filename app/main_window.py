from __future__ import annotations

import shutil
from pathlib import Path

from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from app import theme
from app.splitter import SplitResult
from app.widgets import DropZone, PlatformPicker, ResultsPanel
from app.worker import SplitWorker


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Let Me Send Pls")
        self.setMinimumSize(640, 580)
        self.resize(720, 700)

        self._worker: SplitWorker | None = None

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(20)

        # -- header --------------------------------------------------------
        header = QLabel("let me send pls")
        header.setStyleSheet(
            f"font-size: 22px; font-weight: 800; color: {theme.TEXT};"
        )
        root.addWidget(header)

        subtitle = QLabel("Split videos to fit chat upload limits")
        subtitle.setStyleSheet(
            f"color: {theme.SUBTEXT0}; font-size: 13px;"
        )
        root.addWidget(subtitle)

        # -- platform picker -----------------------------------------------
        self._picker = PlatformPicker()
        root.addWidget(self._picker)

        # -- drop zone -----------------------------------------------------
        self._drop = DropZone()
        root.addWidget(self._drop)

        # -- output folder -------------------------------------------------
        out_label = QLabel("OUTPUT FOLDER")
        out_label.setObjectName("sectionLabel")
        root.addWidget(out_label)

        folder_row = QHBoxLayout()
        self._out_edit = QLineEdit()
        self._out_edit.setPlaceholderText("Select output folder\u2026")
        folder_row.addWidget(self._out_edit)

        browse_btn = QPushButton("Browse\u2026")
        browse_btn.clicked.connect(self._browse_output)
        folder_row.addWidget(browse_btn)
        root.addLayout(folder_row)

        # -- split button --------------------------------------------------
        self._split_btn = QPushButton("\u2702  Split Video")
        self._split_btn.setObjectName("splitBtn")
        self._split_btn.setEnabled(False)
        self._split_btn.clicked.connect(self._start_split)
        root.addWidget(self._split_btn)

        # -- progress ------------------------------------------------------
        self._progress = QProgressBar()
        self._progress.setRange(0, 1000)
        self._progress.setValue(0)
        self._progress.hide()
        root.addWidget(self._progress)

        self._status = QLabel("")
        self._status.setStyleSheet(
            f"color: {theme.SUBTEXT0}; font-size: 12px;"
        )
        self._status.hide()
        root.addWidget(self._status)

        # -- results -------------------------------------------------------
        self._results = ResultsPanel()
        root.addWidget(self._results)

        root.addStretch()

        # -- signals -------------------------------------------------------
        self._drop.file_selected.connect(self._on_file_selected)
        self._picker.selection_changed.connect(lambda _: self._update_split_btn())

        # -- ffmpeg check --------------------------------------------------
        if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
            QMessageBox.warning(
                self,
                "ffmpeg not found",
                "ffmpeg and ffprobe are required.\n\n"
                "Install with:\n"
                "  macOS:  brew install ffmpeg\n"
                "  Linux:  sudo apt install ffmpeg\n"
                "  Windows: winget install ffmpeg",
            )

    # -- slots -------------------------------------------------------------

    def _on_file_selected(self, path: str):
        p = Path(path)
        if not self._out_edit.text():
            self._out_edit.setText(str(p.parent / "splits"))
        self._update_split_btn()

    def _update_split_btn(self):
        self._split_btn.setEnabled(
            bool(self._drop.file_path) and self._worker is None
        )

    def _browse_output(self):
        d = QFileDialog.getExistingDirectory(self, "Select output folder")
        if d:
            self._out_edit.setText(d)

    def _start_split(self):
        fp = self._drop.file_path
        if not fp:
            return
        out_dir = self._out_edit.text().strip()
        if not out_dir:
            QMessageBox.warning(
                self, "No output folder", "Please select an output folder."
            )
            return

        self._results.clear()
        self._split_btn.setEnabled(False)
        self._progress.setValue(0)
        self._progress.show()
        self._status.show()
        self._status.setStyleSheet(
            f"color: {theme.SUBTEXT0}; font-size: 12px;"
        )
        self._status.setText("Starting\u2026")

        self._worker = SplitWorker(
            input_path=Path(fp),
            output_dir=Path(out_dir),
            max_size_mb=self._picker.max_size_mb,
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_progress(self, pct: float, msg: str):
        self._progress.setValue(int(pct * 1000))
        self._status.setText(msg)

    def _on_finished(self, result: SplitResult):
        self._worker = None
        self._progress.hide()
        self._update_split_btn()

        if result.error:
            self._status.setText(f"Error: {result.error}")
            self._status.setStyleSheet(
                f"color: {theme.RED}; font-size: 12px;"
            )
            return

        n = len(result.parts)
        self._status.setText(
            f"Done \u2014 split into {n} part{'s' if n != 1 else ''}"
        )
        self._status.setStyleSheet(
            f"color: {theme.GREEN}; font-size: 12px;"
        )
        self._results.set_parts(result.parts)
