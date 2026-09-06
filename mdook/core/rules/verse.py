"""Rule 9.2 — Poetry / Verse Detection.

Implements Rule 9.2 from `Mdook-docs/RULES.md`:
- Condition: Multiple short lines (< 50-65 chars each) with irregular right
  margins, not matching body text flow. Often indented or centered.
- Action: Preserve line breaks exactly. Do not merge into prose paragraphs.
  Render with two trailing spaces per line (markdown hard line break) and
  preserve stanza breaks. If indented or quoted, render with blockquote markers.

Pulls consecutive verse lines out of the stream of text blocks BEFORE
Rule 5.1's same-style paragraph continuation joins them into flowing prose,
which would destroy poetic lineation and stanza structure.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from mdook.core.models import TextBlock, VerseBlock
from mdook.core.rules.paragraphs import (
    ENDNOTE_MARKER_SENTINEL,
    FOOTNOTE_MARKER_SENTINEL,
    LINE_HEIGHT_MULTIPLIER,
    _same_style,
)
from mdook.core.rules.scripts import is_caseless_text

MAX_VERSE_LINE_LENGTH = 65
"""Rule 9.2: verse lines are characteristically short (< 50 chars typically;
allowing up to 65 for long meters like hexameter or alexandrine)."""

MAX_AVG_VERSE_LINE_LENGTH = 52
"""The mean line length across a candidate stanza must be short -- ordinary
prose lines in books average 65-90+ characters."""

MIN_VERSE_LINES = 3
"""Minimum number of lines to qualify as an unindented verse stanza."""

MIN_COUPLET_LINES = 2
"""A 2-line stanza (couplet) is recognized if indented or showing strong
poetic lineation signals."""

MIN_UPPERCASE_START_RATIO = 0.60
"""In poetry, most lines begin with a capital letter (even across enjambment),
unlike wrapped prose where continuation lines begin with lowercase."""

STANZA_GAP_MULTIPLIER = 1.4
"""A vertical gap between blocks larger than this multiple of line height
is treated as a stanza break rather than adjacent lines in the same stanza."""

MAX_STANZA_GAP_MULTIPLIER = 3.5
"""A vertical gap larger than this multiple of line height is treated as a
major section/paragraph boundary, not a stanza break within the same poem."""

ATTRIBUTION_RE = re.compile(r"^[\s—–~·•-]{1,3}\s*([A-Za-z0-9\(\[\"'].*)$")
ATTRIBUTION_PAREN_RE = re.compile(r"^\(([A-Za-z0-9\s.,'\"—–-]+)\)$")

DIALOGUE_PREFIXES = ('"', "'", "“", "”", "‘", "’", "«", "»")
DIALOGUE_VERBS_RE = re.compile(
    r"\b(said|asked|replied|whispered|shouted|exclaimed|answered|cried|muttered|yelled)\b",
    re.IGNORECASE,
)


@dataclass
class _LineInfo:
    page_number: int
    block: TextBlock
    raw_blocks: list[tuple[int, TextBlock]]
    text: str


def _looks_like_dialogue_line(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    has_quote = stripped.startswith(DIALOGUE_PREFIXES) or stripped.endswith(DIALOGUE_PREFIXES)
    has_speech_verb = bool(DIALOGUE_VERBS_RE.search(stripped))
    return has_quote and has_speech_verb


def _is_attribution_line(text: str) -> str | None:
    stripped = text.strip()
    if not stripped or len(stripped.split()) > 15:
        return None
    match = ATTRIBUTION_RE.match(stripped)
    if match:
        return match.group(1).strip()
    match_paren = ATTRIBUTION_PAREN_RE.match(stripped)
    if match_paren:
        return match_paren.group(1).strip()
    return None


def is_verse_stanza(
    cluster: list[_LineInfo],
    body_font_size: float | None = None,
    body_left_margin: float | None = None,
    body_right_margin: float | None = None,
) -> bool:
    """Checks whether a group of vertically adjacent lines forms a verse stanza."""
    if len(cluster) < 2:
        return False

    texts = [line.text.strip() for line in cluster if line.text.strip()]
    if len(texts) < 2:
        return False

    # 1. Dialogue check -- dialogue exchanges with speech attribution are not poetry
    if any(_looks_like_dialogue_line(t) for t in texts):
        return False

    # Definition / glossary list check -- lines formatted as "Term: Definition" are not verse
    definition_matches = sum(1 for t in texts if bool(re.match(r"^[^:]{1,30}:\s+\S", t)))
    if definition_matches >= 2 or (len(texts) == 2 and definition_matches == 2):
        return False

    # 2. Line lengths
    lengths = [len(t) for t in texts]
    if any(length > MAX_VERSE_LINE_LENGTH for length in lengths):
        return False
    avg_len = sum(lengths) / len(lengths)
    if avg_len > MAX_AVG_VERSE_LINE_LENGTH:
        return False

    # 3. Capitalization / script case
    joined_text = " ".join(texts)
    caseless = is_caseless_text(joined_text)

    upper_count = sum(1 for t in texts if t[0].isupper())
    upper_ratio = upper_count / len(texts)

    # 4. Check indentation
    is_indented = False
    if body_left_margin is not None and body_font_size is not None:
        min_indent = body_font_size * 1.2
        avg_x0 = sum(line.block.bbox[0] for line in cluster) / len(cluster)
        if avg_x0 > body_left_margin + min_indent:
            is_indented = True

    # 5. Terminal punctuation check:
    # In poetry, lines rarely all end with terminal punctuation ('.', '?', '!').
    # Sentences span across lines via enjambment. A block where most lines end with
    # periods is a sequence of discrete prose sentences, not poetic lines.
    terminal_count = sum(1 for t in texts if t.endswith((".", "?", "!")))
    if len(texts) >= 3 and (terminal_count / len(texts)) > 0.50:
        return False
    if len(texts) == 2 and not is_indented and terminal_count == 2:
        return False

    if not caseless:
        if len(texts) >= MIN_VERSE_LINES:
            min_upper = 0.45 if is_indented else MIN_UPPERCASE_START_RATIO
            if upper_ratio < min_upper:
                return False
        else:  # Couplet (2 lines)
            if not is_indented and upper_ratio < 1.0:
                return False
            if any(length > 55 for length in lengths):
                return False

    # 6. Right margin check
    if body_right_margin is not None:
        reaching = sum(1 for line in cluster if line.block.bbox[2] >= body_right_margin - 20.0)
        if reaching > 1 or (len(cluster) >= 3 and reaching / len(cluster) > 0.30):
            return False
    else:
        x1_vals = [line.block.bbox[2] for line in cluster]
        x1_span = max(x1_vals) - min(x1_vals)
        if x1_span < 8.0 and avg_len > 40:
            return False

    # 7. Left margin alignment
    x0_vals = [line.block.bbox[0] for line in cluster]
    if max(x0_vals) - min(x0_vals) > 60.0:
        return False

    return True


def _is_short_verse_continuation(cluster: list[_LineInfo], prev_cluster: list[_LineInfo]) -> bool:
    """Checks whether a short 1-2 line cluster continues an already active poem."""
    if len(cluster) > 2:
        return False
    if any(_looks_like_dialogue_line(item.text) for item in cluster):
        return False
    if any(len(item.text.strip()) > MAX_VERSE_LINE_LENGTH for item in cluster):
        return False
    if not _same_style(prev_cluster[-1].block, cluster[0].block):
        return False
    if abs(cluster[0].block.bbox[0] - prev_cluster[0].block.bbox[0]) > 8.0:
        return False
    return True


def _group_into_lines(
    blocks_with_pages: list[tuple[int, TextBlock]],
    inline_marker_ids: set[int],
    endnote_marker_ids: set[int],
) -> list[_LineInfo]:
    lines: list[_LineInfo] = []
    for page_number, block in blocks_with_pages:
        if id(block) in inline_marker_ids or id(block) in endnote_marker_ids:
            if lines:
                is_footnote = id(block) in inline_marker_ids
                sentinel = FOOTNOTE_MARKER_SENTINEL if is_footnote else ENDNOTE_MARKER_SENTINEL
                marker_text = block.text.strip()
                lines[-1].text = lines[-1].text.rstrip() + sentinel + marker_text + sentinel
                lines[-1].raw_blocks.append((page_number, block))
            else:
                lines.append(
                    _LineInfo(
                        page_number=page_number,
                        block=block,
                        raw_blocks=[(page_number, block)],
                        text=block.text,
                    )
                )
        else:
            lines.append(
                _LineInfo(
                    page_number=page_number,
                    block=block,
                    raw_blocks=[(page_number, block)],
                    text=block.text,
                )
            )
    return lines


def _cluster_lines(lines: list[_LineInfo]) -> list[tuple[str, list[_LineInfo]]]:
    """Clusters lines into (boundary_type, cluster_lines)."""
    if not lines:
        return []

    clusters: list[tuple[str, list[_LineInfo]]] = []
    current_cluster: list[_LineInfo] = [lines[0]]
    current_boundary = "start"

    for i in range(1, len(lines)):
        prev_line = lines[i - 1]
        curr_line = lines[i]

        if curr_line.page_number != prev_line.page_number:
            clusters.append((current_boundary, current_cluster))
            current_cluster = [curr_line]
            current_boundary = "page_break"
            continue

        line_height = (prev_line.block.font_size or 10.0) * LINE_HEIGHT_MULTIPLIER
        vertical_gap = curr_line.block.bbox[1] - prev_line.block.bbox[3]

        if vertical_gap <= line_height * STANZA_GAP_MULTIPLIER and _same_style(
            prev_line.block, curr_line.block
        ):
            current_cluster.append(curr_line)
        else:
            clusters.append((current_boundary, current_cluster))
            current_cluster = [curr_line]
            if vertical_gap <= line_height * MAX_STANZA_GAP_MULTIPLIER and _same_style(
                prev_line.block, curr_line.block
            ):
                current_boundary = "stanza_break"
            else:
                current_boundary = "major_break"

    if current_cluster:
        clusters.append((current_boundary, current_cluster))

    return clusters


def _build_verse_block(
    poem_clusters: list[list[_LineInfo]],
    attribution: str | None,
    body_font_size: float | None,
    body_left_margin: float | None,
) -> VerseBlock:
    lines: list[str] = []
    all_blocks: list[TextBlock] = []
    first_page = poem_clusters[0][0].page_number

    for idx, cluster in enumerate(poem_clusters):
        if idx > 0:
            lines.append("")  # Blank line between stanzas
        for line in cluster:
            lines.append(line.text.strip())
            all_blocks.append(line.block)

    is_quoted = False
    if body_left_margin is not None and body_font_size is not None and all_blocks:
        avg_x0 = sum(b.bbox[0] for b in all_blocks) / len(all_blocks)
        if avg_x0 > body_left_margin + body_font_size * 1.2:
            is_quoted = True

    return VerseBlock(
        lines=lines,
        page_number=first_page,
        is_quoted=is_quoted,
        attribution=attribution,
    )


def split_verse_runs(
    blocks_with_pages: list[tuple[int, TextBlock]],
    body_font_size: float | None = None,
    body_left_margin: float | None = None,
    body_right_margin: float | None = None,
    inline_marker_ids: set[int] | None = None,
    endnote_marker_ids: set[int] | None = None,
) -> list[tuple[str, list[tuple[int, TextBlock]] | VerseBlock]]:
    """Splits a run of raw text blocks into alternating ("text", blocks) and
    ("verse", VerseBlock) sub-runs, preserving original order.

    Consecutive verse stanzas belonging to the same poem are merged into a
    single `VerseBlock` with blank-line stanza separators and optional
    attribution.
    """
    if not blocks_with_pages:
        return []

    inline_marker_ids = inline_marker_ids or set()
    endnote_marker_ids = endnote_marker_ids or set()

    lines = _group_into_lines(blocks_with_pages, inline_marker_ids, endnote_marker_ids)
    clusters = _cluster_lines(lines)

    i = 0
    text_buffer: list[tuple[int, TextBlock]] = []
    sub_runs: list[tuple[str, list[tuple[int, TextBlock]] | VerseBlock]] = []

    def flush_text() -> None:
        if text_buffer:
            sub_runs.append(("text", list(text_buffer)))
            text_buffer.clear()

    while i < len(clusters):
        _, cluster = clusters[i]

        if is_verse_stanza(cluster, body_font_size, body_left_margin, body_right_margin):
            flush_text()

            poem_clusters = [cluster]
            attribution: str | None = None
            i += 1

            while i < len(clusters):
                next_boundary, next_cluster = clusters[i]

                # Check for trailing attribution line in a separate cluster
                if len(next_cluster) == 1 and poem_clusters:
                    prev_last_line = poem_clusters[-1][-1]
                    if next_cluster[0].page_number == prev_last_line.page_number:
                        line_height = (
                            prev_last_line.block.font_size or 10.0
                        ) * LINE_HEIGHT_MULTIPLIER
                        gap = next_cluster[0].block.bbox[1] - prev_last_line.block.bbox[3]
                        if 0 <= gap <= line_height * 4.0:
                            attr = _is_attribution_line(next_cluster[0].text)
                            if attr is not None:
                                attribution = attr
                                i += 1
                                break

                # Check if next cluster continues the poem
                if next_boundary in ("stanza_break", "page_break"):
                    if is_verse_stanza(
                        next_cluster, body_font_size, body_left_margin, body_right_margin
                    ):
                        poem_clusters.append(next_cluster)
                        i += 1
                        continue
                    if _is_short_verse_continuation(next_cluster, poem_clusters[-1]):
                        poem_clusters.append(next_cluster)
                        i += 1
                        continue

                break

            # If attribution wasn't in a separate cluster, check if it was grouped
            # as the final line of the last stanza cluster.
            if attribution is None and poem_clusters:
                last_cluster = poem_clusters[-1]
                if len(last_cluster) >= 2:
                    attr = _is_attribution_line(last_cluster[-1].text)
                    if attr is not None:
                        total_lines = sum(len(c) for c in poem_clusters)
                        if total_lines - 1 >= 2:
                            attribution = attr
                            last_cluster.pop()
                        else:
                            # 1-line quote + attribution is prose/blockquote, not verse
                            for c in poem_clusters:
                                for line in c:
                                    text_buffer.extend(line.raw_blocks)
                            continue

            verse_block = _build_verse_block(
                poem_clusters, attribution, body_font_size, body_left_margin
            )
            sub_runs.append(("verse", verse_block))
        else:
            for line in cluster:
                text_buffer.extend(line.raw_blocks)
            i += 1

    flush_text()
    return sub_runs
