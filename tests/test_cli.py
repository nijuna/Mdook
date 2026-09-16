from __future__ import annotations

from pathlib import Path

import pymupdf
import pytest
from rich.console import Console

from mdook import __version__
from mdook.cli import build_parser, run_cli


def _create_sample_pdf(
    path: Path,
    title: str | None = None,
    author: str | None = None,
) -> Path:
    doc = pymupdf.open()
    meta: dict[str, str] = {}
    if title:
        meta["title"] = title
    if author:
        meta["author"] = author
    if meta:
        doc.set_metadata(meta)
    for i in range(2):
        page = doc.new_page(width=400, height=600)
        page.insert_text((72, 60), f"Chapter {i + 1}", fontsize=20, fontname="helv")
        page.insert_text(
            (72, 100), f"This is body text for chapter {i + 1}.", fontsize=11, fontname="helv"
        )
    doc.save(str(path))
    doc.close()
    return path


def test_cli_version() -> None:
    console = Console(record=True)
    exit_code = run_cli(["version"], console=console)
    assert exit_code == 0
    output = console.export_text()
    assert f"Mdook v{__version__}" in output


def test_cli_help() -> None:
    parser = build_parser()
    help_text = parser.format_help()
    assert (
        "Convert books (PDF, EPUB, DOCX) into structured, interlinked Markdown libraries"
        in help_text
    )
    assert "convert" in help_text
    assert "gui" in help_text


def test_cli_convert_missing_file(tmp_path: Path) -> None:
    console = Console(record=True)
    missing_path = tmp_path / "nonexistent.pdf"
    exit_code = run_cli(["convert", str(missing_path)], console=console)
    assert exit_code == 1
    output = console.export_text()
    assert "File not found" in output


def test_cli_convert_successful(tmp_path: Path) -> None:
    pdf_path = _create_sample_pdf(tmp_path / "sample.pdf")
    vault_out = tmp_path / "vaults"
    console = Console(record=True)

    exit_code = run_cli(["convert", str(pdf_path), "-o", str(vault_out)], console=console)
    assert exit_code == 0

    output = console.export_text()
    assert "Vault Generated" in output
    assert "Chapters" in output

    vault_dir = vault_out / "sample"
    assert vault_dir.exists()
    assert (vault_dir / "sample - Index.md").exists()
    assert (vault_dir / "01 - Chapter 1.md").exists()
    assert (vault_dir / "02 - Chapter 2.md").exists()


def test_cli_convert_quiet_mode(tmp_path: Path) -> None:
    pdf_path = _create_sample_pdf(tmp_path / "quiet_sample.pdf")
    vault_out = tmp_path / "quiet_vaults"
    console = Console(record=True)

    exit_code = run_cli(
        ["convert", str(pdf_path), "-o", str(vault_out), "--quiet"],
        console=console,
    )
    assert exit_code == 0

    output = console.export_text()
    # In quiet mode, progress bar and summary table are suppressed
    assert "Vault Generated" not in output

    vault_dir = vault_out / "quiet_sample"
    assert vault_dir.exists()


def test_cli_convert_shorthand_routing(tmp_path: Path) -> None:
    pdf_path = _create_sample_pdf(tmp_path / "shorthand.pdf")
    vault_out = tmp_path / "shorthand_vaults"
    console = Console(record=True)

    # Calling without the explicit `convert` subcommand
    exit_code = run_cli([str(pdf_path), "-o", str(vault_out), "-q"], console=console)
    assert exit_code == 0

    vault_dir = vault_out / "shorthand"
    assert vault_dir.exists()


def test_cli_ai_flags_parsing() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "convert",
            "book.pdf",
            "--ai",
            "--ai-model",
            "llama-3.3-70b",
            "--ai-base-url",
            "http://localhost:11434/v1",
            "--ai-api-key",
            "sk-test-secret",
        ]
    )
    assert args.ai is True
    assert args.ai_model == "llama-3.3-70b"
    assert args.ai_base_url == "http://localhost:11434/v1"
    assert args.ai_api_key == "sk-test-secret"


def test_cli_no_args_in_headless(monkeypatch: pytest.MonkeyPatch) -> None:
    # Simulate headless environment without DISPLAY
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    monkeypatch.setattr("sys.platform", "linux")

    console = Console(record=True)
    exit_code = run_cli([], console=console)
    assert exit_code == 0


def test_cli_scan_empty_directory(tmp_path: Path) -> None:
    console = Console(record=True)
    exit_code = run_cli(["scan", str(tmp_path)], console=console)
    assert exit_code == 0
    output = console.export_text()
    assert "No supported publications" in output


def test_cli_scan_with_publications(tmp_path: Path) -> None:
    _create_sample_pdf(tmp_path / "book1.pdf", title="PDF Book")
    console = Console(record=True)
    exit_code = run_cli(["scan", str(tmp_path)], console=console)
    assert exit_code == 0
    output = console.export_text()
    assert "Discovered Publications (1)" in output
    assert "book1.pdf" in output
    assert "PDF Book" in output
    assert "Total: 1 publication(s)" in output


def test_cli_scan_json_output(tmp_path: Path) -> None:
    import json

    _create_sample_pdf(tmp_path / "book1.pdf", title="PDF Book")
    console = Console(record=True)
    exit_code = run_cli(["scan", str(tmp_path), "--json"], console=console)
    assert exit_code == 0
    output = console.export_text()
    data = json.loads(output)
    assert len(data) == 1
    assert data[0]["filename"] == "book1.pdf"
    assert data[0]["format"] == "pdf"
    assert data[0]["title"] == "PDF Book"


def test_cli_scan_recursive(tmp_path: Path) -> None:
    sub = tmp_path / "nested"
    sub.mkdir()
    _create_sample_pdf(sub / "nested.pdf", title="Nested Book")

    console = Console(record=True)
    # Non-recursive should find 0
    exit_code = run_cli(["scan", str(tmp_path)], console=console)
    assert exit_code == 0
    assert "No supported publications" in console.export_text()

    # Recursive should find 1
    console_rec = Console(record=True)
    exit_code_rec = run_cli(["scan", str(tmp_path), "-r"], console=console_rec)
    assert exit_code_rec == 0
    output_rec = console_rec.export_text()
    assert "nested.pdf" in output_rec
    assert "Nested Book" in output_rec


def test_cli_scan_missing_directory(tmp_path: Path) -> None:
    console = Console(record=True)
    missing = tmp_path / "not_found"
    exit_code = run_cli(["scan", str(missing)], console=console)
    assert exit_code == 1
    output = console.export_text()
    assert "Error:" in output

