from pathlib import Path

from mdook.core.models import BookManifest, BookMetadata, Chapter, DocumentTree, PageData
from mdook.core.stages.extraction import run_extraction
from mdook.core.stages.intake import run_intake
from mdook.core.stages.rendering import RenderResult, render_vault
from mdook.core.stages.semantic import run_semantic
from mdook.core.stages.validation import run_validation


def _manifest(tmp_path: Path, total_pages: int) -> BookManifest:
    return BookManifest(
        file_path=str(tmp_path / "book.pdf"),
        title="Test Book",
        author="Test Author",
        total_pages=total_pages,
        needs_ocr=False,
        profile="literature",
        zone_map=[],
        bookmarks=None,
    )


def _single_chapter_tree(page_spans: list[tuple[int, int]]) -> DocumentTree:
    return DocumentTree(
        metadata=BookMetadata(title="Test Book", author="Test Author"),
        chapters=[
            Chapter(
                number=1,
                title="Chapter One",
                level=1,
                sections=[],
                footnotes=[],
                page_spans=page_spans,
            )
        ],
    )


def _write_chapter(vault_dir: Path, text: str) -> RenderResult:
    vault_dir.mkdir(parents=True, exist_ok=True)
    chapter_path = vault_dir / "01 - Chapter One.md"
    chapter_path.write_text(text, encoding="utf-8")
    return RenderResult(
        vault_dir=vault_dir,
        index_path=vault_dir / "Index.md",
        chapter_paths=[chapter_path],
        attachments_dir=vault_dir / "attachments",
    )


def test_clean_vault_has_no_errors(bookmarked_pdf: Path, tmp_path: Path) -> None:
    manifest = run_intake(bookmarked_pdf)
    pages = run_extraction(manifest)
    tree = run_semantic(manifest, pages)
    render_result = render_vault(tree, manifest, tmp_path / "vault")

    report = run_validation(tree, manifest, render_result)

    assert report.errors == []
    assert report.total_chapters == 3


def test_ocr_pages_reflects_real_per_page_count_not_whole_book_flag(tmp_path: Path) -> None:
    """Regression: `ocr_pages` used to be `manifest.total_pages if
    manifest.needs_ocr else 0` -- an all-or-nothing guess. It should
    instead reflect exactly which pages actually went through OCR
    (Phase 3's per-page routing), independent of `manifest.needs_ocr`."""
    manifest = _manifest(tmp_path, total_pages=3)
    tree = _single_chapter_tree(page_spans=[(1, 3)])
    render_result = _write_chapter(tmp_path / "vault", "# Chapter One\n\nSome text.\n")
    pages = [
        PageData(page_number=1, width=400, height=600, blocks=[], was_ocrd=False),
        PageData(page_number=2, width=400, height=600, blocks=[], was_ocrd=True),
        PageData(page_number=3, width=400, height=600, blocks=[], was_ocrd=False),
    ]

    report = run_validation(tree, manifest, render_result, pages=pages)

    assert report.ocr_pages == 1


def test_orphan_footnote_marker_is_flagged(tmp_path: Path) -> None:
    render_result = _write_chapter(
        tmp_path / "vault", "# Chapter One\n\nA claim[^1] with no definition.\n"
    )
    manifest = _manifest(tmp_path, total_pages=1)
    tree = _single_chapter_tree([(1, 1)])

    report = run_validation(tree, manifest, render_result)

    assert any("[^1]" in w and "no matching definition" in w for w in report.warnings)


def test_orphan_footnote_definition_is_flagged(tmp_path: Path) -> None:
    render_result = _write_chapter(
        tmp_path / "vault", "# Chapter One\n\nSome text.\n\n[^1]: An unused definition.\n"
    )
    manifest = _manifest(tmp_path, total_pages=1)
    tree = _single_chapter_tree([(1, 1)])

    report = run_validation(tree, manifest, render_result)

    assert any("never referenced" in w for w in report.warnings)


def test_missing_image_file_is_flagged_as_error(tmp_path: Path) -> None:
    render_result = _write_chapter(tmp_path / "vault", "# Chapter One\n\n![[fig-1-1.png]]\n")
    manifest = _manifest(tmp_path, total_pages=1)
    tree = _single_chapter_tree([(1, 1)])

    report = run_validation(tree, manifest, render_result)

    assert any("missing from attachments" in e for e in report.errors)


def test_page_continuity_gap_is_flagged(tmp_path: Path) -> None:
    render_result = _write_chapter(
        tmp_path / "vault", "# Chapter One\n\n" + ("Body text. " * 100) + "\n"
    )
    manifest = _manifest(tmp_path, total_pages=5)
    tree = _single_chapter_tree([(3, 5)])

    report = run_validation(tree, manifest, render_result)

    assert any("not included in any chapter" in w and "1-2" in w for w in report.warnings)


def test_small_chapter_file_is_flagged(tmp_path: Path) -> None:
    render_result = _write_chapter(tmp_path / "vault", "# Chapter One\n\nToo short.\n")
    manifest = _manifest(tmp_path, total_pages=1)
    tree = _single_chapter_tree([(1, 1)])

    report = run_validation(tree, manifest, render_result)

    assert any("possible extraction failure" in w for w in report.warnings)
