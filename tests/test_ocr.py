import shutil

import pytest

from mdook.core.rules.ocr import _group_words_into_lines, extract_page_via_ocr

TESSERACT_AVAILABLE = shutil.which("tesseract") is not None


def test_group_words_into_lines_groups_by_block_par_line() -> None:
    data = {
        "text": ["", "", "", "", "Hello", "world", "", "Second", "line"],
        "conf": [-1, -1, -1, -1, 90, 88, -1, 91, 85],
        "block_num": [0, 1, 1, 1, 1, 1, 1, 1, 1],
        "par_num": [0, 0, 1, 1, 1, 1, 2, 2, 2],
        "line_num": [0, 0, 0, 1, 1, 1, 0, 1, 1],
        "left": [0, 10, 10, 10, 10, 60, 10, 10, 60],
        "top": [0, 10, 10, 10, 10, 10, 40, 40, 40],
        "width": [100, 80, 80, 80, 40, 30, 80, 40, 30],
        "height": [200, 20, 20, 20, 15, 15, 20, 15, 15],
    }
    blocks = _group_words_into_lines(data, page_number=1)
    assert [b.text for b in blocks] == ["Hello world", "Second line"]
    assert all(b.page_number == 1 for b in blocks)
    assert all(b.font_name == "OCR" for b in blocks)
    assert all(b.is_bold is False and b.is_italic is False for b in blocks)


def test_group_words_into_lines_skips_structural_rows_with_no_text() -> None:
    data = {
        "text": ["", ""],
        "conf": [-1, -1],
        "block_num": [0, 1],
        "par_num": [0, 0],
        "line_num": [0, 0],
        "left": [0, 0],
        "top": [0, 0],
        "width": [100, 100],
        "height": [100, 100],
    }
    assert _group_words_into_lines(data, page_number=1) == []


def test_extract_page_via_ocr_degrades_gracefully_on_failure(monkeypatch) -> None:
    import pymupdf
    import pytesseract

    def _raise(*args, **kwargs):
        raise RuntimeError("tesseract not found")

    monkeypatch.setattr(pytesseract, "image_to_data", _raise)

    doc = pymupdf.open()
    page = doc.new_page(width=200, height=200)
    result = extract_page_via_ocr(page, page_number=1)
    doc.close()

    assert result == []


@pytest.mark.skipif(not TESSERACT_AVAILABLE, reason="tesseract binary not installed")
def test_extract_page_via_ocr_recovers_text_from_a_rasterized_page() -> None:
    import pymupdf

    # Build a page with real text, rasterize it, then build a SEPARATE page
    # containing only that rasterized image -- simulating a scanned page
    # with no native text layer of its own at all.
    source_doc = pymupdf.open()
    source_page = source_doc.new_page(width=400, height=200)
    source_page.insert_text((20, 80), "The quick brown fox", fontsize=24, fontname="helv")
    pixmap = source_page.get_pixmap(dpi=200)

    scanned_doc = pymupdf.open()
    scanned_page = scanned_doc.new_page(width=400, height=200)
    scanned_page.insert_image(pymupdf.Rect(0, 0, 400, 200), pixmap=pixmap)

    blocks = extract_page_via_ocr(scanned_page, page_number=1)
    source_doc.close()
    scanned_doc.close()

    full_text = " ".join(b.text for b in blocks).lower()
    assert "quick" in full_text
    assert "fox" in full_text
