from mdook.core.models import TextBlock
from mdook.core.rules.images import (
    cluster_drawing_regions,
    extract_figure_number,
    find_caption,
)


def _text_block(text: str, bbox: tuple[float, float, float, float]) -> TextBlock:
    return TextBlock(text=text, font_name="Helvetica", font_size=10.0, bbox=bbox, page_number=1)


def test_caption_below_image_is_found() -> None:
    image_bbox = (100.0, 100.0, 300.0, 250.0)
    caption = _text_block(
        "Figure 3.2: Cross-section of the assembly.", (100.0, 255.0, 300.0, 268.0)
    )
    other = _text_block("Unrelated body prose far away.", (100.0, 400.0, 300.0, 412.0))
    result = find_caption(image_bbox, [other, caption])
    assert result is caption


def test_caption_above_image_is_found() -> None:
    image_bbox = (100.0, 200.0, 300.0, 350.0)
    caption = _text_block("Plate II.", (100.0, 170.0, 300.0, 183.0))
    result = find_caption(image_bbox, [caption])
    assert result is caption


def test_far_away_caption_shaped_text_is_not_matched() -> None:
    image_bbox = (100.0, 100.0, 300.0, 250.0)
    caption = _text_block("Figure 9: Somewhere else entirely.", (100.0, 500.0, 300.0, 512.0))
    assert find_caption(image_bbox, [caption]) is None


def test_ordinary_prose_is_not_mistaken_for_a_caption() -> None:
    image_bbox = (100.0, 100.0, 300.0, 250.0)
    prose = _text_block(
        "This paragraph just happens to follow the image.", (100.0, 255.0, 300.0, 268.0)
    )
    assert find_caption(image_bbox, [prose]) is None


def test_unnumbered_caption_is_detected() -> None:
    image_bbox = (100.0, 100.0, 300.0, 250.0)
    caption = _text_block("Illustration of the device.", (100.0, 255.0, 300.0, 268.0))
    assert find_caption(image_bbox, [caption]) is caption


def test_extract_figure_number_from_caption() -> None:
    assert extract_figure_number("Figure 3.2: Cross-section.") == "3.2"
    assert extract_figure_number("Fig. 4 shows the results.") == "4"
    assert extract_figure_number("Illustration without a number.") is None


def test_single_diagram_cluster_is_returned() -> None:
    rects = [
        (100.0, 100.0, 200.0, 150.0),
        (195.0, 100.0, 300.0, 200.0),
        (100.0, 145.0, 200.0, 250.0),
    ]
    regions = cluster_drawing_regions(rects, exclude=[])
    assert len(regions) == 1
    assert regions[0] == (100.0, 100.0, 300.0, 250.0)


def test_far_apart_rects_form_separate_clusters() -> None:
    rects = [
        (0.0, 0.0, 60.0, 60.0),
        (500.0, 500.0, 560.0, 560.0),
    ]
    regions = cluster_drawing_regions(rects, exclude=[])
    assert len(regions) == 2


def test_tiny_cluster_below_min_size_is_dropped() -> None:
    rects = [(0.0, 0.0, 10.0, 10.0)]
    assert cluster_drawing_regions(rects, exclude=[]) == []


def test_cluster_overlapping_a_table_is_excluded() -> None:
    # A table's own gridlines are vector drawings too -- must not be
    # rasterized as a second copy of the same table.
    rects = [(100.0, 100.0, 300.0, 300.0)]
    table_bbox = (90.0, 90.0, 310.0, 310.0)
    assert cluster_drawing_regions(rects, exclude=[table_bbox]) == []
