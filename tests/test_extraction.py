import shutil
from pathlib import Path

import pymupdf
import pytest

from mdook.core.models import ImageBlock, TableBlock, TextBlock
from mdook.core.stages.extraction import (
    _group_spans_by_style,
    _span_group_to_text_block,
    run_extraction,
)
from mdook.core.stages.intake import run_intake
from tests.conftest import RUNNING_FOOTER, add_grid_table, add_solid_image

TESSERACT_AVAILABLE = shutil.which("tesseract") is not None


def _span(text: str, x0: float, x1: float, size: float = 13.5, flags: int = 0) -> dict:
    return {
        "text": text,
        "size": size,
        "font": f"Type3-{x0}",
        "bbox": (x0, 274.0, x1, 289.0),
        "flags": flags,
    }


def test_extraction_produces_one_page_data_per_page(bookmarked_pdf: Path) -> None:
    manifest = run_intake(bookmarked_pdf)
    pages = run_extraction(manifest)
    assert len(pages) == manifest.total_pages


def test_on_page_extracted_callback_fires_once_per_page_in_order(bookmarked_pdf: Path) -> None:
    manifest = run_intake(bookmarked_pdf)
    progress: list[tuple[int, int]] = []
    run_extraction(manifest, on_page_extracted=lambda done, total: progress.append((done, total)))

    assert progress == [(i + 1, manifest.total_pages) for i in range(manifest.total_pages)]


def test_table_is_extracted_and_not_duplicated_as_text(tmp_path: Path) -> None:
    import pymupdf as fitz

    pdf_path = tmp_path / "table_book.pdf"
    doc = fitz.open()
    page = doc.new_page(width=400, height=300)
    page.insert_text((50, 30), "Text before the table.", fontsize=11, fontname="helv")
    add_grid_table(
        page, (50, 50, 350, 200), [["Name", "Age", "City"], ["Alice", "30", "NYC"]]
    )
    page.insert_text((50, 230), "Text after the table.", fontsize=11, fontname="helv")
    doc.save(str(pdf_path))
    doc.close()

    manifest = run_intake(pdf_path)
    pages = run_extraction(manifest)

    table_blocks = [b for b in pages[0].blocks if isinstance(b, TableBlock)]
    assert len(table_blocks) == 1
    assert table_blocks[0].cells == [["Name", "Age", "City"], ["Alice", "30", "NYC"]]

    all_text = " ".join(
        b.text for b in pages[0].blocks if isinstance(b, TextBlock)
    )
    assert "Alice" not in all_text  # already captured in the table's own cells
    assert "Text before the table." in all_text
    assert "Text after the table." in all_text


@pytest.mark.skipif(not TESSERACT_AVAILABLE, reason="tesseract binary not installed")
def test_scanned_page_routes_to_ocr_while_native_page_does_not(tmp_path: Path) -> None:
    """Per-page routing (Phase 3): a hybrid book with one native-text page
    and one scanned (image-only) page should OCR only the scanned one."""
    doc = pymupdf.open()

    native_page = doc.new_page(width=400, height=200)
    native_page.insert_text(
        (20, 80), "Ordinary native body text here.", fontsize=14, fontname="helv"
    )

    render_doc = pymupdf.open()
    render_page = render_doc.new_page(width=400, height=200)
    render_page.insert_text(
        (20, 80), "A scanned line of recognizable text.", fontsize=18, fontname="helv"
    )
    pixmap = render_page.get_pixmap(dpi=200)
    render_doc.close()

    scanned_page = doc.new_page(width=400, height=200)
    scanned_page.insert_image(pymupdf.Rect(0, 0, 400, 200), pixmap=pixmap)

    pdf_path = tmp_path / "hybrid_scan.pdf"
    doc.save(str(pdf_path))
    doc.close()

    manifest = run_intake(pdf_path)
    pages = run_extraction(manifest)

    assert pages[0].was_ocrd is False
    native_text = " ".join(b.text for b in pages[0].blocks if isinstance(b, TextBlock))
    assert "Ordinary native body text" in native_text

    assert pages[1].was_ocrd is True
    ocr_text = " ".join(b.text for b in pages[1].blocks if isinstance(b, TextBlock)).lower()
    assert "scanned" in ocr_text
    assert "recognizable" in ocr_text


def test_genuinely_blank_page_is_marked_blank_not_ocr_failure(tmp_path: Path) -> None:
    doc = pymupdf.open()
    doc.new_page(width=400, height=600).insert_text(
        (72, 100), "A page with real content.", fontsize=11, fontname="helv"
    )
    doc.new_page(width=400, height=600)  # genuinely blank -- nothing inserted at all
    doc.new_page(width=400, height=600).insert_text(
        (72, 100), "More real content after the blank page.", fontsize=11, fontname="helv"
    )
    pdf_path = tmp_path / "with_blank_page.pdf"
    doc.save(str(pdf_path))
    doc.close()

    manifest = run_intake(pdf_path)
    pages = run_extraction(manifest)

    assert pages[1].is_blank is True
    assert pages[1].was_ocrd is False
    assert pages[1].blocks == []
    assert pages[0].is_blank is False
    assert pages[2].is_blank is False


def test_duplicate_overlapping_text_layers_are_deduplicated(tmp_path: Path) -> None:
    doc = pymupdf.open()
    page = doc.new_page(width=400, height=600)
    # Simulates a scan carrying two overlapping text layers (a faint
    # original plus a separately-applied OCR layer) -- same text, nearly
    # the same position, inserted as two separate content-stream objects.
    page.insert_text(
        (72, 100), "This line appears in both text layers.", fontsize=11, fontname="helv"
    )
    page.insert_text(
        (72, 100.5), "This line appears in both text layers.", fontsize=11, fontname="helv"
    )
    page.insert_text((72, 130), "This line only appears once.", fontsize=11, fontname="helv")
    pdf_path = tmp_path / "duplicate_layers.pdf"
    doc.save(str(pdf_path))
    doc.close()

    manifest = run_intake(pdf_path)
    pages = run_extraction(manifest)

    matching = [
        b
        for b in pages[0].blocks
        if isinstance(b, TextBlock) and "appears in both text layers" in b.text
    ]
    assert len(matching) == 1
    unique = [
        b for b in pages[0].blocks if isinstance(b, TextBlock) and "only appears once" in b.text
    ]
    assert len(unique) == 1


def test_running_footer_is_stripped_and_recorded(unbookmarked_pdf: Path) -> None:
    manifest = run_intake(unbookmarked_pdf)
    pages = run_extraction(manifest)

    for page in pages:
        assert page.footer_text == RUNNING_FOOTER
        for block in page.blocks:
            if isinstance(block, TextBlock):
                assert block.text.strip() != RUNNING_FOOTER


def test_text_blocks_capture_font_metadata(bookmarked_pdf: Path) -> None:
    manifest = run_intake(bookmarked_pdf)
    pages = run_extraction(manifest)

    heading_block = next(
        b for b in pages[0].blocks if isinstance(b, TextBlock) and b.text.strip() == "Chapter 1"
    )
    assert heading_block.font_size > 20


def test_embedded_image_is_extracted(tmp_path: Path) -> None:
    pdf_path = tmp_path / "with_image.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=400, height=600)
    page.insert_text((72, 100), "A page with a figure.", fontsize=11, fontname="helv")
    add_solid_image(page, (72, 200, 172, 300))
    doc.save(str(pdf_path))
    doc.close()

    manifest = run_intake(pdf_path)
    pages = run_extraction(manifest)

    images = [b for b in pages[0].blocks if isinstance(b, ImageBlock)]
    assert len(images) == 1
    assert Path(images[0].image_path).exists()


def test_captioned_image_gets_its_caption_and_the_text_is_removed(tmp_path: Path) -> None:
    pdf_path = tmp_path / "captioned_image.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=400, height=600)
    page.insert_text((72, 100), "A page with a figure.", fontsize=11, fontname="helv")
    add_solid_image(page, (72, 200, 172, 300))
    page.insert_text(
        (72, 310), "Figure 3.2: Cross-section of the assembly.", fontsize=9, fontname="helv"
    )
    doc.save(str(pdf_path))
    doc.close()

    manifest = run_intake(pdf_path)
    pages = run_extraction(manifest)

    images = [b for b in pages[0].blocks if isinstance(b, ImageBlock)]
    assert len(images) == 1
    assert images[0].caption == "Figure 3.2: Cross-section of the assembly."

    remaining_text = " ".join(b.text for b in pages[0].blocks if isinstance(b, TextBlock))
    assert "Cross-section of the assembly" not in remaining_text


def test_uncaptioned_image_has_no_false_caption(tmp_path: Path) -> None:
    pdf_path = tmp_path / "uncaptioned_image.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=400, height=600)
    page.insert_text(
        (72, 100), "A page with a figure but no caption.", fontsize=11, fontname="helv"
    )
    add_solid_image(page, (72, 200, 172, 300))
    doc.save(str(pdf_path))
    doc.close()

    manifest = run_intake(pdf_path)
    pages = run_extraction(manifest)

    images = [b for b in pages[0].blocks if isinstance(b, ImageBlock)]
    assert len(images) == 1
    assert images[0].caption is None


def test_vector_diagram_with_no_embedded_raster_is_rasterized(tmp_path: Path) -> None:
    pdf_path = tmp_path / "vector_diagram.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=400, height=600)
    page.insert_text((72, 60), "A flowchart follows.", fontsize=11, fontname="helv")
    # A simple two-box "flowchart" drawn with vector paths -- no
    # `insert_image` call anywhere, so `get_images()` sees nothing at all.
    page.draw_rect(pymupdf.Rect(72, 150, 172, 220))
    page.draw_rect(pymupdf.Rect(72, 260, 172, 330))
    page.draw_line((122, 220), (122, 260))
    doc.save(str(pdf_path))
    doc.close()

    manifest = run_intake(pdf_path)
    pages = run_extraction(manifest)

    images = [b for b in pages[0].blocks if isinstance(b, ImageBlock)]
    assert len(images) == 1
    assert Path(images[0].image_path).exists()


def test_decorative_horizontal_rule_is_not_rasterized_as_a_diagram(tmp_path: Path) -> None:
    pdf_path = tmp_path / "decorative_rule.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=400, height=600)
    page.insert_text((72, 100), "End of chapter.", fontsize=11, fontname="helv")
    page.draw_line((72, 150), (328, 150))  # a thin decorative rule, not a diagram
    doc.save(str(pdf_path))
    doc.close()

    manifest = run_intake(pdf_path)
    pages = run_extraction(manifest)

    images = [b for b in pages[0].blocks if isinstance(b, ImageBlock)]
    assert images == []


def test_differing_font_names_at_same_size_still_merge() -> None:
    """Regression: HTML-to-PDF exports (newsletter/email digests especially)
    routinely subset one visual run of text across several differently-named
    embedded font resources with zero visual difference. This used to
    fragment ordinary sentences -- and stylized multi-glyph headlines like
    "The Top AI Papers of the Week" -- into one block per glyph run."""
    spans = [
        _span("T", 100.1, 108.8),
        _span("he", 108.8, 124.7),
        _span(" ", 124.7, 128.5),
        _span("T", 128.5, 137.2),
        _span("op", 136.1, 152.5),
    ]
    groups = _group_spans_by_style(spans)
    assert len(groups) == 1
    block = _span_group_to_text_block(groups[0], page_number=1)
    assert block.text == "The Top"


def test_standalone_whitespace_span_is_preserved_as_a_word_gap() -> None:
    """Regression: a lone ' ' span between two words was being dropped
    entirely (not just excluded from starting a new group), silently
    deleting the space between words like "Top" and "AI"."""
    spans = [_span("Top", 51.3, 79.0), _span(" ", 79.0, 83.0), _span("AI", 83.0, 96.0)]
    groups = _group_spans_by_style(spans)
    assert len(groups) == 1
    block = _span_group_to_text_block(groups[0], page_number=1)
    assert block.text == "Top AI"


def test_meaningfully_smaller_font_still_splits_off() -> None:
    """A genuinely smaller run (e.g. a footnote marker) must still split off
    so Rule 4.2 correlation in mdook.core.rules.footnotes keeps working."""
    spans = [_span("word", 72, 100, size=11.0), _span("1", 100, 104, size=7.0)]
    groups = _group_spans_by_style(spans)
    assert len(groups) == 2


def test_small_caps_word_split_across_two_sizes_merges() -> None:
    """Regression: classic small-caps typesetting ("THE" rendered as a
    larger "T" plus a smaller "HE") used to be treated as a style break
    (differing size), fragmenting small-caps chapter titles and inline
    decorative signage (e.g. "HAWBERK, ARMOURER") one letter-group at a
    time. Alphabetic content at a size that isn't drastically smaller
    should merge into one run regardless."""
    spans = [
        _span("T", 100.1, 108.8, size=14.0),
        _span("HE", 108.8, 124.7, size=11.0),
        _span("R", 128.5, 137.2, size=14.0),
        _span("EPAIRER", 136.1, 170.0, size=11.0),
    ]
    groups = _group_spans_by_style(spans)
    assert len(groups) == 1
    block = _span_group_to_text_block(groups[0], page_number=1)
    assert block.text == "THE REPAIRER"


def test_gap_without_a_literal_space_span_still_gets_a_synthetic_space() -> None:
    """Regression: some PDFs encode a word gap purely through glyph
    positioning, with no space character anywhere in the text stream --
    most visibly at a small-caps style-change boundary. Losing that gap
    glued unrelated words together (e.g. "OF" + "REPUTATIONS" ->
    "OFREPUTATIONS")."""
    spans = [_span("OF", 200.0, 217.0, size=11.0), _span("R", 221.0, 230.0, size=14.0)]
    block = _span_group_to_text_block(spans, page_number=1)
    assert block.text == "OF R"
