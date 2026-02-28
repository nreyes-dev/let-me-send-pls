import sys

from PySide6.QtWidgets import QApplication

from app.main_window import MainWindow
from app.theme import apply_theme


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Let Me Send Pls")
    apply_theme(app)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
