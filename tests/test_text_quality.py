from mdook.core.models import PageData, TextBlock
from mdook.core.rules.text_quality import needs_ocr_for_page, score_page_quality


def _text_block(text: str) -> TextBlock:
    return TextBlock(
        text=text, font_name="Helvetica", font_size=11, bbox=(72, 100, 300, 115), page_number=1
    )


def _page(blocks: list[TextBlock]) -> PageData:
    return PageData(page_number=1, width=400.0, height=600.0, blocks=blocks)


def test_clean_prose_scores_high() -> None:
    text = (
        "It was the best of times, it was the worst of times, it was the age "
        "of wisdom, it was the age of foolishness, it was the epoch of belief."
    )
    score = score_page_quality(_page([_text_block(text)]))
    assert score > 0.8


def test_empty_page_scores_zero() -> None:
    score = score_page_quality(_page([]))
    assert score == 0.0


def test_near_empty_page_scores_low() -> None:
    """A bare folio number is exactly what an otherwise image-only scanned
    page's text layer looks like when there is one."""
    score = score_page_quality(_page([_text_block("42")]))
    assert score < 0.5


def test_replacement_characters_are_penalized() -> None:
    clean = _page([_text_block("A page of perfectly normal readable text content here.")])
    corrupted = _page(
        [_text_block("A page of ���������� garbage.")]
    )
    assert score_page_quality(corrupted) < score_page_quality(clean)


def test_needs_ocr_threshold() -> None:
    assert needs_ocr_for_page(0.2) is True
    assert needs_ocr_for_page(0.8) is False
    assert needs_ocr_for_page(0.5, threshold=0.5) is False
