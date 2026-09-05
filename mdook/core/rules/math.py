"""Mathematics & Formal Notation — Batch 17 (`Mdook-docs/BOOK_ELEMENTS.md`
section 7, Tier B). Not in the original `Mdook-docs/RULES.md` catalog.

Handles the *text-layer* math case: Unicode math symbols already present in
extracted text (Word-equation-editor exports, many OCR'd math texts via
Tesseract's Latin+symbol recognition, older typeset technical books). A PDF
built from real LaTeX frequently draws equations as vector paths or Type3
glyph shapes with no extractable Unicode at all -- recovering semantic math
from a pure vector drawing is out of scope here (that's a specialized tool
in its own right, e.g. Mathpix/pix2tex, not a generic heuristic rule); the
vector region still gets rasterized as an ordinary image via Rule 7.2.

Two independent pieces:
- Display/inline equation detection, via Unicode symbol-density scoring,
  rendered through Obsidian's native MathJax support (`$$...$$` / `$...$`)
  rather than a custom fenced block.
- Theorem-like environment grouping (Theorem/Lemma/.../Proof), rendered as
  an Obsidian callout via the same `CalloutBlock` machinery Batch 14 built
  for Note/Warning boxes, rather than a second box-rendering path.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from mdook.core.rules.paragraphs import MergedParagraph

# ---------------------------------------------------------------------------
# Symbol-density scoring
# ---------------------------------------------------------------------------

_STRONG_MATH_RANGES = (
    (0x2100, 0x214F),  # Letterlike Symbols (ℝ, ℕ, ℤ, ℚ, ℂ, ℓ, ...)
    (0x2200, 0x22FF),  # Mathematical Operators (∀, ∃, ∈, ⊆, →, ≤, ≥, ≠, ∞, ∂, ∇, ...)
    (0x2070, 0x209F),  # Superscripts and Subscripts
    (0x1D400, 0x1D7FF),  # Mathematical Alphanumeric Symbols
)
_LEGACY_SUPERSCRIPT_DIGITS = frozenset("¹²³")
"""¹²³ (U+00B9, U+00B2, U+00B3) predate the "Superscripts and Subscripts"
Unicode block (U+2070-209F) and live in Latin-1 Supplement instead, for
backwards compatibility -- ordinary superscript 2/3 in a real equation
("E = mc²") would otherwise score as plain, non-math text."""
_WEAK_MATH_RANGES = ((0x0370, 0x03FF),)  # Greek and Coptic
"""Greek letters are common in math (α, β, θ, Σ, Π) but are also a real
natural-language script -- a book actually written in Greek would score
100% "math" on every page if Greek alone counted. Weak signals are only
added to the density score once at least one *strong*, unambiguous math
symbol is already present somewhere in the same text; they never trigger a
match on their own. `splice_inline_math` relaxes this one step further for
short inline tokens specifically -- see `_is_math_token`."""

DISPLAY_EQUATION_DENSITY = 0.2
DISPLAY_EQUATION_MAX_WORDS = 30
DISPLAY_EQUATION_SHORT_WORDS = 8
"""At or below this word count, the presence of any math symbol at all is
enough (see `detect_display_equation`) -- a real short equation is often
mostly ordinary letters/digits by character count."""
INLINE_TOKEN_DENSITY = 0.5

EQUATION_NUMBER_RE = re.compile(r"\s*\((\d+(?:\.\d+)*)\)\s*$")
_TRAILING_PUNCTUATION_RE = re.compile(r"^(.*?)([.,;:!?)\]]*)$")

THEOREM_LABEL_RE = re.compile(
    r"^(Theorem|Lemma|Corollary|Proposition|Definition|Axiom|Example|Remark|Exercise|Proof|Claim)"
    r"\s*(\d+(?:\.\d+)*)?\s*[.:]\s*",
    re.IGNORECASE,
)
QED_RE = re.compile(r"(□|∎|Q\.?\s?E\.?\s?D\.?)\s*$")


def _in_ranges(code: int, ranges: tuple[tuple[int, int], ...]) -> bool:
    return any(lo <= code <= hi for lo, hi in ranges)


def _is_strong_math_char(c: str) -> bool:
    return _in_ranges(ord(c), _STRONG_MATH_RANGES) or c in _LEGACY_SUPERSCRIPT_DIGITS


def _is_weak_math_char(c: str) -> bool:
    return _in_ranges(ord(c), _WEAK_MATH_RANGES)


def score_symbol_density(text: str) -> float:
    """Fraction of non-space characters that are math symbols. Always 0.0
    unless at least one *strong* (unambiguous) math symbol is present --
    see `_WEAK_MATH_RANGES`."""
    non_space = [c for c in text.strip() if not c.isspace()]
    if not non_space:
        return 0.0
    strong = sum(1 for c in non_space if _is_strong_math_char(c))
    if strong == 0:
        return 0.0
    weak = sum(1 for c in non_space if _is_weak_math_char(c))
    return (strong + weak) / len(non_space)


def detect_display_equation(text: str) -> tuple[str, str | None] | None:
    """Returns `(equation_text, numbering)` if `text` (a whole merged
    paragraph -- already isolated by Rule 5.4's paragraph-boundary
    detection before this is ever called) reads as a display equation on
    its own. `numbering` is a trailing "(3.14)"-style tag, stripped from
    the equation text and preserved separately. Returns None otherwise.

    Two-tier check, since a real equation ("E = mc²") is often *mostly*
    ordinary-looking letters and digits with only one or two actual math
    symbols -- a flat density threshold would miss it entirely. A short
    paragraph (`DISPLAY_EQUATION_SHORT_WORDS` or fewer words) only needs
    *some* math symbol present; a longer one still needs real density,
    since being isolated and short no longer rules out ordinary prose that
    merely mentions a symbol in passing."""
    stripped = text.strip()
    words = stripped.split()
    if not stripped or len(words) > DISPLAY_EQUATION_MAX_WORDS:
        return None
    density = score_symbol_density(stripped)
    if density <= 0.0:
        return None
    if len(words) > DISPLAY_EQUATION_SHORT_WORDS and density < DISPLAY_EQUATION_DENSITY:
        return None
    match = EQUATION_NUMBER_RE.search(stripped)
    if match:
        return stripped[: match.start()].strip(), match.group(1)
    return stripped, None


SHORT_GREEK_TOKEN_MAX_LENGTH = 2
"""A token this short made entirely of Greek letters (optionally with a
trailing digit, e.g. "α1") reads as an isolated math variable in
English-language prose far more often than as an actual embedded Greek
word -- unlike whole-paragraph display-equation detection, where the same
signal at higher character counts risks matching a genuinely Greek-
authored paragraph instead. `score_symbol_density`'s "needs a strong
symbol" rule is relaxed by exactly this much for inline splicing only."""


def _is_math_token(token: str) -> bool:
    if not token:
        return False
    if score_symbol_density(token) >= INLINE_TOKEN_DENSITY:
        return True
    if len(token) > SHORT_GREEK_TOKEN_MAX_LENGTH:
        return False
    has_greek = any(_is_weak_math_char(c) for c in token)
    return has_greek and all(_is_weak_math_char(c) or c.isdigit() for c in token)


def splice_inline_math(text: str) -> str:
    """Wraps any whitespace-delimited token recognized as math by
    `_is_math_token` in Obsidian's inline MathJax delimiters (`$...$`) —
    e.g. "the value of α is 3" -> "the value of $α$ is 3". Token-level
    rather than free-form substring matching, since finding an inline
    equation's correct boundaries within ordinary prose is otherwise
    ambiguous without real per-glyph layout structure."""
    tokens = text.split(" ")
    result = []
    for token in tokens:
        core, trailing = _split_trailing_punctuation(token)
        if _is_math_token(core):
            result.append(f"${core}${trailing}")
        else:
            result.append(token)
    return " ".join(result)


def _split_trailing_punctuation(token: str) -> tuple[str, str]:
    match = _TRAILING_PUNCTUATION_RE.match(token)
    if match is None:
        return token, ""
    return match.group(1), match.group(2)


# ---------------------------------------------------------------------------
# Theorem-like environments
# ---------------------------------------------------------------------------


@dataclass
class TheoremEnvironment:
    label: str
    """The book's own label plus number, verbatim ("Theorem 3.2")."""
    paragraphs: list[str]
    page_number: int


def group_theorem_environments(
    paragraphs: list[MergedParagraph],
) -> list[MergedParagraph | TheoremEnvironment]:
    """Scans merged paragraphs for a Theorem/Lemma/.../Proof label opening
    a new paragraph and groups it with however many subsequent paragraphs
    belong to the same environment. A "Proof" consumes paragraphs until a
    QED marker or the next theorem-labeled paragraph — a real heading
    boundary can't appear mid-run, since headings already split into their
    own run upstream (`mdook.core.stages.semantic._collect_content`).
    Every other environment is just its own paragraph, grouped alone, so
    every theorem-like environment renders uniformly as a callout."""
    items: list[MergedParagraph | TheoremEnvironment] = []
    i = 0
    while i < len(paragraphs):
        paragraph = paragraphs[i]
        match = THEOREM_LABEL_RE.match(paragraph.text.strip())
        if match is None:
            items.append(paragraph)
            i += 1
            continue

        label_word = match.group(1)
        number = match.group(2)
        label = f"{label_word.capitalize()} {number}" if number else label_word.capitalize()
        remainder = paragraph.text[match.end() :].strip()
        body = [remainder] if remainder else []
        page_number = paragraph.page_number
        i += 1

        if label_word.lower() == "proof":
            while i < len(paragraphs):
                next_paragraph = paragraphs[i]
                if THEOREM_LABEL_RE.match(next_paragraph.text.strip()):
                    break
                body.append(next_paragraph.text)
                i += 1
                if QED_RE.search(next_paragraph.text.strip()):
                    break

        items.append(TheoremEnvironment(label=label, paragraphs=body, page_number=page_number))
    return items
