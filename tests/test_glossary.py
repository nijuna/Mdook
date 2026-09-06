from __future__ import annotations

from pathlib import Path

import pymupdf

from mdook.core.models import (
    GlossaryBlock,
    Paragraph,
    TextBlock,
)
from mdook.core.rules import glossary as glossary_rules
from mdook.core.rules.footnotes import FootnoteDetectionResult
from mdook.core.stages.extraction import run_extraction
from mdook.core.stages.intake import run_intake
from mdook.core.stages.rendering import render_vault
from mdook.core.stages.semantic import run_semantic


def _dummy_footnote_result() -> FootnoteDetectionResult:
    return FootnoteDetectionResult()


def test_delimiter_entries_parsed_into_glossary_block() -> None:
    blocks = [
        (
            1,
            TextBlock(
                text="API: Application Programming Interface.",
                font_name="helv",
                font_size=10,
                bbox=(54, 72, 300, 84),
                page_number=1,
            ),
        ),
        (
            1,
            TextBlock(
                text="AST — Abstract Syntax Tree.",
                font_name="helv",
                font_size=10,
                bbox=(54, 90, 280, 102),
                page_number=1,
            ),
        ),
        (
            1,
            TextBlock(
                text="CLI – Command Line Interface.",
                font_name="helv",
                font_size=10,
                bbox=(54, 108, 290, 120),
                page_number=1,
            ),
        ),
    ]
    intro, sub_sections = glossary_rules.process_glossary_text_run(
        blocks,
        footnote_result=_dummy_footnote_result(),
        body_font_size=10.0,
        body_left_margin=54.0,
    )
    assert not sub_sections
    assert len(intro) == 1
    assert isinstance(intro[0], GlossaryBlock)
    items = intro[0].items
    assert len(items) == 3
    assert items[0].term == "API"
    assert items[0].definition == "Application Programming Interface."
    assert items[1].term == "AST"
    assert items[1].definition == "Abstract Syntax Tree."
    assert items[2].term == "CLI"
    assert items[2].definition == "Command Line Interface."


def test_bold_term_entries_parsed_into_glossary_block() -> None:
    blocks = [
        # Entry 1: Bold term span + normal definition span on same line
        (
            1,
            TextBlock(
                text="Binary Search",
                font_name="helv-bold",
                font_size=10,
                is_bold=True,
                bbox=(54, 72, 120, 84),
                page_number=1,
            ),
        ),
        (
            1,
            TextBlock(
                text="An efficient search algorithm on sorted arrays.",
                font_name="helv",
                font_size=10,
                is_bold=False,
                bbox=(122, 72, 350, 84),
                page_number=1,
            ),
        ),
        # Entry 2: Bold term on its own line, followed by definition on next line
        (
            1,
            TextBlock(
                text="Breadth-First Search",
                font_name="helv-bold",
                font_size=10,
                is_bold=True,
                bbox=(54, 96, 160, 108),
                page_number=1,
            ),
        ),
        (
            1,
            TextBlock(
                text="A tree traversal algorithm visiting nodes layer by layer.",
                font_name="helv",
                font_size=10,
                is_bold=False,
                bbox=(54, 110, 360, 122),
                page_number=1,
            ),
        ),
    ]
    intro, sub_sections = glossary_rules.process_glossary_text_run(
        blocks,
        footnote_result=_dummy_footnote_result(),
        body_font_size=10.0,
        body_left_margin=54.0,
    )
    assert not sub_sections
    assert len(intro) == 1
    assert isinstance(intro[0], GlossaryBlock)
    items = intro[0].items
    assert len(items) == 2
    assert items[0].term == "Binary Search"
    assert items[0].definition == "An efficient search algorithm on sorted arrays."
    assert items[1].term == "Breadth-First Search"
    assert items[1].definition == "A tree traversal algorithm visiting nodes layer by layer."


def test_hanging_indent_entries_parsed_into_glossary_block() -> None:
    # First line flush at x0=54, subsequent line indented at x0=72
    blocks = [
        (
            1,
            TextBlock(
                text="Cache", font_name="helv", font_size=10, bbox=(54, 72, 90, 84), page_number=1
            ),
        ),
        (
            1,
            TextBlock(
                text="A hardware or software component that stores data.",
                font_name="helv",
                font_size=10,
                bbox=(72, 86, 320, 98),
                page_number=1,
            ),
        ),
        (
            1,
            TextBlock(
                text="Compiler",
                font_name="helv",
                font_size=10,
                bbox=(54, 110, 105, 122),
                page_number=1,
            ),
        ),
        (
            1,
            TextBlock(
                text="A program that translates source code into machine language.",
                font_name="helv",
                font_size=10,
                bbox=(72, 124, 380, 136),
                page_number=1,
            ),
        ),
    ]
    intro, sub_sections = glossary_rules.process_glossary_text_run(
        blocks,
        footnote_result=_dummy_footnote_result(),
        body_font_size=10.0,
        body_left_margin=54.0,
    )
    assert not sub_sections
    assert len(intro) == 1
    assert isinstance(intro[0], GlossaryBlock)
    items = intro[0].items
    assert len(items) == 2
    assert items[0].term == "Cache"
    assert items[0].definition == "A hardware or software component that stores data."
    assert items[1].term == "Compiler"
    assert items[1].definition == "A program that translates source code into machine language."


def test_multiline_definition_rejoins_hyphenation() -> None:
    blocks = [
        (
            1,
            TextBlock(
                text="Daemon: A background process that handles sys-",
                font_name="helv",
                font_size=10,
                bbox=(54, 72, 320, 84),
                page_number=1,
            ),
        ),
        (
            1,
            TextBlock(
                text="tem services without direct user interaction.",
                font_name="helv",
                font_size=10,
                bbox=(54, 86, 300, 98),
                page_number=1,
            ),
        ),
        (
            1,
            TextBlock(
                text="Deadlock: A situation where two processes wait indefinitely.",
                font_name="helv",
                font_size=10,
                bbox=(54, 108, 360, 120),
                page_number=1,
            ),
        ),
    ]
    intro, _ = glossary_rules.process_glossary_text_run(
        blocks,
        footnote_result=_dummy_footnote_result(),
        body_font_size=10.0,
        body_left_margin=54.0,
    )
    items = intro[0].items
    assert items[0].term == "Daemon"
    assert (
        items[0].definition
        == "A background process that handles system services without direct user interaction."
    )


def test_letter_headings_generate_subsections() -> None:
    blocks = [
        # Intro
        (
            1,
            TextBlock(
                text="This glossary defines technical terms used in the text.",
                font_name="helv",
                font_size=10,
                bbox=(54, 50, 350, 62),
                page_number=1,
            ),
        ),
        # Letter A
        (
            1,
            TextBlock(
                text="A",
                font_name="helv-bold",
                font_size=14,
                is_bold=True,
                bbox=(54, 70, 70, 84),
                page_number=1,
            ),
        ),
        (
            1,
            TextBlock(
                text="API: Application Programming Interface.",
                font_name="helv",
                font_size=10,
                bbox=(54, 90, 300, 102),
                page_number=1,
            ),
        ),
        # Letter B
        (
            1,
            TextBlock(
                text="— B —",
                font_name="helv-bold",
                font_size=14,
                is_bold=True,
                bbox=(54, 120, 90, 134),
                page_number=1,
            ),
        ),
        (
            1,
            TextBlock(
                text="Byte: A sequence of eight adjacent binary digits.",
                font_name="helv",
                font_size=10,
                bbox=(54, 140, 320, 152),
                page_number=1,
            ),
        ),
    ]
    intro, sub_sections = glossary_rules.process_glossary_text_run(
        blocks,
        footnote_result=_dummy_footnote_result(),
        body_font_size=10.0,
        body_left_margin=54.0,
    )
    # Intro content has the leading paragraph
    assert len(intro) == 1
    assert isinstance(intro[0], Paragraph)
    assert "defines technical terms" in intro[0].text

    # Two letter sub-sections
    assert len(sub_sections) == 2
    assert sub_sections[0].title == "A"
    assert sub_sections[0].level == 2
    assert isinstance(sub_sections[0].content[0], GlossaryBlock)
    assert sub_sections[0].content[0].items[0].term == "API"

    assert sub_sections[1].title == "B"
    assert sub_sections[1].level == 2
    assert isinstance(sub_sections[1].content[0], GlossaryBlock)
    assert sub_sections[1].content[0].items[0].term == "Byte"


def test_graceful_fallback_when_not_a_structured_glossary() -> None:
    # A narrative essay that does not follow glossary entry patterns
    blocks = [
        (
            1,
            TextBlock(
                text="The following thoughts reflect on terminology.",
                font_name="helv",
                font_size=10,
                bbox=(54, 72, 320, 84),
                page_number=1,
            ),
        ),
        (
            1,
            TextBlock(
                text="Language evolves through historical usage and culture.",
                font_name="helv",
                font_size=10,
                bbox=(54, 88, 340, 100),
                page_number=1,
            ),
        ),
        (
            1,
            TextBlock(
                text="Words carry nuanced connotations across different eras.",
                font_name="helv",
                font_size=10,
                bbox=(54, 104, 350, 116),
                page_number=1,
            ),
        ),
    ]
    intro, sub_sections = glossary_rules.process_glossary_text_run(
        blocks,
        footnote_result=_dummy_footnote_result(),
        body_font_size=10.0,
        body_left_margin=54.0,
    )
    assert not sub_sections
    # Degraded cleanly to standard Paragraph items
    assert all(isinstance(c, Paragraph) for c in intro)
    assert any("Language evolves" in c.text for c in intro if isinstance(c, Paragraph))


def test_end_to_end_glossary_pdf_rendering(tmp_path: Path) -> None:
    pdf_path = tmp_path / "book_with_glossary.pdf"
    doc = pymupdf.open()

    # 16 body pages so that back matter falls safely in the last 20% zone
    for i in range(16):
        page = doc.new_page(width=400, height=600)
        page.insert_text((72, 60), f"Chapter {i + 1}", fontsize=18, fontname="helv")
        page.insert_text(
            (72, 100), f"Body paragraph for chapter {i + 1}.", fontsize=11, fontname="helv"
        )

    # Back matter Glossary page
    p_gloss = doc.new_page(width=400, height=600)
    p_gloss.insert_text((72, 50), "Glossary", fontsize=18, fontname="helv")
    p_gloss.insert_text(
        (72, 80), "Essential concepts and definitions.", fontsize=11, fontname="helv"
    )

    # Letter A
    p_gloss.insert_text((72, 110), "A", fontsize=14, fontname="helv")
    p_gloss.insert_text(
        (72, 135), "API: Application Programming Interface.", fontsize=11, fontname="helv"
    )
    p_gloss.insert_text(
        (72, 155), "AST: Abstract Syntax Tree representation.", fontsize=11, fontname="helv"
    )

    # Letter B
    p_gloss.insert_text((72, 185), "B", fontsize=14, fontname="helv")
    p_gloss.insert_text(
        (72, 210), "Bit: The basic unit of information in computing.", fontsize=11, fontname="helv"
    )
    p_gloss.insert_text(
        (72, 230), "Byte: Eight bits treated as a single unit.", fontsize=11, fontname="helv"
    )

    doc.save(str(pdf_path))
    doc.close()

    manifest = run_intake(pdf_path)
    pages = run_extraction(manifest)
    tree = run_semantic(manifest, pages)
    result = render_vault(tree, manifest, tmp_path / "vault")

    glossary_file = result.vault_dir / "Glossary.md"
    assert glossary_file.exists()

    content = glossary_file.read_text(encoding="utf-8")
    assert content.startswith("# Glossary")
    assert "Essential concepts and definitions." in content
    assert "## A" in content
    assert "**API** — Application Programming Interface." in content
    assert "**AST** — Abstract Syntax Tree representation." in content
    assert "## B" in content
    assert "**Bit** — The basic unit of information in computing." in content
    assert "**Byte** — Eight bits treated as a single unit." in content
