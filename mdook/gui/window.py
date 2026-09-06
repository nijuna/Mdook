"""Main application window."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import (
    QCloseEvent,
    QColor,
    QDesktopServices,
    QDragEnterEvent,
    QDragLeaveEvent,
    QDropEvent,
)
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from mdook.core.llm import LLMConfig
from mdook.core.models import ConversionResult
from mdook.gui.queue_manager import QueueItem, QueueManager
from mdook.gui.styles import DARK_STYLE, LIGHT_STYLE
from mdook.gui.worker import ConnectionTestWorker, ConversionWorker, ModelFetchWorker

PROFILE_CHOICES = [
    ("Auto-Detect", "auto"),
    ("Literature", "literature"),
    ("Technical", "technical"),
]

QUEUE_STATUS_GLYPH = {
    # Plain Unicode symbols, not pictographic emoji (like an hourglass) --
    # those commonly fall back to a missing-glyph box on systems without a
    # dedicated emoji font installed.
    "pending": "•",
    "active": "▶",
    "completed": "✓",
    "failed": "✗",
}


def _field_row(label_text: str) -> tuple[QWidget, QLineEdit, QPushButton]:
    """Build a "Label | line edit | Browse..." row, returning (row, line_edit, button)."""
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)

    label = QLabel(label_text)
    label.setObjectName("FieldLabel")
    label.setFixedWidth(110)

    line_edit = QLineEdit()
    line_edit.setReadOnly(True)
    line_edit.setPlaceholderText("Not selected")

    button = QPushButton("Browse…")

    layout.addWidget(label)
    layout.addWidget(line_edit, stretch=1)
    layout.addWidget(button)
    return row, line_edit, button


def _input_row(label_text: str, placeholder: str = "") -> tuple[QWidget, QLineEdit]:
    """Build a "Label | line edit" row, returning (row, line_edit)."""
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)

    label = QLabel(label_text)
    label.setObjectName("FieldLabel")
    label.setFixedWidth(110)

    line_edit = QLineEdit()
    line_edit.setPlaceholderText(placeholder)

    layout.addWidget(label)
    layout.addWidget(line_edit, stretch=1)
    return row, line_edit


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Mdook")
        self.resize(820, 480)
        self.setAcceptDrops(True)
        self._dark_mode = True
        self.setStyleSheet(DARK_STYLE)

        self.queue_manager = QueueManager()
        self.worker: ConversionWorker | None = None
        self.conn_worker: ConnectionTestWorker | None = None
        self.model_worker: ModelFetchWorker | None = None
        self._active_item: QueueItem | None = None
        self._last_output_dir: Path | None = None
        self._default_llm_config = LLMConfig.from_env()

        self._build_ui()

    # -- UI construction ---------------------------------------------------

    def _build_ui(self) -> None:
        central = QWidget()
        root = QHBoxLayout(central)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(16)

        root.addLayout(self._build_main_panel(), stretch=3)
        root.addLayout(self._build_queue_panel(), stretch=1)

        self.setCentralWidget(central)

    def toggle_theme(self) -> None:
        self._dark_mode = not self._dark_mode
        self.setStyleSheet(DARK_STYLE if self._dark_mode else LIGHT_STYLE)
        # Plain text, not a sun/moon icon glyph: Unicode symbol coverage
        # varies enough across systems/fonts (confirmed while testing this)
        # that a guaranteed-to-render label beats a possibly-missing glyph.
        self.theme_button.setText("Light" if self._dark_mode else "Dark")

    def _build_main_panel(self) -> QVBoxLayout:
        layout = QVBoxLayout()
        layout.setSpacing(14)

        # Header
        header_row = QWidget()
        header_layout = QHBoxLayout(header_row)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_text = QVBoxLayout()
        title = QLabel("Mdook")
        title.setObjectName("HeaderTitle")
        subtitle = QLabel("Convert PDF books into structured, readable Obsidian vaults.")
        subtitle.setObjectName("HeaderSubtitle")
        header_text.addWidget(title)
        header_text.addWidget(subtitle)
        header_layout.addLayout(header_text, stretch=1)

        self.theme_button = QPushButton("Light")
        self.theme_button.setObjectName("IconButton")
        self.theme_button.setFixedWidth(64)
        self.theme_button.setToolTip("Toggle light/dark theme")
        self.theme_button.clicked.connect(self.toggle_theme)
        header_layout.addWidget(self.theme_button, alignment=Qt.AlignTop)

        layout.addWidget(header_row)

        # Form card
        form_card = QFrame()
        form_card.setObjectName("Card")
        self.form_card = form_card
        form_layout = QVBoxLayout(form_card)
        form_layout.setContentsMargins(16, 16, 16, 16)
        form_layout.setSpacing(12)

        pdf_row, self.pdf_path_edit, pdf_button = _field_row("PDF File")
        pdf_button.clicked.connect(self.browse_pdf)
        form_layout.addWidget(pdf_row)

        drop_hint = QLabel("or drag and drop one or more PDFs anywhere in this window")
        drop_hint.setObjectName("DropHint")
        form_layout.addWidget(drop_hint)

        output_row, self.output_dir_edit, output_button = _field_row("Output Folder")
        output_button.clicked.connect(self.browse_output)
        form_layout.addWidget(output_row)

        profile_row = QWidget()
        profile_layout = QHBoxLayout(profile_row)
        profile_layout.setContentsMargins(0, 0, 0, 0)
        profile_label = QLabel("Profile")
        profile_label.setObjectName("FieldLabel")
        profile_label.setFixedWidth(110)
        self.profile_combo = QComboBox()
        for display_name, _value in PROFILE_CHOICES:
            self.profile_combo.addItem(display_name)
        profile_layout.addWidget(profile_label)
        profile_layout.addWidget(self.profile_combo, stretch=1)
        form_layout.addWidget(profile_row)

        # AI Review Section
        ai_header_row = QWidget()
        ai_header_row.setObjectName("TransparentRow")
        ai_header_layout = QHBoxLayout(ai_header_row)
        ai_header_layout.setContentsMargins(0, 0, 0, 0)
        ai_header_layout.setSpacing(6)

        self.ai_review_checkbox = QCheckBox("Enable AI Structure Review (OpenAI-compatible)")
        self.ai_review_checkbox.setChecked(self._default_llm_config.enabled)
        self.ai_review_checkbox.toggled.connect(self._toggle_ai_settings)
        ai_header_layout.addWidget(self.ai_review_checkbox, stretch=1)

        self.ai_arrow_button = QPushButton("▾" if self._default_llm_config.enabled else "▸")
        self.ai_arrow_button.setObjectName("ArrowButton")
        self.ai_arrow_button.setFixedSize(28, 28)
        self.ai_arrow_button.setToolTip("Collapse / expand AI settings")
        self.ai_arrow_button.clicked.connect(self._toggle_ai_expansion)
        ai_header_layout.addWidget(self.ai_arrow_button)

        form_layout.addWidget(ai_header_row)

        self.ai_settings_widget = QWidget()
        self.ai_settings_widget.setObjectName("AISettingsWidget")
        ai_settings_layout = QVBoxLayout(self.ai_settings_widget)
        ai_settings_layout.setContentsMargins(0, 0, 0, 0)
        ai_settings_layout.setSpacing(6)

        base_url_row, self.ai_base_url_edit = _input_row(
            "Endpoint URL", "https://api.openai.com/v1"
        )
        self.ai_base_url_edit.setText(self._default_llm_config.base_url)
        ai_settings_layout.addWidget(base_url_row)

        model_row = QWidget()
        model_layout = QHBoxLayout(model_row)
        model_layout.setContentsMargins(0, 0, 0, 0)
        model_layout.setSpacing(8)

        model_label = QLabel("Model Name")
        model_label.setObjectName("FieldLabel")
        model_label.setFixedWidth(110)
        model_layout.addWidget(model_label)

        self.ai_model_combo = QComboBox()
        self.ai_model_combo.setEditable(True)
        self.ai_model_combo.setInsertPolicy(QComboBox.NoInsert)
        self.ai_model_combo.addItems(
            [
                "gpt-4o-mini",
                "llama-3.3-70b-versatile",
                "llama-3.1-8b-instant",
                "llama3.2",
                "deepseek-chat",
                "gpt-4o",
                "qwen2.5-coder",
            ]
        )
        self.ai_model_combo.setCurrentText(self._default_llm_config.model)
        self.ai_model_edit = self.ai_model_combo.lineEdit()
        self.ai_model_edit.setPlaceholderText("Select or type model name...")

        completer = self.ai_model_combo.completer()
        if completer is not None:
            completer.setFilterMode(Qt.MatchContains)
            completer.setCaseSensitivity(Qt.CaseInsensitive)

        model_layout.addWidget(self.ai_model_combo, stretch=1)

        self.fetch_models_button = QPushButton("Fetch Models")
        self.fetch_models_button.setToolTip(
            "Query provider's /models endpoint to list and select available models"
        )
        self.fetch_models_button.clicked.connect(self.on_fetch_models_clicked)
        model_layout.addWidget(self.fetch_models_button)

        ai_settings_layout.addWidget(model_row)

        key_row, self.ai_key_edit = _input_row("API Key", "Optional for local Ollama/LM Studio")
        self.ai_key_edit.setEchoMode(QLineEdit.Password)
        if self._default_llm_config.api_key:
            self.ai_key_edit.setText(self._default_llm_config.api_key)
        ai_settings_layout.addWidget(key_row)

        test_row = QWidget()
        test_layout = QHBoxLayout(test_row)
        test_layout.setContentsMargins(0, 2, 0, 0)
        test_layout.setSpacing(8)

        spacer_label = QLabel("")
        spacer_label.setFixedWidth(110)
        test_layout.addWidget(spacer_label)

        self.test_connection_button = QPushButton("Test Connection")
        self.test_connection_button.setToolTip(
            "Verify endpoint reachability and model responsiveness"
        )
        self.test_connection_button.clicked.connect(self.on_test_connection_clicked)
        test_layout.addWidget(self.test_connection_button)

        self.test_connection_status = QLabel("")
        self.test_connection_status.setObjectName("TestStatusLabel")
        self.test_connection_status.setWordWrap(True)
        test_layout.addWidget(self.test_connection_status, stretch=1)

        ai_settings_layout.addWidget(test_row)

        form_layout.addWidget(self.ai_settings_widget)
        self.ai_settings_widget.setVisible(self._default_llm_config.enabled)

        layout.addWidget(form_card)

        # Convert button
        self.convert_button = QPushButton("Convert")
        self.convert_button.setObjectName("PrimaryButton")
        self.convert_button.clicked.connect(self.on_convert_clicked)
        layout.addWidget(self.convert_button)

        # Progress + status
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("Ready")
        self.status_label.setObjectName("StatusLabel")
        layout.addWidget(self.status_label)

        # Summary area
        self.summary_card = QFrame()
        self.summary_card.setObjectName("Card")
        self.summary_card.setVisible(False)
        summary_layout = QVBoxLayout(self.summary_card)
        summary_layout.setContentsMargins(16, 16, 16, 16)
        summary_layout.setSpacing(4)

        summary_title = QLabel("Conversion Summary")
        summary_title.setObjectName("FieldLabel")
        summary_layout.addWidget(summary_title)

        self.summary_label = QLabel("")
        summary_layout.addWidget(self.summary_label)

        self.summary_note_label = QLabel("")
        self.summary_note_label.setObjectName("StatusLabel")
        self.summary_note_label.setWordWrap(True)
        self.summary_note_label.setVisible(False)
        summary_layout.addWidget(self.summary_note_label)

        layout.addWidget(self.summary_card)

        self.open_vault_button = QPushButton("Open Vault")
        self.open_vault_button.setVisible(False)
        self.open_vault_button.clicked.connect(self.open_vault)
        layout.addWidget(self.open_vault_button)

        layout.addStretch(1)
        return layout

    def _build_queue_panel(self) -> QVBoxLayout:
        layout = QVBoxLayout()
        layout.setSpacing(8)

        header_row = QWidget()
        header_layout = QHBoxLayout(header_row)
        header_layout.setContentsMargins(0, 0, 0, 0)
        queue_label = QLabel("Queue")
        queue_label.setObjectName("FieldLabel")
        header_layout.addWidget(queue_label, stretch=1)
        self.clear_completed_button = QPushButton("Clear")
        self.clear_completed_button.setObjectName("IconButton")
        self.clear_completed_button.setToolTip("Remove completed and failed items")
        self.clear_completed_button.clicked.connect(self.clear_completed)
        header_layout.addWidget(self.clear_completed_button)
        layout.addWidget(header_row)

        self.queue_list = QListWidget()
        self.queue_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        layout.addWidget(self.queue_list, stretch=1)
        self._refresh_queue_list()

        return layout

    # -- File pickers --------------------------------------------------------

    def browse_pdf(self) -> None:
        path_str, _filter = QFileDialog.getOpenFileName(
            self, "Select PDF Book", "", "PDF Files (*.pdf)"
        )
        if path_str:
            self.pdf_path_edit.setText(path_str)

    def browse_output(self) -> None:
        path_str = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if path_str:
            self.output_dir_edit.setText(path_str)

    # -- Drag and drop --------------------------------------------------------
    # Visual feedback (the dashed-border highlight) is driven by a dynamic
    # "dragging" property on the form card, toggled here and consumed by the
    # `QFrame#Card[dragging="true"]` selector in `mdook.gui.styles` --
    # otherwise dropping files here has no on-screen affordance at all.

    def _set_dragging(self, dragging: bool) -> None:
        self.form_card.setProperty("dragging", dragging)
        self.form_card.style().unpolish(self.form_card)
        self.form_card.style().polish(self.form_card)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls() and any(
            url.toLocalFile().lower().endswith(".pdf") for url in event.mimeData().urls()
        ):
            self._set_dragging(True)
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:
        self._set_dragging(False)

    def dropEvent(self, event: QDropEvent) -> None:
        self._set_dragging(False)
        pdf_paths = [
            Path(url.toLocalFile())
            for url in event.mimeData().urls()
            if url.toLocalFile().lower().endswith(".pdf")
        ]
        if not pdf_paths:
            event.ignore()
            return
        event.acceptProposedAction()

        output_dir_str = self.output_dir_edit.text().strip()
        if not output_dir_str:
            self.status_label.setText("Select an output folder first, then drop your PDF(s) again.")
            return

        output_dir = Path(output_dir_str)
        profile = self.selected_profile()
        llm_config = self.get_current_llm_config()
        for pdf_path in pdf_paths:
            self.queue_manager.add(pdf_path, output_dir, profile, llm_config=llm_config)
        self._refresh_queue_list()
        self._start_next_queue_item()

    def _toggle_ai_settings(self, checked: bool) -> None:
        self.ai_settings_widget.setVisible(checked)
        if hasattr(self, "ai_arrow_button"):
            self.ai_arrow_button.setText("▾" if checked else "▸")

    def _toggle_ai_expansion(self) -> None:
        is_expanded = self.ai_settings_widget.isHidden()
        self.ai_settings_widget.setVisible(is_expanded)
        self.ai_arrow_button.setText("▾" if is_expanded else "▸")

    def on_fetch_models_clicked(self) -> None:
        cfg = self.get_current_llm_config()
        self.fetch_models_button.setEnabled(False)
        self.fetch_models_button.setText("Fetching...")
        self.test_connection_status.setText("Fetching available models from provider...")
        self.test_connection_status.setToolTip("")
        self._set_test_status_property("pending")

        self.model_worker = ModelFetchWorker(cfg, parent=self)
        self.model_worker.models_ready.connect(self.on_fetch_models_finished)
        self.model_worker.start()

    def on_fetch_models_finished(self, models: list[str], error_message: str) -> None:
        self.fetch_models_button.setEnabled(True)
        self.fetch_models_button.setText("Fetch Models")

        if models:
            current_typed = self.ai_model_combo.currentText().strip()
            self.ai_model_combo.clear()
            self.ai_model_combo.addItems(models)

            if current_typed in models:
                self.ai_model_combo.setCurrentText(current_typed)
            else:
                # Auto-select best matching versatile or chat model if present
                recommended = next(
                    (
                        m
                        for m in models
                        if any(k in m.lower() for k in ("versatile", "chat", "instruct", "mini"))
                    ),
                    models[0],
                )
                self.ai_model_combo.setCurrentText(recommended)

            self._set_test_status_property("success")
            msg = f"Fetched {len(models)} models from provider."
            self.test_connection_status.setText(f"✓ {msg}")
            self.test_connection_status.setToolTip("\n".join(models[:40]))
            self.ai_model_combo.showPopup()
        else:
            self._set_test_status_property("error")
            err = error_message or "No models returned by provider."
            display_text = f"✗ {err}"
            if len(display_text) > 85:
                display_text = f"{display_text[:82]}..."
            self.test_connection_status.setText(display_text)
            self.test_connection_status.setToolTip(error_message)

    def on_test_connection_clicked(self) -> None:
        cfg = self.get_current_llm_config()
        self.test_connection_button.setEnabled(False)
        self.test_connection_status.setText("Testing connection...")
        self.test_connection_status.setToolTip("")
        self._set_test_status_property("pending")

        self.conn_worker = ConnectionTestWorker(cfg, parent=self)
        self.conn_worker.result_ready.connect(self.on_test_connection_finished)
        self.conn_worker.start()

    def on_test_connection_finished(self, success: bool, message: str) -> None:
        self.test_connection_button.setEnabled(True)
        if success:
            display_text = f"✓ {message}"
            self._set_test_status_property("success")
        else:
            if any(
                term in message.lower()
                for term in ("model_not_found", "does not exist", "not found")
            ):
                display_text = "✗ Model not found. Click 'Fetch Models' to select a valid model."
            else:
                display_text = f"✗ {message}"
                if len(display_text) > 85:
                    display_text = f"{display_text[:82]}..."
            self._set_test_status_property("error")

        self.test_connection_status.setText(display_text)
        self.test_connection_status.setToolTip(message)

    def _set_test_status_property(self, status: str) -> None:
        self.test_connection_status.setProperty("status", status)
        self.test_connection_status.style().unpolish(self.test_connection_status)
        self.test_connection_status.style().polish(self.test_connection_status)

    def get_current_llm_config(self) -> LLMConfig:
        return LLMConfig(
            enabled=self.ai_review_checkbox.isChecked(),
            base_url=self.ai_base_url_edit.text().strip() or "https://api.openai.com/v1",
            api_key=self.ai_key_edit.text().strip() or None,
            model=self.ai_model_edit.text().strip() or "gpt-4o-mini",
        )

    # -- Conversion -----------------------------------------------------------

    def selected_profile(self) -> str:
        index = self.profile_combo.currentIndex()
        return PROFILE_CHOICES[index][1]

    def on_convert_clicked(self) -> None:
        pdf_path_str = self.pdf_path_edit.text().strip()
        output_dir_str = self.output_dir_edit.text().strip()

        if not pdf_path_str or not output_dir_str:
            self.status_label.setText("Select a PDF file and an output folder first.")
            return

        self.queue_manager.add(
            Path(pdf_path_str),
            Path(output_dir_str),
            self.selected_profile(),
            llm_config=self.get_current_llm_config(),
        )
        self._refresh_queue_list()
        self._start_next_queue_item()

    def _start_next_queue_item(self) -> None:
        """Advances the queue by one: starts a worker for the next pending
        item, if any, and if nothing is already converting. Chained from
        `on_finished`/`on_failed` so multiple queued books convert one after
        another automatically instead of the queue being a static list that
        only ever holds the single most recent job."""
        if self._active_item is not None:
            return  # a conversion is already in progress

        next_item = next(
            (item for item in self.queue_manager.items if item.status == "pending"), None
        )
        if next_item is None:
            self.convert_button.setEnabled(True)
            return

        self._active_item = next_item
        self.queue_manager.set_status(next_item, "active")
        self._refresh_queue_list()

        self.summary_card.setVisible(False)
        self.open_vault_button.setVisible(False)
        self.convert_button.setEnabled(False)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.status_label.setText(f"Converting {next_item.pdf_path.name}...")

        self.worker = ConversionWorker(
            next_item.pdf_path,
            next_item.output_dir,
            profile=next_item.profile,
            llm_config=next_item.llm_config,
            parent=self,
        )
        self.worker.progress_updated.connect(self.on_progress)
        self.worker.conversion_finished.connect(self.on_finished)
        self.worker.conversion_failed.connect(self.on_failed)
        self.worker.start()

    def on_progress(self, percent: int, message: str) -> None:
        self.progress_bar.setValue(percent)
        self.status_label.setText(message)

    def on_finished(self, result: ConversionResult) -> None:
        self.progress_bar.setValue(100)
        self.status_label.setText("Complete!")
        self._last_output_dir = result.output_dir

        summary_text = (
            f"Pages: {result.pages}    "
            f"Chapters: {result.chapters}    "
            f"Footnotes: {result.footnotes}    "
            f"Images: {result.images}"
        )
        if result.llm_review_applied:
            summary_text += "    AI Review: Applied"
        self.summary_label.setText(summary_text)

        warnings = result.validation_report.warnings if result.validation_report else []
        if warnings:
            self.summary_note_label.setText(" ".join(warnings))
            self.summary_note_label.setVisible(True)
        else:
            self.summary_note_label.setVisible(False)

        self.summary_card.setVisible(True)
        self.open_vault_button.setVisible(result.success)

        if self._active_item is not None:
            self.queue_manager.set_status(self._active_item, "completed")
            self._active_item = None
            self._refresh_queue_list()
        self._start_next_queue_item()

    def on_failed(self, message: str) -> None:
        self.progress_bar.setVisible(False)
        self.status_label.setText(f"Failed: {message}")

        if self._active_item is not None:
            self.queue_manager.set_status(self._active_item, "failed")
            self._active_item = None
            self._refresh_queue_list()
        self._start_next_queue_item()

    def open_vault(self) -> None:
        if self._last_output_dir is not None:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._last_output_dir)))

    def clear_completed(self) -> None:
        self.queue_manager.clear_completed()
        self._refresh_queue_list()

    def _refresh_queue_list(self) -> None:
        self.queue_list.clear()
        if not self.queue_manager.items:
            placeholder = QListWidgetItem("No conversions yet.")
            placeholder.setFlags(Qt.NoItemFlags)
            placeholder.setForeground(QColor("#8a8a8e"))
            font = placeholder.font()
            font.setItalic(True)
            placeholder.setFont(font)
            self.queue_list.addItem(placeholder)
            return
        for item in self.queue_manager.items:
            glyph = QUEUE_STATUS_GLYPH.get(item.status, "")
            self.queue_list.addItem(f"{glyph}  {item.pdf_path.name}")

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.conn_worker is not None and self.conn_worker.isRunning():
            self.conn_worker.wait(300)
        if self.model_worker is not None and self.model_worker.isRunning():
            self.model_worker.wait(300)
        super().closeEvent(event)
