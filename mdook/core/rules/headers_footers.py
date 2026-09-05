"""Rules 3.1-3.2 — Header & Footer Detection.

Identify running headers/footers (book title, chapter title, page numbers)
that repeat across pages, strip them from the content flow, and record them
on `PageData.header_text` / `PageData.footer_text`. See `Mdook-docs/RULES.md`
section 3.

Rule 3.3 (page-marker callout rendering) belongs to Stage 4 (Rendering),
not here.
"""

from __future__ import annotations

from difflib import SequenceMatcher

from mdook.core.models import PageData, TextBlock

TOP_BAND_RATIO = 0.15
BOTTOM_BAND_RATIO = 0.15
"""A scanned page's canvas (Phase 3) routinely includes a wider blank
border around the actual printed area than a tightly-cropped native PDF --
a real scanned book's running header was measured landing 9-13% down from
the page top, just outside an 8% band. The wider band is safe even for
native PDFs: a candidate only gets stripped if it also *repeats* across
`MIN_REPEAT_PAGES` pages below, and an ordinary paragraph's first line
essentially never does."""
MIN_REPEAT_PAGES = 5
SIMILARITY_THRESHOLD = 0.82
"""Two normalized header/footer candidates cluster together at or above this
`SequenceMatcher` ratio. Native PDFs repeat a running header byte-for-byte
(ratio 1.0), but an OCR'd page (Phase 3) misreads a handful of characters
differently every time -- exact-match grouping never reaches
`MIN_REPEAT_PAGES` for those, so the header/footer leaks into the body on
every single page of a scanned book. 0.82 tolerates that level of per-page
OCR noise on a typical header/footer's length without also merging two
distinct short phrases that happen to share most of their characters."""


def detect_headers_footers(pages: list[PageData]) -> None:
    """Mutates `pages` in place."""
    header_candidates: list[tuple[int, TextBlock, str]] = []
    footer_candidates: list[tuple[int, TextBlock, str]] = []

    for page in pages:
        top_limit = page.height * TOP_BAND_RATIO
        bottom_limit = page.height * (1 - BOTTOM_BAND_RATIO)

        for block in page.blocks:
            if not isinstance(block, TextBlock):
                continue
            _, y0, _, y1 = block.bbox
            normalized = _normalize(block.text)
            if not normalized:
                continue
            if y1 <= top_limit:
                header_candidates.append((page.page_number, block, normalized))
            elif y0 >= bottom_limit:
                footer_candidates.append((page.page_number, block, normalized))

    repeating_headers = _select_repeating(header_candidates)
    repeating_footers = _select_repeating(footer_candidates)
    header_text_by_page = {p: b.text for p, b, _ in repeating_headers}
    footer_text_by_page = {p: b.text for p, b, _ in repeating_footers}
    strip_ids = {id(block) for _, block, _ in repeating_headers + repeating_footers}

    for page in pages:
        if page.page_number in header_text_by_page:
            page.header_text = header_text_by_page[page.page_number]
        if page.page_number in footer_text_by_page:
            page.footer_text = footer_text_by_page[page.page_number]
        page.blocks = [b for b in page.blocks if id(b) not in strip_ids]


def _select_repeating(
    candidates: list[tuple[int, TextBlock, str]],
) -> list[tuple[int, TextBlock, str]]:
    """Cluster candidates by near-identical normalized text (nearest-cluster
    greedy clustering by `SequenceMatcher` ratio, not exact string equality
    -- see `SIMILARITY_THRESHOLD`). A cluster that recurs on at least
    `MIN_REPEAT_PAGES` pages is a genuine running header/footer; anything
    smaller is left alone as ordinary content that merely sits in the
    header/footer band on a few pages."""
    clusters: list[list[tuple[int, TextBlock, str]]] = []
    for candidate in candidates:
        _, _, normalized = candidate
        best_cluster = None
        best_score = 0.0
        for cluster in clusters:
            score = SequenceMatcher(None, normalized, cluster[0][2]).ratio()
            if score > best_score:
                best_score = score
                best_cluster = cluster
        if best_cluster is not None and best_score >= SIMILARITY_THRESHOLD:
            best_cluster.append(candidate)
        else:
            clusters.append([candidate])

    result: list[tuple[int, TextBlock, str]] = []
    for cluster in clusters:
        if len(cluster) >= MIN_REPEAT_PAGES:
            result.extend(cluster)
    return result


def _normalize(text: str) -> str:
    """Collapse whitespace and mask digits so a page-number-only footer
    (Rule 3.2) still groups as "repeating" across pages even though the
    printed number itself changes."""
    masked = "".join("#" if ch.isdigit() else ch for ch in text)
    return " ".join(masked.lower().split())
