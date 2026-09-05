"""Rules 5.1-5.4 — Paragraph Merging.

Combine fragmented text blocks (one per source line, from Stage 2) into
coherent paragraphs. See `Mdook-docs/RULES.md` section 5.

Implements:
- Rule 5.1 (same-font continuation)
- Rule 5.2 (hyphenated line rejoin)
- Rule 5.3 (cross-page paragraph continuation)
- Rule 5.4 (paragraph boundary detection: indent or vertical gap)

Simplification: Rule 5.2's dictionary-lookup exception for legitimate
compound hyphenation ("well-known") is not implemented — every trailing
hyphen followed by a lowercase letter is rejoined.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from mdook.core.models import PageData, TextBlock

TERMINAL_PUNCTUATION = (".", "!", "?", ":")
LINE_HEIGHT_MULTIPLIER = 1.3
BOUNDARY_GAP_MULTIPLIER = 1.5
INDENT_RATIO = 0.8
FONT_SIZE_MATCH_TOLERANCE = 0.5

FOOTNOTE_MARKER_SENTINEL = "\ue000"
"""Wraps a Rule 4.2 inline marker's text (e.g. `1`) so Stage 4
(Rendering) can reliably convert it to `[^1]` without guessing from plain
text. A Unicode private-use character never appears in real book text."""

ENDNOTE_MARKER_SENTINEL = ""
"""Wraps a Rule 4.3 inline endnote reference's text the same way, but
distinctly, since Stage 4 renders it as a wiki-link into the back-matter
Notes section instead of a same-file `[^n]` footnote (Obsidian footnotes
are file-scoped -- a definition living in a different file can't use that
syntax at all)."""


@dataclass
class MergedParagraph:
    text: str
    page_number: int
    """The page the paragraph starts on."""
    x0: float
    """The left edge of the paragraph's first block -- used by Stage 3 to
    tell an indented block quote (Rule 9.3) apart from an ordinary
    paragraph, a distinction otherwise lost once text is merged."""


def find_body_left_margin(pages: list[PageData]) -> float | None:
    """The most frequent left-edge x-position, weighted by character count,
    is the body's ordinary paragraph margin -- the baseline for Rule 9.3's
    "indented > 1.5x normal" block-quote signal."""
    weighted_counts: dict[float, int] = defaultdict(int)
    for page in pages:
        for block in page.blocks:
            if isinstance(block, TextBlock):
                weighted_counts[round(block.bbox[0])] += max(len(block.text), 1)
    if not weighted_counts:
        return None
    return max(weighted_counts, key=weighted_counts.get)


def merge_text_blocks(
    blocks_with_pages: list[tuple[int, TextBlock]],
    inline_marker_ids: set[int] | None = None,
    endnote_marker_ids: set[int] | None = None,
) -> list[MergedParagraph]:
    """`blocks_with_pages` must already be in reading order (page, then
    top-to-bottom) and should exclude headings/footnote-definitions/special
    content that Stage 3 handles separately."""
    inline_marker_ids = inline_marker_ids or set()
    endnote_marker_ids = endnote_marker_ids or set()

    paragraphs: list[MergedParagraph] = []
    current_text: str | None = None
    current_page: int | None = None
    current_x0: float = 0.0
    prev_block: TextBlock | None = None
    prev_page: int | None = None

    for page_number, block in blocks_with_pages:
        if current_text is None:
            current_text = block.text
            current_page = page_number
            current_x0 = block.bbox[0]
        elif id(block) in inline_marker_ids or id(block) in endnote_marker_ids:
            # Rule 4.2/4.3 correlation: splice the marker in (sentinel-wrapped
            # so Stage 4 can turn it into `[^n]` or a Notes wiki-link), don't
            # break the paragraph, and don't let its tiny marker font style
            # poison the next merge decision.
            is_footnote = id(block) in inline_marker_ids
            sentinel = FOOTNOTE_MARKER_SENTINEL if is_footnote else ENDNOTE_MARKER_SENTINEL
            marker_text = block.text.strip()
            current_text = current_text.rstrip() + sentinel + marker_text + sentinel
            continue
        elif prev_block is not None and _should_merge(prev_block, prev_page, block, page_number):
            current_text = _join(current_text, block.text)
        else:
            paragraphs.append(
                MergedParagraph(text=current_text.strip(), page_number=current_page, x0=current_x0)
            )
            current_text = block.text
            current_page = page_number
            current_x0 = block.bbox[0]

        prev_block = block
        prev_page = page_number

    if current_text is not None and current_text.strip():
        paragraphs.append(
            MergedParagraph(text=current_text.strip(), page_number=current_page, x0=current_x0)
        )

    return paragraphs


def _should_merge(prev: TextBlock, prev_page: int, curr: TextBlock, curr_page: int) -> bool:
    if not _same_style(prev, curr):
        return False
    if curr_page != prev_page:
        return not _ends_with_terminal_punctuation(prev.text)  # Rule 5.3
    return not _has_paragraph_boundary(prev, curr)  # Rule 5.4 gates Rule 5.1


def _same_style(a: TextBlock, b: TextBlock) -> bool:
    return (
        a.font_name == b.font_name
        and abs(a.font_size - b.font_size) < FONT_SIZE_MATCH_TOLERANCE
        and a.is_bold == b.is_bold
        and a.is_italic == b.is_italic
    )


def _ends_with_terminal_punctuation(text: str) -> bool:
    return text.rstrip().endswith(TERMINAL_PUNCTUATION)


def _has_paragraph_boundary(prev: TextBlock, curr: TextBlock) -> bool:
    line_height = prev.font_size * LINE_HEIGHT_MULTIPLIER
    vertical_gap = curr.bbox[1] - prev.bbox[3]
    if vertical_gap > line_height * BOUNDARY_GAP_MULTIPLIER:
        return True

    indent_threshold = prev.font_size * INDENT_RATIO
    if curr.bbox[1] > prev.bbox[1] and (curr.bbox[0] - prev.bbox[0]) > indent_threshold:
        return True

    return False


def _join(current_text: str, next_text: str) -> str:
    """Rule 5.2 — rejoin a hyphenated line break."""
    current_stripped = current_text.rstrip()
    next_lstripped = next_text.lstrip()
    if current_stripped.endswith("-") and next_lstripped[:1].islower():
        return current_stripped[:-1] + next_lstripped
    return current_stripped + " " + next_lstripped
