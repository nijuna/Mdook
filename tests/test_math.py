from mdook.core.rules.math import (
    TheoremEnvironment,
    detect_display_equation,
    group_theorem_environments,
    score_symbol_density,
    splice_inline_math,
)
from mdook.core.rules.paragraphs import MergedParagraph


def _paragraph(text: str, page_number: int = 1) -> MergedParagraph:
    return MergedParagraph(text=text, page_number=page_number, x0=72.0)


def test_ordinary_prose_scores_zero_density() -> None:
    assert score_symbol_density("This is an ordinary English sentence.") == 0.0


def test_greek_letters_alone_do_not_score_as_math() -> None:
    # A book genuinely written in Greek shouldn't misfire on every page.
    assert score_symbol_density("αβγδεζηθ") == 0.0


def test_greek_letters_count_once_a_strong_symbol_is_present() -> None:
    density = score_symbol_density("∀θ")
    assert density > 0.0


def test_strong_math_symbols_score_positive() -> None:
    assert score_symbol_density("∀x ∈ ℝ, x² ≥ 0") > 0.0


def test_display_equation_is_detected() -> None:
    result = detect_display_equation("∀x ∈ ℝ, x² ≥ 0")
    assert result is not None
    text, numbering = result
    assert numbering is None


def test_display_equation_with_numbering_tag_is_split_out() -> None:
    result = detect_display_equation("E = mc² (3.14)")
    assert result is not None
    text, numbering = result
    assert text == "E = mc²"
    assert numbering == "3.14"


def test_long_prose_paragraph_mentioning_a_symbol_is_not_a_display_equation() -> None:
    text = (
        "In this chapter we will discuss the properties of the variable x "
        "and how it relates to the broader argument being made throughout "
        "this rather long paragraph of ordinary prose that just happens to "
        "reference a single mathematical symbol like ∀ in passing."
    )
    assert detect_display_equation(text) is None


def test_ordinary_short_sentence_is_not_a_display_equation() -> None:
    assert detect_display_equation("This is a short sentence.") is None


def test_inline_math_token_is_wrapped() -> None:
    result = splice_inline_math("the value of α is 3")
    assert result == "the value of $α$ is 3"


def test_inline_math_token_with_trailing_punctuation_is_wrapped_correctly() -> None:
    result = splice_inline_math("we know that x² is positive.")
    assert "$x²$" in result
    assert result.endswith(" is positive.")


def test_prose_without_symbols_is_untouched_by_inline_splicing() -> None:
    text = "This sentence has no math symbols at all."
    assert splice_inline_math(text) == text


def test_plain_paragraph_passes_through_grouping_unchanged() -> None:
    paragraphs = [_paragraph("Just an ordinary paragraph.")]
    result = group_theorem_environments(paragraphs)
    assert result == paragraphs


def test_theorem_paragraph_is_grouped_with_number() -> None:
    paragraphs = [_paragraph("Theorem 3.2. For all x, x equals x.")]
    result = group_theorem_environments(paragraphs)
    assert len(result) == 1
    assert isinstance(result[0], TheoremEnvironment)
    assert result[0].label == "Theorem 3.2"
    assert result[0].paragraphs == ["For all x, x equals x."]


def test_unnumbered_theorem_label_still_groups() -> None:
    paragraphs = [_paragraph("Definition: A set is a collection of objects.")]
    result = group_theorem_environments(paragraphs)
    assert isinstance(result[0], TheoremEnvironment)
    assert result[0].label == "Definition"


def test_proof_consumes_paragraphs_until_qed_marker() -> None:
    paragraphs = [
        _paragraph("Proof. We proceed by induction."),
        _paragraph("The base case holds trivially."),
        _paragraph("The inductive step follows similarly. ∎"),
        _paragraph("This is unrelated text after the proof."),
    ]
    result = group_theorem_environments(paragraphs)
    assert len(result) == 2
    proof = result[0]
    assert isinstance(proof, TheoremEnvironment)
    assert proof.label == "Proof"
    assert proof.paragraphs == [
        "We proceed by induction.",
        "The base case holds trivially.",
        "The inductive step follows similarly. ∎",
    ]
    assert result[1] == paragraphs[3]


def test_proof_stops_at_next_theorem_label_if_no_qed_found() -> None:
    paragraphs = [
        _paragraph("Proof. We proceed by induction."),
        _paragraph("The base case holds trivially."),
        _paragraph("Lemma 4. A related fact."),
    ]
    result = group_theorem_environments(paragraphs)
    assert len(result) == 2
    proof, lemma = result
    assert isinstance(proof, TheoremEnvironment)
    assert proof.label == "Proof"
    assert proof.paragraphs == ["We proceed by induction.", "The base case holds trivially."]
    assert isinstance(lemma, TheoremEnvironment)
    assert lemma.label == "Lemma 4"
