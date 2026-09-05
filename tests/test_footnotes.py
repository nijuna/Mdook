from mdook.core.models import PageData, TextBlock
from mdook.core.rules.footnotes import detect_endnote_markers, detect_footnotes


def _text_block(
    text: str, x0: float, y0: float, x1: float, y1: float, font_size: float = 11.0
) -> TextBlock:
    return TextBlock(
        text=text, font_name="Helvetica", font_size=font_size, bbox=(x0, y0, x1, y1), page_number=1
    )


def _page(blocks: list[TextBlock], height: float = 600.0) -> PageData:
    return PageData(page_number=1, width=400.0, height=height, blocks=blocks)


def test_bottom_band_footnote_is_extracted_and_stripped() -> None:
    body = _text_block("Body text goes here.", 72, 100, 300, 115)
    definition = _text_block("1. This is the footnote.", 72, 560, 250, 572, font_size=8.0)
    page = _page([body, definition])

    result = detect_footnotes([page], body_font_size=11.0)

    assert result.footnotes_by_page[1][0].marker == "1"
    assert result.footnotes_by_page[1][0].text == "This is the footnote."
    assert definition not in page.blocks
    assert body in page.blocks


def test_footnote_requires_smaller_font_than_body() -> None:
    same_size_bottom_text = _text_block(
        "1. Not actually a footnote.", 72, 560, 250, 572, font_size=11.0
    )
    page = _page([same_size_bottom_text])

    result = detect_footnotes([page], body_font_size=11.0)

    assert result.footnotes_by_page == {}
    assert same_size_bottom_text in page.blocks


def test_inline_marker_adjacent_to_body_text_is_correlated() -> None:
    note = _text_block("A claim needing a note", 72, 100, 183, 115)
    marker = _text_block("1", 183, 100, 187, 110, font_size=7.0)
    tail = _text_block(" follows here.", 190, 100, 250, 115)
    definition = _text_block("1. This is the footnote.", 72, 560, 250, 572, font_size=8.0)
    page = _page([note, marker, tail, definition])

    result = detect_footnotes([page], body_font_size=11.0)

    assert id(marker) in result.inline_marker_ids


def test_unmatched_marker_text_is_not_correlated() -> None:
    note = _text_block("A claim with a stray digit", 72, 100, 220, 115)
    stray = _text_block("9", 220, 100, 224, 110, font_size=7.0)
    definition = _text_block("1. This is the footnote.", 72, 560, 250, 572, font_size=8.0)
    page = _page([note, stray, definition])

    result = detect_footnotes([page], body_font_size=11.0)

    assert id(stray) not in result.inline_marker_ids


def test_detect_endnote_markers_finds_numbered_entries_under_notes_label() -> None:
    label = _text_block("Notes", 72, 60, 150, 75)
    entry1 = _text_block("1. First citation.", 72, 100, 300, 115)
    entry2 = _text_block("2. Second citation.", 72, 120, 300, 135)
    page = _page([label, entry1, entry2])

    assert detect_endnote_markers([page]) == {"1", "2"}


def test_detect_endnote_markers_ignores_numbers_before_the_notes_label() -> None:
    stray = _text_block("3. Not an endnote, comes before the label.", 72, 60, 300, 75)
    label = _text_block("Notes", 72, 90, 150, 105)
    entry = _text_block("1. First citation.", 72, 120, 300, 135)
    page = _page([stray, label, entry])

    assert detect_endnote_markers([page]) == {"1"}


def test_endnote_marker_is_correlated_by_position_across_the_book() -> None:
    """An inline reference to an endnote lives on a body page with no
    page-bottom definition of its own -- the marker set itself is book-wide
    (Rule 4.3), unlike page-bottom footnotes which are matched per page."""
    note = _text_block("A claim needing a note", 72, 100, 183, 115)
    marker = _text_block("14", 183, 100, 191, 110, font_size=7.0)
    tail = _text_block(" follows here.", 194, 100, 250, 115)
    page = _page([note, marker, tail])

    result = detect_footnotes([page], body_font_size=11.0, endnote_markers=frozenset({"14"}))

    assert id(marker) in result.endnote_marker_ids
    assert id(marker) not in result.inline_marker_ids


def test_page_bottom_footnote_takes_priority_over_matching_endnote_marker() -> None:
    note = _text_block("A claim needing a note", 72, 100, 183, 115)
    marker = _text_block("1", 183, 100, 187, 110, font_size=7.0)
    tail = _text_block(" follows here.", 190, 100, 250, 115)
    definition = _text_block("1. This is the footnote.", 72, 560, 250, 572, font_size=8.0)
    page = _page([note, marker, tail, definition])

    result = detect_footnotes([page], body_font_size=11.0, endnote_markers=frozenset({"1"}))

    assert id(marker) in result.inline_marker_ids
    assert id(marker) not in result.endnote_marker_ids
