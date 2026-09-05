"""Sprint 1 scaffold checks: Pydantic models import and validate cleanly.

No GUI (Qt) imports here — these tests must pass on a headless CI runner.
See test_pipeline.py for the real end-to-end conversion test.
"""

from mdook.core.models import (
    BookManifest,
    Bookmark,
    BookMetadata,
    Chapter,
    DocumentTree,
    ZoneEntry,
)


def test_book_manifest_roundtrip() -> None:
    manifest = BookManifest(
        file_path="book.pdf",
        title="Test Book",
        author="Test Author",
        total_pages=100,
        needs_ocr=False,
        profile="literature",
        zone_map=[ZoneEntry(start_page=1, end_page=10, zone_type="front_matter")],
        bookmarks=[Bookmark(level=1, title="Chapter One", page_number=11)],
    )
    assert manifest.zone_map[0].zone_type == "front_matter"
    assert manifest.bookmarks[0].title == "Chapter One"


def test_document_tree_defaults() -> None:
    tree = DocumentTree(metadata=BookMetadata(title="T", author="A"))
    assert tree.chapters == []

    chapter = Chapter(number=1, title="Ch. 1", level=1)
    tree.chapters.append(chapter)
    assert tree.chapters[0].number == 1
