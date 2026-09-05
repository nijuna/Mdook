from pathlib import Path

import pytest

from mdook.core.errors import CorruptPDFError, EncryptedPDFError
from mdook.core.stages.intake import run_intake


def test_bookmarks_extracted(bookmarked_pdf: Path) -> None:
    manifest = run_intake(bookmarked_pdf)
    assert manifest.bookmarks is not None
    assert [b.title for b in manifest.bookmarks] == ["Chapter 1", "Chapter 2", "Chapter 3"]
    assert manifest.total_pages == 6


def test_no_bookmarks_when_absent(unbookmarked_pdf: Path) -> None:
    manifest = run_intake(unbookmarked_pdf)
    assert manifest.bookmarks is None


def test_text_layer_present_means_no_ocr(bookmarked_pdf: Path) -> None:
    manifest = run_intake(bookmarked_pdf)
    assert manifest.needs_ocr is False


def test_profile_override_is_respected(bookmarked_pdf: Path) -> None:
    manifest = run_intake(bookmarked_pdf, profile_override="technical")
    assert manifest.profile == "technical"


def test_profile_defaults_to_literature(bookmarked_pdf: Path) -> None:
    manifest = run_intake(bookmarked_pdf)
    assert manifest.profile == "literature"


def test_garbage_metadata_title_falls_back_to_filename(tmp_path: Path) -> None:
    """Regression: a real-world PDF was found with a metadata title that was
    literally a URL-encoded local file path ending in ".htm" (an artifact of
    whatever tool produced the PDF from an HTML source). Propagating that
    verbatim made an unusable 150+ character vault folder name."""
    import pymupdf

    pdf_path = tmp_path / "book.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=400, height=600)
    page.insert_text((72, 100), "Some body text.", fontsize=11, fontname="helv")
    doc.set_metadata({"title": "fileHKaZaA%20Shared%20Folder--My%20Book--My%20Book.htm"})
    doc.save(str(pdf_path))
    doc.close()

    manifest = run_intake(pdf_path)
    assert manifest.title == "book"


def test_normal_metadata_title_is_kept(tmp_path: Path) -> None:
    import pymupdf

    pdf_path = tmp_path / "irrelevant_filename.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=400, height=600)
    page.insert_text((72, 100), "Some body text.", fontsize=11, fontname="helv")
    doc.set_metadata({"title": "A Perfectly Normal Book Title"})
    doc.save(str(pdf_path))
    doc.close()

    manifest = run_intake(pdf_path)
    assert manifest.title == "A Perfectly Normal Book Title"


def test_password_protected_pdf_fails_intake_with_clear_message(tmp_path: Path) -> None:
    import pymupdf

    pdf_path = tmp_path / "encrypted.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=400, height=600)
    page.insert_text((72, 100), "Secret content.", fontsize=11, fontname="helv")
    doc.save(
        str(pdf_path),
        encryption=pymupdf.PDF_ENCRYPT_AES_256,
        user_pw="secret123",
        owner_pw="owner123",
    )
    doc.close()

    with pytest.raises(EncryptedPDFError, match="password-protected"):
        run_intake(pdf_path)


def test_corrupt_pdf_fails_intake_with_clear_message(tmp_path: Path) -> None:
    pdf_path = tmp_path / "corrupt.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\nthis is not a real pdf structure at all")

    with pytest.raises(CorruptPDFError):
        run_intake(pdf_path)
