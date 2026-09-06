from mdook.core.models import BookManifest, PageData, TextBlock
from mdook.core.rules.headings import detect_headings, find_body_font_size, merge_drop_caps


def _text_block(
    text: str, x0: float, y0: float, x1: float, y1: float, font_size: float
) -> TextBlock:
    return TextBlock(
        text=text, font_name="Helvetica", font_size=font_size, bbox=(x0, y0, x1, y1), page_number=1
    )


def _page(blocks: list[TextBlock], was_ocrd: bool = False) -> PageData:
    return PageData(page_number=1, width=400.0, height=600.0, blocks=blocks, was_ocrd=was_ocrd)


def _manifest() -> BookManifest:
    return BookManifest(
        title="Test Book",
        author="Test Author",
        file_path="test.pdf",
        total_pages=1,
        needs_ocr=False,
        profile="literature",
    )


def test_body_font_size_is_most_frequent_by_character_weight() -> None:
    blocks = [
        _text_block("Short heading", 72, 100, 200, 130, font_size=24.0),
        _text_block(
            "A much longer body sentence that dominates by character count.",
            72,
            140,
            350,
            155,
            font_size=11.0,
        ),
    ]
    assert find_body_font_size([_page(blocks)]) == 11.0


def test_drop_cap_is_merged_into_following_text() -> None:
    drop_cap = _text_block("T", 72, 100, 95, 130, font_size=24.0)
    continuation = _text_block("he story begins.", 95, 108, 250, 123, font_size=11.0)
    page = _page([drop_cap, continuation])

    merge_drop_caps([page], body_font_size=11.0)

    assert len(page.blocks) == 1
    assert page.blocks[0].text == "The story begins."


def test_oversized_multi_character_block_is_not_treated_as_drop_cap() -> None:
    heading = _text_block("BIG", 72, 100, 200, 130, font_size=24.0)
    continuation = _text_block("body text follows", 72, 140, 250, 155, font_size=11.0)
    page = _page([heading, continuation])

    merge_drop_caps([page], body_font_size=11.0)

    assert len(page.blocks) == 2


def test_drop_cap_below_size_threshold_is_left_alone() -> None:
    almost_drop_cap = _text_block("T", 72, 100, 90, 118, font_size=15.0)  # < 2x body size
    continuation = _text_block("he story begins.", 90, 108, 250, 123, font_size=11.0)
    page = _page([almost_drop_cap, continuation])

    merge_drop_caps([page], body_font_size=11.0)

    assert len(page.blocks) == 2


def _ocr_noise_fixture(was_ocrd: bool, heading_text: str) -> PageData:
    # OCR font size is approximated from each line's own bbox height
    # (`mdook.core.rules.ocr`), so an ordinary lowercase body line can land
    # a couple of points above the body-size cluster purely from
    # ascender/descender jitter -- not because it's a real heading.
    body_blocks = [
        _text_block("This is ordinary body prose that repeats often.", 72, 200, 350, 215, 11.0),
        _text_block("More ordinary body prose filling out the page.", 72, 220, 350, 235, 11.0),
        _text_block("Yet more body prose to establish the body size.", 72, 240, 350, 255, 11.0),
    ]
    noisy_line = _text_block(heading_text, 72, 50, 300, 65, 13.0)
    return _page([noisy_line, *body_blocks], was_ocrd=was_ocrd)


def test_ocr_font_size_jitter_does_not_promote_lowercase_line_to_heading() -> None:
    page = _ocr_noise_fixture(was_ocrd=True, heading_text="jecting me to denunciations in speeches")
    headings = detect_headings(_manifest(), [page])
    assert not any("jecting" in h.title for h in headings)


def test_same_font_size_jitter_on_native_page_is_a_known_false_positive() -> None:
    # Baseline showing the bug this guards against: without the OCR-aware
    # check, position + word-count alone confirms the candidate.
    page = _ocr_noise_fixture(
        was_ocrd=False, heading_text="jecting me to denunciations in speeches"
    )
    headings = detect_headings(_manifest(), [page])
    assert any("jecting" in h.title for h in headings)


def test_ocr_uppercase_line_is_still_confirmed_as_heading() -> None:
    page = _ocr_noise_fixture(was_ocrd=True, heading_text="CHAPTER TWO")
    headings = detect_headings(_manifest(), [page])
    assert any(h.title == "CHAPTER TWO" for h in headings)


def test_ocr_caseless_script_heading_is_not_rejected_for_lacking_uppercase() -> None:
    # Chinese text has no uppercase concept at all -- `str.isupper()` is
    # always False for it, so the OCR-page uppercase-mandatory guard would
    # reject every heading candidate on a case-less-script page if it
    # applied unconditionally (Batch 18).
    page = _ocr_noise_fixture(was_ocrd=True, heading_text="第二章 引言")
    headings = detect_headings(_manifest(), [page])
    assert any(h.title == "第二章 引言" for h in headings)
