"""Rules 2.1-2.5 — Heading Detection & Drop-Cap Immunity.

Identify chapter/section headings and map them to a consistent hierarchy.
See `Mdook-docs/RULES.md` section 2.

Implements:
- Rule 2.1 (bookmark-based hierarchy, preferred when >=3 bookmarks exist)
- Rule 2.2 (font-size clustering fallback)
- Rule 2.3 (positional confirmation of font-size candidates)
- Rule 2.4 (numbered-section detection, "1.1.2" style, technical profile —
  overrides font-size clustering entirely since technical books routinely
  set numbered sub-sections at body text size)
- Rule 2.5 (drop-cap immunity: merge an oversized single-character block back
  into the following paragraph instead of misreading it as a heading)

Not implemented yet:
- Rule 2.6 heading text preservation is inherent here: headings are stored
  with the book's exact text, never normalized.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass

from mdook.core.models import BookManifest, Bookmark, PageData, ProfileName, TextBlock
from mdook.core.rules import scripts as script_rules

MIN_BOOKMARKS_TO_TRUST = 3
MAX_HEADING_TIERS = 3
MIN_TIER_GAP = 1.5
TIER_MATCH_TOLERANCE = 1.0
BODY_FONT_SIZE_EPSILON = 0.5
MAX_HEADING_WORDS = 15
MIN_CONFIRMATION_SIGNALS = 2
DROP_CAP_SIZE_RATIO = 2.0
MAX_NUMBERED_SECTION_DEPTH = 4

NUMBERED_SECTION_RE = re.compile(r"^(\d+(?:\.\d+){0,3})\.?\s+\S")


@dataclass
class Heading:
    level: int
    title: str
    page_number: int
    block: TextBlock | None = None
    extra_block: TextBlock | None = None
    """Set when a second text block (e.g. a title set apart from a bare
    chapter number) was absorbed into `title` — see
    `mdook.core.stages.semantic._merge_chapter_number_titles`. Callers must
    exclude this block from both body content and sub-heading detection, the
    same as `block` itself."""


def detect_headings(
    manifest: BookManifest,
    pages: list[PageData],
    body_font_size: float | None = None,
) -> list[Heading]:
    if manifest.bookmarks and len(manifest.bookmarks) >= MIN_BOOKMARKS_TO_TRUST:
        return _headings_from_bookmarks(manifest.bookmarks, pages)
    return _headings_from_font_clustering(pages, body_font_size, manifest.profile)


def find_body_font_size(pages: list[PageData]) -> float | None:
    """The most frequent font size, weighted by character count, is the body size.

    Shared with `mdook.core.rules.footnotes` (font-size margin) and the
    drop-cap merge below, so callers should compute it once per book.
    """
    weighted_counts: dict[float, int] = defaultdict(int)
    for page in pages:
        for block in page.blocks:
            if isinstance(block, TextBlock):
                weighted_counts[round(block.font_size, 1)] += max(len(block.text), 1)
    if not weighted_counts:
        return None
    return max(weighted_counts, key=weighted_counts.get)


# ---------------------------------------------------------------------------
# Rule 2.5 — Drop-cap immunity
# ---------------------------------------------------------------------------


def merge_drop_caps(pages: list[PageData], body_font_size: float | None) -> None:
    """Mutates `pages` in place: a single oversized character at the start of
    a paragraph is merged into the following text block instead of being
    left to masquerade as a heading candidate."""
    if body_font_size is None:
        return
    threshold = body_font_size * DROP_CAP_SIZE_RATIO

    for page in pages:
        blocks = page.blocks
        merged: list = []
        i = 0
        while i < len(blocks):
            block = blocks[i]
            next_block = blocks[i + 1] if i + 1 < len(blocks) else None
            if _is_drop_cap(block, next_block, threshold):
                combined = next_block.model_copy(
                    update={"text": block.text.strip() + next_block.text, "bbox": block.bbox}
                )
                merged.append(combined)
                i += 2
                continue
            merged.append(block)
            i += 1
        page.blocks = merged


def _is_drop_cap(block: object, next_block: object, threshold: float) -> bool:
    return (
        isinstance(block, TextBlock)
        and len(block.text.strip()) == 1
        and block.font_size >= threshold
        and isinstance(next_block, TextBlock)
        and next_block.text[:1].islower()
    )


# ---------------------------------------------------------------------------
# Rule 2.1 — Bookmark-based hierarchy
# ---------------------------------------------------------------------------


def _headings_from_bookmarks(bookmarks: list[Bookmark], pages: list[PageData]) -> list[Heading]:
    pages_by_number = {page.page_number: page for page in pages}
    headings: list[Heading] = []
    for bookmark in bookmarks:
        page = pages_by_number.get(bookmark.page_number)
        block = _find_matching_text_block(page, bookmark.title)
        headings.append(
            Heading(
                level=min(bookmark.level, 3),
                title=bookmark.title,
                page_number=bookmark.page_number,
                block=block,
            )
        )
    return headings


def _find_matching_text_block(page: PageData | None, title: str) -> TextBlock | None:
    """Fuzzy match: bookmarks sometimes abbreviate the printed heading text."""
    if page is None:
        return None
    normalized_title = _normalize(title)
    if not normalized_title:
        return None

    best: TextBlock | None = None
    for block in page.blocks:
        if not isinstance(block, TextBlock):
            continue
        normalized_text = _normalize(block.text)
        if normalized_title in normalized_text or normalized_text in normalized_title:
            if best is None or len(block.text) < len(best.text):
                best = block
    return best


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


# ---------------------------------------------------------------------------
# Rules 2.2-2.4 — Font-size clustering, positional confirmation, numbered sections
# ---------------------------------------------------------------------------


def _headings_from_font_clustering(
    pages: list[PageData],
    body_font_size: float | None = None,
    profile: ProfileName = "literature",
) -> list[Heading]:
    if body_font_size is None:
        body_font_size = find_body_font_size(pages)
    if body_font_size is None:
        return []

    tiers = _cluster_heading_sizes(pages, body_font_size)

    headings: list[Heading] = []
    for page in pages:
        for index, block in enumerate(page.blocks):
            if not isinstance(block, TextBlock):
                continue

            numbered_level = _numbered_section_level(block.text, profile)
            if numbered_level is not None:
                headings.append(
                    Heading(
                        level=numbered_level,
                        title=block.text.strip(),
                        page_number=page.page_number,
                        block=block,
                    )
                )
                continue

            if not tiers:
                continue
            level = _tier_level(block.font_size, tiers)
            if level is None:
                continue
            if _confirm_heading(block, page, index):
                headings.append(
                    Heading(
                        level=level,
                        title=block.text.strip(),
                        page_number=page.page_number,
                        block=block,
                    )
                )
    return headings


def _numbered_section_level(text: str, profile: ProfileName) -> int | None:
    """Rule 2.4 — a dot-numbered heading ("1.1.2 Something") overrides
    font-size clustering entirely, since technical books routinely set
    numbered sub-sections at the same size as body text, where font-tier
    clustering alone would never notice them. Level is the number of
    dot-separated segments: "1" -> 1, "1.1" -> 2, "1.1.1" -> 3."""
    if profile != "technical":
        return None
    match = NUMBERED_SECTION_RE.match(text.strip())
    if not match:
        return None
    return min(match.group(1).count(".") + 1, MAX_NUMBERED_SECTION_DEPTH)


def _cluster_heading_sizes(pages: list[PageData], body_font_size: float) -> list[float]:
    threshold = body_font_size + BODY_FONT_SIZE_EPSILON
    larger_sizes = sorted(
        {
            round(block.font_size, 1)
            for page in pages
            for block in page.blocks
            if isinstance(block, TextBlock) and block.font_size > threshold
        },
        reverse=True,
    )

    tiers: list[float] = []
    for size in larger_sizes:
        if tiers and (tiers[-1] - size) < MIN_TIER_GAP:
            continue  # merge into the previous tier — too close to be distinct
        tiers.append(size)
        if len(tiers) == MAX_HEADING_TIERS:
            break
    return tiers


def _tier_level(font_size: float, tiers: list[float]) -> int | None:
    for level, tier_size in enumerate(tiers, start=1):
        if abs(font_size - tier_size) <= TIER_MATCH_TOLERANCE:
            return level
    return None


def _confirm_heading(block: TextBlock, page: PageData, index: int) -> bool:
    """Promote a font-size candidate to a confirmed heading if it passes at
    least 2 of the Rule 2.3 signals."""
    signals = 0

    if block.bbox[1] <= page.height * 0.3:
        signals += 1
    if index == 0:
        signals += 1  # first block on the page -> likely preceded by a page break
    if len(block.text.split()) <= MAX_HEADING_WORDS:
        signals += 1
    is_upper = bool(block.text.strip()) and block.text.isupper()
    if block.is_bold or is_upper:
        signals += 1

    if page.was_ocrd and not is_upper and not script_rules.is_caseless_text(block.text):
        # OCR font size is approximated from each line's own bbox height
        # (`mdook.core.rules.ocr`), which jitters by several points across
        # ordinary body lines depending on which letters happen to have
        # ascenders/descenders -- an unlucky tall line routinely tier-matches
        # as a "heading" candidate purely by chance. `is_bold` is always
        # False for OCR (Tesseract exposes no style flags), so uppercase is
        # the only Rule 2.3 signal OCR doesn't degrade; require it rather
        # than letting position + word-count alone (near-guaranteed on any
        # short first line of a scanned page) confirm the candidate.
        #
        # Batch 18: "uppercase" doesn't exist in a case-less script (CJK,
        # Arabic, Hebrew, Devanagari, Thai) -- `str.isupper()` is always
        # False there since Python's Unicode database assigns no case
        # property to those characters, so this guard would reject *every*
        # heading candidate on such a page, not just the noisy ones. The
        # jitter this guards against is also largely Latin-specific: CJK
        # ideographs all occupy a uniform em-box with no ascenders or
        # descenders to vary line height in the first place, so the
        # original failure mode barely applies there. Case-less scripts
        # fall back to the plain signal-count threshold instead.
        return False

    return signals >= MIN_CONFIRMATION_SIGNALS
