"""Per-Page Text Quality Scoring — Phase 3 prep (`Mdook-docs/ROADMAP.md`).

Not yet wired to an OCR engine (that's Batch 12) -- this module only scores
whether a page's already-extracted native text layer looks usable, so
Stage 2 can eventually decide per page whether to trust PyMuPDF's
extraction or route that specific page to OCR instead.

Combines three signals into one 0.0-1.0 confidence score:
- Character count: a page with almost no extractable text is very likely a
  bare scanned image with no text layer at all -- this is the strongest
  and most common signal, and the only one today's whole-book
  `mdook.core.stages.intake._detect_needs_ocr` checks, averaged across an
  8-page sample rather than scored per page.
- Unicode validity: a page whose text contains replacement characters or
  unmapped-glyph placeholders is the signature of a font with no (or a
  broken) ToUnicode CMap -- a real, distinct corruption pattern from the
  one found twice in this session's real-book testing (King in Yellow,
  Book of Soyga), where a decorative font's glyphs map to *other valid*
  characters ("^", "AWOKE", a bare "H") rather than replacement/PUA
  codepoints. That specific failure mode looks like ordinary text to any
  per-page score and isn't something this function can catch -- it needed
  the structural fixes already shipped this session (chapter-tier
  selection, TOC-page hardening), not an OCR-routing signal. Unicode
  validity here catches its own separate, real class of corruption.
- Word-likeness: a lightweight heuristic (alphabetic run length within a
  plausible range), not a real dictionary lookup -- avoids a new
  dependency for v1. A genuine dictionary/word-frequency check is a
  possible future refinement, not attempted here.
"""

from __future__ import annotations

import re

from mdook.core.models import PageData, TextBlock

MIN_CHARS_FOR_USABLE_PAGE = 20
"""Below this many extracted characters, a page is almost certainly a bare
scanned image -- matches `mdook.core.stages.intake.MIN_CHARS_FOR_TEXT_LAYER`,
just applied per page instead of averaged across a whole-book sample."""

WORD_LIKE_RE = re.compile(r"^[A-Za-z]{2,20}$")
"""A "real" word: purely alphabetic (after stripping surrounding
punctuation), plausible length. Digits, symbol-only tokens, and garbled
glyph runs don't count toward the word-likeness signal. Deliberately
undercounts legitimate single-letter words ("I", "A") for simplicity --
negligible at whole-page aggregate scale."""

STRIP_PUNCTUATION = ".,;:!?\"'()[]{}“”‘’—-*"

SUSPICIOUS_CHAR_RE = re.compile(r"[�-]")
"""Unicode replacement character, or private-use-area codepoints -- neither
should appear in a properly-decoded PDF text stream."""

CHAR_COUNT_WEIGHT = 0.4
VALIDITY_WEIGHT = 0.3
WORD_LIKENESS_WEIGHT = 0.3
SUSPICIOUS_CHAR_PENALTY_MULTIPLIER = 10.0
"""Even a low percentage of suspicious characters is a strong corruption
signal (unlike word-likeness, where some variance from numbers/citations/
proper nouns is normal) -- amplified so a handful of replacement characters
meaningfully drags the score down rather than barely registering."""

DEFAULT_OCR_THRESHOLD = 0.5


def score_page_quality(page: PageData) -> float:
    """Returns a 0.0-1.0 confidence score that this page's existing
    `TextBlock`s came from a genuinely usable text layer. Does not itself
    decide whether to route to OCR -- see `needs_ocr_for_page`."""
    text_blocks = [b for b in page.blocks if isinstance(b, TextBlock)]
    full_text = "".join(b.text for b in text_blocks)

    char_score = min(len(full_text) / MIN_CHARS_FOR_USABLE_PAGE, 1.0) if full_text else 0.0
    validity_score = _validity_score(full_text)
    word_score = _word_likeness_score(full_text)

    return (
        char_score * CHAR_COUNT_WEIGHT
        + validity_score * VALIDITY_WEIGHT
        + word_score * WORD_LIKENESS_WEIGHT
    )


def needs_ocr_for_page(score: float, threshold: float = DEFAULT_OCR_THRESHOLD) -> bool:
    return score < threshold


def _validity_score(text: str) -> float:
    if not text:
        return 0.0
    suspicious_count = len(SUSPICIOUS_CHAR_RE.findall(text))
    penalty = (suspicious_count / len(text)) * SUSPICIOUS_CHAR_PENALTY_MULTIPLIER
    return max(1.0 - penalty, 0.0)


def _word_likeness_score(text: str) -> float:
    tokens = [t for t in text.split() if t]
    if not tokens:
        return 0.0
    word_like_count = sum(1 for t in tokens if WORD_LIKE_RE.match(t.strip(STRIP_PUNCTUATION)))
    return word_like_count / len(tokens)
