"""Queue data structure backing the GUI's side panel.

Tracks conversion jobs the user has queued up. Plain Python — no pipeline
wiring yet, just enough structure for the window to list pending, active,
and completed items.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import count
from pathlib import Path
from typing import Literal

QueueStatus = Literal["pending", "active", "completed", "failed"]

_id_counter = count(1)


@dataclass
class QueueItem:
    pdf_path: Path
    output_dir: Path
    profile: str
    status: QueueStatus = "pending"
    llm_config: object = None
    id: int = field(default_factory=lambda: next(_id_counter))

    @property
    def label(self) -> str:
        return f"{self.pdf_path.name} — {self.status}"


class QueueManager:
    """Ordered collection of `QueueItem`s with simple status transitions."""

    def __init__(self) -> None:
        self._items: list[QueueItem] = []

    @property
    def items(self) -> list[QueueItem]:
        return list(self._items)

    def add(
        self,
        pdf_path: Path,
        output_dir: Path,
        profile: str,
        llm_config: object = None,
    ) -> QueueItem:
        item = QueueItem(
            pdf_path=pdf_path,
            output_dir=output_dir,
            profile=profile,
            llm_config=llm_config,
        )
        self._items.append(item)
        return item

    def set_status(self, item: QueueItem, status: QueueStatus) -> None:
        item.status = status

    def remove(self, item: QueueItem) -> None:
        self._items.remove(item)

    def clear_completed(self) -> None:
        self._items = [i for i in self._items if i.status not in ("completed", "failed")]
