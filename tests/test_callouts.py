from mdook.core.rules.callouts import detect_callout, obsidian_callout_type


def test_colon_label_is_detected() -> None:
    result = detect_callout("Note: always back up your data before proceeding.")
    assert result == ("Note", "always back up your data before proceeding.")


def test_period_label_is_detected() -> None:
    result = detect_callout("Warning. Do not touch the reactor core.")
    assert result == ("Warning", "Do not touch the reactor core.")


def test_case_insensitive_label() -> None:
    result = detect_callout("IMPORTANT: read this first.")
    assert result is not None
    assert result[0] == "IMPORTANT"


def test_prose_starting_with_label_word_is_not_a_callout() -> None:
    # No punctuation directly after "Note" -- ordinary prose, not a callout.
    assert detect_callout("Note that the results varied across trials.") is None


def test_unrelated_prose_is_not_a_callout() -> None:
    assert detect_callout("The results varied across trials.") is None


def test_label_with_no_remaining_text() -> None:
    result = detect_callout("Note:")
    assert result == ("Note", "")


def test_known_label_maps_to_obsidian_type() -> None:
    assert obsidian_callout_type("Warning") == "warning"
    assert obsidian_callout_type("caution") == "warning"
    assert obsidian_callout_type("Key Point") == "important"


def test_unmapped_label_falls_back_to_info() -> None:
    assert obsidian_callout_type("Something Else Entirely") == "info"
