"""GUI tests — run against Qt's offscreen platform plugin so they work in a
headless environment without a real display. `QT_QPA_PLATFORM` is forced
here (before importing PySide6) rather than left to the invoking shell, so
`uv run pytest` works out of the box in CI/containers; a real desktop launch
of `python -m mdook` is a separate process and is unaffected."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path
from typing import Callable

import pytest
from PySide6.QtCore import QMimeData, QPointF, QUrl
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import QApplication

from mdook.core.models import ConversionResult
from mdook.gui import window as window_module
from mdook.gui.styles import DARK_STYLE, LIGHT_STYLE
from mdook.gui.window import MainWindow


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    app = QApplication.instance()
    return app if app is not None else QApplication([])


class FakeWorker:
    """Stands in for `ConversionWorker` in tests: records that it was
    constructed and started, but never actually runs the pipeline or spawns
    a real thread -- the test triggers `conversion_finished`/`conversion_failed`
    manually, the same way the real worker would via its Qt signals."""

    instances: list["FakeWorker"] = []

    def __init__(
        self,
        pdf_path: Path,
        output_dir: Path,
        profile: str = "literature",
        parent=None,
        llm_config=None,
    ):
        self.pdf_path = pdf_path
        self.output_dir = output_dir
        self.profile = profile
        self.llm_config = llm_config
        self.started = False
        self._progress_slots: list[Callable[[int, str], None]] = []
        self._finished_slots: list[Callable[[ConversionResult], None]] = []
        self._failed_slots: list[Callable[[str], None]] = []
        FakeWorker.instances.append(self)

    class _Signal:
        def __init__(self, slots: list) -> None:
            self._slots = slots

        def connect(self, slot) -> None:
            self._slots.append(slot)

    @property
    def progress_updated(self) -> "FakeWorker._Signal":
        return FakeWorker._Signal(self._progress_slots)

    @property
    def conversion_finished(self) -> "FakeWorker._Signal":
        return FakeWorker._Signal(self._finished_slots)

    @property
    def conversion_failed(self) -> "FakeWorker._Signal":
        return FakeWorker._Signal(self._failed_slots)

    def start(self) -> None:
        self.started = True

    def emit_finished(self, result: ConversionResult) -> None:
        for slot in self._finished_slots:
            slot(result)

    def emit_failed(self, message: str) -> None:
        for slot in self._failed_slots:
            slot(message)


@pytest.fixture
def fake_worker(monkeypatch: pytest.MonkeyPatch) -> type[FakeWorker]:
    FakeWorker.instances = []
    monkeypatch.setattr(window_module, "ConversionWorker", FakeWorker)
    return FakeWorker


@pytest.fixture
def window(qapp: QApplication) -> MainWindow:
    return MainWindow()


def _result(success: bool = True) -> ConversionResult:
    return ConversionResult(success=success, output_dir=Path("/tmp/vault"))


# -- QueueManager -------------------------------------------------------------


def test_queue_manager_add_and_status(window: MainWindow) -> None:
    item = window.queue_manager.add(Path("a.pdf"), Path("/out"), "literature")
    assert item.status == "pending"
    window.queue_manager.set_status(item, "completed")
    assert item.status == "completed"


def test_queue_manager_clear_completed_keeps_pending(window: MainWindow) -> None:
    pending = window.queue_manager.add(Path("a.pdf"), Path("/out"), "literature")
    done = window.queue_manager.add(Path("b.pdf"), Path("/out"), "literature")
    window.queue_manager.set_status(done, "completed")

    window.queue_manager.clear_completed()

    assert window.queue_manager.items == [pending]


# -- Theme toggle ---------------------------------------------------------------


def test_toggle_theme_switches_stylesheet_and_label(window: MainWindow) -> None:
    assert window.styleSheet() == DARK_STYLE
    assert window.theme_button.text() == "Light"

    window.toggle_theme()
    assert window.styleSheet() == LIGHT_STYLE
    assert window.theme_button.text() == "Dark"

    window.toggle_theme()
    assert window.styleSheet() == DARK_STYLE
    assert window.theme_button.text() == "Light"


# -- Queue list rendering --------------------------------------------------------


def test_empty_queue_shows_placeholder(window: MainWindow) -> None:
    window._refresh_queue_list()
    assert window.queue_list.count() == 1
    assert "No conversions yet" in window.queue_list.item(0).text()


def test_populated_queue_shows_status_glyphs(window: MainWindow) -> None:
    a = window.queue_manager.add(Path("alpha.pdf"), Path("/out"), "literature")
    b = window.queue_manager.add(Path("beta.pdf"), Path("/out"), "literature")
    window.queue_manager.set_status(a, "completed")
    window.queue_manager.set_status(b, "active")

    window._refresh_queue_list()

    assert window.queue_list.count() == 2
    assert window.queue_list.item(0).text() == "✓  alpha.pdf"
    assert window.queue_list.item(1).text() == "▶  beta.pdf"


# -- Drag and drop ----------------------------------------------------------------


def _pdf_drop_event(paths: list[str]) -> tuple[QMimeData, QDropEvent]:
    # `mime` must be kept alive by the caller for as long as `event` is used:
    # QDropEvent stores a raw pointer to it rather than taking Python-level
    # ownership, so letting `mime` go out of scope first leaves a dangling
    # pointer and segfaults on the next access (`event.mimeData()...`).
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(p) for p in paths])
    event = QDropEvent(
        QPointF(0, 0),
        window_module.Qt.DropAction.CopyAction,
        mime,
        window_module.Qt.MouseButton.NoButton,
        window_module.Qt.KeyboardModifier.NoModifier,
    )
    return mime, event


def _pdf_drag_enter_event(paths: list[str]) -> tuple[QMimeData, QDragEnterEvent]:
    mime = QMimeData()  # see the note in `_pdf_drop_event` above
    mime.setUrls([QUrl.fromLocalFile(p) for p in paths])
    event = QDragEnterEvent(
        QPointF(0, 0).toPoint(),
        window_module.Qt.DropAction.CopyAction,
        mime,
        window_module.Qt.MouseButton.NoButton,
        window_module.Qt.KeyboardModifier.NoModifier,
    )
    return mime, event


def test_drag_enter_accepts_pdf_and_sets_dragging_property(window: MainWindow) -> None:
    _mime, event = _pdf_drag_enter_event(["/tmp/book.pdf"])
    window.dragEnterEvent(event)
    assert event.isAccepted()
    assert window.form_card.property("dragging") is True


def test_drag_enter_rejects_non_pdf(window: MainWindow) -> None:
    _mime, event = _pdf_drag_enter_event(["/tmp/book.txt"])
    window.dragEnterEvent(event)
    assert not event.isAccepted()


def test_drop_without_output_folder_shows_status_and_does_not_queue(window: MainWindow) -> None:
    window.output_dir_edit.setText("")
    _mime, event = _pdf_drop_event(["/tmp/book.pdf"])
    window.dropEvent(event)

    assert window.queue_manager.items == []
    assert "output folder" in window.status_label.text().lower()


def test_drop_with_output_folder_queues_and_clears_dragging(
    window: MainWindow, fake_worker: type[FakeWorker]
) -> None:
    window.output_dir_edit.setText("/out")
    window._set_dragging(True)

    _mime, event = _pdf_drop_event(["/tmp/book1.pdf", "/tmp/book2.pdf"])
    window.dropEvent(event)

    assert len(window.queue_manager.items) == 2
    assert window.form_card.property("dragging") is False
    assert len(fake_worker.instances) == 1  # sequential processing started automatically


# -- Sequential queue processing ---------------------------------------------------


def test_convert_click_starts_worker_for_queued_item(
    window: MainWindow, fake_worker: type[FakeWorker]
) -> None:
    window.pdf_path_edit.setText("/tmp/book.pdf")
    window.output_dir_edit.setText("/out")

    window.on_convert_clicked()

    assert len(fake_worker.instances) == 1
    worker = fake_worker.instances[0]
    assert worker.pdf_path == Path("/tmp/book.pdf")
    assert worker.started is True
    assert window.convert_button.isEnabled() is False
    assert window.queue_manager.items[0].status == "active"


def test_second_queued_item_starts_automatically_after_first_finishes(
    window: MainWindow, fake_worker: type[FakeWorker]
) -> None:
    output_dir = Path("/out")
    window.queue_manager.add(Path("/tmp/first.pdf"), output_dir, "literature")
    window.queue_manager.add(Path("/tmp/second.pdf"), output_dir, "literature")
    window._start_next_queue_item()

    assert len(fake_worker.instances) == 1
    first_worker = fake_worker.instances[0]
    assert first_worker.pdf_path == Path("/tmp/first.pdf")

    first_worker.emit_finished(_result())

    assert len(fake_worker.instances) == 2
    second_worker = fake_worker.instances[1]
    assert second_worker.pdf_path == Path("/tmp/second.pdf")
    statuses = [item.status for item in window.queue_manager.items]
    assert statuses == ["completed", "active"]


def test_failed_item_does_not_block_the_next_one(
    window: MainWindow, fake_worker: type[FakeWorker]
) -> None:
    output_dir = Path("/out")
    window.queue_manager.add(Path("/tmp/first.pdf"), output_dir, "literature")
    window.queue_manager.add(Path("/tmp/second.pdf"), output_dir, "literature")
    window._start_next_queue_item()

    fake_worker.instances[0].emit_failed("boom")

    assert len(fake_worker.instances) == 2
    statuses = [item.status for item in window.queue_manager.items]
    assert statuses == ["failed", "active"]


def test_convert_button_reenabled_once_queue_is_empty(
    window: MainWindow, fake_worker: type[FakeWorker]
) -> None:
    window.queue_manager.add(Path("/tmp/only.pdf"), Path("/out"), "literature")
    window._start_next_queue_item()

    fake_worker.instances[0].emit_finished(_result())

    assert window.convert_button.isEnabled() is True
    assert window.queue_manager.items[0].status == "completed"


def test_ai_review_gui_controls_and_config(window: MainWindow) -> None:
    # Initially disabled
    window.ai_review_checkbox.setChecked(False)
    assert window.ai_settings_widget.isHidden() is True
    cfg = window.get_current_llm_config()
    assert cfg.enabled is False

    # Toggle enabled
    window.ai_review_checkbox.setChecked(True)
    assert window.ai_settings_widget.isHidden() is False

    window.ai_base_url_edit.setText("http://localhost:11434/v1")
    window.ai_model_edit.setText("llama3.2")
    window.ai_key_edit.setText("ollama-local")

    cfg_updated = window.get_current_llm_config()
    assert cfg_updated.enabled is True
    assert cfg_updated.base_url == "http://localhost:11434/v1"
    assert cfg_updated.model == "llama3.2"
    assert cfg_updated.api_key == "ollama-local"


def test_ai_review_arrow_toggle(window: MainWindow) -> None:
    # When disabled, arrow is right-pointing
    window.ai_review_checkbox.setChecked(False)
    assert window.ai_arrow_button.text() == "▸"
    assert window.ai_settings_widget.isHidden() is True

    # Clicking arrow expands settings without enabling conversion checkbox
    window.ai_arrow_button.click()
    assert window.ai_arrow_button.text() == "▾"
    assert window.ai_settings_widget.isHidden() is False
    assert window.ai_review_checkbox.isChecked() is False

    # Clicking arrow again collapses settings
    window.ai_arrow_button.click()
    assert window.ai_arrow_button.text() == "▸"
    assert window.ai_settings_widget.isHidden() is True

    # Checking the checkbox expands settings and sets arrow to ▾
    window.ai_review_checkbox.setChecked(True)
    assert window.ai_arrow_button.text() == "▾"
    assert window.ai_settings_widget.isHidden() is False

    # Unchecking checkbox collapses settings and sets arrow to ▸
    window.ai_review_checkbox.setChecked(False)
    assert window.ai_arrow_button.text() == "▸"
    assert window.ai_settings_widget.isHidden() is True


def test_ai_test_connection_ui_feedback(window: MainWindow) -> None:
    # Initial state
    assert window.test_connection_button.isEnabled() is True
    assert window.test_connection_status.text() == ""

    # Simulated start: disables button, sets pending status
    window.test_connection_button.setEnabled(False)
    window.test_connection_status.setText("Testing connection...")
    window._set_test_status_property("pending")
    assert window.test_connection_button.isEnabled() is False
    assert window.test_connection_status.property("status") == "pending"

    # Simulated success callback
    window.on_test_connection_finished(True, "Connected (120ms) — model 'gpt-4o-mini'")
    assert window.test_connection_button.isEnabled() is True
    assert "Connected (120ms)" in window.test_connection_status.text()
    assert window.test_connection_status.property("status") == "success"

    # Simulated failure callback
    window.on_test_connection_finished(False, "Connection refused to http://localhost:11434")
    assert window.test_connection_button.isEnabled() is True
    assert "Connection refused" in window.test_connection_status.text()
    assert window.test_connection_status.property("status") == "error"


def test_ai_test_connection_worker_execution(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    from mdook.core.llm.client import OpenAICompatibleClient

    monkeypatch.setattr(
        OpenAICompatibleClient,
        "test_connection",
        lambda self, timeout_seconds=8.0: (True, "Connected (50ms) — model 'llama3.2'"),
    )

    window.on_test_connection_clicked()
    assert window.conn_worker is not None
    window.conn_worker.wait(2000)
    QApplication.processEvents()

    assert window.test_connection_button.isEnabled() is True
    assert "Connected (50ms)" in window.test_connection_status.text()
    assert window.test_connection_status.property("status") == "success"


def test_ai_model_combo_defaults_and_filtering(window: MainWindow) -> None:
    assert window.ai_model_combo.count() >= 5
    items = [window.ai_model_combo.itemText(i) for i in range(window.ai_model_combo.count())]
    assert "gpt-4o-mini" in items

    window.ai_model_edit.setText("custom-finetuned-model")
    cfg = window.get_current_llm_config()
    assert cfg.model == "custom-finetuned-model"


def test_ai_fetch_models_worker_and_ui(window: MainWindow, monkeypatch: pytest.MonkeyPatch) -> None:
    from mdook.core.llm.client import OpenAICompatibleClient

    monkeypatch.setattr(
        OpenAICompatibleClient,
        "list_models",
        lambda self, timeout_seconds=8.0: ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"],
    )

    window.on_fetch_models_clicked()
    assert window.model_worker is not None
    window.model_worker.wait(2000)
    QApplication.processEvents()

    assert window.fetch_models_button.isEnabled() is True
    assert window.ai_model_combo.count() == 2
    assert window.ai_model_combo.currentText() == "llama-3.3-70b-versatile"
    assert "Fetched 2 models" in window.test_connection_status.text()
    assert window.test_connection_status.property("status") == "success"


def test_ai_test_connection_model_not_found_hint(window: MainWindow) -> None:
    err_msg = (
        'HTTP 404: {"error":{"message":"The model gpt-4o-mini does not exist",'
        '"code":"model_not_found"}}'
    )
    window.on_test_connection_finished(False, err_msg)
    assert "Model not found" in window.test_connection_status.text()
    assert "Fetch Models" in window.test_connection_status.text()
    assert window.test_connection_status.property("status") == "error"
