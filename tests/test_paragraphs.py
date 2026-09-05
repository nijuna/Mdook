from mdook.core.models import TextBlock
from mdook.core.rules.paragraphs import FOOTNOTE_MARKER_SENTINEL, merge_text_blocks


def _block(
    text: str,
    x0: float = 72,
    y0: float = 100,
    x1: float = 200,
    y1: float = 115,
    font_size: float = 11.0,
    is_bold: bool = False,
    is_italic: bool = False,
) -> TextBlock:
    return TextBlock(
        text=text,
        font_name="Helvetica",
        font_size=font_size,
        is_bold=is_bold,
        is_italic=is_italic,
        bbox=(x0, y0, x1, y1),
        page_number=1,
    )


def test_same_font_lines_merge() -> None:
    a = _block("This is line one", y0=100, y1=115)
    b = _block("continuing here.", y0=115, y1=130)
    merged = merge_text_blocks([(1, a), (1, b)])
    assert len(merged) == 1
    assert merged[0].text == "This is line one continuing here."


def test_hyphenated_line_is_rejoined() -> None:
    a = _block("This word is extraordi-", y0=100, y1=115)
    b = _block("nary indeed.", y0=115, y1=130)
    merged = merge_text_blocks([(1, a), (1, b)])
    assert merged[0].text == "This word is extraordinary indeed."


def test_large_vertical_gap_starts_new_paragraph() -> None:
    a = _block("First paragraph.", y0=100, y1=115)
    b = _block("Second paragraph.", y0=160, y1=175)  # gap >> 1.5x line height
    merged = merge_text_blocks([(1, a), (1, b)])
    assert [p.text for p in merged] == ["First paragraph.", "Second paragraph."]


def test_indented_line_starts_new_paragraph() -> None:
    a = _block("End of one paragraph.", x0=72, y0=100, y1=115)
    b = _block("Indented start of next.", x0=100, y0=115, y1=130)
    merged = merge_text_blocks([(1, a), (1, b)])
    assert len(merged) == 2


def test_cross_page_continuation_without_terminal_punctuation() -> None:
    a = _block("This sentence continues", y0=550, y1=565)  # no terminal punctuation
    b = _block("onto the next page.", y0=100, y1=115)
    merged = merge_text_blocks([(1, a), (2, b)])
    assert len(merged) == 1
    assert merged[0].text == "This sentence continues onto the next page."


def test_cross_page_stops_after_terminal_punctuation() -> None:
    a = _block("This sentence ends here.", y0=550, y1=565)
    b = _block("A new one starts.", y0=100, y1=115)
    merged = merge_text_blocks([(1, a), (2, b)])
    assert len(merged) == 2


def test_different_style_does_not_merge() -> None:
    a = _block("Normal text.", y0=100, y1=115, is_italic=False)
    b = _block("Italic text.", y0=115, y1=130, is_italic=True)
    merged = merge_text_blocks([(1, a), (1, b)])
    assert len(merged) == 2


def test_inline_marker_is_spliced_not_split() -> None:
    a = _block("A claim needing a note", x0=72, x1=183, y0=100, y1=115)
    marker = _block("1", x0=183, x1=187, y0=100, y1=110, font_size=7.0)
    b = _block(" follows here.", x0=190, x1=250, y0=100, y1=115)
    merged = merge_text_blocks([(1, a), (1, marker), (1, b)], inline_marker_ids={id(marker)})
    assert len(merged) == 1
    s = FOOTNOTE_MARKER_SENTINEL
    assert merged[0].text == f"A claim needing a note{s}1{s} follows here."
