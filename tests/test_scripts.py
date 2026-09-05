from mdook.core.models import PageData, TextBlock
from mdook.core.rules.scripts import is_caseless_text, is_rtl_text, page_is_rtl


def _text_block(text: str, page_number: int = 1) -> TextBlock:
    return TextBlock(
        text=text,
        font_name="Helvetica",
        font_size=11.0,
        bbox=(72, 100, 300, 115),
        page_number=page_number,
    )


def _page(blocks: list[TextBlock]) -> PageData:
    return PageData(page_number=1, width=400.0, height=600.0, blocks=blocks)


def test_english_text_is_not_rtl() -> None:
    assert is_rtl_text("This is an ordinary English sentence.") is False


def test_arabic_text_is_rtl() -> None:
    assert is_rtl_text("هذا نص عربي عادي تماما") is True


def test_hebrew_text_is_rtl() -> None:
    assert is_rtl_text("זהו טקסט עברי רגיל") is True


def test_mixed_text_with_minority_arabic_is_not_rtl() -> None:
    text = "This is mostly an English sentence with one Arabic word عربي in it."
    assert is_rtl_text(text) is False


def test_english_text_is_not_caseless() -> None:
    assert is_caseless_text("This is an ordinary English sentence.") is False


def test_chinese_text_is_caseless() -> None:
    assert is_caseless_text("这是一句普通的中文句子") is True


def test_arabic_text_is_also_caseless() -> None:
    assert is_caseless_text("هذا نص عربي عادي تماما") is True


def test_page_is_rtl_checks_all_blocks() -> None:
    page = _page([_text_block("هذا نص عربي عادي تماما")])
    assert page_is_rtl(page) is True


def test_page_is_rtl_false_for_english_page() -> None:
    page = _page([_text_block("This is an ordinary English page.")])
    assert page_is_rtl(page) is False
