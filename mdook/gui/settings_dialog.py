"""Settings Dialog for Mdook Desktop GUI.

Provides a modal interface for:
- Appearance & Theme selection (The Library, Amethyst, Carbon in Dark/Light modes)
  with live stylesheet switching.
- Default conversion preferences (Output mode, Profile, Default folder).
- AI Structure Review credentials and non-blocking endpoint latency test.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from mdook.core.llm import LLMConfig
from mdook.core.llm.client import OpenAICompatibleClient
from mdook.gui.config import GUIConfig
from mdook.gui.theme import get_stylesheet


class ConnectionTestWorker(QObject):
    finished = Signal(bool, str)

    def __init__(self, config: LLMConfig) -> None:
        super().__init__()
        self.config = config

    def run(self) -> None:
        client = OpenAICompatibleClient(self.config)
        ok, msg = client.test_connection(timeout_seconds=6.0)
        self.finished.emit(ok, msg)


class SettingsDialog(QDialog):
    settings_saved = Signal(GUIConfig)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Mdook Settings")
        self.setMinimumWidth(560)
        self.setObjectName("SettingsDialog")

        self.config = GUIConfig.load()
        self._initial_theme = self.config.theme_family
        self._initial_mode = self.config.color_mode

        self._thread: QThread | None = None
        self._worker: ConnectionTestWorker | None = None

        self._build_ui()
        self._load_values()

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(20)

        # Dialog Title
        title_label = QLabel("Settings")
        title_label.setObjectName("HeaderTitle")
        main_layout.addWidget(title_label)

        # -------------------------------------------------------------------
        # 1. Appearance Section
        # -------------------------------------------------------------------
        appear_card = QFrame()
        appear_card.setObjectName("Card")
        appear_layout = QVBoxLayout(appear_card)
        appear_layout.setContentsMargins(16, 16, 16, 16)
        appear_layout.setSpacing(12)

        sec1_title = QLabel("Appearance & Themes")
        sec1_title.setObjectName("FieldLabel")
        appear_layout.addWidget(sec1_title)

        # Theme Family Row
        family_row = QHBoxLayout()
        family_label = QLabel("Theme Palette:")
        family_label.setFixedWidth(130)
        self.family_combo = QComboBox()
        self.family_combo.addItem("The Library (Warm Amber)", "library")
        self.family_combo.addItem("Amethyst (Royal Violet)", "amethyst")
        self.family_combo.addItem("Carbon (Graphite & Ice Cyan)", "carbon")
        self.family_combo.currentIndexChanged.connect(self._on_theme_changed)
        family_row.addWidget(family_label)
        family_row.addWidget(self.family_combo)
        appear_layout.addLayout(family_row)

        # Color Mode Row
        mode_row = QHBoxLayout()
        mode_label = QLabel("Color Mode:")
        mode_label.setFixedWidth(130)
        self.dark_radio = QRadioButton("Dark")
        self.light_radio = QRadioButton("Light")
        self.mode_group = QButtonGroup(self)
        self.mode_group.addButton(self.dark_radio)
        self.mode_group.addButton(self.light_radio)
        self.dark_radio.toggled.connect(self._on_theme_changed)
        mode_row.addWidget(mode_label)
        mode_row.addWidget(self.dark_radio)
        mode_row.addWidget(self.light_radio)
        mode_row.addStretch()
        appear_layout.addLayout(mode_row)

        main_layout.addWidget(appear_card)

        # -------------------------------------------------------------------
        # 2. Conversion Preferences Section
        # -------------------------------------------------------------------
        pref_card = QFrame()
        pref_card.setObjectName("Card")
        pref_layout = QVBoxLayout(pref_card)
        pref_layout.setContentsMargins(16, 16, 16, 16)
        pref_layout.setSpacing(12)

        sec2_title = QLabel("Default Conversion Preferences")
        sec2_title.setObjectName("FieldLabel")
        pref_layout.addWidget(sec2_title)

        # Default Output Mode
        out_mode_row = QHBoxLayout()
        out_mode_label = QLabel("Default Output Mode:")
        out_mode_label.setFixedWidth(150)
        self.vault_radio = QRadioButton("Modular Vault")
        self.single_radio = QRadioButton("Single Document (.md)")
        self.out_mode_group = QButtonGroup(self)
        self.out_mode_group.addButton(self.vault_radio)
        self.out_mode_group.addButton(self.single_radio)
        out_mode_row.addWidget(out_mode_label)
        out_mode_row.addWidget(self.vault_radio)
        out_mode_row.addWidget(self.single_radio)
        out_mode_row.addStretch()
        pref_layout.addLayout(out_mode_row)

        # Default Profile
        prof_row = QHBoxLayout()
        prof_label = QLabel("Default Profile:")
        prof_label.setFixedWidth(150)
        self.profile_combo = QComboBox()
        self.profile_combo.addItem("Auto-Detect (Recommended)", "auto")
        self.profile_combo.addItem("Literature (Fiction / History / Prose)", "literature")
        self.profile_combo.addItem("Technical (Math / Code / Tables)", "technical")
        prof_row.addWidget(prof_label)
        prof_row.addWidget(self.profile_combo)
        pref_layout.addLayout(prof_row)

        # Default Output Directory
        dir_row = QHBoxLayout()
        dir_label = QLabel("Default Folder:")
        dir_label.setFixedWidth(150)
        self.dir_input = QLineEdit()
        self.dir_input.setPlaceholderText("Current working directory")
        self.dir_browse_btn = QPushButton("Browse...")
        self.dir_browse_btn.clicked.connect(self._browse_default_dir)
        dir_row.addWidget(dir_label)
        dir_row.addWidget(self.dir_input)
        dir_row.addWidget(self.dir_browse_btn)
        pref_layout.addLayout(dir_row)

        main_layout.addWidget(pref_card)

        # -------------------------------------------------------------------
        # 3. AI Structure Review Section (Optional)
        # -------------------------------------------------------------------
        ai_card = QFrame()
        ai_card.setObjectName("Card")
        ai_layout = QVBoxLayout(ai_card)
        ai_layout.setContentsMargins(16, 16, 16, 16)
        ai_layout.setSpacing(12)

        sec3_title = QLabel("AI Structure Review (Optional)")
        sec3_title.setObjectName("FieldLabel")
        ai_layout.addWidget(sec3_title)

        self.ai_enabled_cb = QCheckBox("Enable AI Outline Review via OpenAI-compatible endpoint")
        self.ai_enabled_cb.toggled.connect(self._toggle_ai_fields)
        ai_layout.addWidget(self.ai_enabled_cb)

        self.ai_fields_widget = QWidget()
        self.ai_fields_widget.setObjectName("TransparentRow")
        ai_fields_layout = QVBoxLayout(self.ai_fields_widget)
        ai_fields_layout.setContentsMargins(0, 0, 0, 0)
        ai_fields_layout.setSpacing(8)

        # Model
        m_row = QHBoxLayout()
        m_label = QLabel("Model Name:")
        m_label.setFixedWidth(110)
        self.ai_model_input = QLineEdit()
        self.ai_model_input.setPlaceholderText("e.g. gpt-4o-mini, llama3.2, mistral")
        m_row.addWidget(m_label)
        m_row.addWidget(self.ai_model_input)
        ai_fields_layout.addLayout(m_row)

        # Base URL
        url_row = QHBoxLayout()
        url_label = QLabel("Base URL:")
        url_label.setFixedWidth(110)
        self.ai_url_input = QLineEdit()
        self.ai_url_input.setPlaceholderText("e.g. https://api.openai.com/v1 or http://localhost:11434/v1")
        url_row.addWidget(url_label)
        url_row.addWidget(self.ai_url_input)
        ai_fields_layout.addLayout(url_row)

        # API Key
        key_row = QHBoxLayout()
        key_label = QLabel("API Key:")
        key_label.setFixedWidth(110)
        self.ai_key_input = QLineEdit()
        self.ai_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.ai_key_input.setPlaceholderText("API key (optional for local Ollama / LM Studio)")
        key_row.addWidget(key_label)
        key_row.addWidget(self.ai_key_input)
        ai_fields_layout.addLayout(key_row)

        # Test Connection Row
        test_row = QHBoxLayout()
        self.test_btn = QPushButton("Test Connection")
        self.test_btn.clicked.connect(self._test_ai_connection)
        self.test_status_label = QLabel("")
        self.test_status_label.setObjectName("StatusLabel")
        test_row.addWidget(self.test_btn)
        test_row.addWidget(self.test_status_label)
        test_row.addStretch()
        ai_fields_layout.addLayout(test_row)

        ai_layout.addWidget(self.ai_fields_widget)
        main_layout.addWidget(ai_card)

        # -------------------------------------------------------------------
        # Footer Action Buttons
        # -------------------------------------------------------------------
        footer_layout = QHBoxLayout()
        footer_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self._on_cancel)
        footer_layout.addWidget(self.cancel_btn)

        self.save_btn = QPushButton("Save Settings")
        self.save_btn.setObjectName("PrimaryButton")
        self.save_btn.clicked.connect(self._on_save)
        footer_layout.addWidget(self.save_btn)

        main_layout.addLayout(footer_layout)

    def _load_values(self) -> None:
        # Appearance
        idx = self.family_combo.findData(self.config.theme_family)
        if idx >= 0:
            self.family_combo.setCurrentIndex(idx)
        if self.config.color_mode == "light":
            self.light_radio.setChecked(True)
        else:
            self.dark_radio.setChecked(True)

        # Conversion Preferences
        if self.config.output_mode == "single_document":
            self.single_radio.setChecked(True)
        else:
            self.vault_radio.setChecked(True)

        prof_idx = self.profile_combo.findData(self.config.profile)
        if prof_idx >= 0:
            self.profile_combo.setCurrentIndex(prof_idx)

        self.dir_input.setText(self.config.output_dir)

        # AI
        self.ai_enabled_cb.setChecked(self.config.ai_enabled)
        self.ai_model_input.setText(self.config.ai_model)
        self.ai_url_input.setText(self.config.ai_base_url)
        self.ai_key_input.setText(self.config.ai_api_key)
        self._toggle_ai_fields(self.config.ai_enabled)

    def _on_theme_changed(self) -> None:
        family = self.family_combo.currentData() or "library"
        mode = "light" if self.light_radio.isChecked() else "dark"
        app = QApplication.instance()
        if app:
            app.setStyleSheet(get_stylesheet(family, mode))

    def _browse_default_dir(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, "Select Default Output Folder")
        if chosen:
            self.dir_input.setText(chosen)

    def _toggle_ai_fields(self, enabled: bool) -> None:
        self.ai_fields_widget.setEnabled(enabled)

    def _test_ai_connection(self) -> None:
        self.test_btn.setEnabled(False)
        self.test_status_label.setText("Testing connection...")
        self.test_status_label.setStyleSheet("")

        config = LLMConfig(
            enabled=True,
            model=self.ai_model_input.text().strip() or "gpt-4o-mini",
            base_url=self.ai_url_input.text().strip() or "https://api.openai.com/v1",
            api_key=self.ai_key_input.text().strip() or None,
            timeout_seconds=6.0,
        )

        self._thread = QThread()
        self._worker = ConnectionTestWorker(config)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_test_finished)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()

    def _on_test_finished(self, ok: bool, message: str) -> None:
        self.test_btn.setEnabled(True)
        if ok:
            self.test_status_label.setText(f"Connected: {message}")
            self.test_status_label.setStyleSheet("color: #10b981; font-weight: 600;")
        else:
            self.test_status_label.setText(f"Failed: {message[:70]}")
            self.test_status_label.setStyleSheet("color: #f43f5e; font-weight: 500;")

    def _on_cancel(self) -> None:
        # Revert any live previewed theme
        app = QApplication.instance()
        if app:
            app.setStyleSheet(get_stylesheet(self._initial_theme, self._initial_mode))
        self.reject()

    def _on_save(self) -> None:
        family = self.family_combo.currentData() or "library"
        mode = "light" if self.light_radio.isChecked() else "dark"
        out_mode = "single_document" if self.single_radio.isChecked() else "vault"
        profile = self.profile_combo.currentData() or "auto"
        output_dir = self.dir_input.text().strip()

        ai_enabled = self.ai_enabled_cb.isChecked()
        ai_model = self.ai_model_input.text().strip()
        ai_base_url = self.ai_url_input.text().strip()
        ai_api_key = self.ai_key_input.text().strip()

        self.config.theme_family = family
        self.config.color_mode = mode
        self.config.output_mode = out_mode
        self.config.profile = profile
        self.config.output_dir = output_dir
        self.config.ai_enabled = ai_enabled
        self.config.ai_model = ai_model
        self.config.ai_base_url = ai_base_url
        self.config.ai_api_key = ai_api_key

        self.config.save()
        self.settings_saved.emit(self.config)
        self.accept()
