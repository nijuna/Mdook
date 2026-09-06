from mdook.core.models import PageData, TextBlock
from mdook.core.rules.headers_footers import detect_headers_footers


def _header(text: str, page_number: int) -> TextBlock:
    return TextBlock(
        text=text,
        font_name="Helvetica",
        font_size=10.0,
        bbox=(72, 10, 300, 20),
        page_number=page_number,
    )


def _footer(text: str, page_number: int) -> TextBlock:
    return TextBlock(
        text=text,
        font_name="Helvetica",
        font_size=10.0,
        bbox=(72, 780, 300, 792),
        page_number=page_number,
    )


def _body(text: str, page_number: int) -> TextBlock:
    return TextBlock(
        text=text,
        font_name="Helvetica",
        font_size=11.0,
        bbox=(72, 100, 300, 400),
        page_number=page_number,
    )


def _page(page_number: int, blocks: list[TextBlock]) -> PageData:
    return PageData(page_number=page_number, width=400.0, height=800.0, blocks=blocks)


def test_exact_repeating_header_is_stripped() -> None:
    pages = [
        _page(n, [_header("MY BOOK TITLE", n), _body(f"Body text {n}.", n)]) for n in range(1, 6)
    ]
    detect_headers_footers(pages)

    for page in pages:
        assert page.header_text == "MY BOOK TITLE"
        assert all("MY BOOK TITLE" not in b.text for b in page.blocks)


def test_ocr_noisy_header_variants_still_cluster_and_strip() -> None:
    # Same running header, misread slightly differently by Tesseract on
    # every page -- the failure mode found converting a real scanned book.
    variants = [
        "MY BOOK TITLE",
        "MY BOOK TITLB",
        "MV BOOK TITLE",
        "MY BOOK TITLE.",
        "MY B00K TITLE",
    ]
    pages = [
        _page(n, [_header(variants[n - 1], n), _body(f"Body text {n}.", n)]) for n in range(1, 6)
    ]
    detect_headers_footers(pages)

    for page in pages:
        assert page.header_text is not None
        assert len(page.blocks) == 1
        assert page.blocks[0].text.startswith("Body text")


def test_footer_page_numbers_still_strip_via_digit_masking() -> None:
    pages = [_page(n, [_body(f"Body text {n}.", n), _footer(str(n), n)]) for n in range(1, 6)]
    detect_headers_footers(pages)

    for page in pages:
        assert page.footer_text is not None
        assert all(b.text != page.footer_text for b in page.blocks)


def test_non_repeating_header_band_text_is_left_alone() -> None:
    # Fewer than MIN_REPEAT_PAGES occurrences -- not a real running header.
    pages = [_page(n, [_header(f"One-off note {n}", n), _body("Body.", n)]) for n in range(1, 4)]
    detect_headers_footers(pages)

    for page in pages:
        assert page.header_text is None
        assert len(page.blocks) == 2
