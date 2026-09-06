"""Rule 9.6 — Structured Glossary Processing.

Detects term-definition pairs in back-matter Glossary sections and structures
them into clean GlossaryItem and GlossaryBlock models.

Implements:
- Font-styling signal: bold terms (is_bold=True) followed by normal-weight definitions.
- Syntactic delimiter signal: "Term: Definition", "Term — Definition", "Term – Definition".
- Geometric signal: hanging indents (flush term at baseline_x0 with indented definition lines).
- Letter dividers: single-letter headings ("A", "B", "— C —", "Section D") preserved as
  level-2 markdown sub-headings.
- Inline marker preservation: footnote, endnote, and citation sentinels preserved within
  definitions.
- Introductory prose preservation: leading text before the first term remains regular Paragraphs.
- Graceful fallback: non-glossary or unrecognized text cleanly degrades to standard paragraphs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from mdook.core.models import (
    GlossaryBlock,
    GlossaryItem,
    Section,
    SectionContent,
    TextBlock,
)
from mdook.core.rules import citations as citation_rules
from mdook.core.rules.paragraphs import (
    ENDNOTE_MARKER_SENTINEL,
    FOOTNOTE_MARKER_SENTINEL,
    _join,
)

if TYPE_CHECKING:
    from mdook.core.rules.footnotes import FootnoteDetectionResult

GLOSSARY_TITLES = {
    "glossary",
    "definitions",
    "glossary of terms",
    "terms and definitions",
    "terms & definitions",
    "vocabulary",
    "list of terms",
    "terminology",
}

LETTER_HEADING_RE = re.compile(
    r"^(?:—\s*|–\s*|-+\s*|\[|\()?([A-Z])(?:\]|\))?(?:\s*—|\s*–|\s*-+|\.)?$"
)
LETTER_WORD_HEADING_RE = re.compile(r"^(?:letter|section)\s+([A-Z])$", re.IGNORECASE)

TERM_DELIM_RE = re.compile(r"^([A-Za-z0-9\(\[\"'][^:—–\n\r]{0,60}?)\s*(?::|—|–|-)\s+(.+)$")

STOPWORDS = {
    "in",
    "if",
    "when",
    "because",
    "although",
    "while",
    "as",
    "after",
    "before",
    "since",
    "note",
    "recall",
    "for",
    "we",
    "the",
    "this",
    "these",
    "those",
    "however",
    "therefore",
    "furthermore",
    "moreover",
}

MAX_TERM_WORDS = 8
MAX_TERM_LENGTH = 60
HANGING_INDENT_THRESHOLD = 7.0


def is_glossary_title(title: str | None) -> bool:
    """True if title matches a known glossary section heading."""
    if not title:
        return False
    normalized = " ".join(title.strip().lower().split()).rstrip(".:")
    return normalized in GLOSSARY_TITLES


def parse_letter_heading(text: str) -> str | None:
    """Returns the uppercase single letter if text represents an alphabetical divider, else None."""
    stripped = text.strip()
    if not stripped or len(stripped) > 15:
        return None
    m = LETTER_HEADING_RE.match(stripped)
    if m:
        return m.group(1).upper()
    m = LETTER_WORD_HEADING_RE.match(stripped)
    if m:
        return m.group(1).upper()
    return None


def clean_term(raw_term: str) -> str:
    """Strips leading/trailing punctuation and markdown markers from candidate term."""
    term = raw_term.strip().strip("*_").strip()
    term = term.rstrip(" :—-–.")
    return " ".join(term.split())


def clean_definition_start(raw_def: str) -> str:
    """Strips leading delimiters and whitespace from definition beginning."""
    stripped = raw_def.lstrip(" :—-–.")
    return stripped.strip()


def _match_term_delimiter(text: str) -> tuple[str, str] | None:
    """Attempts to match a term and definition separator (colon, em-dash, en-dash, hyphen)."""
    stripped = text.strip()
    match = TERM_DELIM_RE.match(stripped)
    if not match:
        return None
    term_candidate = match.group(1).strip()
    def_candidate = match.group(2).strip()
    words = term_candidate.split()
    if not (1 <= len(words) <= MAX_TERM_WORDS) or len(term_candidate) > MAX_TERM_LENGTH:
        return None
    if term_candidate.rstrip().endswith(("?", "!", ";")):
        return None
    if words[0].lower() in STOPWORDS and len(words) > 2:
        return None
    return clean_term(term_candidate), clean_definition_start(def_candidate)


@dataclass
class _ParsedEntry:
    term: str
    definition: str
    page_number: int


def process_glossary_text_run(
    blocks_with_pages: list[tuple[int, TextBlock]],
    footnote_result: FootnoteDetectionResult,
    body_font_size: float | None,
    body_left_margin: float | None,
    body_right_margin: float | None = None,
    bibliography_markers: set[str] | None = None,
) -> tuple[list[SectionContent], list[Section]]:
    """Parses a text run in a Glossary section into structured glossary blocks.

    Returns:
        (intro_content, letter_sections)
        - intro_content: content items (e.g. Paragraphs or flat GlossaryBlocks) for the
          root Glossary section.
        - letter_sections: level-2 Section objects for letter headings (A, B, C...).
    """
    if not blocks_with_pages:
        return [], []

    inline_marker_ids = footnote_result.inline_marker_ids or set()
    endnote_marker_ids = footnote_result.endnote_marker_ids or set()

    # Find minimum left margin for hanging-indent detection
    x0_values = [round(b.bbox[0], 1) for _, b in blocks_with_pages if not b.is_superscript]
    baseline_x0 = min(x0_values) if x0_values else None

    # We will accumulate items partitioned by letter divider
    # Structure: list of (letter_or_None, list[_ParsedEntry])
    letter_clusters: list[tuple[str | None, list[_ParsedEntry]]] = []
    current_letter: str | None = None
    current_entries: list[_ParsedEntry] = []
    intro_blocks: list[tuple[int, TextBlock]] = []

    active_term: str | None = None
    active_def: str | None = None
    active_page: int | None = None

    def flush_active_entry() -> None:
        nonlocal active_term, active_def, active_page
        if active_term is not None:
            full_def = (active_def or "").strip()
            if bibliography_markers:
                full_def = citation_rules.splice_citation_links(full_def, bibliography_markers)
            current_entries.append(
                _ParsedEntry(term=active_term, definition=full_def, page_number=active_page or 1)
            )
            active_term = None
            active_def = None
            active_page = None

    def flush_current_letter() -> None:
        nonlocal current_entries
        flush_active_entry()
        if current_entries:
            letter_clusters.append((current_letter, list(current_entries)))
            current_entries = []

    idx = 0
    n_blocks = len(blocks_with_pages)

    while idx < n_blocks:
        page_num, block = blocks_with_pages[idx]
        text = block.text.strip()

        # Check for inline marker block (e.g. footnote superscript)
        if id(block) in inline_marker_ids or id(block) in endnote_marker_ids:
            if active_term is not None:
                is_fn = id(block) in inline_marker_ids
                sentinel = FOOTNOTE_MARKER_SENTINEL if is_fn else ENDNOTE_MARKER_SENTINEL
                marker_txt = text
                active_def = (active_def or "").rstrip() + sentinel + marker_txt + sentinel
            idx += 1
            continue

        # 1. Letter heading divider check
        letter = parse_letter_heading(text)
        if letter is not None:
            flush_current_letter()
            current_letter = letter
            idx += 1
            continue

        # Is the block roughly flush at left margin?
        is_flush = baseline_x0 is None or (block.bbox[0] <= baseline_x0 + 5.0)

        # 2. Delimiter match on single block (Term: Definition or Term — Definition)
        delim_match = _match_term_delimiter(text)
        if is_flush and delim_match is not None:
            term, def_start = delim_match
            flush_active_entry()
            active_term = term
            active_def = def_start
            active_page = page_num
            idx += 1
            continue

        # 3. Bold term start (typography signal)
        if is_flush and block.is_bold:
            # Collect contiguous bold blocks on same line
            bold_blocks = [block]
            advance = 1
            while idx + advance < n_blocks:
                next_p, next_b = blocks_with_pages[idx + advance]
                if (
                    next_p == page_num
                    and next_b.is_bold
                    and abs(next_b.bbox[1] - block.bbox[1]) < block.font_size * 0.5
                ):
                    bold_blocks.append(next_b)
                    advance += 1
                else:
                    break

            bold_text = " ".join(b.text.strip() for b in bold_blocks)
            words = bold_text.split()
            if (
                1 <= len(words) <= MAX_TERM_WORDS
                and len(bold_text) <= MAX_TERM_LENGTH
                and not bold_text.endswith(("?", "!"))
            ):
                flush_active_entry()
                active_term = clean_term(bold_text)
                active_page = page_num
                idx += advance

                # Check if next block starts definition
                if idx < n_blocks:
                    next_p, next_b = blocks_with_pages[idx]
                    if parse_letter_heading(next_b.text) is None:
                        is_same_line = (
                            next_p == page_num
                            and abs(next_b.bbox[1] - block.bbox[1]) < block.font_size * 0.8
                        )
                        is_next_line = (
                            next_p == page_num
                            and (next_b.bbox[1] - block.bbox[3]) < block.font_size * 1.8
                        )
                        if is_same_line or (is_next_line and not next_b.is_bold):
                            active_def = clean_definition_start(next_b.text)
                            idx += 1
                        else:
                            active_def = ""
                    else:
                        active_def = ""
                else:
                    active_def = ""
                continue

        # 4. Hanging indent outdent geometry (flush term line, indented definition next line)
        if is_flush and idx + 1 < n_blocks and baseline_x0 is not None:
            next_p, next_b = blocks_with_pages[idx + 1]
            if (
                next_p == page_num
                and (next_b.bbox[0] - baseline_x0) >= HANGING_INDENT_THRESHOLD
                and parse_letter_heading(next_b.text) is None
            ):
                words = text.split()
                if (
                    1 <= len(words) <= MAX_TERM_WORDS
                    and len(text) <= MAX_TERM_LENGTH
                    and not text.endswith((".", "?", "!", ";"))
                ):
                    flush_active_entry()
                    active_term = clean_term(text)
                    active_def = clean_definition_start(next_b.text)
                    active_page = page_num
                    idx += 2
                    continue

        # If an entry is currently active, this line is a continuation of its definition
        if active_term is not None:
            active_def = _join(active_def or "", text)
            idx += 1
            continue

        # Otherwise, block appears before any entry / letter divider (introductory text)
        intro_blocks.append((page_num, block))
        idx += 1

    flush_current_letter()

    total_entries = sum(len(entries) for _, entries in letter_clusters)

    # Fallback guard: if 0 entries detected (or 1 entry amid many intro blocks),
    # treat as standard text rather than corrupting structure.
    if total_entries == 0 or (total_entries == 1 and len(intro_blocks) >= 4):
        from mdook.core.stages.semantic import _content_items_from_text_run

        return _content_items_from_text_run(
            blocks_with_pages,
            footnote_result,
            body_font_size,
            body_left_margin,
            body_right_margin,
            bibliography_markers,
        ), []

    # Build intro content
    intro_content: list[SectionContent] = []
    if intro_blocks:
        from mdook.core.stages.semantic import _content_items_from_text_run

        intro_content = _content_items_from_text_run(
            intro_blocks,
            footnote_result,
            body_font_size,
            body_left_margin,
            body_right_margin,
            bibliography_markers,
        )

    # Check if we have letter dividers
    has_letters = any(letter is not None for letter, _ in letter_clusters)

    if not has_letters:
        # Flat glossary: group entries by contiguous page number into GlossaryBlocks
        flat_entries = [entry for _, entries in letter_clusters for entry in entries]
        intro_content.extend(_group_entries_into_blocks(flat_entries))
        return intro_content, []

    # Letter-divided glossary: each letter becomes a level-2 Section
    letter_sections: list[Section] = []
    for letter, entries in letter_clusters:
        blocks = _group_entries_into_blocks(entries)
        if letter is None:
            intro_content.extend(blocks)
        else:
            letter_sections.append(
                Section(
                    title=letter,
                    level=2,
                    content=list(blocks),
                )
            )

    return intro_content, letter_sections


def _group_entries_into_blocks(entries: list[_ParsedEntry]) -> list[GlossaryBlock]:
    """Groups entries into GlossaryBlock instances by contiguous page number."""
    if not entries:
        return []

    blocks: list[GlossaryBlock] = []
    current_page: int | None = None
    current_items: list[GlossaryItem] = []

    for entry in entries:
        if current_page is None:
            current_page = entry.page_number
            current_items.append(
                GlossaryItem(
                    term=entry.term,
                    definition=entry.definition,
                    page_number=entry.page_number,
                )
            )
        elif entry.page_number == current_page:
            current_items.append(
                GlossaryItem(
                    term=entry.term,
                    definition=entry.definition,
                    page_number=entry.page_number,
                )
            )
        else:
            blocks.append(GlossaryBlock(items=current_items, page_number=current_page))
            current_page = entry.page_number
            current_items = [
                GlossaryItem(
                    term=entry.term,
                    definition=entry.definition,
                    page_number=entry.page_number,
                )
            ]

    if current_items and current_page is not None:
        blocks.append(GlossaryBlock(items=current_items, page_number=current_page))

    return blocks
