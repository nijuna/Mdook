"""Stage 1 — Intake & Classification.

Input: a PDF file path (+ optional profile override).
Output: a `mdook.core.models.BookManifest`.

Implements: text-layer check, bookmark extraction, metadata extraction, and
zone detection (delegated to `mdook.core.rules.zones`). See
`Mdook-docs/ARCHITECTURE.md` ("Stage 1").

Not implemented yet: signal-based profile auto-detection (table density,
numbered headings, figure captions) is a Phase 4 task per
`Mdook-docs/ROADMAP.md` — for now the caller-supplied profile is used as-is,
defaulting to "literature".
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

import pymupdf

from mdook.core.errors import CorruptPDFError, EncryptedPDFError
from mdook.core.models import BookManifest, Bookmark, ProfileName
from mdook.core.rules import zones as zone_rules

logger = logging.getLogger(__name__)

SAMPLE_PAGE_COUNT = 8
MIN_CHARS_FOR_TEXT_LAYER = 20
MAX_PLAUSIBLE_TITLE_LENGTH = 150
GARBAGE_TITLE_RE = re.compile(r"%[0-9A-Fa-f]{2}|[\\/]")
LARGE_BOOK_PAGE_COUNT = 1000
"""Batch 19: purely an observability threshold, logged so a very large
conversion's slowness has an explanation up front -- not a hard limit, and
nothing about extraction changes because of it."""


def run_intake(pdf_path: Path, profile_override: ProfileName | None = None) -> BookManifest:
    try:
        doc = pymupdf.open(pdf_path)
    except Exception as exc:
        # Batch 19: PyMuPDF/MuPDF repairs many corrupt PDFs silently, but a
        # sufficiently damaged file still fails outright here -- fail with
        # a clear, specific error instead of an opaque traceback surfacing
        # from deep inside extraction.
        raise CorruptPDFError(f"Could not open '{pdf_path.name}': {exc}") from exc

    try:
        if doc.needs_pass:
            raise EncryptedPDFError(
                f"'{pdf_path.name}' is password-protected -- Mdook doesn't support "
                "encrypted PDFs. Remove the password and try again."
            )

        if doc.page_count >= LARGE_BOOK_PAGE_COUNT:
            logger.info(
                "'%s' is %d pages -- conversion may take a while, especially if "
                "many pages need OCR.",
                pdf_path.name,
                doc.page_count,
            )

        meta = doc.metadata or {}
        title = _clean_metadata_title(meta.get("title"), fallback=pdf_path.stem)
        author = meta.get("author") or "Unknown"

        bookmarks = _extract_bookmarks(doc)
        zone_map = zone_rules.detect_zones(doc)

        return BookManifest(
            file_path=str(pdf_path),
            title=title,
            author=author,
            total_pages=doc.page_count,
            needs_ocr=_detect_needs_ocr(doc),
            profile=profile_override or "literature",
            zone_map=zone_map,
            bookmarks=bookmarks or None,
            metadata={k: v for k, v in meta.items() if v},
        )
    except EncryptedPDFError:
        raise
    except Exception as exc:
        raise CorruptPDFError(f"'{pdf_path.name}' appears to be corrupt: {exc}") from exc
    finally:
        doc.close()


def _clean_metadata_title(raw_title: str | None, fallback: str) -> str:
    """PDF metadata titles are sometimes garbage rather than an actual book
    title: seen in the wild, a title that was literally a URL-encoded local
    file path ending in ".htm", baked in by whatever tool produced the PDF
    from an HTML source. Propagating that verbatim makes an unusable vault
    folder name and page-marker callout text, so reject anything implausibly
    long or containing URL-encoding/path-separator artifacts."""
    if not raw_title:
        return fallback
    if len(raw_title) > MAX_PLAUSIBLE_TITLE_LENGTH or GARBAGE_TITLE_RE.search(raw_title):
        return fallback
    return raw_title


def _detect_needs_ocr(doc) -> bool:
    """Rule: sample pages spread across the document; if most have no usable
    text layer, flag the book for OCR (Phase 3 — not yet implemented, but the
    flag is recorded now)."""
    indices = _sample_page_indices(doc.page_count, SAMPLE_PAGE_COUNT)
    if not indices:
        return False
    empty_count = sum(
        1 for i in indices if len(doc[i].get_text("text").strip()) < MIN_CHARS_FOR_TEXT_LAYER
    )
    return empty_count > len(indices) / 2


def _sample_page_indices(total_pages: int, sample_size: int) -> list[int]:
    if total_pages <= 0:
        return []
    if total_pages <= sample_size:
        return list(range(total_pages))
    step = total_pages / sample_size
    return sorted({int(i * step) for i in range(sample_size)})


def _extract_bookmarks(doc) -> list[Bookmark]:
    toc = doc.get_toc(simple=True)  # list of [level, title, page_number]
    return [Bookmark(level=level, title=title, page_number=page) for level, title, page in toc]
