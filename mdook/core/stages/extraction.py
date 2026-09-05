"""Stage 2 — Extraction.

Input: `mdook.core.models.BookManifest`.
Output: `list[mdook.core.models.PageData]`.

Implements the text-layer path from `Mdook-docs/ARCHITECTURE.md` ("Stage 2"):
per-page text spans (font, size, bold/italic/superscript, bbox) grouped into
`TextBlock`s, plus embedded raster image extraction into `ImageBlock`s and
grid-ruled table extraction into `TableBlock`s (Rule 6.1, delegated to
`mdook.core.rules.tables`, which uses pdfplumber for its table finder --
PyMuPDF has no equivalent). A text block whose center falls inside a
detected table's bounding box is dropped from the ordinary text-block list,
since its content is already captured in the table's own cells. Multi-column
reading order (Rules 8.1-8.3, delegated to `mdook.core.rules.columns`) is
reconstructed as a final whole-book pass, after every page's blocks exist.

Phase 3 per-page OCR fallback: each page's native text is scored
(`mdook.core.rules.text_quality`); a page that scores below threshold is
re-extracted via Tesseract instead (`mdook.core.rules.ocr`), whose output
normalizes into the same `TextBlock` shape so every downstream Stage 3 rule
runs unchanged regardless of source. `PageData.was_ocrd` records which path
a page actually took.

Not implemented yet (later sprints/phases per `Mdook-docs/ROADMAP.md`):
- Vector diagram rasterization, caption association, decorative filtering
  (Phase 2)
- Header/footer stripping is delegated to
  `mdook.core.rules.headers_footers.detect_headers_footers`.
"""

from __future__ import annotations

import logging
import re
import tempfile
from pathlib import Path
from typing import Callable

import pdfplumber
import pymupdf

from mdook.core.models import BookManifest, ImageBlock, PageData, TableBlock, TextBlock
from mdook.core.rules import columns as column_rules
from mdook.core.rules import headers_footers as hf_rules
from mdook.core.rules import images as image_rules
from mdook.core.rules import ocr as ocr_rules
from mdook.core.rules import tables as table_rules
from mdook.core.rules import text_quality as text_quality_rules

logger = logging.getLogger(__name__)

# PyMuPDF span "flags" bitfield (see PyMuPDF docs on TextPage.extractDICT).
SUPERSCRIPT_FLAG = 1 << 0
ITALIC_FLAG = 1 << 1
BOLD_FLAG = 1 << 4

# A span whose text is only digits/footnote symbols (Rule 4.1: "begins with a
# number, asterisk, or symbol") -- used to tell a real footnote marker apart
# from decorative same-word styling (see `_same_style`).
FOOTNOTE_MARKER_TEXT_RE = re.compile(r"^[\d*†‡§¶]+$")
MIN_SAME_WORD_SIZE_RATIO = 0.5
"""Below this size ratio, a differently-sized adjacent span is treated as a
genuine size-class change (a drop cap, or heading text abutting body text)
rather than decorative same-word styling, regardless of its text."""

WORD_GAP_RATIO = 0.2
"""A horizontal gap between two spans wider than this fraction of the
current span's font size is treated as a word boundary needing a synthetic
space -- some PDF generators encode inter-word gaps purely through glyph
positioning, with no literal space character in the text stream."""

FULL_PAGE_IMAGE_AREA_RATIO = 0.9
"""An embedded image covering at least this fraction of the page area is
treated as the page's own scan background (Rule 7.4 extension), not a real
figure -- see `_extract_images`."""


PageProgressCallback = Callable[[int, int], None]


def run_extraction(
    manifest: BookManifest, on_page_extracted: PageProgressCallback | None = None
) -> list[PageData]:
    """`on_page_extracted(pages_done, total_pages)`, called after each page --
    lets the GUI report finer-grained progress than a single "Extracting..."
    step, since a scanned book's per-page OCR pass (Phase 3) can take
    several seconds a page and would otherwise look frozen for minutes."""
    doc = pymupdf.open(manifest.file_path)
    tmp_dir = Path(tempfile.mkdtemp(prefix="mdook_"))
    try:
        plumber_doc = pdfplumber.open(manifest.file_path)
    except Exception:
        plumber_doc = None  # degrade to "no tables found" rather than failing the whole book

    try:
        pages = []
        for index in range(doc.page_count):
            pages.append(
                _extract_page(
                    doc, index, tmp_dir, plumber_doc.pages[index] if plumber_doc else None
                )
            )
            if on_page_extracted is not None:
                on_page_extracted(index + 1, doc.page_count)
    finally:
        doc.close()
        if plumber_doc is not None:
            plumber_doc.close()

    hf_rules.detect_headers_footers(pages)
    column_rules.reorder_columns_if_warranted(pages, manifest.profile)  # Rules 8.1-8.3
    return pages


def _extract_page(doc, index: int, tmp_dir: Path, plumber_page: object | None) -> PageData:
    page = doc[index]
    page_number = index + 1

    table_blocks = table_rules.detect_tables(plumber_page)  # Rule 6.1
    text_blocks = _extract_native_text_blocks(page, page_number, table_blocks)
    text_blocks = _deduplicate_overlapping_text(text_blocks)  # Batch 19
    is_vertical_text = _page_is_vertical_text(page)  # Batch 18

    # Rule 4.1-style per-page decision (Phase 3): score the native text
    # layer just extracted, and if it looks unusable, re-extract this one
    # page via OCR instead. A page whose OCR attempt itself produces
    # nothing (missing `tesseract` binary, or a mid-page failure) falls
    # back to keeping the native blocks, however poor -- losing the page
    # entirely would be worse than keeping low-quality native text.
    was_ocrd = False
    is_blank = False
    native_page_data = PageData(
        page_number=page_number,
        width=page.rect.width,
        height=page.rect.height,
        blocks=text_blocks,
    )
    quality_score = text_quality_rules.score_page_quality(native_page_data)
    if text_quality_rules.needs_ocr_for_page(quality_score):
        if _page_is_blank(text_blocks, page):
            # Batch 19: a page an author left intentionally blank has
            # nothing for OCR to find -- that's the expected, correct
            # outcome, not the same failure the warning below describes.
            is_blank = True
            logger.info("Page %d: appears blank -- skipping OCR.", page_number)
        else:
            ocr_blocks = ocr_rules.extract_page_via_ocr(page, page_number)
            if ocr_blocks:
                text_blocks = [
                    b for b in ocr_blocks if not _falls_inside_a_table(b.bbox, table_blocks)
                ]
                was_ocrd = True
                logger.info(
                    "Page %d: text quality score %.2f -- routed to OCR", page_number, quality_score
                )
            else:
                logger.warning(
                    "Page %d: text quality score %.2f warranted OCR, but OCR produced "
                    "nothing (is the `tesseract` binary installed?) -- keeping native text",
                    page_number,
                    quality_score,
                )

    image_blocks = _extract_images(doc, page, page_number, tmp_dir)
    image_blocks.extend(
        _rasterize_vector_diagrams(page, page_number, tmp_dir, image_blocks, table_blocks)
    )
    caption_ids = _associate_captions(image_blocks, text_blocks)  # Rule 7.3
    text_blocks = [b for b in text_blocks if id(b) not in caption_ids]

    blocks: list[TextBlock | ImageBlock | TableBlock] = list(text_blocks)
    for image_block in image_blocks:
        insert_index = next(
            (i for i, b in enumerate(blocks) if b.bbox[1] > image_block.bbox[1]),
            len(blocks),
        )
        blocks.insert(insert_index, image_block)
    for table_block in table_blocks:
        insert_index = next(
            (i for i, b in enumerate(blocks) if b.bbox[1] > table_block.bbox[1]),
            len(blocks),
        )
        blocks.insert(insert_index, table_block)

    return PageData(
        page_number=page_number,
        width=page.rect.width,
        height=page.rect.height,
        blocks=blocks,
        was_ocrd=was_ocrd,
        is_vertical_text=is_vertical_text,
        is_blank=is_blank,
    )


def _page_is_vertical_text(page) -> bool:
    """Batch 18 — PyMuPDF exposes each line's own writing mode (0 =
    horizontal, 1 = vertical, straight from the PDF's `WMode`); a page
    typeset in traditional vertical CJK style sets this on most or all of
    its lines. A second, lightweight `get_text("dict")` call rather than
    threading an extra return value through `_extract_native_text_blocks`
    -- simpler to keep a single-bool check isolated."""
    lines = [
        line
        for raw_block in page.get_text("dict")["blocks"]
        if raw_block.get("type") == 0
        for line in raw_block["lines"]
    ]
    if not lines:
        return False
    vertical = sum(1 for line in lines if line.get("wmode") == 1)
    return vertical / len(lines) > 0.5


def _extract_native_text_blocks(
    page, page_number: int, table_blocks: list[TableBlock]
) -> list[TextBlock]:
    # PyMuPDF's own line/span traversal already yields correct left-to-right,
    # top-to-bottom reading order *within* a line. Re-sorting everything by
    # raw bbox top would break that: a small inline span (e.g. a superscript
    # footnote marker) can have a bbox top that sits numerically *below* its
    # full-size neighbors on the same visual line, since a smaller font has
    # less ascent. So text blocks keep their natural order.
    text_blocks: list[TextBlock] = []
    for raw_block in page.get_text("dict")["blocks"]:
        if raw_block.get("type") != 0:
            continue  # 0 = text, 1 = image; images are pulled separately elsewhere
        for line in raw_block["lines"]:
            for span_group in _group_spans_by_style(line["spans"]):
                block = _span_group_to_text_block(span_group, page_number)
                if _falls_inside_a_table(block.bbox, table_blocks):
                    continue  # already captured as this table's own cell text
                text_blocks.append(block)
    return text_blocks


BLANK_PAGE_MAX_CHARS = 5
"""Batch 19: a page at or below this many native characters, with no
embedded images either, is treated as intentionally blank rather than
routed through OCR -- there is nothing on it for OCR to find."""


def _page_is_blank(text_blocks: list[TextBlock], page) -> bool:
    full_text = "".join(b.text for b in text_blocks).strip()
    if len(full_text) > BLANK_PAGE_MAX_CHARS:
        return False
    return not page.get_images(full=True)


DUPLICATE_TEXT_OVERLAP_RATIO = 0.7
"""Batch 19: some scanned PDFs carry two overlapping text layers at once
-- a faint original layer plus a separately-applied OCR layer from
whatever archival tool processed the scan before it ever reached Mdook.
Extracting both doubles every paragraph. Two blocks with matching text
whose bounding boxes overlap by at least this fraction of the smaller
block's area are treated as the same content appearing twice."""


def _deduplicate_overlapping_text(text_blocks: list[TextBlock]) -> list[TextBlock]:
    """Keeps the first-seen block at each position; a later block whose
    text matches (ignoring case/whitespace) and whose bbox substantially
    overlaps an already-kept block is a duplicate layer, not new content."""
    kept: list[TextBlock] = []
    for block in text_blocks:
        normalized = _normalize_for_dedup(block.text)
        if any(
            _normalize_for_dedup(existing.text) == normalized
            and _bbox_overlap_ratio(block.bbox, existing.bbox) >= DUPLICATE_TEXT_OVERLAP_RATIO
            for existing in kept
        ):
            continue
        kept.append(block)
    return kept


def _normalize_for_dedup(text: str) -> str:
    return " ".join(text.lower().split())


def _bbox_overlap_ratio(
    a: tuple[float, float, float, float], b: tuple[float, float, float, float]
) -> float:
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    ix0, iy0 = max(ax0, bx0), max(ay0, by0)
    ix1, iy1 = min(ax1, bx1), min(ay1, by1)
    if ix1 <= ix0 or iy1 <= iy0:
        return 0.0
    intersection = (ix1 - ix0) * (iy1 - iy0)
    area_a = max(ax1 - ax0, 0.0) * max(ay1 - ay0, 0.0)
    area_b = max(bx1 - bx0, 0.0) * max(by1 - by0, 0.0)
    smaller = min(area_a, area_b)
    return intersection / smaller if smaller > 0 else 0.0


def _falls_inside_a_table(
    bbox: tuple[float, float, float, float], tables: list[TableBlock]
) -> bool:
    center_x = (bbox[0] + bbox[2]) / 2
    center_y = (bbox[1] + bbox[3]) / 2
    for table in tables:
        tx0, ty0, tx1, ty1 = table.bbox
        if tx0 <= center_x <= tx1 and ty0 <= center_y <= ty1:
            return True
    return False


def _group_spans_by_style(spans: list[dict]) -> list[list[dict]]:
    """Adjacent spans on the same line sharing size/weight/slant become one
    block (font *name* is deliberately not part of the comparison — see
    `_same_style`)."""
    groups: list[list[dict]] = []
    current: list[dict] = []
    for span in spans:
        if span["text"] == "":
            continue  # a whitespace-only span (e.g. a lone " ") is a real word gap, not filler
        if current and not _same_style(current[-1], span):
            groups.append(current)
            current = []
        current.append(span)
    if current:
        groups.append(current)
    return groups


def _same_style(a: dict, b: dict) -> bool:
    """Font *name* is intentionally not compared here. HTML-to-PDF exports
    (newsletter/email digests especially) routinely subset one visual run of
    text across several differently-named embedded font resources with zero
    visual difference -- comparing names used to fragment ordinary sentences,
    and stylized multi-glyph headlines, into one block per glyph run.

    A meaningfully different font *size* also doesn't automatically split the
    run: classic small-caps typesetting (a word's leading letter set larger
    than the rest -- "THE" as "T" + "he") uses two sizes for one word, and
    treating that as a style break used to shred small-caps headings and
    inline decorative signage ("HAWBERK, ARMOURER") one letter-group at a
    time. The split still happens when it should: a genuine footnote marker
    (Rule 4.1: digit or a dagger/section symbol) or a dramatically smaller
    span (a real drop cap, or heading text abutting body text) still forces
    a new block.
    """
    if a["flags"] != b["flags"]:
        return False
    if abs(a["size"] - b["size"]) < 0.1:
        return True

    smaller_size, larger_size = sorted((a["size"], b["size"]))
    if smaller_size / larger_size < MIN_SAME_WORD_SIZE_RATIO:
        return False

    smaller_span = a if a["size"] < b["size"] else b
    return not FOOTNOTE_MARKER_TEXT_RE.match(smaller_span["text"].strip())


def _join_span_texts(spans: list[dict]) -> str:
    """Concatenate a merged group's span texts, inserting a synthetic space
    across any gap wide enough to be a real word boundary. Most PDFs already
    carry an explicit space character between words, but some encode the gap
    purely through glyph positioning -- most visibly at a small-caps
    boundary like "OF" -> "REPUTATIONS", where nothing in the text stream
    marks the word break at all."""
    text = spans[0]["text"]
    for prev, curr in zip(spans, spans[1:]):
        gap = curr["bbox"][0] - prev["bbox"][2]
        needs_space = (
            gap > curr["size"] * WORD_GAP_RATIO
            and not text.endswith((" ", " "))
            and not curr["text"].startswith((" ", " "))
        )
        text += (" " if needs_space else "") + curr["text"]
    return text


def _span_group_to_text_block(spans: list[dict], page_number: int) -> TextBlock:
    text = _join_span_texts(spans)
    first = spans[0]
    flags = first["flags"]
    x0 = min(s["bbox"][0] for s in spans)
    y0 = min(s["bbox"][1] for s in spans)
    x1 = max(s["bbox"][2] for s in spans)
    y1 = max(s["bbox"][3] for s in spans)

    return TextBlock(
        text=text,
        font_name=first["font"],
        font_size=round(first["size"], 2),
        is_bold=bool(flags & BOLD_FLAG),
        is_italic=bool(flags & ITALIC_FLAG),
        is_superscript=bool(flags & SUPERSCRIPT_FLAG),
        bbox=(x0, y0, x1, y1),
        page_number=page_number,
    )


def _extract_images(doc, page, page_number: int, tmp_dir: Path) -> list[ImageBlock]:
    results: list[ImageBlock] = []
    page_area = page.rect.width * page.rect.height

    for image_index, img in enumerate(page.get_images(full=True)):
        xref = img[0]

        rects = page.get_image_rects(xref)
        if not rects:
            continue  # not actually placed/visible on the page (e.g. an unused shared resource)
        bbox = tuple(rects[0])

        image_area = max(bbox[2] - bbox[0], 0.0) * max(bbox[3] - bbox[1], 0.0)
        if page_area > 0 and image_area >= page_area * FULL_PAGE_IMAGE_AREA_RATIO:
            # Rule 7.4 extension: a scanned book's underlying page photo, laid
            # under an OCR text layer, is embedded as one full-page image on
            # every single page. It isn't a meaningful figure -- extracting it
            # anyway turns every scanned book into a duplicate of itself in
            # attachments/ and multiplies conversion time for no benefit.
            continue

        try:
            base_image = doc.extract_image(xref)
        except Exception:
            continue  # unsupported/corrupt image stream — skip rather than fail the page

        ext = base_image.get("ext", "png")
        image_path = tmp_dir / f"page-{page_number}-img-{image_index}.{ext}"
        image_path.write_bytes(base_image["image"])

        results.append(
            ImageBlock(
                image_path=str(image_path),
                bbox=bbox,
                caption=None,
                page_number=page_number,
            )
        )
    return results


def _rasterize_vector_diagrams(
    page,
    page_number: int,
    tmp_dir: Path,
    existing_images: list[ImageBlock],
    table_blocks: list[TableBlock],
) -> list[ImageBlock]:
    """Rule 7.2 — `page.get_drawings()` exposes vector paths (lines, fills,
    curves) that never appear in `get_images()` since they're drawn
    directly rather than placed as a bitmap. A diagram built this way (a
    chart, a flowchart) would otherwise vanish from the vault entirely."""
    try:
        drawings = page.get_drawings()
    except Exception:
        return []  # degrade gracefully, same pattern as pdfplumber/image-extraction failures

    rects = [tuple(d["rect"]) for d in drawings if d.get("rect") is not None]
    exclude = [b.bbox for b in existing_images] + [t.bbox for t in table_blocks]
    regions = image_rules.cluster_drawing_regions(rects, exclude)

    results: list[ImageBlock] = []
    for region_index, region in enumerate(regions):
        try:
            pixmap = page.get_pixmap(clip=pymupdf.Rect(*region), dpi=300)
            image_path = tmp_dir / f"page-{page_number}-diagram-{region_index}.png"
            pixmap.save(str(image_path))
        except Exception:
            continue  # a malformed clip region shouldn't fail the whole page
        results.append(
            ImageBlock(
                image_path=str(image_path),
                bbox=region,
                caption=None,
                page_number=page_number,
            )
        )
    return results


def _associate_captions(image_blocks: list[ImageBlock], text_blocks: list[TextBlock]) -> set[int]:
    """Rule 7.3 — mutates `image_blocks` in place, populating `caption`.
    Returns the `id()`s of matched caption `TextBlock`s so the caller can
    remove them from the ordinary text flow (otherwise the caption would
    render twice: once as a stray paragraph, once as the image's own
    caption line)."""
    consumed_ids: set[int] = set()
    for image_block in image_blocks:
        available = [b for b in text_blocks if id(b) not in consumed_ids]
        caption_block = image_rules.find_caption(image_block.bbox, available)
        if caption_block is not None:
            image_block.caption = caption_block.text.strip()
            consumed_ids.add(id(caption_block))
    return consumed_ids
