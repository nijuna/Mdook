from datetime import date
from pathlib import Path

from mdook.cli import build_parser
from mdook.core.models import (
    BookManifest,
    BookMetadata,
    Chapter,
    DocumentTree,
    Footnote,
    ImageRef,
    Paragraph,
    Section,
)
from mdook.core.pipeline import convert
from mdook.core.rules.citations import CITATION_MARKER_SENTINEL
from mdook.core.rules.paragraphs import (
    ENDNOTE_MARKER_SENTINEL,
    FOOTNOTE_MARKER_SENTINEL,
)
from mdook.core.stages.rendering import render_single_file
from mdook.core.stages.validation import run_validation


def _dummy_manifest(title: str = "Test Book") -> BookManifest:
    return BookManifest(
        file_path=f"/tmp/{title}.pdf",
        title=title,
        author="Test Author",
        total_pages=10,
        needs_ocr=False,
        profile="literature",
    )


def test_render_single_file_basic_structure(tmp_path: Path) -> None:
    manifest = _dummy_manifest("Single Story")
    tree = DocumentTree(
        metadata=BookMetadata(
            title="Single Story",
            author="Author Name",
            isbn="978-0-123456-78-9",
            publisher="Book Press",
        ),
        front_matter=[
            Section(
                title="Preface",
                level=1,
                content=[Paragraph(text="This is the preface text.", page_number=1)],
            )
        ],
        chapters=[
            Chapter(
                number=1,
                title="Chapter One: The Awakening",
                level=1,
                sections=[
                    Section(
                        title="Dawn",
                        level=1,
                        content=[
                            Paragraph(text="Dawn broke slowly over the hills.", page_number=2)
                        ],
                    )
                ],
            ),
            Chapter(
                number=2,
                title="Chapter Two: The Journey",
                level=1,
                sections=[
                    Section(
                        title=None,
                        level=1,
                        content=[Paragraph(text="They marched into the forest.", page_number=3)],
                    )
                ],
            ),
        ],
        back_matter=[
            Section(
                title="Epilogue",
                level=1,
                content=[Paragraph(text="All was quiet.", page_number=4)],
            )
        ],
    )

    out_dir = tmp_path / "output"
    result = render_single_file(tree, manifest, out_dir)

    assert result.vault_dir.exists()
    assert result.index_path.exists()
    assert result.index_path.name == "Single Story.md"
    assert result.chapter_paths == [result.index_path]

    content = result.index_path.read_text(encoding="utf-8")

    # Check YAML Frontmatter
    assert content.startswith("---\n")
    assert "title: Single Story" in content
    assert "author: Author Name" in content
    assert "isbn: 978-0-123456-78-9" in content
    assert "output_mode: single_document" in content
    assert f"converted: {date.today().isoformat()}" in content

    # Check headings hierarchy
    assert "# Single Story" in content
    assert "## Front Matter" in content
    assert "### Preface" in content
    assert "## Chapter One: The Awakening" in content
    assert "### Dawn" in content
    assert "## Chapter Two: The Journey" in content
    assert "## Back Matter" in content
    assert "### Epilogue" in content

    # Verify no page-marker callouts
    assert "> [!quote]- p." not in content


def test_render_single_file_universal_image_syntax(tmp_path: Path) -> None:
    manifest = _dummy_manifest("Illustrated Book")
    dummy_img = tmp_path / "chart.png"
    dummy_img.write_bytes(b"\x89PNG\r\n\x1a\nFakePngData")

    tree = DocumentTree(
        metadata=BookMetadata(title="Illustrated Book", author="Author"),
        chapters=[
            Chapter(
                number=1,
                title="Chapter 1",
                level=1,
                sections=[
                    Section(
                        title=None,
                        level=1,
                        content=[
                            Paragraph(text="See figure below:", page_number=1),
                            ImageRef(
                                source_path=str(dummy_img),
                                figure_id="fig-1",
                                caption="Ecology Diagram",
                                page_number=1,
                            ),
                        ],
                    )
                ],
            )
        ],
    )

    out_dir = tmp_path / "output"
    result = render_single_file(tree, manifest, out_dir)

    content = result.index_path.read_text(encoding="utf-8")
    # Universal standard markdown image syntax: ![caption](attachments/fig-1.png)
    assert "![Ecology Diagram](attachments/fig-1.png)" in content
    assert "*Ecology Diagram*" in content
    assert (result.attachments_dir / "fig-1.png").exists()

    # Validation should recognize the image and pass without errors
    val_report = run_validation(tree, manifest, result)
    assert not val_report.errors


def test_render_single_file_footnotes_consolidation_and_collision_handling(
    tmp_path: Path,
) -> None:
    manifest = _dummy_manifest("Notes Book")
    # Chapter 1 and Chapter 2 both use footnote marker '1'
    ch1_p = (
        f"Chapter one fact{FOOTNOTE_MARKER_SENTINEL}1{FOOTNOTE_MARKER_SENTINEL}. "
        + ("Detail " * 80)
    )
    ch2_p = (
        f"Chapter two fact{FOOTNOTE_MARKER_SENTINEL}1{FOOTNOTE_MARKER_SENTINEL}. "
        + ("Detail " * 80)
    )

    tree = DocumentTree(
        metadata=BookMetadata(title="Notes Book", author="Author"),
        chapters=[
            Chapter(
                number=1,
                title="Chapter 1",
                level=1,
                sections=[
                    Section(
                        title=None,
                        level=1,
                        content=[Paragraph(text=ch1_p, page_number=1)],
                    )
                ],
                footnotes=[
                    Footnote(
                        marker="1",
                        text="First chapter note",
                        page_number=1,
                        style="page_bottom",
                    )
                ],
            ),
            Chapter(
                number=2,
                title="Chapter 2",
                level=1,
                sections=[
                    Section(
                        title=None,
                        level=1,
                        content=[Paragraph(text=ch2_p, page_number=2)],
                    )
                ],
                footnotes=[
                    Footnote(
                        marker="1",
                        text="Second chapter note",
                        page_number=2,
                        style="page_bottom",
                    )
                ],
            ),
        ],
    )

    out_dir = tmp_path / "output"
    result = render_single_file(tree, manifest, out_dir)
    content = result.index_path.read_text(encoding="utf-8")

    # Both footnotes should be re-indexed sequentially (1 and 2) to eliminate collisions
    assert "Chapter one fact[^1]." in content
    assert "Chapter two fact[^2]." in content

    # Unified footnote section at bottom
    assert "## Footnotes" in content
    assert "[^1]: First chapter note" in content
    assert "[^2]: Second chapter note" in content

    # Run validation audit: all footnote definitions and usages must match 1:1 with 0 warnings
    val_report = run_validation(tree, manifest, result)
    footnote_warnings = [w for w in val_report.warnings if "footnote" in w.lower()]
    assert not footnote_warnings


def test_render_single_file_endnotes_and_citations(tmp_path: Path) -> None:
    manifest = _dummy_manifest("Scholarly Work")
    body_text = (
        f"Text citing endnote {ENDNOTE_MARKER_SENTINEL}1{ENDNOTE_MARKER_SENTINEL} "
        f"and biblio {CITATION_MARKER_SENTINEL}1{CITATION_MARKER_SENTINEL}."
    )

    tree = DocumentTree(
        metadata=BookMetadata(title="Scholarly Work", author="Scholar"),
        chapters=[
            Chapter(
                number=1,
                title="Chapter 1",
                level=1,
                sections=[
                    Section(
                        title=None,
                        level=1,
                        content=[Paragraph(text=body_text, page_number=1)],
                    )
                ],
            )
        ],
        back_matter=[
            Section(
                title="Notes",
                level=1,
                content=[Paragraph(text="Detailed endnote 1", page_number=2)],
            ),
            Section(
                title="Bibliography",
                level=1,
                content=[Paragraph(text="Author, Book Title (2020)", page_number=3)],
            ),
        ],
    )

    out_dir = tmp_path / "output"
    result = render_single_file(tree, manifest, out_dir)
    content = result.index_path.read_text(encoding="utf-8")

    # In single document mode, cross-references point to anchors within the same file
    assert "[[#^note-1|1]]" in content
    assert "[[#^ref-1|1]]" in content


def test_validation_exempts_single_file_from_max_chapter_size(tmp_path: Path) -> None:
    manifest = _dummy_manifest("Long Book")
    # Single file > 200,000 bytes
    large_text = "A" * 250_000

    tree = DocumentTree(
        metadata=BookMetadata(title="Long Book", author="Author"),
        chapters=[
            Chapter(
                number=1,
                title="Chapter 1",
                level=1,
                sections=[
                    Section(
                        title=None,
                        level=1,
                        content=[Paragraph(text=large_text, page_number=1)],
                    )
                ],
            )
        ],
    )

    out_dir = tmp_path / "output"
    result = render_single_file(tree, manifest, out_dir)
    val_report = run_validation(tree, manifest, result)

    size_warnings = [w for w in val_report.warnings if "possible merge error" in w]
    assert not size_warnings


def test_pipeline_single_file_epub_integration(tmp_path: Path) -> None:
    from tests.test_epub import _create_sample_epub

    epub_path = _create_sample_epub(tmp_path / "sample.epub", title="Epub Sample")
    out_dir = tmp_path / "epub_out"
    conv_result = convert(book_path=epub_path, output_dir=out_dir, single_file=True)

    assert conv_result.success
    assert conv_result.single_file is True
    single_doc = conv_result.output_dir / f"{conv_result.manifest.title}.md"
    assert single_doc.exists()
    text = single_doc.read_text(encoding="utf-8")
    assert "output_mode: single_document" in text
    assert "# Epub Sample" in text


def test_cli_parser_single_file_flag() -> None:
    parser = build_parser()
    args = parser.parse_args(["convert", "book.pdf", "-s"])
    assert args.single_file is True

    args_long = parser.parse_args(["convert", "book.pdf", "--single-file"])
    assert args_long.single_file is True

    args_default = parser.parse_args(["convert", "book.pdf"])
    assert args_default.single_file is False
