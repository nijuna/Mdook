"""Rules 1.1-1.3 — Zone Detection.

Classify every page as front_matter / body / back_matter before any content
analysis begins. See `Mdook-docs/RULES.md` section 1.

Implements:
- Rule 1.1 (page-number style boundary: roman -> arabic transition)
- Rule 1.2 (front-matter keyword scanning)
- Rule 1.3 (back-matter keyword scanning)

Rule 1.4 (title page detection) is not implemented: `BookManifest.title`
already comes from PDF metadata, which covers the same need for Sprint 2.
"""

from __future__ import annotations

import re

from mdook.core.models import ZoneEntry

FRONT_KEYWORDS = [
    "table of contents",
    "contents",
    "preface",
    "foreword",
    "dedication",
    "acknowledgments",
    "copyright",
    "published by",
    "isbn",
    "all rights reserved",
]

BACK_KEYWORDS = [
    "bibliography",
    "references",
    "works cited",
    "glossary",
    "index",
    "notes",
    "endnotes",
    "appendix",
    "about the author",
]

ROMAN_NUMERAL_RE = re.compile(r"^[ivxlcdm]+$", re.IGNORECASE)
FRONT_MATTER_SEARCH_RATIO = 0.15
BACK_MATTER_SEARCH_RATIO = 0.20


def detect_zones(doc) -> list[ZoneEntry]:
    """`doc` is an open `pymupdf.Document`."""
    total_pages = doc.page_count
    if total_pages == 0:
        return []

    front_end = _detect_front_matter_end(doc, total_pages)
    back_start = _detect_back_matter_start(doc, total_pages, front_end)

    zones: list[ZoneEntry] = []
    if front_end > 0:
        zones.append(ZoneEntry(start_page=1, end_page=front_end, zone_type="front_matter"))

    body_start = front_end + 1
    body_end = (back_start - 1) if back_start else total_pages
    if body_end >= body_start:
        zones.append(ZoneEntry(start_page=body_start, end_page=body_end, zone_type="body"))

    if back_start:
        zones.append(
            ZoneEntry(start_page=back_start, end_page=total_pages, zone_type="back_matter")
        )

    return zones


def _detect_front_matter_end(doc, total_pages: int) -> int:
    limit = max(1, int(total_pages * FRONT_MATTER_SEARCH_RATIO))
    limit = min(limit, total_pages)

    last_keyword_page = 0
    for i in range(limit):
        text = doc[i].get_text("text").lower()
        if any(keyword in text for keyword in FRONT_KEYWORDS):
            last_keyword_page = i + 1

    transition_page = _find_roman_to_arabic_transition(doc, limit)
    if transition_page is not None:
        return max(transition_page - 1, last_keyword_page)
    return last_keyword_page


def _find_roman_to_arabic_transition(doc, limit: int) -> int | None:
    saw_roman = False
    for i in range(limit):
        label = _bottom_band_short_text(doc[i])
        if not label:
            continue
        if ROMAN_NUMERAL_RE.match(label):
            saw_roman = True
        elif label.isdigit() and saw_roman:
            return i + 1
    return None


def _bottom_band_short_text(page) -> str | None:
    height = page.rect.height
    for block in page.get_text("blocks"):
        y0, text = block[1], block[4]
        text = text.strip()
        if y0 > height * 0.85 and 0 < len(text) <= 6:
            return text
    return None


def _detect_back_matter_start(doc, total_pages: int, front_end: int) -> int | None:
    start_index = max(front_end, int(total_pages * (1 - BACK_MATTER_SEARCH_RATIO)))
    for i in range(start_index, total_pages):
        text = doc[i].get_text("text").lower()
        if any(keyword in text for keyword in BACK_KEYWORDS):
            return i + 1
    return None
