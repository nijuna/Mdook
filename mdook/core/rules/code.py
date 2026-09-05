"""Code Block Detection — not in `Mdook-docs/RULES.md`'s original rule
catalog (`Mdook-docs/ROADMAP.md`'s Phase 2 describes it only as "monospaced
font detection -> fenced code blocks", with no rule numbers assigned).

Implements: consecutive text blocks set in a recognizably monospace font
are pulled out of the ordinary paragraph-merge flow and preserved as a
fenced code block with original line breaks intact -- Rule 5.1's
same-style continuation would otherwise join them into flowing prose,
destroying code's line structure and indentation.

Simplification: monospace detection is font-*name* keyword matching, not
per-glyph advance-width measurement (Stage 2's `TextBlock` doesn't carry
per-character positions). This is the same class of heuristic most
PDF-to-markdown tools use. A monospace font renamed to something
unrecognizable by an HTML-to-PDF export (the same failure mode
`mdook.core.stages.extraction._same_style` works around for style
continuity) will simply not be detected as code -- a false negative, not a
false positive, so ordinary prose is never miscategorized as code by this
gap. No language is guessed for the fence (` ``` ` with no tag) since
nothing in the PDF reliably identifies one.
"""

from __future__ import annotations

import re

from mdook.core.models import CodeBlock, TextBlock

MONOSPACE_FONT_KEYWORDS = (
    "courier",
    "consolas",
    "menlo",
    "monaco",
    "mono",
    "sourcecodepro",
    "firacode",
    "inconsolata",
    "dejavusansmono",
    "lucidaconsole",
    "andalemono",
    "robotomono",
    "ibmplexmono",
    "jetbrainsmono",
    "typewriter",
)


def is_monospace_font(font_name: str) -> bool:
    normalized = re.sub(r"[^a-z]", "", font_name.lower())
    return any(keyword in normalized for keyword in MONOSPACE_FONT_KEYWORDS)


def split_code_run(
    blocks_with_pages: list[tuple[int, TextBlock]],
) -> list[tuple[str, list[tuple[int, TextBlock]]]]:
    """Splits a run of raw text blocks into alternating ("text", blocks) and
    ("code", blocks) sub-runs, in original order. Consecutive monospace
    blocks stay grouped as one code block; each keeps its own line rather
    than being joined into a single paragraph-style sentence."""
    sub_runs: list[tuple[str, list[tuple[int, TextBlock]]]] = []
    current_kind: str | None = None
    current: list[tuple[int, TextBlock]] = []

    for page_number, block in blocks_with_pages:
        kind = "code" if is_monospace_font(block.font_name) else "text"
        if current_kind is not None and kind != current_kind:
            sub_runs.append((current_kind, current))
            current = []
        current_kind = kind
        current.append((page_number, block))

    if current and current_kind is not None:
        sub_runs.append((current_kind, current))
    return sub_runs


def build_code_block(blocks_with_pages: list[tuple[int, TextBlock]]) -> CodeBlock:
    return CodeBlock(
        lines=[block.text for _, block in blocks_with_pages],
        page_number=blocks_with_pages[0][0],
    )
