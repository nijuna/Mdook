"""Entry point: `python -m mdook` launches the GUI."""

from __future__ import annotations

import sys


def main() -> None:
    from PySide6.QtWidgets import QApplication

    from mdook.gui.window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("Mdook")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
