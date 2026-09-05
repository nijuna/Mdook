from mdook.core.models import PageData, TextBlock
from mdook.core.rules.citations import (
    CITATION_MARKER_SENTINEL,
    detect_bibliography_markers,
    splice_citation_links,
)


def _text_block(text: str, page_number: int = 1) -> TextBlock:
    return TextBlock(
        text=text,
        font_name="Helvetica",
        font_size=11.0,
        bbox=(72, 100, 300, 115),
        page_number=page_number,
    )


def _page(blocks: list[TextBlock], page_number: int = 1) -> PageData:
    return PageData(page_number=page_number, width=400.0, height=600.0, blocks=blocks)


def test_detects_numbered_bibliography_entries() -> None:
    pages = [
        _page(
            [
                _text_block("Bibliography"),
                _text_block("1. Smith, J. (2020). A Study of Things."),
                _text_block("2. Jones, A. (2019). Another Study."),
            ]
        )
    ]
    assert detect_bibliography_markers(pages) == {"1", "2"}


def test_bracketed_entry_markers_are_detected() -> None:
    pages = [
        _page(
            [
                _text_block("References"),
                _text_block("[1] Smith, J. (2020). A Study of Things."),
            ]
        )
    ]
    assert detect_bibliography_markers(pages) == {"1"}


def test_text_before_bibliography_label_is_not_scanned() -> None:
    pages = [
        _page(
            [
                _text_block("3. This looks like an entry but isn't in the section yet."),
                _text_block("Bibliography"),
                _text_block("1. Smith, J. (2020). A Study of Things."),
            ]
        )
    ]
    assert detect_bibliography_markers(pages) == {"1"}


def test_single_numeric_citation_is_spliced() -> None:
    result = splice_citation_links("As shown previously [1].", {"1"})
    expected = f"As shown previously [{CITATION_MARKER_SENTINEL}1{CITATION_MARKER_SENTINEL}]."
    assert result == expected


def test_comma_separated_citation_list_is_spliced() -> None:
    result = splice_citation_links("Multiple sources agree [1, 3].", {"1", "3"})
    expected = (
        f"Multiple sources agree [{CITATION_MARKER_SENTINEL}1{CITATION_MARKER_SENTINEL}, "
        f"{CITATION_MARKER_SENTINEL}3{CITATION_MARKER_SENTINEL}]."
    )
    assert result == expected


def test_range_citation_expands_to_every_number() -> None:
    result = splice_citation_links("See the surveys [1-3].", {"1", "2", "3"})
    expected = (
        f"See the surveys [{CITATION_MARKER_SENTINEL}1{CITATION_MARKER_SENTINEL}, "
        f"{CITATION_MARKER_SENTINEL}2{CITATION_MARKER_SENTINEL}, "
        f"{CITATION_MARKER_SENTINEL}3{CITATION_MARKER_SENTINEL}]."
    )
    assert result == expected


def test_citation_with_unmatched_number_degrades_to_plain_text() -> None:
    # Entry 9 doesn't exist in this (malformed/incomplete) bibliography.
    result = splice_citation_links("As shown previously [9].", {"1", "2"})
    assert result == "As shown previously [9]."


def test_no_bibliography_markers_leaves_text_untouched() -> None:
    text = "Some text with a [1] bracket that isn't a real citation."
    assert splice_citation_links(text, set()) == text


def test_bracketed_number_unrelated_to_citations_is_untouched() -> None:
    # A bracket whose number was never seen as a bibliography entry at all.
    result = splice_citation_links("Section [42] covers this.", {"1", "2"})
    assert result == "Section [42] covers this."
