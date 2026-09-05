"""Citation-to-Bibliography Linking — Batch 15 (`Mdook-docs/BOOK_ELEMENTS.md`
section 9, Tier A). Not in the original `Mdook-docs/RULES.md` catalog.

Numeric in-text citations ("[1]", "[1, 3]", "[1-4]") are linked to their
matching entry in a back-matter Bibliography/References section, using the
same sentinel-then-Stage-4-resolves-the-link pattern already proven for
endnotes (`mdook.core.rules.footnotes`) — Stage 3 doesn't know Stage 4's
back-matter filename convention, so the actual `[[...]]` wiki-link syntax
is only built once rendering has that name.

Unlike footnote/endnote markers, a numeric citation is ordinary inline
text (a bracketed number sitting inside a normal sentence, not a discrete
superscript `TextBlock`), so detection works directly on already-merged
paragraph text via regex — no separate `TextBlock` correlation step is
needed, unlike `mdook.core.rules.footnotes._correlate_inline_markers`. See
`mdook.core.stages.semantic._append_paragraph_items`.

MVP scope: numeric style only ("[1]", "[1, 3]", "[1-4]"). Author-date style
("(Smith, 2020)") needs fuzzy author/year matching against bibliography
entry text and is a lower-confidence stretch goal, not built here.
"""

from __future__ import annotations

import re

from mdook.core.models import PageData, TextBlock

CITATION_MARKER_SENTINEL = ""
BIBLIOGRAPHY_SECTION_LABELS = frozenset({"bibliography", "references", "works cited"})
ENTRY_MARKER_RE = re.compile(r"^\s*\[?(\d{1,3})[\]\.\):]?\s+")
NUMERIC_CITATION_RE = re.compile(r"\[(\d{1,3}(?:\s*[-,]\s*\d{1,3})*)\]")


def detect_bibliography_markers(back_pages: list[PageData]) -> set[str]:
    """Scans back-matter pages for a Bibliography/References-labeled
    section and collects the entry number of each of its listed works, so
    `splice_citation_links` below can recognize a real reference instead of
    linking every bracketed number that happens to appear in the book."""
    markers: set[str] = set()
    in_bibliography_section = False
    for page in back_pages:
        for block in page.blocks:
            if not isinstance(block, TextBlock):
                continue
            normalized = " ".join(block.text.strip().lower().split()).rstrip(".:")
            if normalized in BIBLIOGRAPHY_SECTION_LABELS:
                in_bibliography_section = True
                continue
            if not in_bibliography_section:
                continue
            match = ENTRY_MARKER_RE.match(block.text)
            if match:
                markers.add(match.group(1))
    return markers


def _expand_numbers(group_text: str) -> list[str]:
    """"1, 3" -> ["1", "3"]; "1-4" -> ["1", "2", "3", "4"]."""
    numbers: list[str] = []
    for part in group_text.split(","):
        part = part.strip()
        if "-" in part:
            start, end = part.split("-", 1)
            numbers.extend(str(n) for n in range(int(start), int(end) + 1))
        elif part:
            numbers.append(part)
    return numbers


def splice_citation_links(text: str, bibliography_markers: set[str]) -> str:
    """Replaces a numeric citation bracket with sentinel-wrapped marker(s)
    when every number inside it matches a known bibliography entry, so
    Stage 4 can turn it into a link. A bracket containing any unmatched
    number (a malformed/incomplete bibliography, or a coincidental
    bracketed number that isn't a citation at all) is left as plain text
    rather than producing a broken or wrong link."""
    if not bibliography_markers:
        return text

    def _replace(match: re.Match[str]) -> str:
        numbers = _expand_numbers(match.group(1))
        if not numbers or any(n not in bibliography_markers for n in numbers):
            return match.group(0)
        linked = ", ".join(
            f"{CITATION_MARKER_SENTINEL}{n}{CITATION_MARKER_SENTINEL}" for n in numbers
        )
        return f"[{linked}]"

    return NUMERIC_CITATION_RE.sub(_replace, text)
