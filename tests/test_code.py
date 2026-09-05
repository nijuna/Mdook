from mdook.core.models import TextBlock
from mdook.core.rules.code import build_code_block, is_monospace_font, split_code_run


def _block(text: str, font_name: str, page: int = 1) -> TextBlock:
    return TextBlock(
        text=text, font_name=font_name, font_size=10, bbox=(72, 0, 200, 12), page_number=page
    )


def test_is_monospace_font_recognizes_common_names() -> None:
    assert is_monospace_font("Courier New") is True
    assert is_monospace_font("Consolas") is True
    assert is_monospace_font("ABCDEF+SourceCodePro-Regular") is True


def test_is_monospace_font_rejects_proportional_names() -> None:
    assert is_monospace_font("Helvetica") is False
    assert is_monospace_font("Times New Roman") is False


def test_split_code_run_groups_consecutive_monospace_blocks() -> None:
    blocks = [
        (1, _block("Here is some code:", "Helvetica")),
        (1, _block("def foo():", "Courier New")),
        (1, _block("    return 1", "Courier New")),
        (1, _block("That's the function.", "Helvetica")),
    ]
    sub_runs = split_code_run(blocks)
    kinds = [kind for kind, _ in sub_runs]
    assert kinds == ["text", "code", "text"]
    code_lines = [block.text for _, block in sub_runs[1][1]]
    assert code_lines == ["def foo():", "    return 1"]


def test_build_code_block_preserves_lines_and_page() -> None:
    blocks = [
        (3, _block("line one", "Courier")),
        (3, _block("line two", "Courier")),
    ]
    code = build_code_block(blocks)
    assert code.lines == ["line one", "line two"]
    assert code.page_number == 3
