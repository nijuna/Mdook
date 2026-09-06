"""Profile Auto-Detection Heuristics.

Classifies a document as "literature" or "technical" based on structural
signals extracted during Stage 1 (Intake). See `Mdook-docs/PROFILES.md`
and `Mdook-docs/ROADMAP.md` (Phase 4 / Phase 5).

Signals evaluated:
1. Numbered section headings (1.1, 1.2.3 pattern) in bookmarks and page text.
2. Monospaced font spans and code blocks.
3. Mathematical symbols and notation density.
4. Table density across sampled pages.
5. Technical figure/table/listing caption patterns.

Defaults to "literature" when signals are absent or inconclusive.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from mdook.core.models import Bookmark, ProfileName
from mdook.core.rules.code import is_monospace_font
from mdook.core.rules.math import THEOREM_LABEL_RE, _is_strong_math_char

if TYPE_CHECKING:
    import pymupdf

logger = logging.getLogger(__name__)

SAMPLE_PAGE_LIMIT = 25
TECHNICAL_THRESHOLD_SCORE = 3

NUMBERED_HEADING_RE = re.compile(r"^\s*\d+\.\d+(?:\.\d+)*\.?\s+\S")
CAPTION_RE = re.compile(
    r"^\s*(?:Figure|Fig\.|Table|Listing|Algorithm)\s+\d+(?:\.\d+)?\s*[:\.]",
    re.IGNORECASE,
)
CODE_KEYWORD_LINE_RE = re.compile(
    r"^\s*(?:def |class |import |from \S+ import |function\s*\("
    r"|const |let |var |public\s+class|#include\s*<)",
)


@dataclass(frozen=True)
class ProfileSignals:
    """Breakdown of signals extracted during profile classification."""

    table_count: int
    table_density: float
    numbered_headings_count: int
    code_block_count: int
    math_symbol_count: int
    caption_count: int
    technical_score: int
    detected_profile: ProfileName


def _contains_strong_math(text: str) -> bool:
    """Check if any character belongs to strong math Unicode ranges or superscripts."""
    return any(_is_strong_math_char(ch) for ch in text)


def _sample_indices(total_pages: int, max_samples: int) -> list[int]:
    """Sample up to `max_samples` page indices, avoiding the very first page (cover)
    when possible."""
    if total_pages <= 0:
        return []
    if total_pages <= max_samples:
        return list(range(total_pages))

    # Skip page 0 (cover/front) if book has plenty of pages
    start = 1 if total_pages > 3 else 0
    end = total_pages - 1
    sample_count = min(max_samples, end - start + 1)
    step = (end - start) / max(sample_count - 1, 1)
    return sorted({int(start + i * step) for i in range(sample_count)})


def detect_profile_from_doc(
    doc: pymupdf.Document,
    bookmarks: list[Bookmark] | None = None,
) -> ProfileSignals:
    """Inspect PyMuPDF document to score and classify as literature or technical."""
    table_count = 0
    numbered_headings_count = 0
    code_block_count = 0
    math_symbol_count = 0
    caption_count = 0

    # 1. Bookmarks signal: check for numbered section patterns (e.g. "1.1 Introduction")
    if bookmarks:
        for bm in bookmarks:
            if NUMBERED_HEADING_RE.match(bm.title):
                numbered_headings_count += 1

    sample_indices = _sample_indices(doc.page_count, SAMPLE_PAGE_LIMIT)
    sampled_pages = len(sample_indices) or 1

    for page_idx in sample_indices:
        try:
            page = doc[page_idx]

            # 2. Table detection via PyMuPDF native table finder
            try:
                tables = page.find_tables()
                table_count += len(tables.tables)
            except Exception:
                pass

            # 3. Text inspection via text page dict (spans & fonts)
            text_dict = page.get_text("dict") or {}
            for block in text_dict.get("blocks", []):
                lines = block.get("lines", [])
                for line in lines:
                    line_text = "".join(
                        span.get("text", "") for span in line.get("spans", [])
                    ).strip()
                    if not line_text:
                        continue

                    # Numbered heading check in page text
                    if NUMBERED_HEADING_RE.match(line_text):
                        numbered_headings_count += 1

                    # Caption check
                    if CAPTION_RE.match(line_text):
                        caption_count += 1

                    # Monospace font check
                    for span in line.get("spans", []):
                        font_name = span.get("font", "")
                        span_text = span.get("text", "")
                        if is_monospace_font(font_name) and len(span_text.strip()) > 3:
                            code_block_count += 1
                            break

                    # Math symbols and theorem environment check
                    if _contains_strong_math(line_text) or THEOREM_LABEL_RE.match(line_text):
                        math_symbol_count += 1

                    # Code keyword heuristic check
                    if CODE_KEYWORD_LINE_RE.match(line_text):
                        code_block_count += 1

        except Exception as exc:
            logger.debug("Error inspecting page %d during profile detection: %s", page_idx, exc)
            continue

    table_density = table_count / sampled_pages

    # Calculate technical score based on weights
    score = 0
    if numbered_headings_count >= 2:
        score += 3
    elif numbered_headings_count == 1:
        score += 1

    if code_block_count >= 3:
        score += 3
    elif code_block_count >= 1:
        score += 1

    if math_symbol_count >= 3:
        score += 3
    elif math_symbol_count >= 1:
        score += 1

    if table_density >= 0.05 or table_count >= 2:
        score += 2
    elif table_count == 1:
        score += 1

    if caption_count >= 2:
        score += 2
    elif caption_count == 1:
        score += 1

    detected: ProfileName = "technical" if score >= TECHNICAL_THRESHOLD_SCORE else "literature"

    signals = ProfileSignals(
        table_count=table_count,
        table_density=table_density,
        numbered_headings_count=numbered_headings_count,
        code_block_count=code_block_count,
        math_symbol_count=math_symbol_count,
        caption_count=caption_count,
        technical_score=score,
        detected_profile=detected,
    )
    logger.info("Auto-detected profile '%s' (score=%d, signals=%s)", detected, score, signals)
    return signals


def classify_profile(
    doc: Any,
    bookmarks: list[Bookmark] | None = None,
) -> ProfileName:
    """Convenience entry point returning 'literature' or 'technical'."""
    try:
        signals = detect_profile_from_doc(doc, bookmarks=bookmarks)
        return signals.detected_profile
    except Exception as exc:
        logger.warning(
            "Profile auto-detection encountered an error; falling back to literature: %s", exc
        )
        return "literature"
