"""Rules 8.1-8.3 — Multi-Column Reading Order.

Column detection and per-column sorting, column-span detection, and the
literature-profile single-column shortcut. See `Mdook-docs/RULES.md`
section 8.

Implements:
- Rule 8.1 (column detection: text blocks cluster into 2+ distinct
  x-position bands with a clear gap; sort within each column by y-position,
  concatenate left-to-right)
- Rule 8.2 (a block spanning most of the page width -- a heading, or an
  image/table, since neither is addressed by Rule 8.1/8.2's own text --
  interrupts the columns at its vertical position instead of being folded
  into either one)
- Rule 8.3 (literature profile shortcut: only apply reordering if more than
  10% of the book's pages actually show the column signal)

Runs as a whole-book post-process in Stage 2 (`run_extraction`), not
per-page during extraction, since Rule 8.3's shortcut needs to see every
page's signal before deciding whether to touch any of them.
"""

from __future__ import annotations

from mdook.core.models import Block, PageData, ProfileName, TextBlock
from mdook.core.rules import scripts as script_rules

COLUMN_GAP_RATIO = 0.04
"""Minimum horizontal gap between two column bands, as a fraction of page
width -- guards against ordinary paragraph indent variance within a single
column being mistaken for a second column."""
MIN_BLOCKS_FOR_COLUMN_DETECTION = 6
MIN_BLOCKS_PER_BAND = 2
"""A band with only one stray block is noise (a caption, a pull-quote),
not a real column."""
COLUMN_SPAN_WIDTH_RATIO = 0.8
MULTI_COLUMN_PAGE_RATIO = 0.1


def reorder_columns_if_warranted(pages: list[PageData], profile: ProfileName) -> None:
    """Mutates `pages` in place. Rule 8.3: a literature-profile book only
    gets column reordering applied at all if enough of it actually shows
    the signal -- otherwise a single false-positive page (e.g. a caption
    and a pull-quote happening to land side by side) would get needlessly
    reordered in an otherwise single-column book."""
    if profile == "literature":
        signal_pages = sum(1 for page in pages if _has_column_signal(page))
        if not pages or signal_pages / len(pages) <= MULTI_COLUMN_PAGE_RATIO:
            return

    for page in pages:
        if page.is_vertical_text:
            # Batch 18: this whole rule assumes horizontal left-to-right
            # (or, with `is_rtl`, right-to-left) reading -- reordering a
            # traditional vertical-CJK page by x-position band would
            # scramble it rather than fix it. Full vertical-layout reading
            # order is out of scope; leaving the page's natural extraction
            # order alone is the honest "don't corrupt it" fallback.
            continue
        page.blocks = reorder_columns(
            page.blocks, page.width, is_rtl=script_rules.page_is_rtl(page)
        )


def _has_column_signal(page: PageData) -> bool:
    if page.is_vertical_text:
        return False
    text_blocks = [b for b in page.blocks if isinstance(b, TextBlock)]
    return detect_column_ranges(text_blocks, page.width) is not None


def detect_column_ranges(
    text_blocks: list[TextBlock], page_width: float
) -> list[tuple[float, float]] | None:
    """Rule 8.1 — clusters non-spanning text blocks' left edges into 2+
    distinct x-position bands with a clear gap between them. Returns each
    band's (min_x0, max_x1) extent, sorted left-to-right, or None if the
    page doesn't show a clean multi-column split."""
    candidates = [b for b in text_blocks if not _is_column_spanning(b, page_width)]
    if len(candidates) < MIN_BLOCKS_FOR_COLUMN_DETECTION:
        return None

    sorted_blocks = sorted(candidates, key=lambda b: b.bbox[0])
    gap_threshold = page_width * COLUMN_GAP_RATIO

    bands: list[list[TextBlock]] = [[sorted_blocks[0]]]
    band_max_x1 = sorted_blocks[0].bbox[2]
    for block in sorted_blocks[1:]:
        if block.bbox[0] - band_max_x1 > gap_threshold:
            bands.append([])
        bands[-1].append(block)
        band_max_x1 = max(band_max_x1, block.bbox[2])

    if len(bands) < 2 or any(len(band) < MIN_BLOCKS_PER_BAND for band in bands):
        return None

    return [(min(b.bbox[0] for b in band), max(b.bbox[2] for b in band)) for band in bands]


def _is_column_spanning(block: TextBlock, page_width: float) -> bool:
    """Rule 8.2 — a block spanning most of the page width is a heading or
    other column-spanning element, not part of either column."""
    return (block.bbox[2] - block.bbox[0]) >= page_width * COLUMN_SPAN_WIDTH_RATIO


def reorder_columns(blocks: list[Block], page_width: float, is_rtl: bool = False) -> list[Block]:
    """Reconstructs top-to-bottom-per-column reading order, columns taken
    left-to-right by default or right-to-left when `is_rtl` (Batch 18 --
    the page's dominant script decides this, `mdook.core.rules.scripts
    .page_is_rtl`). A column-spanning block (Rule 8.2) -- along with any
    image or table, which Rule 8.1/8.2 doesn't classify by column
    membership at all -- interrupts the columns at its vertical position,
    splitting the reading order above and below it. Returns `blocks`
    unchanged (natural extraction order) if no clean column split exists."""
    text_blocks = [b for b in blocks if isinstance(b, TextBlock)]
    column_ranges = detect_column_ranges(text_blocks, page_width)
    if column_ranges is None:
        return blocks

    columned_text = [b for b in text_blocks if not _is_column_spanning(b, page_width)]
    spanning_text = [b for b in text_blocks if _is_column_spanning(b, page_width)]
    non_text = [b for b in blocks if not isinstance(b, TextBlock)]
    spanning = sorted(spanning_text + non_text, key=lambda b: b.bbox[1])

    columns: list[list[TextBlock]] = [[] for _ in column_ranges]
    for block in columned_text:
        columns[_nearest_column(block, column_ranges)].append(block)
    for column in columns:
        column.sort(key=lambda b: b.bbox[1])
    if is_rtl:
        # Rightmost column read first; each column's own top-to-bottom order is unaffected.
        columns.reverse()

    result: list[Block] = []
    segment_start = float("-inf")
    for spanning_block in spanning:
        for column in columns:
            result.extend(b for b in column if segment_start <= b.bbox[1] < spanning_block.bbox[1])
        result.append(spanning_block)
        segment_start = spanning_block.bbox[1]
    for column in columns:
        result.extend(b for b in column if b.bbox[1] >= segment_start)

    return result


def _nearest_column(block: TextBlock, column_ranges: list[tuple[float, float]]) -> int:
    center_x = (block.bbox[0] + block.bbox[2]) / 2
    return min(
        range(len(column_ranges)),
        key=lambda i: abs(center_x - (column_ranges[i][0] + column_ranges[i][1]) / 2),
    )
