from __future__ import annotations

from pathlib import Path

import pymupdf
import pytest
from rich.console import Console

from mdook import __version__
from mdook.cli import build_parser, run_cli


def _create_sample_pdf(path: Path, title: str = "CLI Test Book") -> Path:
    doc = pymupdf.open()
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
    assert "Convert PDF books into structured, readable Obsidian vaults." in help_text
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
    args = parser.parse_args([
        "convert",
        "book.pdf",
        "--ai",
        "--ai-model",
        "llama-3.3-70b",
        "--ai-base-url",
        "http://localhost:11434/v1",
        "--ai-api-key",
        "sk-test-secret",
    ])
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
