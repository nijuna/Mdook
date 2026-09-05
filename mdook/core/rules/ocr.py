"""OCR Engine Integration — Phase 3, Batch 12 (`Mdook-docs/ROADMAP.md`).

Wraps Tesseract (via `pytesseract`) as the OCR engine for pages that fail
Stage 2's per-page text-quality check (`mdook.core.rules.text_quality`).
Tesseract's own output -- per-word text, confidence, and a pixel bounding
box grouped by block/paragraph/line -- is normalized directly into the
same `TextBlock` schema PyMuPDF's native extraction produces, so every
Stage 3 rule built for native PDFs (heading detection, footnote/endnote
correlation, lists, quotes, tables, columns) runs identically on OCR'd
pages without any format-specific branching downstream. This is the
"single unified pipeline" design chosen over trusting a separate layout
model's own structure output -- see the Phase 3 plan discussion.

Known precision loss, accepted per `Mdook-docs/ROADMAP.md`'s own Phase 3
exit criterion ("some degradation from OCR is expected, but structure
should be correct"):
- Font size is approximated from each detected line's pixel bounding-box
  height, scaled to points -- Tesseract exposes no real font metrics. This
  makes Stage 3's font-size-clustering heuristics (heading detection)
  noisier on OCR'd pages than on native ones.
- `is_bold`/`is_italic`/`is_superscript` are always False -- Tesseract
  doesn't reliably expose style flags. Heading/footnote-marker heuristics
  that lean on these signals fall back to whatever other signals remain
  (position, uppercase text, adjacency).
- `font_name` is a constant sentinel ("OCR"), not a real font -- this
  deliberately never matches `mdook.core.rules.code.is_monospace_font`'s
  keyword list, so OCR'd text is never misdetected as a code block.

Requires the `tesseract` binary on PATH (a system package, not pip-
installable -- `pytesseract` is only a thin wrapper around it). A missing
binary, or any failure mid-page, degrades that single page to an empty
block list rather than failing the whole conversion -- the same
resilience pattern already used for `pdfplumber.open()` failures and
corrupt embedded images elsewhere in Stage 2.
"""

from __future__ import annotations

import io

import pymupdf
import pytesseract
from PIL import Image

from mdook.core.models import TextBlock

OCR_DPI = 300
POINTS_PER_INCH = 72
PIXEL_TO_POINT_SCALE = POINTS_PER_INCH / OCR_DPI
OCR_FONT_NAME = "OCR"
MIN_FONT_SIZE = 1.0


def extract_page_via_ocr(page: pymupdf.Page, page_number: int) -> list[TextBlock]:
    """Rasterizes `page` and runs it through Tesseract, returning one
    `TextBlock` per detected line, in Tesseract's own reading-order.
    Returns an empty list (never raises) if the `tesseract` binary is
    missing or OCR otherwise fails on this page -- that page's content is
    lost, but the rest of the book's conversion continues."""
    try:
        pixmap = page.get_pixmap(dpi=OCR_DPI)
        image = Image.open(io.BytesIO(pixmap.tobytes("png")))
        data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
    except Exception:
        return []

    return _group_words_into_lines(data, page_number)


def _group_words_into_lines(data: dict[str, list], page_number: int) -> list[TextBlock]:
    line_word_indices: dict[tuple[int, int, int], list[int]] = {}
    line_order: list[tuple[int, int, int]] = []

    for i, text in enumerate(data["text"]):
        if not text.strip() or data["conf"][i] == -1:
            continue  # a structural (block/paragraph/line) row, not an actual word
        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        if key not in line_word_indices:
            line_word_indices[key] = []
            line_order.append(key)
        line_word_indices[key].append(i)

    blocks: list[TextBlock] = []
    for key in line_order:
        indices = line_word_indices[key]
        blocks.append(_line_to_text_block(data, indices, page_number))
    return blocks


def _line_to_text_block(data: dict[str, list], indices: list[int], page_number: int) -> TextBlock:
    words = [data["text"][i] for i in indices]
    left = min(data["left"][i] for i in indices)
    top = min(data["top"][i] for i in indices)
    right = max(data["left"][i] + data["width"][i] for i in indices)
    bottom = max(data["top"][i] + data["height"][i] for i in indices)

    bbox = (
        left * PIXEL_TO_POINT_SCALE,
        top * PIXEL_TO_POINT_SCALE,
        right * PIXEL_TO_POINT_SCALE,
        bottom * PIXEL_TO_POINT_SCALE,
    )
    font_size = max((bottom - top) * PIXEL_TO_POINT_SCALE, MIN_FONT_SIZE)

    return TextBlock(
        text=" ".join(words),
        font_name=OCR_FONT_NAME,
        font_size=round(font_size, 2),
        is_bold=False,
        is_italic=False,
        is_superscript=False,
        bbox=bbox,
        page_number=page_number,
    )
