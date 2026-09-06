from pathlib import Path

from mdook.core.models import Paragraph
from mdook.core.stages.extraction import run_extraction
from mdook.core.stages.intake import run_intake
from mdook.core.stages.semantic import run_semantic


def test_bookmark_path_segments_chapters(bookmarked_pdf: Path) -> None:
    manifest = run_intake(bookmarked_pdf)
    pages = run_extraction(manifest)
    tree = run_semantic(manifest, pages)

    assert [c.title for c in tree.chapters] == ["Chapter 1", "Chapter 2", "Chapter 3"]
    assert tree.chapters[0].page_spans == [(1, 2)]
    assert tree.chapters[-1].page_spans == [(5, 6)]


def test_font_clustering_path_segments_chapters(unbookmarked_pdf: Path) -> None:
    manifest = run_intake(unbookmarked_pdf)
    pages = run_extraction(manifest)
    tree = run_semantic(manifest, pages)

    assert [c.title for c in tree.chapters] == ["THE 1 STORY", "THE 2 STORY"]


def test_heading_block_is_not_duplicated_as_a_paragraph(bookmarked_pdf: Path) -> None:
    manifest = run_intake(bookmarked_pdf)
    pages = run_extraction(manifest)
    tree = run_semantic(manifest, pages)

    chapter_one = tree.chapters[0]
    paragraphs = [c for c in chapter_one.sections[0].content if isinstance(c, Paragraph)]
    assert all(p.text.strip() != "Chapter 1" for p in paragraphs)
    assert len(paragraphs) > 0


def test_no_headings_falls_back_to_single_chapter(tmp_path: Path) -> None:
    import pymupdf

    pdf_path = tmp_path / "flat.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=400, height=600)
    page.insert_text(
        (72, 100), "Just a plain paragraph with no heading at all.", fontsize=11, fontname="helv"
    )
    doc.save(str(pdf_path))
    doc.close()

    manifest = run_intake(pdf_path)
    pages = run_extraction(manifest)
    tree = run_semantic(manifest, pages)

    assert len(tree.chapters) == 1
    assert tree.chapters[0].title == "Untitled"


def test_same_page_heading_collision_keeps_longer_title(tmp_path: Path) -> None:
    """Regression: a decorative badge/icon (e.g. an emoji) and the real
    title both scoring as H1 candidates on the same physical page used to
    give the earlier one an inverted, empty page range -- silently
    producing a chapter file with nothing but its own heading in it."""
    import pymupdf

    pdf_path = tmp_path / "collision.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=400, height=600)
    page.insert_text((72, 50), "X", fontsize=24, fontname="helv")  # decorative badge
    page.insert_text((72, 90), "Real Chapter Title", fontsize=24, fontname="helv")
    for i in range(8):
        page.insert_text(
            (72, 130 + i * 16), f"Body filler sentence number {i}.", fontsize=11, fontname="helv"
        )
    doc.save(str(pdf_path))
    doc.close()

    manifest = run_intake(pdf_path)
    pages = run_extraction(manifest)
    tree = run_semantic(manifest, pages)

    assert len(tree.chapters) == 1
    assert tree.chapters[0].title == "Real Chapter Title"
    paragraphs = [c for c in tree.chapters[0].sections[0].content if isinstance(c, Paragraph)]
    assert len(paragraphs) > 0


def test_epigraph_and_drop_cap_are_handled(tmp_path: Path) -> None:
    import pymupdf

    from mdook.core.models import BlockQuote

    pdf_path = tmp_path / "epigraph.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=400, height=600)
    page.insert_text(
        (72, 100), "Once upon a time in a land far away.", fontsize=11, fontname="heit"
    )
    page.insert_text((72, 120), "-- Old Proverb", fontsize=11, fontname="heit")
    page.insert_text((72, 150), "T", fontsize=24, fontname="helv")  # drop cap
    page.insert_text((85, 158), "he story begins on a quiet morning.", fontsize=11, fontname="helv")
    for i in range(8):
        page.insert_text(
            (72, 175 + i * 16),
            f"Body filler sentence number {i} for weighting.",
            fontsize=11,
            fontname="helv",
        )
    doc.save(str(pdf_path))
    doc.close()

    manifest = run_intake(pdf_path)
    pages = run_extraction(manifest)
    tree = run_semantic(manifest, pages)

    content = tree.chapters[0].sections[0].content
    assert isinstance(content[0], BlockQuote)
    assert content[0].lines == ["Once upon a time in a land far away."]
    assert content[0].attribution == "Old Proverb"

    paragraphs = [c for c in content if isinstance(c, Paragraph)]
    assert paragraphs[0].text.startswith("The story begins on a quiet morning.")


def test_decorative_divider_is_dropped(tmp_path: Path) -> None:
    import pymupdf

    pdf_path = tmp_path / "decorative.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=400, height=600)
    page.insert_text((190, 100), "***", fontsize=11, fontname="helv")
    for i in range(8):
        page.insert_text(
            (72, 130 + i * 16),
            f"More body filler sentence number {i}.",
            fontsize=11,
            fontname="helv",
        )
    doc.save(str(pdf_path))
    doc.close()

    manifest = run_intake(pdf_path)
    pages = run_extraction(manifest)
    tree = run_semantic(manifest, pages)

    all_text = " ".join(
        p.text for p in tree.chapters[0].sections[0].content if isinstance(p, Paragraph)
    )
    assert "***" not in all_text


def test_printed_toc_page_is_discarded(tmp_path: Path) -> None:
    import pymupdf

    pdf_path = tmp_path / "toc.pdf"
    doc = pymupdf.open()
    toc_page = doc.new_page(width=400, height=600)
    toc_page.insert_text((72, 100), "Chapter One .......... 1", fontsize=11, fontname="helv")
    toc_page.insert_text((72, 120), "Chapter Two .......... 15", fontsize=11, fontname="helv")
    toc_page.insert_text((72, 140), "Chapter Three ........ 30", fontsize=11, fontname="helv")
    body_page = doc.new_page(width=400, height=600)
    for i in range(8):
        body_page.insert_text(
            (72, 100 + i * 16), f"Real body sentence number {i}.", fontsize=11, fontname="helv"
        )
    doc.save(str(pdf_path))
    doc.close()

    manifest = run_intake(pdf_path)
    pages = run_extraction(manifest)
    tree = run_semantic(manifest, pages)

    all_text = " ".join(
        p.text for p in tree.chapters[0].sections[0].content if isinstance(p, Paragraph)
    )
    assert "Chapter One" not in all_text
    assert "Real body sentence number 0." in all_text


def test_footnotes_are_attached_to_chapter(tmp_path: Path) -> None:
    import pymupdf

    pdf_path = tmp_path / "footnote_chapter.pdf"
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

    assert len(tree.chapters[0].footnotes) == 1
    assert tree.chapters[0].footnotes[0].marker == "1"


def test_numbered_sections_become_nested_headings_in_technical_profile(tmp_path: Path) -> None:
    """Rule 2.4 — dot-numbered headings ("1.1 Getting Started") are set at
    body-text size in most technical books, so font clustering alone would
    never notice them. They should nest under the chapter as sub-`Section`s
    instead of flattening into ordinary paragraphs."""
    import pymupdf

    pdf_path = tmp_path / "numbered.pdf"
    doc = pymupdf.open()

    page1 = doc.new_page(width=400, height=600)
    page1.insert_text((72, 60), "Chapter One", fontsize=24, fontname="helv")
    page1.insert_text((72, 100), "1.1 Getting Started", fontsize=11, fontname="helv")
    for i in range(4):
        page1.insert_text(
            (72, 130 + i * 16), f"Section 1.1 body sentence {i}.", fontsize=11, fontname="helv"
        )
    page1.insert_text((72, 210), "1.2 Advanced Usage", fontsize=11, fontname="helv")
    for i in range(4):
        page1.insert_text(
            (72, 240 + i * 16), f"Section 1.2 body sentence {i}.", fontsize=11, fontname="helv"
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

    assert [c.title for c in tree.chapters] == ["Chapter One", "Chapter Two"]
    section_titles = [s.title for s in tree.chapters[0].sections if s.title]
    assert section_titles == ["1.1 Getting Started", "1.2 Advanced Usage"]

    body_paragraphs = [
        c for s in tree.chapters[0].sections for c in s.content if isinstance(c, Paragraph)
    ]
    assert all("Getting Started" not in p.text for p in body_paragraphs)
    assert len(tree.chapters[1].sections) == 1  # no numbered sections in Chapter Two


def test_chapter_number_and_separate_title_are_merged(tmp_path: Path) -> None:
    """Regression: some books typeset the chapter number as its own oversized
    element with the real title set smaller (but still visually distinct
    from body text) immediately below it. Font clustering alone only sees
    the number as the size outlier, leaving the chapter titled just "9"."""
    import pymupdf

    pdf_path = tmp_path / "split_title.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=400, height=600)
    page.insert_text((72, 80), "9", fontsize=36, fontname="helv")
    page.insert_text((72, 120), "Creative Problem Solving", fontsize=16, fontname="helv")
    for i in range(8):
        page.insert_text(
            (72, 160 + i * 16), f"Body sentence number {i}.", fontsize=11, fontname="helv"
        )
    doc.save(str(pdf_path))
    doc.close()

    manifest = run_intake(pdf_path)
    pages = run_extraction(manifest)
    tree = run_semantic(manifest, pages)

    assert tree.chapters[0].title == "9 Creative Problem Solving"
    assert all(s.title != "Creative Problem Solving" for s in tree.chapters[0].sections)

    paragraphs = [c for c in tree.chapters[0].sections[0].content if isinstance(c, Paragraph)]
    assert all("Creative Problem Solving" not in p.text for p in paragraphs)


def test_bare_roman_numeral_chapter_title_does_not_swallow_body_text(tmp_path: Path) -> None:
    """A chapter genuinely titled just a roman numeral (no separate title
    element at all) must not absorb the opening words of its first
    paragraph -- the merge only fires when the adjacent block looks like a
    title (bigger than body / bold), not ordinary body-sized prose."""
    import pymupdf

    pdf_path = tmp_path / "bare_numeral.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=400, height=600)
    page.insert_text((72, 80), "IX", fontsize=24, fontname="helv")
    page.insert_text((72, 120), "It was a dark and stormy night.", fontsize=11, fontname="helv")
    for i in range(8):
        page.insert_text(
            (72, 150 + i * 16), f"Body sentence number {i}.", fontsize=11, fontname="helv"
        )
    doc.save(str(pdf_path))
    doc.close()

    manifest = run_intake(pdf_path)
    pages = run_extraction(manifest)
    tree = run_semantic(manifest, pages)

    assert tree.chapters[0].title == "IX"
    paragraphs = [c for c in tree.chapters[0].sections[0].content if isinstance(c, Paragraph)]
    assert any(p.text.startswith("It was a dark and stormy night.") for p in paragraphs)


def test_bulleted_list_is_extracted_as_list_data(tmp_path: Path) -> None:
    import pymupdf

    from mdook.core.models import ListData

    pdf_path = tmp_path / "list_book.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=400, height=600)
    page.insert_text((72, 60), "Chapter One", fontsize=24, fontname="helv")
    page.insert_text(
        (72, 100), "An intro paragraph before the list of items here.", fontsize=11, fontname="helv"
    )
    page.insert_text((72, 130), "- First item in the list", fontsize=11, fontname="helv")
    page.insert_text((72, 150), "- Second item in the list", fontsize=11, fontname="helv")
    page.insert_text((72, 170), "- Third item in the list", fontsize=11, fontname="helv")
    page.insert_text(
        (72, 200), "A closing paragraph after the list here too.", fontsize=11, fontname="helv"
    )
    doc.save(str(pdf_path))
    doc.close()

    manifest = run_intake(pdf_path)
    pages = run_extraction(manifest)
    tree = run_semantic(manifest, pages)

    content = tree.chapters[0].sections[0].content
    list_items = [c for c in content if isinstance(c, ListData)]
    assert len(list_items) == 1
    assert [item.text for item in list_items[0].items] == [
        "First item in the list",
        "Second item in the list",
        "Third item in the list",
    ]


def test_indented_paragraph_becomes_general_block_quote(tmp_path: Path) -> None:
    import pymupdf

    from mdook.core.models import BlockQuote as BlockQuoteModel

    pdf_path = tmp_path / "quote_book.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=400, height=600)
    page.insert_text((72, 60), "Chapter One", fontsize=24, fontname="helv")
    for i in range(4):
        page.insert_text(
            (72, 100 + i * 16), f"Ordinary body sentence number {i}.", fontsize=11, fontname="helv"
        )
    page.insert_text(
        (110, 180),
        "A deeply indented quotation set apart from the body text.",
        fontsize=11,
        fontname="helv",
    )
    for i in range(4):
        page.insert_text(
            (72, 220 + i * 16),
            f"More ordinary body sentence number {i}.",
            fontsize=11,
            fontname="helv",
        )
    doc.save(str(pdf_path))
    doc.close()

    manifest = run_intake(pdf_path)
    pages = run_extraction(manifest)
    tree = run_semantic(manifest, pages)

    content = tree.chapters[0].sections[0].content
    quotes = [c for c in content if isinstance(c, BlockQuoteModel)]
    assert len(quotes) == 1
    assert "deeply indented quotation" in quotes[0].lines[0]
    assert quotes[0].italic is False

    paragraphs = [c for c in content if isinstance(c, Paragraph)]
    assert all("deeply indented quotation" not in p.text for p in paragraphs)


def test_table_is_extracted_as_table_data(tmp_path: Path) -> None:
    import pymupdf

    from mdook.core.models import TableData
    from tests.conftest import add_grid_table

    pdf_path = tmp_path / "table_chapter.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=400, height=300)
    page.insert_text((72, 30), "Chapter One", fontsize=18, fontname="helv")
    add_grid_table(page, (50, 60, 350, 150), [["Name", "Age"], ["Alice", "30"]])
    doc.save(str(pdf_path))
    doc.close()

    manifest = run_intake(pdf_path)
    pages = run_extraction(manifest)
    tree = run_semantic(manifest, pages)

    content = tree.chapters[0].sections[0].content
    tables = [c for c in content if isinstance(c, TableData)]
    assert len(tables) == 1
    assert tables[0].cells == [["Name", "Age"], ["Alice", "30"]]
    assert tables[0].is_complex is False


def test_monospace_text_is_extracted_as_code_block(tmp_path: Path) -> None:
    import pymupdf

    from mdook.core.models import CodeBlock

    pdf_path = tmp_path / "code_book.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=400, height=300)
    page.insert_text((72, 40), "Chapter One", fontsize=18, fontname="helv")
    page.insert_text((72, 80), "Here is an example:", fontsize=11, fontname="helv")
    page.insert_text((72, 100), "def foo():", fontsize=10, fontname="cour")
    page.insert_text((72, 115), "    return 1", fontsize=10, fontname="cour")
    page.insert_text((72, 140), "That was the function.", fontsize=11, fontname="helv")
    doc.save(str(pdf_path))
    doc.close()

    manifest = run_intake(pdf_path)
    pages = run_extraction(manifest)
    tree = run_semantic(manifest, pages)

    content = tree.chapters[0].sections[0].content
    code_blocks = [c for c in content if isinstance(c, CodeBlock)]
    assert len(code_blocks) == 1
    assert code_blocks[0].lines == ["def foo():", "    return 1"]

    paragraphs = [c for c in content if isinstance(c, Paragraph)]
    assert all("def foo" not in p.text for p in paragraphs)


def test_labeled_paragraph_is_extracted_as_callout_block(tmp_path: Path) -> None:
    import pymupdf

    from mdook.core.models import CalloutBlock

    pdf_path = tmp_path / "callout_book.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=400, height=300)
    page.insert_text((72, 40), "Chapter One", fontsize=18, fontname="helv")
    page.insert_text((72, 90), "Ordinary body text before the box.", fontsize=11, fontname="helv")
    page.insert_text(
        (72, 150), "Warning: this step cannot be undone.", fontsize=11, fontname="helv"
    )
    page.insert_text((72, 210), "Ordinary body text after the box.", fontsize=11, fontname="helv")
    doc.save(str(pdf_path))
    doc.close()

    manifest = run_intake(pdf_path)
    pages = run_extraction(manifest)
    tree = run_semantic(manifest, pages)

    content = tree.chapters[0].sections[0].content
    callouts = [c for c in content if isinstance(c, CalloutBlock)]
    assert len(callouts) == 1
    assert callouts[0].label == "Warning"
    assert callouts[0].paragraphs == ["this step cannot be undone."]

    paragraphs = [c for c in content if isinstance(c, Paragraph)]
    assert all("cannot be undone" not in p.text for p in paragraphs)


def test_front_matter_zone_does_not_pollute_chapter_tier_detection(tmp_path: Path) -> None:
    """Regression: found via real-book testing. A decorative cover/title-page
    font (much larger than any real chapter heading) used to dominate the
    whole-book font-size tier histogram, since font clustering scanned every
    page regardless of zone. That starved real chapter headings of a tier
    slot and turned the entire body into one garbage "chapter" titled after
    whatever the cover page's stray oversized text happened to say. Rule 2.2
    scopes clustering to the body zone specifically to prevent this."""
    import pymupdf

    pdf_path = tmp_path / "cover_garbage.pdf"
    doc = pymupdf.open()

    cover = doc.new_page(width=400, height=600)
    cover.insert_text((72, 100), "GARBLED COVER TITLE", fontsize=60, fontname="helv")
    cover.insert_text((72, 250), "Copyright 2020 Some Publisher", fontsize=10, fontname="helv")

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

    doc.save(str(pdf_path))
    doc.close()

    manifest = run_intake(pdf_path)
    assert len(manifest.zone_map) >= 2  # cover page correctly split into its own zone
    pages = run_extraction(manifest)
    tree = run_semantic(manifest, pages)

    assert [c.title for c in tree.chapters] == ["Chapter One", "Chapter Two"]


def test_front_matter_preface_becomes_named_section(tmp_path: Path) -> None:
    import pymupdf

    from mdook.core.models import Paragraph as ParagraphModel

    pdf_path = tmp_path / "preface_book.pdf"
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

    doc.save(str(pdf_path))
    doc.close()

    manifest = run_intake(pdf_path)
    pages = run_extraction(manifest)
    tree = run_semantic(manifest, pages)

    assert [c.title for c in tree.chapters] == ["Chapter One", "Chapter Two"]
    preface_section = next((s for s in tree.front_matter if s.title == "Preface"), None)
    assert preface_section is not None
    preface_text = " ".join(
        c.text for c in preface_section.content if isinstance(c, ParagraphModel)
    )
    assert "Preface body sentence 0." in preface_text


def test_back_matter_glossary_becomes_named_section(tmp_path: Path) -> None:
    import pymupdf

    from mdook.core.models import GlossaryBlock

    pdf_path = tmp_path / "glossary_book.pdf"
    doc = pymupdf.open()

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

    assert [c.title for c in tree.chapters] == ["Chapter One", "Chapter Two"]
    glossary_section = next((s for s in tree.back_matter if s.title == "Glossary"), None)
    assert glossary_section is not None
    glossary_blocks = [c for c in glossary_section.content if isinstance(c, GlossaryBlock)]
    assert len(glossary_blocks) >= 1
    items = [item for block in glossary_blocks for item in block.items]
    assert items[0].term == "Term 0"
    assert items[0].definition == "a definition."
    assert len(items) == 4


def test_degenerate_short_chapter_titles_do_not_wipe_out_every_page(tmp_path: Path) -> None:
    """Regression: found via real-book testing. A book whose chapter-title
    detection degenerated to garbage (font-encoding corruption producing
    several chapters all titled bare "H") turned the TOC heading
    cross-reference signal into a false-positive machine: a single
    normalized character substring-matches almost any page's text, so
    nearly every page in the book got wrongly discarded as "the printed
    TOC," silently dropping all of its content -- not just tables."""
    import pymupdf

    pdf_path = tmp_path / "degenerate_titles.pdf"
    doc = pymupdf.open()

    for i in range(3):
        page = doc.new_page(width=400, height=600)
        page.insert_text((72, 60), "H", fontsize=24, fontname="helv")
        for line in range(8):
            page.insert_text(
                (72, 100 + line * 16),
                f"Chapter {i} real body content line {line} with the letter h in it.",
                fontsize=11,
                fontname="helv",
            )
    doc.save(str(pdf_path))
    doc.close()

    manifest = run_intake(pdf_path)
    pages = run_extraction(manifest)
    tree = run_semantic(manifest, pages)

    assert len(tree.chapters) == 3
    for chapter in tree.chapters:
        paragraphs = [c for c in chapter.sections[0].content if isinstance(c, Paragraph)]
        assert len(paragraphs) > 0, "content was wrongly discarded as a printed TOC page"


def test_page_number_less_toc_is_discarded_via_heading_cross_reference(tmp_path: Path) -> None:
    """Regression: ebook-derived PDFs (Gutenberg-style HTML exports
    especially) often print a table of contents as a bare list of chapter
    titles with no page numbers at all, which the "Title .... 123" dot-leader
    pattern can't catch. Cross-referencing the book's own detected chapter
    titles against the page's text catches it regardless."""
    import pymupdf

    titles = ["THE KING IN YELLOW", "THE REPAIRER OF REPUTATIONS", "THE MASK", "IN THE COURT"]
    pdf_path = tmp_path / "toc_book.pdf"
    doc = pymupdf.open()
    page_width = 700

    title_page = doc.new_page(width=page_width, height=600)
    title_page.insert_text((72, 200), titles[0], fontsize=24, fontname="helv")
    for i in range(8):
        title_page.insert_text(
            (72, 240 + i * 16), f"Body filler sentence number {i}.", fontsize=11, fontname="helv"
        )

    toc_page = doc.new_page(width=page_width, height=600)
    toc_page.insert_text((72, 60), "CONTENTS", fontsize=11, fontname="helv")
    y = 80.0
    for title in titles[1:]:
        first, rest = title[0], title[1:]
        toc_page.insert_text((72, y), first, fontsize=14, fontname="helv")  # small-caps split
        toc_page.insert_text((80, y), rest, fontsize=11, fontname="helv")
        y += 20

    for title in titles[1:]:
        chapter_page = doc.new_page(width=page_width, height=600)
        chapter_page.insert_text((72, 100), title, fontsize=24, fontname="helv")
        for i in range(8):
            chapter_page.insert_text(
                (72, 140 + i * 16), f"{title} body sentence {i}.", fontsize=11, fontname="helv"
            )

    doc.save(str(pdf_path))
    doc.close()

    manifest = run_intake(pdf_path)
    pages = run_extraction(manifest)
    tree = run_semantic(manifest, pages)

    assert len(tree.chapters) == len(titles)
    first_chapter_text = " ".join(
        p.text for p in tree.chapters[0].sections[0].content if isinstance(p, Paragraph)
    )
    assert "CONTENTS" not in first_chapter_text
    assert "REPAIRER" not in first_chapter_text
    assert "Body filler sentence number 0." in first_chapter_text


def _add_heading_page(doc, title: str, font_size: float, body_lines: int = 4) -> None:
    page = doc.new_page(width=700, height=600)
    y = 100.0
    page.insert_text((72, y), title, fontsize=font_size, fontname="helv")
    y += 40
    for line in range(body_lines):
        page.insert_text((72, y), f"Body text line {line}.", fontsize=11, fontname="helv")
        y += 20


def test_part_labeled_tier_groups_chapters_under_it(tmp_path: Path) -> None:
    import pymupdf

    pdf_path = tmp_path / "parted.pdf"
    doc = pymupdf.open()
    _add_heading_page(doc, "PART ONE: THE BEGINNING", font_size=32, body_lines=0)
    _add_heading_page(doc, "CHAPTER ONE STORY", font_size=24)
    _add_heading_page(doc, "CHAPTER TWO STORY", font_size=24)
    _add_heading_page(doc, "PART TWO: THE END", font_size=32, body_lines=0)
    _add_heading_page(doc, "CHAPTER THREE STORY", font_size=24)
    _add_heading_page(doc, "CHAPTER FOUR STORY", font_size=24)
    doc.save(str(pdf_path))
    doc.close()

    manifest = run_intake(pdf_path)
    pages = run_extraction(manifest)
    tree = run_semantic(manifest, pages)

    assert len(tree.chapters) == 4
    assert [c.part_title for c in tree.chapters] == [
        "PART ONE: THE BEGINNING",
        "PART ONE: THE BEGINNING",
        "PART TWO: THE END",
        "PART TWO: THE END",
    ]
    # A "PART ..." heading is never itself mistaken for a chapter.
    assert "PART ONE" not in [c.title for c in tree.chapters]


def test_book_without_parts_leaves_part_title_none(unbookmarked_pdf: Path) -> None:
    manifest = run_intake(unbookmarked_pdf)
    pages = run_extraction(manifest)
    tree = run_semantic(manifest, pages)

    assert all(c.part_title is None for c in tree.chapters)


def test_isolated_symbol_dense_paragraph_becomes_a_display_math_block(tmp_path: Path) -> None:
    import pymupdf

    from mdook.core.models import MathBlock

    pdf_path = tmp_path / "math_book.pdf"
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

    content = tree.chapters[0].sections[0].content
    math_blocks = [c for c in content if isinstance(c, MathBlock)]
    assert len(math_blocks) == 1
    assert math_blocks[0].display is True
    assert math_blocks[0].latex_or_text == "E = mc²"
    assert math_blocks[0].numbering == "3.14"


def test_theorem_and_proof_are_grouped_as_callouts(tmp_path: Path) -> None:
    import pymupdf

    from mdook.core.models import CalloutBlock

    pdf_path = tmp_path / "theorem_book.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=400, height=400)
    page.insert_text((72, 40), "Chapter One", fontsize=18, fontname="helv")
    page.insert_text((72, 90), "Theorem 3.2. For all x, x equals x.", fontsize=11, fontname="helv")
    page.insert_text((72, 150), "Proof. This follows by reflexivity.", fontsize=11, fontname="helv")
    page.insert_text(
        (72, 210), "The claim is therefore established. Q.E.D.", fontsize=11, fontname="helv"
    )
    page.insert_text((72, 270), "We now move on to the next topic.", fontsize=11, fontname="helv")
    doc.save(str(pdf_path))
    doc.close()

    manifest = run_intake(pdf_path)
    pages = run_extraction(manifest)
    tree = run_semantic(manifest, pages)

    content = tree.chapters[0].sections[0].content
    callouts = [c for c in content if isinstance(c, CalloutBlock)]
    assert len(callouts) == 2
    theorem, proof = callouts
    assert theorem.label == "Theorem 3.2"
    assert theorem.paragraphs == ["For all x, x equals x."]
    assert proof.label == "Proof"
    assert proof.paragraphs == [
        "This follows by reflexivity.",
        "The claim is therefore established. Q.E.D.",
    ]
