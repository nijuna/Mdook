"""Tests for Rule 9.2 — Poetry / Verse Detection and Rendering."""

from pathlib import Path

import pymupdf

from mdook.core.models import TextBlock, VerseBlock
from mdook.core.pipeline import convert
from mdook.core.rules.verse import (
    _is_attribution_line,
    _looks_like_dialogue_line,
    is_verse_stanza,
    split_verse_runs,
)
from mdook.core.stages.rendering import _render_verse


def _make_block(
    text: str,
    x0: float = 72.0,
    y0: float = 100.0,
    x1: float = 240.0,
    y1: float = 112.0,
    font_size: float = 10.0,
    font_name: str = "Times-Roman",
    is_italic: bool = False,
    is_bold: bool = False,
    page_number: int = 1,
) -> TextBlock:
    return TextBlock(
        text=text,
        bbox=(x0, y0, x1, y1),
        font_size=font_size,
        font_name=font_name,
        is_italic=is_italic,
        is_bold=is_bold,
        page_number=page_number,
    )


def test_is_verse_stanza_detects_quatrain() -> None:
    from mdook.core.rules.verse import _group_into_lines

    lines = [
        (1, _make_block("The woods are lovely, dark and deep,", y0=100, y1=112, x1=260)),
        (1, _make_block("But I have promises to keep,", y0=116, y1=128, x1=230)),
        (1, _make_block("And miles to go before I sleep,", y0=132, y1=144, x1=245)),
        (1, _make_block("And miles to go before I sleep.", y0=148, y1=160, x1=245)),
    ]
    grouped = _group_into_lines(lines, set(), set())
    assert is_verse_stanza(
        grouped, body_font_size=10.0, body_left_margin=72.0, body_right_margin=450.0
    )


def test_is_verse_stanza_rejects_long_wrapped_prose() -> None:
    from mdook.core.rules.verse import _group_into_lines

    lines = [
        (
            1,
            _make_block(
                "It was the best of times, it was the worst of times, it was the age of wisdom,",
                x0=72,
                y0=100,
                x1=450,
                y1=112,
            ),
        ),
        (
            1,
            _make_block(
                "it was the age of foolishness, it was the epoch of belief, it was the epoch of",
                x0=72,
                y0=116,
                x1=450,
                y1=128,
            ),
        ),
        (
            1,
            _make_block(
                "incredulity, it was the season of light, it was the season of darkness, it",
                x0=72,
                y0=132,
                x1=448,
                y1=144,
            ),
        ),
        (
            1,
            _make_block(
                "was the spring of hope, it was the winter of despair.",
                x0=72,
                y0=148,
                x1=340,
                y1=160,
            ),
        ),
    ]
    grouped = _group_into_lines(lines, set(), set())
    assert (
        is_verse_stanza(
            grouped, body_font_size=10.0, body_left_margin=72.0, body_right_margin=450.0
        )
        is False
    )


def test_is_verse_stanza_rejects_discrete_prose_sentences() -> None:
    from mdook.core.rules.verse import _group_into_lines

    lines = [
        (1, _make_block("Ordinary body sentence number 0.", y0=100, y1=112)),
        (1, _make_block("Ordinary body sentence number 1.", y0=116, y1=128)),
        (1, _make_block("Ordinary body sentence number 2.", y0=132, y1=144)),
        (1, _make_block("Ordinary body sentence number 3.", y0=148, y1=160)),
    ]
    grouped = _group_into_lines(lines, set(), set())
    # All 4 lines end in '.', indicating separate prose sentences
    assert (
        is_verse_stanza(
            grouped, body_font_size=10.0, body_left_margin=72.0, body_right_margin=450.0
        )
        is False
    )


def test_is_verse_stanza_rejects_glossary_term_definitions() -> None:
    from mdook.core.rules.verse import _group_into_lines

    lines = [
        (1, _make_block("Sonnet: a 14-line poem in iambic meter.", y0=100, y1=112)),
        (1, _make_block("Stanza: a grouped set of lines in poetry.", y0=116, y1=128)),
        (1, _make_block("Meter: rhythmic structure of verse lines.", y0=132, y1=144)),
    ]
    grouped = _group_into_lines(lines, set(), set())
    assert (
        is_verse_stanza(
            grouped, body_font_size=10.0, body_left_margin=72.0, body_right_margin=450.0
        )
        is False
    )


def test_dialogue_check_helpers() -> None:
    assert _looks_like_dialogue_line('"Where are you going?" he asked.') is True
    assert _looks_like_dialogue_line("“Not today,” she whispered.") is True
    assert _looks_like_dialogue_line('"Shall I compare thee to a summer\'s day?"') is False
    assert _looks_like_dialogue_line("The sea is calm tonight.") is False


def test_attribution_line_helpers() -> None:
    assert _is_attribution_line("— Robert Frost") == "Robert Frost"
    assert _is_attribution_line("-- Emily Dickinson, Poem 254") == "Emily Dickinson, Poem 254"
    assert _is_attribution_line("- William Blake") == "William Blake"
    assert _is_attribution_line("(Lord Byron)") == "Lord Byron"
    assert _is_attribution_line("This is an ordinary sentence.") is None


def test_split_verse_runs_multi_stanza_with_attribution() -> None:
    blocks = [
        # Stanza 1
        (1, _make_block("Two roads diverged in a yellow wood,", y0=100, y1=112)),
        (1, _make_block("And sorry I could not travel both", y0=116, y1=128)),
        (1, _make_block("And be one traveler, long I stood", y0=132, y1=144)),
        (1, _make_block("And looked down one as far as I could", y0=148, y1=160)),
        # Stanza break gap (24pt)
        # Stanza 2
        (1, _make_block("Then took the other, as just as fair,", y0=184, y1=196)),
        (1, _make_block("And having perhaps the better claim,", y0=200, y1=212)),
        (1, _make_block("Because it was grassy and wanted wear;", y0=216, y1=228)),
        (1, _make_block("Though as for that the passing there", y0=232, y1=244)),
        # Attribution line
        (1, _make_block("— Robert Frost", y0=260, y1=272)),
    ]

    runs = split_verse_runs(
        blocks,
        body_font_size=10.0,
        body_left_margin=72.0,
        body_right_margin=450.0,
    )

    assert len(runs) == 1
    kind, payload = runs[0]
    assert kind == "verse"
    assert isinstance(payload, VerseBlock)
    assert payload.attribution == "Robert Frost"
    assert payload.page_number == 1
    # 4 lines + blank stanza break + 4 lines = 9 items
    assert len(payload.lines) == 9
    assert payload.lines[0] == "Two roads diverged in a yellow wood,"
    assert payload.lines[3] == "And looked down one as far as I could"
    assert payload.lines[4] == ""
    assert payload.lines[5] == "Then took the other, as just as fair,"
    assert payload.lines[8] == "Though as for that the passing there"


def test_split_verse_runs_with_inline_footnotes() -> None:
    fn_block = _make_block("1", x0=265, y0=98, x1=272, y1=106, font_size=6.0)
    blocks = [
        (1, _make_block("The woods are lovely, dark and deep,", y0=100, y1=112)),
        (1, fn_block),
        (1, _make_block("But I have promises to keep,", y0=116, y1=128)),
        (1, _make_block("And miles to go before I sleep,", y0=132, y1=144)),
        (1, _make_block("And miles to go before I sleep.", y0=148, y1=160)),
    ]

    runs = split_verse_runs(
        blocks,
        body_font_size=10.0,
        body_left_margin=72.0,
        body_right_margin=450.0,
        inline_marker_ids={id(fn_block)},
    )

    assert len(runs) == 1
    kind, payload = runs[0]
    assert kind == "verse"
    assert isinstance(payload, VerseBlock)
    assert len(payload.lines) == 4
    # Marker was spliced into line 1
    assert "\ue0001\ue000" in payload.lines[0]


def test_split_verse_runs_interleaved_with_prose() -> None:
    blocks = [
        # Prose paragraph 1
        (
            1,
            _make_block(
                "He opened the dusty anthology and turned slowly to the favorite page.",
                y0=50,
                y1=62,
                x1=450,
            ),
        ),
        (
            1,
            _make_block(
                "The lines seemed as fresh now as when they were first penned decades ago.",
                y0=66,
                y1=78,
                x1=450,
            ),
        ),
        # Verse stanza (gap 26pt)
        (1, _make_block("Water, water, everywhere,", y0=104, y1=116, x1=230)),
        (1, _make_block("And all the boards did shrink;", y0=120, y1=132, x1=235)),
        (1, _make_block("Water, water, everywhere,", y0=136, y1=148, x1=230)),
        (1, _make_block("Nor any drop to drink.", y0=152, y1=164, x1=205)),
        # Prose paragraph 2 (gap 26pt)
        (
            1,
            _make_block(
                "He closed the volume with a sigh and looked out toward the gray horizon.",
                y0=190,
                y1=202,
                x1=450,
            ),
        ),
        (
            1,
            _make_block(
                "The sea was calm, but the memories were stormy and unforgiving.",
                y0=206,
                y1=218,
                x1=450,
            ),
        ),
    ]

    runs = split_verse_runs(
        blocks,
        body_font_size=10.0,
        body_left_margin=72.0,
        body_right_margin=450.0,
    )

    assert len(runs) == 3
    assert runs[0][0] == "text"
    assert runs[1][0] == "verse"
    assert runs[2][0] == "text"

    verse_item = runs[1][1]
    assert isinstance(verse_item, VerseBlock)
    assert len(verse_item.lines) == 4
    assert verse_item.lines[0] == "Water, water, everywhere,"
    assert verse_item.lines[3] == "Nor any drop to drink."


def test_render_verse_standalone() -> None:
    verse = VerseBlock(
        lines=[
            "Line 1",
            "Line 2",
            "",
            "Line 3",
            "Line 4",
        ],
        page_number=1,
        is_quoted=False,
        attribution="Author",
    )
    rendered = _render_verse(verse, back_matter_stem=None)
    assert rendered == [
        "Line 1  ",
        "Line 2  ",
        "",
        "Line 3  ",
        "Line 4  ",
        "— Author",
    ]


def test_render_verse_quoted() -> None:
    verse = VerseBlock(
        lines=[
            "Quoted 1",
            "Quoted 2",
            "",
            "Quoted 3",
        ],
        page_number=1,
        is_quoted=True,
        attribution="Poet",
    )
    rendered = _render_verse(verse, back_matter_stem=None)
    assert rendered == [
        "> Quoted 1  ",
        "> Quoted 2  ",
        ">",
        "> Quoted 3  ",
        "> — Poet",
    ]


def test_end_to_end_pdf_with_poem(tmp_path: Path) -> None:
    pdf_path = tmp_path / "poem_book.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=500, height=700)

    # Chapter Title
    page.insert_text((72, 60), "Chapter 1 - The Forest", fontsize=22, fontname="helv")

    # Prose lead-in (reaches margin ~430)
    page.insert_text(
        (72, 100),
        "The traveler hesitated at the fork where the ancient path split into two directions.",
        fontsize=10,
        fontname="helv",
    )
    page.insert_text(
        (72, 114),
        "Both branches were carpeted with golden leaves that had fallen during the autumn night.",
        fontsize=10,
        fontname="helv",
    )

    # Poem (indented at x=110, short lines)
    page.insert_text(
        (110, 150), "Two roads diverged in a yellow wood,", fontsize=10, fontname="tiro"
    )
    page.insert_text((110, 164), "And sorry I could not travel both", fontsize=10, fontname="tiro")
    page.insert_text((110, 178), "And be one traveler, long I stood", fontsize=10, fontname="tiro")
    page.insert_text(
        (110, 192), "And looked down one as far as I could", fontsize=10, fontname="tiro"
    )

    # Stanza 2 (gap of 22pt)
    page.insert_text(
        (110, 214), "Then took the other, as just as fair,", fontsize=10, fontname="tiro"
    )
    page.insert_text(
        (110, 228), "And having perhaps the better claim,", fontsize=10, fontname="tiro"
    )
    page.insert_text(
        (110, 242), "Because it was grassy and wanted wear;", fontsize=10, fontname="tiro"
    )
    page.insert_text(
        (110, 256), "Though as for that the passing there", fontsize=10, fontname="tiro"
    )

    # Attribution
    page.insert_text((110, 276), "— Robert Frost", fontsize=10, fontname="tiro")

    # Prose continuation (gap of 30pt, back to body left margin x=72)
    page.insert_text(
        (72, 310),
        "With those lines lingering in his mind, he chose the less trodden path and walked on.",
        fontsize=10,
        fontname="helv",
    )
    page.insert_text(
        (72, 324),
        "The forest grew quieter as the shadows lengthened across the mossy boulders ahead.",
        fontsize=10,
        fontname="helv",
    )

    doc.save(str(pdf_path))
    doc.close()

    vault_dir = tmp_path / "vault"
    res = convert(pdf_path, vault_dir)

    assert res.success
    assert res.chapters == 1
    assert res.validation_report is not None
    assert len(res.validation_report.errors) == 0

    chapter_files = [
        f
        for f in res.output_dir.glob("*.md")
        if not f.name.endswith("- Index.md") and f.name != "index.md"
    ]
    assert len(chapter_files) == 1
    chapter_content = chapter_files[0].read_text(encoding="utf-8")

    # Verse lines must have double trailing spaces for line breaks
    assert "Two roads diverged in a yellow wood,  \n" in chapter_content
    assert "And sorry I could not travel both  \n" in chapter_content
    assert "Then took the other, as just as fair,  \n" in chapter_content
    assert "— Robert Frost" in chapter_content

    # Surrounding prose must be merged into flowing paragraphs, not line-broken
    assert (
        "The traveler hesitated at the fork where the ancient path split into two directions. Both"
        " branches were carpeted with golden leaves that had fallen during the autumn night."
        in chapter_content
    )
