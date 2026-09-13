"""Unit tests for GUI redesign, theme system, and settings dialog."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from mdook.gui.config import GUIConfig
from mdook.gui.settings_dialog import SettingsDialog
from mdook.gui.theme import THEME_FAMILIES, get_stylesheet, get_tokens
from mdook.gui.window import MainWindow


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    app = QApplication.instance()
    return app if app is not None else QApplication([])


def test_theme_system_all_variants_generate_valid_css() -> None:
    for family in THEME_FAMILIES:
        for mode in ("dark", "light"):
            tokens = get_tokens(family, mode)
            assert "primary_accent" in tokens
            assert "base_bg" in tokens
            assert "surface_card" in tokens

            css = get_stylesheet(family, mode)
            assert f"background-color: {tokens['base_bg']}" in css
            assert tokens["primary_accent"] in css


def test_gui_config_load_save(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_config_file = tmp_path / "gui_config.json"
    monkeypatch.setattr(GUIConfig, "get_config_path", classmethod(lambda cls: fake_config_file))

    # Defaults
    cfg = GUIConfig.load()
    assert cfg.theme_family == "library"
    assert cfg.color_mode == "dark"
    assert cfg.output_mode == "vault"

    # Modify and save
    cfg.theme_family = "carbon"
    cfg.color_mode = "light"
    cfg.output_mode = "single_document"
    cfg.profile = "technical"
    cfg.ai_enabled = True
    cfg.ai_model = "llama3.2"
    cfg.save()

    assert fake_config_file.exists()

    loaded = GUIConfig.load()
    assert loaded.theme_family == "carbon"
    assert loaded.color_mode == "light"
    assert loaded.output_mode == "single_document"
    assert loaded.profile == "technical"
    assert loaded.ai_enabled is True
    assert loaded.ai_model == "llama3.2"


def test_settings_dialog_appearance_and_save(
    qapp: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_config_file = tmp_path / "gui_config.json"
    monkeypatch.setattr(GUIConfig, "get_config_path", classmethod(lambda cls: fake_config_file))

    dialog = SettingsDialog()

    # Change theme family to Amethyst
    amethyst_idx = dialog.family_combo.findData("amethyst")
    assert amethyst_idx >= 0
    dialog.family_combo.setCurrentIndex(amethyst_idx)

    # Change mode to light
    dialog.light_radio.setChecked(True)

    # Change output mode to single document
    dialog.single_radio.setChecked(True)

    received_configs = []
    dialog.settings_saved.connect(received_configs.append)

    dialog._on_save()

    assert len(received_configs) == 1
    saved_cfg = received_configs[0]
    assert saved_cfg.theme_family == "amethyst"
    assert saved_cfg.color_mode == "light"
    assert saved_cfg.output_mode == "single_document"


def test_main_window_output_mode_selector(qapp: QApplication) -> None:
    window = MainWindow()
    # Default is vault
    assert window.vault_radio.isChecked() is True
    assert window.single_radio.isChecked() is False

    # Switch to single document
    window.single_radio.setChecked(True)
    assert window.single_radio.isChecked() is True
    assert window.vault_radio.isChecked() is False


def test_main_window_book_inspection_card(qapp: QApplication, tmp_path: Path) -> None:
    sample_book = tmp_path / "dune.epub"
    sample_book.write_bytes(b"PK\x03\x04" + b"A" * 1024 * 50)  # 50 KB dummy file

    window = MainWindow()
    assert window.book_card.isHidden() is True

    window.pdf_path_edit.setText(str(sample_book))
    assert window.book_card.isHidden() is False
    assert window.book_title_badge.text() == "EPUB"
    assert "dune.epub" in window.book_size_badge.text()


def test_settings_live_preview_and_window_theme_application(
    qapp: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_config_file = tmp_path / "gui_config.json"
    monkeypatch.setattr(GUIConfig, "get_config_path", classmethod(lambda cls: fake_config_file))

    window = MainWindow()
    initial_qss = window.styleSheet()

    dialog = SettingsDialog(window)
    dialog.settings_saved.connect(window._on_settings_saved)

    # Change to Amethyst
    amethyst_idx = dialog.family_combo.findData("amethyst")
    dialog.family_combo.setCurrentIndex(amethyst_idx)

    amethyst_dark_qss = get_stylesheet("amethyst", "dark")
    assert window.styleSheet() == amethyst_dark_qss
    assert dialog.styleSheet() == amethyst_dark_qss

    # Cancel should revert
    dialog._on_cancel()
    assert window.styleSheet() == initial_qss

    # Open again, change to Carbon, and Save
    dialog2 = SettingsDialog(window)
    dialog2.settings_saved.connect(window._on_settings_saved)
    carbon_idx = dialog2.family_combo.findData("carbon")
    dialog2.family_combo.setCurrentIndex(carbon_idx)
    dialog2._on_save()

    carbon_dark_qss = get_stylesheet("carbon", "dark")
    assert window.styleSheet() == carbon_dark_qss
    assert window.config.theme_family == "carbon"
