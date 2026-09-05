from mdook.core.models import TextBlock
from mdook.core.rules.lists import parse_list_marker, split_list_run


def _block(text: str, x0: float, page: int = 1) -> TextBlock:
    return TextBlock(
        text=text, font_name="Helvetica", font_size=11, bbox=(x0, 0, x0 + 100, 12), page_number=page
    )


def test_parse_bullet_marker() -> None:
    parsed = parse_list_marker("- First item")
    assert parsed is not None
    assert (parsed.text, parsed.ordered, parsed.marker) == ("First item", False, None)

    parsed = parse_list_marker("• Second item")
    assert parsed is not None
    assert (parsed.text, parsed.ordered, parsed.marker) == ("Second item", False, None)


def test_parse_numbered_marker() -> None:
    parsed = parse_list_marker("1. First item")
    assert parsed is not None
    assert (parsed.text, parsed.ordered, parsed.marker) == ("First item", True, "1")

    parsed = parse_list_marker("2) Second item")
    assert parsed is not None
    assert (parsed.text, parsed.ordered, parsed.marker) == ("Second item", True, "2")


def test_ordinary_prose_is_not_a_marker() -> None:
    assert parse_list_marker("A. Einstein once said something clever.") is None
    assert parse_list_marker("This is a normal sentence.") is None


def test_french_dialogue_dash_is_not_a_marker() -> None:
    """Em/en-dash-opened dialogue lines must not be misread as bullets."""
    assert parse_list_marker("— Where are you going? she asked.") is None


def test_split_list_run_groups_consecutive_items() -> None:
    blocks = [
        (1, _block("Intro paragraph before the list.", x0=72)),
        (1, _block("- First item", x0=72)),
        (1, _block("- Second item", x0=72)),
        (1, _block("- Third item", x0=72)),
        (1, _block("Closing paragraph after the list.", x0=72)),
    ]
    sub_runs = split_list_run(blocks)
    kinds = [kind for kind, _ in sub_runs]
    assert kinds == ["text", "list", "text"]

    list_data = sub_runs[1][1]
    assert [item.text for item in list_data.items] == ["First item", "Second item", "Third item"]
    assert all(not item.ordered for item in list_data.items)


def test_nested_list_levels_by_indent() -> None:
    blocks = [
        (1, _block("- Top level item", x0=72)),
        (1, _block("- Nested item", x0=100)),
        (1, _block("- Another top level item", x0=72)),
    ]
    sub_runs = split_list_run(blocks)
    list_data = sub_runs[0][1]
    assert [item.level for item in list_data.items] == [0, 1, 0]


def test_list_page_number_is_first_items_page() -> None:
    blocks = [
        (3, _block("- An item", x0=72, page=3)),
        (3, _block("- Another item", x0=72, page=3)),
    ]
    list_data = split_list_run(blocks)[0][1]
    assert list_data.page_number == 3


def test_numbered_item_marker_survives_prose_interruption() -> None:
    """Regression: found via real-book testing. Narrative prose routinely
    interrupts a numbered sequence ("1. Relax completely. <paragraph>
    2. Observe the visual images."), splitting it into several separate
    single-item `ListData` runs. Each one must still carry its own true
    printed number so rendering doesn't show "1." for every step."""
    blocks = [
        (1, _block("1. Relax completely", x0=72)),
        (1, _block("An explanatory paragraph goes here.", x0=72)),
        (1, _block("2. Observe the visual images", x0=72)),
    ]
    sub_runs = split_list_run(blocks)
    kinds = [kind for kind, _ in sub_runs]
    assert kinds == ["list", "text", "list"]
    assert sub_runs[0][1].items[0].marker == "1"
    assert sub_runs[2][1].items[0].marker == "2"
