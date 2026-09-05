"""Rules 4.1-4.3, 4.5 — Footnote & Endnote Detection.

Identify footnote definitions at the bottom of a page and correlate them
with their in-text superscript/adjacent markers, plus endnotes collected in
a back-matter "Notes"/"Endnotes" section. See `Mdook-docs/RULES.md`
section 4.

Implements:
- Rule 4.1 (page-bottom footnote detection)
- Rule 4.2 (inline marker correlation)
- Rule 4.3 (endnote detection: `detect_endnote_markers` scans back-matter
  pages for a Notes/Endnotes-labeled section and collects its entries'
  marker numbers)
- Rule 4.5 (symbol markers, e.g. *dagger/section, are preserved verbatim
  rather than normalized to numbers -- `DEFINITION_MARKER_RE` and
  `INLINE_MARKER_RE` both already accept them)

Simplification: endnote numbering is treated as book-wide, not chapter-
scoped. Rule 4.3's own documented failure case -- two different chapters
each restarting at note "14" -- would collide under a single global marker
set; the correlated inline marker would link to whichever chapter's note
list happened to define it. Most non-academic books use continuous
book-wide numbering, where this doesn't arise at all.

Not implemented yet:
- Rule 4.4's "chapter-scoped" half (Stage 4 renders a single flat Notes
  file, matching the simplification above)
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field

from mdook.core.models import Footnote, PageData, TextBlock

BOTTOM_BAND_RATIO = 0.25
FONT_SIZE_MARGIN = 0.5
DEFINITION_MARKER_RE = re.compile(r"^\s*(\d{1,3}|[*†‡§¶])[.):]?\s+")
INLINE_MARKER_RE = re.compile(r"^[\d*†‡§¶]{1,3}$")
MAX_ADJACENCY_GAP = 3.0
MIN_ADJACENCY_GAP = -2.0
NOTE_SECTION_LABELS = frozenset({"notes", "endnotes"})
"""Shared with `mdook.core.stages.semantic` (label matching a back-matter
section as endnotes) and `mdook.core.stages.rendering` (deciding which
rendered section gets `^note-N` block-ID anchors for linking)."""


@dataclass
class FootnoteDetectionResult:
    footnotes_by_page: dict[int, list[Footnote]] = field(default_factory=dict)
    inline_marker_ids: set[int] = field(default_factory=set)
    """`id()` of in-body `TextBlock`s that are page-bottom footnote
    reference markers (Rule 4.2) — paragraph merging should splice these
    inline as `[^n]` rather than treat them as paragraph breaks."""
    endnote_marker_ids: set[int] = field(default_factory=set)
    """`id()` of in-body `TextBlock`s that reference a back-matter endnote
    (Rule 4.3) instead — spliced inline as a wiki-link to the Notes section
    rather than a same-file footnote, since Obsidian footnotes are file-
    scoped."""


def detect_endnote_markers(back_pages: list[PageData]) -> set[str]:
    """Rule 4.3 — scans back-matter pages for a Notes/Endnotes-labeled
    section and collects the marker numbers of its entries, so inline
    correlation below can recognize a body-text reference to an endnote
    even though page-bottom footnotes and endnotes are detected by entirely
    different signals (position-on-page vs. back-matter section label)."""
    markers: set[str] = set()
    in_notes_section = False
    for page in back_pages:
        for block in page.blocks:
            if not isinstance(block, TextBlock):
                continue
            normalized = " ".join(block.text.strip().lower().split()).rstrip(".:")
            if normalized in NOTE_SECTION_LABELS:
                in_notes_section = True
                continue
            if not in_notes_section:
                continue
            match = DEFINITION_MARKER_RE.match(block.text)
            if match and match.group(1).isdigit():
                markers.add(match.group(1))
    return markers


def detect_footnotes(
    pages: list[PageData],
    body_font_size: float | None,
    endnote_markers: frozenset[str] = frozenset(),
) -> FootnoteDetectionResult:
    """Mutates `pages` in place: strips footnote-definition blocks out of the
    body content flow."""
    footnotes_by_page: dict[int, list[Footnote]] = defaultdict(list)

    if body_font_size is not None:
        for page in pages:
            bottom_threshold = page.height * (1 - BOTTOM_BAND_RATIO)
            remaining = []
            for block in page.blocks:
                if isinstance(block, TextBlock) and _looks_like_definition(
                    block, bottom_threshold, body_font_size
                ):
                    match = DEFINITION_MARKER_RE.match(block.text)
                    marker = match.group(1)
                    text = block.text[match.end() :].strip()
                    footnotes_by_page[page.page_number].append(
                        Footnote(
                            marker=marker,
                            text=text,
                            page_number=page.page_number,
                            style="page_bottom",
                        )
                    )
                else:
                    remaining.append(block)
            page.blocks = remaining

    inline_marker_ids, endnote_marker_ids = _correlate_inline_markers(
        pages, footnotes_by_page, endnote_markers
    )
    return FootnoteDetectionResult(
        footnotes_by_page=dict(footnotes_by_page),
        inline_marker_ids=inline_marker_ids,
        endnote_marker_ids=endnote_marker_ids,
    )


def _looks_like_definition(
    block: TextBlock, bottom_threshold: float, body_font_size: float
) -> bool:
    return (
        block.bbox[1] >= bottom_threshold
        and block.font_size < body_font_size - FONT_SIZE_MARGIN
        and DEFINITION_MARKER_RE.match(block.text) is not None
    )


def _correlate_inline_markers(
    pages: list[PageData],
    footnotes_by_page: dict[int, list[Footnote]],
    endnote_markers: frozenset[str],
) -> tuple[set[int], set[int]]:
    """Rule 4.2: an in-body marker whose text matches a known footnote's
    marker on the same page is a reference, not stray paragraph text. Rule
    4.3 extends this to endnotes -- checked page-by-page too, even though
    the endnote marker set itself is book-wide, so an ordinary digit
    elsewhere in body prose isn't swept up by coincidence; a page-bottom
    match takes priority if a marker number happens to satisfy both.

    PyMuPDF's `is_superscript` flag is rarely set by real-world PDF
    generators, so — per the Rule 4.2 failure-mode note in RULES.md — the
    primary signal here is positional: a short marker block sitting flush
    against the preceding text with no intervening space.
    """
    footnote_ids: set[int] = set()
    endnote_ids: set[int] = set()
    for page in pages:
        known_footnote_markers = {fn.marker for fn in footnotes_by_page.get(page.page_number, [])}
        if not known_footnote_markers and not endnote_markers:
            continue

        prev_block: TextBlock | None = None
        for block in page.blocks:
            if not isinstance(block, TextBlock):
                prev_block = None
                continue
            stripped = block.text.strip()
            is_positional = block.is_superscript or _is_adjacent(prev_block, block)
            if INLINE_MARKER_RE.match(stripped) is not None and is_positional:
                if stripped in known_footnote_markers:
                    footnote_ids.add(id(block))
                elif stripped in endnote_markers:
                    endnote_ids.add(id(block))
            prev_block = block
    return footnote_ids, endnote_ids


def _is_adjacent(prev: TextBlock | None, curr: TextBlock) -> bool:
    if prev is None:
        return False
    vertical_overlap = curr.bbox[1] < prev.bbox[3] and curr.bbox[3] > prev.bbox[1]
    gap = curr.bbox[0] - prev.bbox[2]
    return vertical_overlap and MIN_ADJACENCY_GAP <= gap <= MAX_ADJACENCY_GAP
