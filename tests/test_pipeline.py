from pathlib import Path

from mdook.core.models import ConversionResult
from mdook.core.pipeline import convert


def test_convert_reports_progress_and_real_stats(bookmarked_pdf: Path, tmp_path: Path) -> None:
    events: list[tuple[int, str]] = []
    output_dir = tmp_path / "vault"
    result = convert(
        pdf_path=bookmarked_pdf,
        output_dir=output_dir,
        profile="literature",
        on_progress=lambda percent, message: events.append((percent, message)),
    )

    assert isinstance(result, ConversionResult)
    assert result.success is True
    assert events[-1][0] == 100
    assert result.pages == 6
    assert result.chapters == 3
    assert result.footnotes == 0  # this fixture has no footnotes

    assert result.validation_report is not None
    assert result.validation_report.errors == []


def test_convert_writes_the_vault_into_its_own_subfolder(
    bookmarked_pdf: Path, tmp_path: Path
) -> None:
    """The user picks a parent folder to hold vaults in -- the book's files
    must land in a subfolder named after the book, not loose alongside
    whatever else (or whichever other book) is already in that folder."""
    chosen_output_dir = tmp_path / "vault"
    result = convert(pdf_path=bookmarked_pdf, output_dir=chosen_output_dir, profile="literature")

    assert result.manifest is not None
    assert result.output_dir != chosen_output_dir
    assert result.output_dir.parent == chosen_output_dir
    assert list(chosen_output_dir.iterdir()) == [result.output_dir]

    index_path = result.output_dir / f"{result.manifest.title} - Index.md"
    assert index_path.exists()

    chapter_files = sorted(result.output_dir.glob("0* - *.md"))
    assert len(chapter_files) == 3
    assert chapter_files[0].read_text(encoding="utf-8").startswith("# Chapter 1")
