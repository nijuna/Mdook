"""Unit tests for the interactive terminal wizard."""

from pathlib import Path

import pymupdf
import pytest
from rich.console import Console

from mdook.cli_wizard import WizardConfig, interactive_wizard, parse_selection
from mdook.core.scanner import DiscoveredBook


def _create_sample_pdf(path: Path) -> Path:
    doc = pymupdf.open()
    page = doc.new_page(width=400, height=600)
    page.insert_text((72, 60), "Chapter 1", fontsize=20, fontname="helv")
    doc.save(str(path))
    doc.close()
    return path


def test_parse_selection_single_index(tmp_path: Path) -> None:
    p1 = tmp_path / "book1.pdf"
    p2 = tmp_path / "book2.epub"
    books = [
        DiscoveredBook(path=p1, format="pdf", size_bytes=100, title="Book 1", author="Author 1"),
        DiscoveredBook(path=p2, format="epub", size_bytes=200, title="Book 2", author="Author 2"),
    ]
    res = parse_selection("1", books)
    assert res == [p1]

    res2 = parse_selection("2", books)
    assert res2 == [p2]


def test_parse_selection_multiple_indices(tmp_path: Path) -> None:
    p1 = tmp_path / "book1.pdf"
    p2 = tmp_path / "book2.epub"
    p3 = tmp_path / "book3.docx"
    books = [
        DiscoveredBook(path=p1, format="pdf", size_bytes=100, title="Book 1", author="Author 1"),
        DiscoveredBook(path=p2, format="epub", size_bytes=200, title="Book 2", author="Author 2"),
        DiscoveredBook(path=p3, format="docx", size_bytes=300, title="Book 3", author="Author 3"),
    ]
    res = parse_selection("1, 3", books)
    assert res == [p1, p3]


def test_parse_selection_range(tmp_path: Path) -> None:
    p1 = tmp_path / "book1.pdf"
    p2 = tmp_path / "book2.epub"
    p3 = tmp_path / "book3.docx"
    books = [
        DiscoveredBook(path=p1, format="pdf", size_bytes=100, title="Book 1", author="Author 1"),
        DiscoveredBook(path=p2, format="epub", size_bytes=200, title="Book 2", author="Author 2"),
        DiscoveredBook(path=p3, format="docx", size_bytes=300, title="Book 3", author="Author 3"),
    ]
    res = parse_selection("1-3", books)
    assert res == [p1, p2, p3]


def test_parse_selection_all(tmp_path: Path) -> None:
    p1 = tmp_path / "book1.pdf"
    p2 = tmp_path / "book2.epub"
    books = [
        DiscoveredBook(path=p1, format="pdf", size_bytes=100, title="Book 1", author="Author 1"),
        DiscoveredBook(path=p2, format="epub", size_bytes=200, title="Book 2", author="Author 2"),
    ]
    res = parse_selection("all", books)
    assert res == [p1, p2]

    res_star = parse_selection("*", books)
    assert res_star == [p1, p2]


def test_parse_selection_direct_path(tmp_path: Path) -> None:
    pdf = _create_sample_pdf(tmp_path / "manual.pdf")
    res = parse_selection(str(pdf), [])
    assert res == [pdf.resolve()]


def test_parse_selection_errors(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="empty"):
        parse_selection("", [])

    with pytest.raises(ValueError, match="out of range"):
        p1 = tmp_path / "book1.pdf"
        books = [
            DiscoveredBook(
                path=p1, format="pdf", size_bytes=100, title="Book 1", author="Author 1"
            )
        ]
        parse_selection("5", books)

    with pytest.raises(ValueError, match="Unrecognized selection"):
        parse_selection("not_a_number_or_path", [])


def test_interactive_wizard_flow_defaults(tmp_path: Path) -> None:
    pdf1 = _create_sample_pdf(tmp_path / "book1.pdf")
    console = Console(record=True)

    inputs = [
        "1",           # Step 1: select book 1
        "1",           # Step 2: mode (modular library)
        "1",           # Step 3: profile (auto)
        str(tmp_path / "out"),  # Step 4: dest dir
        "n",           # Step 5: no AI
        "y",           # Step 6: confirm
    ]
    input_idx = 0

    def mock_input(prompt: str) -> str:
        nonlocal input_idx
        val = inputs[input_idx]
        input_idx += 1
        return val

    cfg = interactive_wizard(console=console, start_dir=tmp_path, input_fn=mock_input)
    assert cfg is not None
    assert isinstance(cfg, WizardConfig)
    assert cfg.books == [pdf1.resolve()]
    assert cfg.output_dir == (tmp_path / "out").resolve()
    assert cfg.profile == "auto"
    assert cfg.single_file is False
    assert cfg.ai_enabled is False


def test_interactive_wizard_flow_single_file_custom(tmp_path: Path) -> None:
    pdf1 = _create_sample_pdf(tmp_path / "doc.pdf")
    console = Console(record=True)

    inputs = [
        "1",           # Step 1: select book 1
        "2",           # Step 2: single document mode
        "2",           # Step 3: literature profile
        str(tmp_path / "custom_lib"),  # Step 4: dest dir
        "n",           # Step 5: no AI
        "y",           # Step 6: confirm
    ]
    input_idx = 0

    def mock_input(prompt: str) -> str:
        nonlocal input_idx
        val = inputs[input_idx]
        input_idx += 1
        return val

    cfg = interactive_wizard(console=console, start_dir=tmp_path, input_fn=mock_input)
    assert cfg is not None
    assert cfg.books == [pdf1.resolve()]
    assert cfg.single_file is True
    assert cfg.profile == "literature"
    assert cfg.output_dir == (tmp_path / "custom_lib").resolve()


def test_interactive_wizard_flow_ai_ollama(tmp_path: Path) -> None:
    pdf1 = _create_sample_pdf(tmp_path / "tech.pdf")
    console = Console(record=True)

    inputs = [
        "1",           # Step 1: select book 1
        "1",           # Step 2: modular library
        "3",           # Step 3: technical profile
        str(tmp_path / "out"),  # Step 4: dest dir
        "y",           # Step 5: enable AI
        "1",           # Step 5a: Ollama provider
        "llama3.2",    # Step 5b: model name
        "y",           # Step 6: confirm
    ]
    input_idx = 0

    def mock_input(prompt: str) -> str:
        nonlocal input_idx
        val = inputs[input_idx]
        input_idx += 1
        return val

    cfg = interactive_wizard(console=console, start_dir=tmp_path, input_fn=mock_input)
    assert cfg is not None
    assert cfg.books == [pdf1.resolve()]
    assert cfg.ai_enabled is True
    assert cfg.ai_base_url == "http://localhost:11434/v1"
    assert cfg.ai_model == "llama3.2"
    assert cfg.profile == "technical"


def test_interactive_wizard_cancelled(tmp_path: Path) -> None:
    _create_sample_pdf(tmp_path / "book.pdf")
    console = Console(record=True)

    inputs = [
        "1",           # Step 1: select book 1
        "1",           # Step 2: modular
        "1",           # Step 3: auto
        str(tmp_path / "out"),  # Step 4: dest
        "n",           # Step 5: no AI
        "n",           # Step 6: CANCEL
    ]
    input_idx = 0

    def mock_input(prompt: str) -> str:
        nonlocal input_idx
        val = inputs[input_idx]
        input_idx += 1
        return val

    cfg = interactive_wizard(console=console, start_dir=tmp_path, input_fn=mock_input)
    assert cfg is None
    output = console.export_text()
    assert "Conversion cancelled" in output


def test_interactive_wizard_no_books_prompt_path(tmp_path: Path) -> None:
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    pdf = _create_sample_pdf(tmp_path / "outside.pdf")
    console = Console(record=True)

    inputs = [
        str(pdf),      # Step 1: manual path entered
        "1",           # Step 2: modular
        "1",           # Step 3: auto
        str(tmp_path / "out"),  # Step 4: dest
        "n",           # Step 5: no AI
        "y",           # Step 6: confirm
    ]
    input_idx = 0

    def mock_input(prompt: str) -> str:
        nonlocal input_idx
        val = inputs[input_idx]
        input_idx += 1
        return val

    cfg = interactive_wizard(console=console, start_dir=empty_dir, input_fn=mock_input)
    assert cfg is not None
    assert cfg.books == [pdf.resolve()]
