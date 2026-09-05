"""List Detection — not in `Mdook-docs/RULES.md`'s original rule catalog.

Bulleted and numbered lists were entirely unhandled: each item shares font,
size, and left margin with its siblings, so Rule 5.1 (same-font
continuation) used to flatten a whole list into one merged paragraph with no
markdown list syntax at all. This module pulls consecutive marker-prefixed
text blocks out of a normal paragraph run before merging ever sees them.

Simplifications:
- An item must be a single extracted line. A list item whose text wraps
  across two source lines will only capture its first line -- multi-line
  items are a known gap, not attempted here.
- Lettered ("a.", "b.") and roman-numeral ("i.", "ii.") markers are
  deliberately not recognized: a single letter followed by a period is
  indistinguishable from a personal initial at the start of a sentence
  ("A. Einstein once said..."), so this only recognizes unambiguous
  signals: bullet glyphs and digit-numbered markers.
- A numbered item's own printed number is preserved and rendered verbatim
  rather than synthesized from a running counter (found via real-book
  testing: narrative prose routinely interrupts a numbered sequence --
  "1. Relax completely. <paragraph of explanation> 2. Observe the visual
  images." -- which splits it into several separate single-item `ListData`
  runs; a synthesized counter would print "1." for every one of them).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from mdook.core.models import ListData, ListItem, TextBlock

BULLET_CHARS = "•◦▪‣∙○■□◆♦*-"
"""Hyphen deliberately placed last in the class so it doesn't need escaping.
Em/en-dash ("—"/"–") are intentionally excluded: French-style dialogue opens
every line of speech with one, which would otherwise be misread as a list."""
BULLET_MARKER_RE = re.compile(rf"^[{BULLET_CHARS}]\s+(\S.*)$")
NUMBERED_MARKER_RE = re.compile(r"^(\d+)[.)]\s+(\S.*)$")

LEVEL_INDENT_TOLERANCE = 3.0
"""Two list items' left edges within this many PDF points of each other are
treated as the same nesting level -- absorbs font-rendering jitter without
merging genuinely different indent tiers."""


@dataclass
class ParsedMarker:
    text: str
    ordered: bool
    marker: str | None
    """The literal printed number (e.g. "1", "2") for an ordered item, used
    verbatim at render time instead of a synthesized counter. None for a
    bullet item."""


def parse_list_marker(text: str) -> ParsedMarker | None:
    """Returns the parsed marker, or None if `text` doesn't start with a
    recognized list marker."""
    stripped = text.strip()
    match = BULLET_MARKER_RE.match(stripped)
    if match:
        return ParsedMarker(text=match.group(1), ordered=False, marker=None)
    match = NUMBERED_MARKER_RE.match(stripped)
    if match:
        return ParsedMarker(text=match.group(2), ordered=True, marker=match.group(1))
    return None


def split_list_run(
    blocks_with_pages: list[tuple[int, TextBlock]],
) -> list[tuple[str, list[tuple[int, TextBlock]] | ListData]]:
    """Splits a run of raw text blocks into alternating ("text", blocks) and
    ("list", ListData) sub-runs, in original order."""
    sub_runs: list[tuple[str, object]] = []
    text_buffer: list[tuple[int, TextBlock]] = []
    item_buffer: list[tuple[TextBlock, ParsedMarker]] = []

    def flush_text() -> None:
        if text_buffer:
            sub_runs.append(("text", list(text_buffer)))
            text_buffer.clear()

    def flush_list() -> None:
        if item_buffer:
            sub_runs.append(("list", _build_list_data(item_buffer)))
            item_buffer.clear()

    for page_number, block in blocks_with_pages:
        parsed = parse_list_marker(block.text)
        if parsed is not None:
            flush_text()
            item_buffer.append((block, parsed))
        else:
            flush_list()
            text_buffer.append((page_number, block))

    flush_text()
    flush_list()
    return sub_runs


def _build_list_data(items: list[tuple[TextBlock, ParsedMarker]]) -> ListData:
    indent_tiers = _cluster_indents([block.bbox[0] for block, _ in items])
    return ListData(
        items=[
            ListItem(
                text=parsed.text,
                level=_level_for(block.bbox[0], indent_tiers),
                ordered=parsed.ordered,
                marker=parsed.marker,
            )
            for block, parsed in items
        ],
        page_number=items[0][0].page_number,
    )


def _cluster_indents(x0_values: list[float]) -> list[float]:
    tiers: list[float] = []
    for x0 in sorted(x0_values):
        if tiers and (x0 - tiers[-1]) <= LEVEL_INDENT_TOLERANCE:
            continue
        tiers.append(x0)
    return tiers


def _level_for(x0: float, tiers: list[float]) -> int:
    return min(range(len(tiers)), key=lambda i: abs(tiers[i] - x0))
