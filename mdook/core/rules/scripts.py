"""Non-Latin Script Detection — Batch 18 (`Mdook-docs/BOOK_ELEMENTS.md`
section 14). Not in the original `Mdook-docs/RULES.md` catalog.

Small, standalone module shared by `mdook.core.rules.columns` (RTL column
reading order) and `mdook.core.rules.headings` (case-less-script heading
confirmation), rather than duplicating Unicode-range logic in each rule
file. Vertical-writing-mode detection lives in
`mdook.core.stages.extraction` instead — it needs PyMuPDF's raw per-line
data, which isn't available once text has already become a `TextBlock`.
"""

from __future__ import annotations

from mdook.core.models import PageData, TextBlock

_RTL_RANGES = (
    (0x0590, 0x05FF),  # Hebrew
    (0x0600, 0x06FF),  # Arabic
    (0x0750, 0x077F),  # Arabic Supplement
    (0x08A0, 0x08FF),  # Arabic Extended-A
    (0xFB1D, 0xFB4F),  # Hebrew presentation forms
    (0xFB50, 0xFDFF),  # Arabic presentation forms A
    (0xFE70, 0xFEFF),  # Arabic presentation forms B
)
_CASELESS_RANGES = (
    *_RTL_RANGES,
    (0x0900, 0x097F),  # Devanagari
    (0x0E00, 0x0E7F),  # Thai
    (0x3040, 0x30FF),  # Hiragana / Katakana
    (0x4E00, 0x9FFF),  # CJK Unified Ideographs
    (0xAC00, 0xD7AF),  # Hangul syllables
)
"""Every script in `_RTL_RANGES` is also caseless, plus the major East/
South Asian scripts that have no case distinction at all -- `str.isupper()`
is always False for text made of these characters (Python's Unicode
database has no case property for them), which matters directly to
`mdook.core.rules.headings._confirm_heading`'s OCR-page uppercase gate."""

DOMINANT_SCRIPT_RATIO = 0.5
"""A text sample counts as "in" a script once at least this fraction of
its alphabetic characters fall in that script's ranges -- tolerates a few
stray Latin digits/punctuation or transliterated terms without losing the
signal."""


def _in_ranges(code: int, ranges: tuple[tuple[int, int], ...]) -> bool:
    return any(lo <= code <= hi for lo, hi in ranges)


def _script_char_ratio(text: str, ranges: tuple[tuple[int, int], ...]) -> float:
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 0.0
    matches = sum(1 for c in letters if _in_ranges(ord(c), ranges))
    return matches / len(letters)


def is_rtl_text(text: str) -> bool:
    return _script_char_ratio(text, _RTL_RANGES) >= DOMINANT_SCRIPT_RATIO


def is_caseless_text(text: str) -> bool:
    return _script_char_ratio(text, _CASELESS_RANGES) >= DOMINANT_SCRIPT_RATIO


def page_is_rtl(page: PageData) -> bool:
    """A page's own dominant script decides its column reading order
    (Rule 8's RTL extension) — checked per page, not whole-book, since a
    hybrid book (an English preface, an Arabic body) shouldn't force one
    reading direction onto every page."""
    text = " ".join(b.text for b in page.blocks if isinstance(b, TextBlock))
    return is_rtl_text(text)
