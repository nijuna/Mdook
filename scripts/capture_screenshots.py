"""Automated offscreen screenshot capture for Mdook documentation.

Generates high-resolution PNG captures of all 3 theme families in both
Dark and Light modes, as well as the modal SettingsDialog, without requiring
an active display server.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Force Qt offscreen platform plugin before importing Qt modules
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication  # noqa: E402

from mdook.gui.settings_dialog import SettingsDialog  # noqa: E402
from mdook.gui.theme import COLOR_MODES, THEME_FAMILIES, get_stylesheet  # noqa: E402
from mdook.gui.window import MainWindow  # noqa: E402


def setup_sample_data(window: MainWindow) -> None:
    """Populates the main window with realistic sample data for screenshots."""
    window.pdf_path_edit.setText("The_Pragmatic_Programmer.pdf")
    window.book_title_badge.setText("PDF")
    window.book_size_badge.setText("2.4 MB  ·  The_Pragmatic_Programmer.pdf")
    window.book_card.setVisible(True)
    window.output_dir_edit.setText("~/Libraries/Programming/")
    window.profile_combo.setCurrentIndex(0)
    window.vault_radio.setChecked(True)


def capture_all() -> None:
    """Captures and saves all theme variations and dialogs."""
    repo_root = Path(__file__).resolve().parent.parent
    screenshots_dir = repo_root / "assets" / "screenshots"
    screenshots_dir.mkdir(parents=True, exist_ok=True)

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("Mdook")

    window = MainWindow()
    setup_sample_data(window)
    window.resize(900, 580)
    window.show()

    print("Generating GUI theme screenshots...")

    for family_key in THEME_FAMILIES:
        for mode_key in COLOR_MODES:
            window.config.theme_family = family_key
            window.config.color_mode = mode_key
            window._dark_mode = mode_key == "dark"

            qss = get_stylesheet(family_key, mode_key)
            app.setStyleSheet(qss)
            window.setStyleSheet(qss)
            window.theme_button.setText("Light" if window._dark_mode else "Dark")
            window.resize(900, 580)
            app.processEvents()

            filename = f"gui-{family_key}-{mode_key}.png"
            dest_path = screenshots_dir / filename
            pixmap = window.grab()
            pixmap.save(str(dest_path), "PNG")
            print(f"  Saved: {dest_path.name} ({pixmap.width()}x{pixmap.height()})")

    # Capture Settings Modal
    print("Generating SettingsDialog screenshot...")
    window.config.theme_family = "library"
    window.config.color_mode = "dark"
    window._dark_mode = True
    qss = get_stylesheet("library", "dark")
    app.setStyleSheet(qss)
    window.setStyleSheet(qss)
    app.processEvents()

    dialog = SettingsDialog(window)
    dialog.family_combo.setCurrentIndex(0)
    dialog.dark_radio.setChecked(True)
    dialog._on_theme_changed()
    dialog.resize(580, 500)
    dialog.show()
    app.processEvents()

    settings_dest = screenshots_dir / "gui-settings-modal.png"
    dialog_pixmap = dialog.grab()
    dialog_pixmap.save(str(settings_dest), "PNG")
    print(f"  Saved: {settings_dest.name} ({dialog_pixmap.width()}x{dialog_pixmap.height()})")
    dialog.close()

    window.close()
    print("All screenshots successfully captured in:", screenshots_dir)


if __name__ == "__main__":
    capture_all()
