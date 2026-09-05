"""Callout / Sidebar Box Detection — Batch 14 (`Mdook-docs/BOOK_ELEMENTS.md`
section 3.3, Tier A). Not in the original `Mdook-docs/RULES.md` catalog.

A paragraph whose own text opens with a recognizable label ("Note:",
"Warning.", ...) is pulled out of the ordinary paragraph flow and rendered
as an Obsidian callout instead of plain prose — see
`mdook.core.stages.semantic._append_paragraph_items`.

MVP signal only: the label text itself, not a vector-drawn box border
around it (`page.get_drawings()`) — real scans make box-border detection a
much noisier signal, and the label convention alone already covers the
common case. Generic across genres — the label set below is a fixed
vocabulary (English only, consistent with this project's other label-based
rules such as `mdook.core.stages.semantic.CHAPTER_LABEL_ONLY_RE`), not tied
to any one subject area.

False-positive guard: requiring the label to be followed immediately by
`:` or `.` (not just any word boundary) is what keeps ordinary prose like
"Note that the results varied" from being misread as a callout — there is
no punctuation directly after "Note" there.
"""

from __future__ import annotations

import re

CALLOUT_LABEL_RE = re.compile(
    r"^(Note|Warning|Tip|Caution|Important|Key Point|Remember)\s*[:.]\s*",
    re.IGNORECASE,
)

_OBSIDIAN_CALLOUT_TYPES = {
    "note": "note",
    "warning": "warning",
    "tip": "tip",
    "caution": "warning",
    "important": "important",
    "key point": "important",
    "remember": "tip",
    # Batch 17 — theorem-like environments (`mdook.core.rules.math`) reuse
    # this same callout machinery. Obsidian renders any callout type name
    # it doesn't specifically recognize with a generic bordered style, so
    # self-mapping each word is enough to get "> [!theorem]", "> [!proof]",
    # etc. without inventing a second box-rendering path.
    "theorem": "theorem",
    "lemma": "lemma",
    "corollary": "corollary",
    "proposition": "proposition",
    "definition": "definition",
    "axiom": "axiom",
    "example": "example",
    "remark": "remark",
    "exercise": "exercise",
    "proof": "proof",
    "claim": "claim",
}


def detect_callout(text: str) -> tuple[str, str] | None:
    """Returns `(label, remaining_text)` if `text` opens with a callout
    label, else None. `label` is the book's own printed word, verbatim."""
    match = CALLOUT_LABEL_RE.match(text)
    if match is None:
        return None
    label = match.group(1)
    remainder = text[match.end() :].strip()
    return label, remainder


def obsidian_callout_type(label: str) -> str:
    """Maps a detected label to one of Obsidian's built-in callout types,
    falling back to a generic "info" callout for an unmapped label. A
    label carrying its own trailing number ("Theorem 3.2", from a theorem
    environment) is matched by its leading word alone once the full label
    doesn't match exactly."""
    normalized = label.strip().lower()
    if normalized in _OBSIDIAN_CALLOUT_TYPES:
        return _OBSIDIAN_CALLOUT_TYPES[normalized]
    words = normalized.split()
    first_word = words[0] if words else normalized
    return _OBSIDIAN_CALLOUT_TYPES.get(first_word, "info")
