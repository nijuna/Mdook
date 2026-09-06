"""Background thread that runs the conversion pipeline off the GUI thread.

The GUI must never freeze, even during the stub pipeline's simulated
progress. `mdook.core.pipeline.convert` only knows about a plain
`on_progress(percent, message)` callback — this class is the sole place
that translates that into Qt signals.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Signal

from mdook.core.models import ConversionResult
from mdook.core.pipeline import convert


class ConversionWorker(QThread):
    progress_updated = Signal(int, str)
    conversion_finished = Signal(object)  # ConversionResult
    conversion_failed = Signal(str)

    def __init__(
        self,
        pdf_path: Path,
        output_dir: Path,
        profile: str = "auto",
        llm_config=None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.pdf_path = pdf_path
        self.output_dir = output_dir
        self.profile = profile
        self.llm_config = llm_config

    def run(self) -> None:
        try:
            result: ConversionResult = convert(
                self.pdf_path,
                self.output_dir,
                profile=self.profile,
                on_progress=lambda percent, message: self.progress_updated.emit(percent, message),
                llm_config=self.llm_config,
            )
        except Exception as exc:  # noqa: BLE001 — surface any pipeline failure to the GUI
            self.conversion_failed.emit(str(exc))
            return

        self.conversion_finished.emit(result)


class ConnectionTestWorker(QThread):
    """Background thread to test OpenAI-compatible LLM endpoint reachability.

    Keeps the GUI responsive during network timeouts or DNS resolution.
    """

    result_ready = Signal(bool, str)

    def __init__(
        self,
        config,
        timeout_seconds: float = 8.0,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.config = config
        self.timeout_seconds = timeout_seconds

    def run(self) -> None:
        from mdook.core.llm.client import OpenAICompatibleClient

        try:
            client = OpenAICompatibleClient(self.config)
            success, message = client.test_connection(timeout_seconds=self.timeout_seconds)
        except Exception as exc:  # noqa: BLE001
            success, message = False, f"Connection test failed: {exc}"

        self.result_ready.emit(success, message)


class ModelFetchWorker(QThread):
    """Background thread to fetch available models from provider's /models endpoint.

    Keeps the GUI responsive during network I/O.
    """

    models_ready = Signal(list, str)  # (models: list[str], error_message: str)

    def __init__(
        self,
        config,
        timeout_seconds: float = 8.0,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.config = config
        self.timeout_seconds = timeout_seconds

    def run(self) -> None:
        from mdook.core.llm.client import OpenAICompatibleClient

        try:
            client = OpenAICompatibleClient(self.config)
            models = client.list_models(timeout_seconds=self.timeout_seconds)
            self.models_ready.emit(models, "")
        except Exception as exc:  # noqa: BLE001
            self.models_ready.emit([], str(exc))
