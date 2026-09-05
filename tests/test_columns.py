from mdook.core.models import ImageBlock, PageData, TextBlock
from mdook.core.rules.columns import (
    detect_column_ranges,
    reorder_columns,
    reorder_columns_if_warranted,
)

PAGE_WIDTH = 500.0


def _block(text: str, x0: float, x1: float, y0: float, y1: float | None = None) -> TextBlock:
    return TextBlock(
        text=text,
        font_name="Helvetica",
        font_size=11,
        bbox=(x0, y0, x1, y1 if y1 is not None else y0 + 12),
        page_number=1,
    )


def _two_column_blocks() -> list[TextBlock]:
    left = [_block(f"L{i}", 50, 200, 100 + i * 30) for i in range(3)]
    right = [_block(f"R{i}", 300, 450, 100 + i * 30) for i in range(3)]
    return left + right


def test_detect_column_ranges_finds_two_bands() -> None:
    ranges = detect_column_ranges(_two_column_blocks(), PAGE_WIDTH)
    assert ranges is not None
    assert len(ranges) == 2
    assert ranges[0][0] == 50 and ranges[0][1] == 200
    assert ranges[1][0] == 300 and ranges[1][1] == 450


def test_single_column_returns_none() -> None:
    blocks = [_block(f"P{i}", 50, 450, 100 + i * 20) for i in range(6)]
    assert detect_column_ranges(blocks, PAGE_WIDTH) is None


def test_too_few_blocks_returns_none() -> None:
    blocks = [_block("L", 50, 200, 100), _block("R", 300, 450, 100)]
    assert detect_column_ranges(blocks, PAGE_WIDTH) is None


def test_column_spanning_block_is_excluded_from_band_detection() -> None:
    blocks = _two_column_blocks()
    blocks.append(_block("Heading spans the whole page", 40, 460, 50))
    ranges = detect_column_ranges(blocks, PAGE_WIDTH)
    assert ranges is not None
    assert len(ranges) == 2  # the spanning block didn't form a third band


def test_reorder_columns_reads_left_column_fully_before_right() -> None:
    blocks = _two_column_blocks()
    reordered = reorder_columns(blocks, PAGE_WIDTH)
    assert [b.text for b in reordered] == ["L0", "L1", "L2", "R0", "R1", "R2"]


def test_reorder_columns_returns_unchanged_for_single_column_page() -> None:
    blocks = [_block(f"P{i}", 50, 450, 100 + i * 20) for i in range(6)]
    assert reorder_columns(blocks, PAGE_WIDTH) == blocks


def test_spanning_heading_splits_columns_above_and_below() -> None:
    top_left = [_block(f"TL{i}", 50, 200, 100 + i * 20) for i in range(3)]
    top_right = [_block(f"TR{i}", 300, 450, 100 + i * 20) for i in range(3)]
    heading = _block("Section Heading spanning wide", 40, 460, 200)
    bottom_left = [_block(f"BL{i}", 50, 200, 240 + i * 20) for i in range(3)]
    bottom_right = [_block(f"BR{i}", 300, 450, 240 + i * 20) for i in range(3)]

    blocks = top_left + top_right + [heading] + bottom_left + bottom_right
    reordered = reorder_columns(blocks, PAGE_WIDTH)
    texts = [b.text for b in reordered]

    assert texts == [
        "TL0", "TL1", "TL2", "TR0", "TR1", "TR2",
        "Section Heading spanning wide",
        "BL0", "BL1", "BL2", "BR0", "BR1", "BR2",
    ]


def test_image_block_acts_as_spanning_anchor() -> None:
    top_left = [_block(f"TL{i}", 50, 200, 100 + i * 20) for i in range(3)]
    top_right = [_block(f"TR{i}", 300, 450, 100 + i * 20) for i in range(3)]
    image = ImageBlock(image_path="/tmp/fig.png", bbox=(40, 200, 460, 260), page_number=1)
    bottom_left = [_block(f"BL{i}", 50, 200, 280 + i * 20) for i in range(3)]
    bottom_right = [_block(f"BR{i}", 300, 450, 280 + i * 20) for i in range(3)]

    blocks = [*top_left, *top_right, image, *bottom_left, *bottom_right]
    reordered = reorder_columns(blocks, PAGE_WIDTH)
    kinds = [getattr(b, "text", "IMAGE") for b in reordered]
    assert kinds.index("IMAGE") == 6  # after the 6 top-column blocks, before the bottom ones


def _interleaved_two_column_blocks() -> list[TextBlock]:
    """Row-major natural extraction order (as PyMuPDF's top-to-bottom
    traversal might actually produce for a real 2-column page) -- distinct
    from the column-major order reordering should produce, so a test can
    tell "skipped" apart from "applied but coincidentally the same"."""
    left = [_block(f"L{i}", 50, 200, 100 + i * 30) for i in range(3)]
    right = [_block(f"R{i}", 300, 450, 100 + i * 30) for i in range(3)]
    interleaved = []
    for l_block, r_block in zip(left, right, strict=True):
        interleaved.extend([l_block, r_block])
    return interleaved


def test_literature_profile_skips_reordering_below_signal_threshold() -> None:
    signal_page = PageData(
        page_number=1, width=PAGE_WIDTH, height=600, blocks=_interleaved_two_column_blocks()
    )
    plain_pages = [
        PageData(
            page_number=i,
            width=PAGE_WIDTH,
            height=600,
            blocks=[_block(f"P{i}", 50, 450, 100)],
        )
        for i in range(2, 12)
    ]
    pages = [signal_page] + plain_pages

    reorder_columns_if_warranted(pages, "literature")

    assert [b.text for b in pages[0].blocks] == ["L0", "R0", "L1", "R1", "L2", "R2"]


def test_technical_profile_always_reorders_signal_pages() -> None:
    page = PageData(
        page_number=1, width=PAGE_WIDTH, height=600, blocks=_interleaved_two_column_blocks()
    )
    reorder_columns_if_warranted([page], "technical")
    assert [b.text for b in page.blocks] == ["L0", "L1", "L2", "R0", "R1", "R2"]


def test_reorder_columns_reads_right_column_first_when_rtl() -> None:
    blocks = _two_column_blocks()
    reordered = reorder_columns(blocks, PAGE_WIDTH, is_rtl=True)
    assert [b.text for b in reordered] == ["R0", "R1", "R2", "L0", "L1", "L2"]


def test_arabic_multi_column_page_reorders_right_to_left() -> None:
    # Same physical layout as `_two_column_blocks`, but with Arabic text --
    # the page's dominant script (not an explicit flag) drives RTL order.
    left = [_block(f"يسار{i}", 50, 200, 100 + i * 30) for i in range(3)]
    right = [_block(f"يمين{i}", 300, 450, 100 + i * 30) for i in range(3)]
    interleaved = []
    for l_block, r_block in zip(left, right, strict=True):
        interleaved.extend([l_block, r_block])
    page = PageData(page_number=1, width=PAGE_WIDTH, height=600, blocks=interleaved)

    reorder_columns_if_warranted([page], "technical")

    assert [b.text for b in page.blocks] == [
        "يمين0",
        "يمين1",
        "يمين2",
        "يسار0",
        "يسار1",
        "يسار2",
    ]


def test_vertical_text_page_is_left_unreordered() -> None:
    page = PageData(
        page_number=1,
        width=PAGE_WIDTH,
        height=600,
        blocks=_interleaved_two_column_blocks(),
        is_vertical_text=True,
    )
    original_order = [b.text for b in page.blocks]

    reorder_columns_if_warranted([page], "technical")

    assert [b.text for b in page.blocks] == original_order
