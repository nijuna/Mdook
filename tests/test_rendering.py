from pathlib import Path

from mdook.core.stages.extraction import run_extraction
from mdook.core.stages.intake import run_intake
from mdook.core.stages.rendering import render_vault
from mdook.core.stages.semantic import run_semantic


def test_index_file_has_frontmatter_and_chapter_links(bookmarked_pdf: Path, tmp_path: Path) -> None:
    manifest = run_intake(bookmarked_pdf)
    pages = run_extraction(manifest)
    tree = run_semantic(manifest, pages)
    result = render_vault(tree, manifest, tmp_path / "vault")

    text = result.index_path.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    assert "profile: literature" in text
    assert "[[01 - Chapter 1|Chapter 1]]" in text
    assert "[[03 - Chapter 3|Chapter 3]]" in text


def test_index_groups_chapters_under_their_part_heading(tmp_path: Path) -> None:
    import pymupdf

    pdf_path = tmp_path / "parted.pdf"
    doc = pymupdf.open()
    for title, size, lines in [
        ("PART ONE: THE BEGINNING", 32, 0),
        ("CHAPTER ONE STORY", 24, 4),
        ("PART TWO: THE END", 32, 0),
        ("CHAPTER TWO STORY", 24, 4),
    ]:
        page = doc.new_page(width=700, height=600)
        y = 100.0
        page.insert_text((72, y), title, fontsize=size, fontname="helv")
        y += 40
        for line in range(lines):
            page.insert_text((72, y), f"Body text line {line}.", fontsize=11, fontname="helv")
            y += 20
    doc.save(str(pdf_path))
    doc.close()

    manifest = run_intake(pdf_path)
    pages = run_extraction(manifest)
    tree = run_semantic(manifest, pages)
    result = render_vault(tree, manifest, tmp_path / "vault")

    text = result.index_path.read_text(encoding="utf-8")
    assert "## PART ONE: THE BEGINNING" in text
    assert "## PART TWO: THE END" in text
    part_one_pos = text.index("## PART ONE: THE BEGINNING")
    chapter_one_pos = text.index("CHAPTER ONE STORY")
    part_two_pos = text.index("## PART TWO: THE END")
    assert part_one_pos < chapter_one_pos < part_two_pos


def test_chapter_file_has_heading_and_page_markers(bookmarked_pdf: Path, tmp_path: Path) -> None:
    manifest = run_intake(bookmarked_pdf)
    pages = run_extraction(manifest)
    tree = run_semantic(manifest, pages)
    result = render_vault(tree, manifest, tmp_path / "vault")

    text = result.chapter_paths[0].read_text(encoding="utf-8")
    assert text.startswith("# Chapter 1\n")
    assert "> [!quote]- p. 1 · " in text
    assert "> [!quote]- p. 2 · " in text  # chapter spans both of its 2 pages


def test_footnote_renders_as_obsidian_syntax(tmp_path: Path) -> None:
    import pymupdf

    pdf_path = tmp_path / "footnote_book.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=400, height=600)
    for i in range(8):
        page.insert_text(
            (72, 100 + i * 16),
            f"Body sentence number {i} with enough length.",
            fontsize=11,
            fontname="helv",
        )
    page.insert_text((72, 560), "1. This is a footnote definition.", fontsize=8, fontname="helv")
    doc.save(str(pdf_path))
    doc.close()

    manifest = run_intake(pdf_path)
    pages = run_extraction(manifest)
    tree = run_semantic(manifest, pages)
    result = render_vault(tree, manifest, tmp_path / "vault")

    text = result.chapter_paths[0].read_text(encoding="utf-8")
    assert "[^1]: This is a footnote definition." in text


def test_image_is_copied_to_attachments_and_referenced(tmp_path: Path) -> None:
    import pymupdf

    pdf_path = tmp_path / "image_book.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=400, height=600)
    page.insert_text((72, 100), "Text before the figure.", fontsize=11, fontname="helv")
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 50, 50))
    pix.set_rect(pix.irect, (200, 30, 30))
    page.insert_image(pymupdf.Rect(72, 160, 172, 260), stream=pix.tobytes("png"))
    doc.save(str(pdf_path))
    doc.close()

    manifest = run_intake(pdf_path)
    pages = run_extraction(manifest)
    tree = run_semantic(manifest, pages)
    result = render_vault(tree, manifest, tmp_path / "vault")

    text = result.chapter_paths[0].read_text(encoding="utf-8")
    assert "![[fig-1-1.png]]" in text
    assert (result.attachments_dir / "fig-1-1.png").exists()


def test_numbered_sub_section_renders_as_nested_heading(tmp_path: Path) -> None:
    import pymupdf

    pdf_path = tmp_path / "numbered_render.pdf"
    doc = pymupdf.open()
    page1 = doc.new_page(width=400, height=600)
    page1.insert_text((72, 60), "Chapter One", fontsize=24, fontname="helv")
    page1.insert_text((72, 100), "1.1 Getting Started", fontsize=11, fontname="helv")
    for i in range(4):
        page1.insert_text(
            (72, 130 + i * 16), f"Section body sentence {i}.", fontsize=11, fontname="helv"
        )
    page2 = doc.new_page(width=400, height=600)
    page2.insert_text((72, 60), "Chapter Two", fontsize=24, fontname="helv")
    for i in range(6):
        page2.insert_text(
            (72, 100 + i * 16), f"Chapter two body sentence {i}.", fontsize=11, fontname="helv"
        )
    doc.save(str(pdf_path))
    doc.close()

    manifest = run_intake(pdf_path, profile_override="technical")
    pages = run_extraction(manifest)
    tree = run_semantic(manifest, pages)
    result = render_vault(tree, manifest, tmp_path / "vault")

    text = result.chapter_paths[0].read_text(encoding="utf-8")
    assert text.startswith("# Chapter One\n")
    assert "## 1.1 Getting Started" in text


def test_list_renders_as_markdown_list(tmp_path: Path) -> None:
    import pymupdf

    pdf_path = tmp_path / "list_render.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=400, height=600)
    page.insert_text((72, 60), "Chapter One", fontsize=24, fontname="helv")
    page.insert_text((72, 100), "- First item", fontsize=11, fontname="helv")
    page.insert_text((72, 120), "- Second item", fontsize=11, fontname="helv")
    page.insert_text((72, 140), "1. A numbered item", fontsize=11, fontname="helv")
    doc.save(str(pdf_path))
    doc.close()

    manifest = run_intake(pdf_path)
    pages = run_extraction(manifest)
    tree = run_semantic(manifest, pages)
    result = render_vault(tree, manifest, tmp_path / "vault")

    text = result.chapter_paths[0].read_text(encoding="utf-8")
    assert "- First item" in text
    assert "- Second item" in text
    assert "1. A numbered item" in text


def test_general_block_quote_renders_without_italics(tmp_path: Path) -> None:
    import pymupdf

    pdf_path = tmp_path / "quote_render.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=400, height=600)
    page.insert_text((72, 60), "Chapter One", fontsize=24, fontname="helv")
    for i in range(4):
        page.insert_text(
            (72, 100 + i * 16), f"Ordinary body sentence number {i}.", fontsize=11, fontname="helv"
        )
    page.insert_text(
        (110, 180), "An indented quotation set apart from the body.", fontsize=11, fontname="helv"
    )
    doc.save(str(pdf_path))
    doc.close()

    manifest = run_intake(pdf_path)
    pages = run_extraction(manifest)
    tree = run_semantic(manifest, pages)
    result = render_vault(tree, manifest, tmp_path / "vault")

    text = result.chapter_paths[0].read_text(encoding="utf-8")
    assert "> An indented quotation set apart from the body." in text
    assert "> *An indented quotation" not in text


def test_table_renders_as_markdown_pipe_table(tmp_path: Path) -> None:
    import pymupdf

    from tests.conftest import add_grid_table

    pdf_path = tmp_path / "table_render.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=400, height=300)
    page.insert_text((72, 30), "Chapter One", fontsize=18, fontname="helv")
    add_grid_table(page, (50, 60, 350, 150), [["Name", "Age"], ["Alice", "30"]])
    doc.save(str(pdf_path))
    doc.close()

    manifest = run_intake(pdf_path)
    pages = run_extraction(manifest)
    tree = run_semantic(manifest, pages)
    result = render_vault(tree, manifest, tmp_path / "vault")

    text = result.chapter_paths[0].read_text(encoding="utf-8")
    assert "| Name | Age |" in text
    assert "|---|---|" in text
    assert "| Alice | 30 |" in text


def test_code_block_renders_as_fenced_code(tmp_path: Path) -> None:
    import pymupdf

    pdf_path = tmp_path / "code_render.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=400, height=300)
    page.insert_text((72, 40), "Chapter One", fontsize=18, fontname="helv")
    page.insert_text((72, 100), "def foo():", fontsize=10, fontname="cour")
    page.insert_text((72, 115), "    return 1", fontsize=10, fontname="cour")
    doc.save(str(pdf_path))
    doc.close()

    manifest = run_intake(pdf_path)
    pages = run_extraction(manifest)
    tree = run_semantic(manifest, pages)
    result = render_vault(tree, manifest, tmp_path / "vault")

    text = result.chapter_paths[0].read_text(encoding="utf-8")
    assert "```\ndef foo():\n    return 1\n```" in text


def test_callout_renders_as_obsidian_callout(tmp_path: Path) -> None:
    import pymupdf

    pdf_path = tmp_path / "callout_render.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=400, height=300)
    page.insert_text((72, 40), "Chapter One", fontsize=18, fontname="helv")
    page.insert_text(
        (72, 150), "Warning: this step cannot be undone.", fontsize=11, fontname="helv"
    )
    doc.save(str(pdf_path))
    doc.close()

    manifest = run_intake(pdf_path)
    pages = run_extraction(manifest)
    tree = run_semantic(manifest, pages)
    result = render_vault(tree, manifest, tmp_path / "vault")

    text = result.chapter_paths[0].read_text(encoding="utf-8")
    assert "> [!warning] Warning" in text
    assert "> this step cannot be undone." in text


def test_endnote_reference_links_to_back_matter_notes_section(tmp_path: Path) -> None:
    import pymupdf

    pdf_path = tmp_path / "endnote_book.pdf"
    doc = pymupdf.open()

    page1 = doc.new_page(width=400, height=300)
    page1.insert_text((72, 40), "Chapter One", fontsize=18, fontname="helv")
    note_text = "A claim needing a note"
    note_width = pymupdf.get_text_length(note_text, fontname="helv", fontsize=11)
    marker_x = 72 + note_width
    marker_width = pymupdf.get_text_length("1", fontname="helv", fontsize=7)
    page1.insert_text((72, 80), note_text, fontsize=11, fontname="helv")
    page1.insert_text((marker_x, 80), "1", fontsize=7, fontname="helv")
    page1.insert_text((marker_x + marker_width, 80), " follows here.", fontsize=11, fontname="helv")
    for i in range(4):
        page1.insert_text(
            (72, 110 + i * 16), f"More body text {i}.", fontsize=11, fontname="helv"
        )

    page2 = doc.new_page(width=400, height=300)
    page2.insert_text((72, 40), "Chapter Two", fontsize=18, fontname="helv")
    for i in range(6):
        page2.insert_text(
            (72, 80 + i * 16), f"Chapter two body {i}.", fontsize=11, fontname="helv"
        )

    back = doc.new_page(width=400, height=300)
    back.insert_text((72, 40), "Notes", fontsize=14, fontname="helv")
    back.insert_text((72, 70), "1. The full citation for this claim.", fontsize=11, fontname="helv")

    doc.save(str(pdf_path))
    doc.close()

    manifest = run_intake(pdf_path)
    pages = run_extraction(manifest)
    tree = run_semantic(manifest, pages)
    result = render_vault(tree, manifest, tmp_path / "vault")

    chapter_text = result.chapter_paths[0].read_text(encoding="utf-8")
    assert "[[99 - Back Matter#^note-1|1]]" in chapter_text

    back_matter_text = (result.vault_dir / "99 - Back Matter.md").read_text(encoding="utf-8")
    assert "^note-1" in back_matter_text
    assert "The full citation for this claim." in back_matter_text


def test_numeric_citation_links_to_back_matter_bibliography_entry(tmp_path: Path) -> None:
    import pymupdf

    pdf_path = tmp_path / "citation_book.pdf"
    doc = pymupdf.open()

    page1 = doc.new_page(width=400, height=300)
    page1.insert_text((72, 40), "Chapter One", fontsize=18, fontname="helv")
    page1.insert_text(
        (72, 90), "As shown by prior work [1], this holds.", fontsize=11, fontname="helv"
    )

    back = doc.new_page(width=400, height=300)
    back.insert_text((72, 40), "Bibliography", fontsize=14, fontname="helv")
    back.insert_text(
        (72, 70), "1. Smith, J. (2020). A Study of Things.", fontsize=11, fontname="helv"
    )

    doc.save(str(pdf_path))
    doc.close()

    manifest = run_intake(pdf_path)
    pages = run_extraction(manifest)
    tree = run_semantic(manifest, pages)
    result = render_vault(tree, manifest, tmp_path / "vault")

    chapter_text = result.chapter_paths[0].read_text(encoding="utf-8")
    assert "[[99 - Back Matter#^ref-1|1]]" in chapter_text

    back_matter_text = (result.vault_dir / "99 - Back Matter.md").read_text(encoding="utf-8")
    assert "^ref-1" in back_matter_text
    assert "Smith, J. (2020). A Study of Things." in back_matter_text


def test_front_and_back_matter_are_rendered_as_files(tmp_path: Path) -> None:
    import pymupdf

    pdf_path = tmp_path / "matter_book.pdf"
    doc = pymupdf.open()

    cover = doc.new_page(width=400, height=600)
    cover.insert_text((72, 100), "Copyright 2020 Some Publisher", fontsize=10, fontname="helv")
    cover.insert_text((72, 130), "Preface", fontsize=14, fontname="helv")
    for i in range(4):
        cover.insert_text(
            (72, 160 + i * 16), f"Preface body sentence {i}.", fontsize=11, fontname="helv"
        )

    for chapter_index, name in enumerate(("One", "Two"), start=1):
        for page_in_chapter in range(2):
            page = doc.new_page(width=400, height=600)
            if page_in_chapter == 0:
                page.insert_text((72, 60), f"Chapter {name}", fontsize=24, fontname="helv")
            for i in range(6):
                page.insert_text(
                    (72, 100 + i * 16),
                    f"Chapter {chapter_index} body sentence {i}.",
                    fontsize=11,
                    fontname="helv",
                )

    back = doc.new_page(width=400, height=600)
    back.insert_text((72, 60), "Glossary", fontsize=14, fontname="helv")
    for i in range(4):
        back.insert_text(
            (72, 90 + i * 16), f"Term {i}: a definition.", fontsize=11, fontname="helv"
        )

    doc.save(str(pdf_path))
    doc.close()

    manifest = run_intake(pdf_path)
    pages = run_extraction(manifest)
    tree = run_semantic(manifest, pages)
    result = render_vault(tree, manifest, tmp_path / "vault")

    front_matter_path = result.vault_dir / "00 - Front Matter.md"
    back_matter_path = result.vault_dir / "99 - Back Matter.md"
    assert front_matter_path.exists()
    assert back_matter_path.exists()
    assert "## Preface" in front_matter_path.read_text(encoding="utf-8")
    assert "## Glossary" in back_matter_path.read_text(encoding="utf-8")

    index_text = result.index_path.read_text(encoding="utf-8")
    assert "[[00 - Front Matter|Front Matter]]" in index_text
    assert "[[99 - Back Matter|Back Matter]]" in index_text


def test_epigraph_renders_as_blockquote(tmp_path: Path) -> None:
    import pymupdf

    pdf_path = tmp_path / "epigraph_book.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=400, height=600)
    page.insert_text(
        (72, 100), "Once upon a time in a land far away.", fontsize=11, fontname="heit"
    )
    page.insert_text((72, 120), "-- Old Proverb", fontsize=11, fontname="heit")
    for i in range(8):
        page.insert_text(
            (72, 150 + i * 16), f"Body filler sentence number {i}.", fontsize=11, fontname="helv"
        )
    doc.save(str(pdf_path))
    doc.close()

    manifest = run_intake(pdf_path)
    pages = run_extraction(manifest)
    tree = run_semantic(manifest, pages)
    result = render_vault(tree, manifest, tmp_path / "vault")

    text = result.chapter_paths[0].read_text(encoding="utf-8")
    assert "> *Once upon a time in a land far away.*" in text
    assert "> — Old Proverb" in text


def test_display_equation_renders_with_mathjax_delimiters(tmp_path: Path) -> None:
    import pymupdf

    pdf_path = tmp_path / "equation_render.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=400, height=300)
    page.insert_text((72, 40), "Chapter One", fontsize=18, fontname="helv")
    page.insert_text(
        (72, 90), "The following identity holds for all real numbers.", fontsize=11, fontname="helv"
    )
    page.insert_text((72, 150), "E = mc² (3.14)", fontsize=11, fontname="helv")
    page.insert_text((72, 210), "This concludes the derivation.", fontsize=11, fontname="helv")
    doc.save(str(pdf_path))
    doc.close()

    manifest = run_intake(pdf_path)
    pages = run_extraction(manifest)
    tree = run_semantic(manifest, pages)
    result = render_vault(tree, manifest, tmp_path / "vault")

    text = result.chapter_paths[0].read_text(encoding="utf-8")
    assert "$$\nE = mc²\n$$\n(3.14)" in text


def test_theorem_renders_as_labeled_callout(tmp_path: Path) -> None:
    import pymupdf

    pdf_path = tmp_path / "theorem_render.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=400, height=300)
    page.insert_text((72, 40), "Chapter One", fontsize=18, fontname="helv")
    page.insert_text(
        (72, 90), "Theorem 3.2. For all x, x equals x.", fontsize=11, fontname="helv"
    )
    doc.save(str(pdf_path))
    doc.close()

    manifest = run_intake(pdf_path)
    pages = run_extraction(manifest)
    tree = run_semantic(manifest, pages)
    result = render_vault(tree, manifest, tmp_path / "vault")

    text = result.chapter_paths[0].read_text(encoding="utf-8")
    assert "> [!theorem] Theorem 3.2" in text
    assert "> For all x, x equals x." in text
