from pathlib import Path

from PySide6.QtCore import QThread, Signal

from app.splitter import SplitResult, get_splitter


class SplitWorker(QThread):
    progress = Signal(float, str)
    finished = Signal(object)

    def __init__(self, input_path: Path, output_dir: Path, max_size_mb: float):
        super().__init__()
        self.input_path = input_path
        self.output_dir = output_dir
        self.max_size_mb = max_size_mb

    def run(self):
        splitter = get_splitter(self.input_path)
        if splitter is None:
            self.finished.emit(
                SplitResult(error=f"Unsupported file type: {self.input_path.suffix}")
            )
            return

        result = splitter.split(
            self.input_path,
            self.output_dir,
            self.max_size_mb,
            on_progress=lambda pct, msg: self.progress.emit(pct, msg),
        )
        self.finished.emit(result)
