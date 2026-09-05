"""Stage 3 — Semantic Analysis.

Input: `mdook.core.models.BookManifest` + `list[mdook.core.models.PageData]`.
Output: `mdook.core.models.DocumentTree`.

Orchestrates, in order:
1. Drop-cap immunity (Rule 2.5) — before heading detection sees the blocks.
2. Footnote detection (Rules 4.1-4.2) — before paragraph merging sees them.
3. Zone split (Rule 1.*, already computed in Stage 1) — for the font-
   clustering heading path only (Rule 2.2 scopes clustering to the body
   zone; the bookmark path is left whole-book, since Rule 2.1 already
   trusts bookmarks completely and zones don't enter into it).
4. Heading detection (Rules 2.1-2.4) -> chapter-tier selection -> chapter
   number/title merge -> chapter segmentation, with every other detected
   heading tier nested inside its chapter as a sub-`Section` (Rule 2.6).
5. Per chapter: printed-TOC discard (Rule 9.4), decorative-element filtering
   (Rule 9.5), epigraph extraction (Rule 9.1), image association (basic —
   no caption search yet), then paragraph merging (Rules 5.1-5.4) on the
   text runs between images and sub-headings.
6. Front/back matter (Rules 1.2-1.3's keyword list doubles as a section-title
   signal here): whatever front/back-zone pages weren't already claimed by a
   chapter get split into named `Section`s the same way, instead of vanishing
   from the vault entirely.

Rules 9.1, 9.4, and 9.5 have no dedicated rule module in
`Mdook-docs/ARCHITECTURE.md`'s documented source tree, so they live here as
Stage 3 glue rather than inventing an undocumented `rules/special.py`.

Not implemented yet (later sprints/phases per `Mdook-docs/ROADMAP.md`):
- Caption association / decorative-image filtering (Rules 7.3-7.4, Phase 2)
- Table extraction (Phase 2+)
- Endnote-style footnotes (Rules 4.3-4.4, Phase 2)
- AI structure review (Phase 4)
"""

from __future__ import annotations

import re
from collections import Counter

from mdook.core.llm import (
    LLMConfig,
    OpenAICompatibleClient,
    StructureReviewResult,
    run_structure_review,
)
from mdook.core.models import (
    BlockQuote,
    BookManifest,
    BookMetadata,
    CalloutBlock,
    Chapter,
    DocumentTree,
    Footnote,
    ImageBlock,
    ImageRef,
    MathBlock,
    PageData,
    Paragraph,
    Section,
    SectionContent,
    TableBlock,
    TableData,
    TextBlock,
    ZoneEntry,
)
from mdook.core.rules import callouts as callout_rules
from mdook.core.rules import citations as citation_rules
from mdook.core.rules import code as code_rules
from mdook.core.rules import footnotes as footnote_rules
from mdook.core.rules import headings as heading_rules
from mdook.core.rules import images as image_rules
from mdook.core.rules import lists as list_rules
from mdook.core.rules import math as math_rules
from mdook.core.rules import tables as table_rules
from mdook.core.rules.footnotes import FootnoteDetectionResult
from mdook.core.rules.headings import Heading
from mdook.core.rules.paragraphs import MergedParagraph, find_body_left_margin, merge_text_blocks

MIN_HEADINGS_FOR_CHAPTER_TIER = 2
MAX_EPIGRAPH_WORDS = 40
TOC_LINE_RE = re.compile(r"^.{3,80}?[.\s]{2,}\d{1,4}$")
MIN_TOC_LINES = 3
MIN_TOC_TITLE_MATCH_LENGTH = 4
"""A heading title shorter than this (after normalization) is too generic
to safely use as a TOC-page cross-reference signal -- a single character
can substring-match almost any page's text."""
DECORATIVE_RE = re.compile(r"^[\s§*❧◆•~×\-—–]{1,5}$")
BLOCK_QUOTE_INDENT_RATIO = 1.5
"""Rule 9.3: a paragraph indented more than this many multiples of the body
font size past the book's ordinary left margin is a block quote, not an
ordinary paragraph."""
BLOCK_QUOTE_MAX_INDENT_RATIO = 6.0
"""An indent past this many multiples of body font size is no longer a
plausible block-quote margin -- found via real-book testing: a sidebar or
right-hand column of reader-testimonial text (which Rule 8's multi-column
handling doesn't exist yet to place correctly) can land x0 hundreds of
points into the page, which the plain indent check alone would misread as
an extremely-indented quote rather than what it actually is."""
MIN_BLOCK_QUOTE_WORDS = 4
"""A 1-3 word "paragraph" this indented is far more likely to be leftover
marker/caption debris than a genuine quotation -- Rule 9.3 also specifies
a quote spans multiple lines, which a handful of words rarely does."""

_ROMAN_NUMERAL_RE = r"(?=[MDCLXVI])M{0,4}(?:CM|CD|D?C{0,3})(?:XC|XL|L?X{0,3})(?:IX|IV|V?I{0,3})"
CHAPTER_LABEL_ONLY_RE = re.compile(
    rf"^(?:chapter|ch\.?|part|section|book|no\.?|number)?\s*(?:{_ROMAN_NUMERAL_RE}|\d+)\.?$",
    re.IGNORECASE,
)
MAX_TITLE_MERGE_WORDS = 12
MAX_TITLE_MERGE_GAP_RATIO = 4.0

FRONT_MATTER_LABELS = (
    "preface",
    "foreword",
    "dedication",
    "acknowledgments",
    "acknowledgements",
    "introduction",
    "prologue",
    "note to the reader",
)
BACK_MATTER_LABELS = (
    "glossary",
    "bibliography",
    "references",
    "works cited",
    "index",
    "appendix",
    "notes",
    "endnotes",
    "about the author",
    "afterword",
    "epilogue",
)
MAX_MATTER_LABEL_WORDS = 4


def run_semantic(
    manifest: BookManifest,
    pages: list[PageData],
    llm_config: LLMConfig | None = None,
    llm_client: OpenAICompatibleClient | None = None,
) -> DocumentTree:
    review_result = StructureReviewResult(attempted=False)

    if not pages:
        metadata = BookMetadata(title=manifest.title, author=manifest.author)
        return DocumentTree(metadata=metadata, chapters=[])

    body_font_size = heading_rules.find_body_font_size(pages)
    body_left_margin = find_body_left_margin(pages)
    heading_rules.merge_drop_caps(pages, body_font_size)  # Rule 2.5

    front_pages, body_pages, back_pages = _split_zones(pages, manifest.zone_map)
    endnote_markers = footnote_rules.detect_endnote_markers(back_pages)  # Rule 4.3
    footnote_result = footnote_rules.detect_footnotes(
        pages, body_font_size, frozenset(endnote_markers)
    )  # Rules 4.1-4.2
    bibliography_markers = citation_rules.detect_bibliography_markers(back_pages)  # Batch 15

    is_bookmark_based = (
        manifest.bookmarks is not None
        and len(manifest.bookmarks) >= heading_rules.MIN_BOOKMARKS_TO_TRUST
    )

    if is_bookmark_based:
        # Rule 2.1: bookmarks are authoritative and already whole-book scoped.
        heading_pages = pages
        clustering_font_size = body_font_size
    else:
        # Rule 2.2: scope clustering to the body zone so a decorative
        # cover/title-page font doesn't dominate the tier histogram and
        # starve real chapter headings of a slot.
        heading_pages = body_pages or pages
        clustering_font_size = heading_rules.find_body_font_size(heading_pages) or body_font_size

    headings = heading_rules.detect_headings(
        manifest, heading_pages, body_font_size=clustering_font_size
    )

    llm_part_headings: list[Heading] = []
    if llm_config and llm_config.enabled:
        headings, llm_part_headings, review_result = run_structure_review(
            headings, pages, manifest, llm_config, client=llm_client
        )

    pages_by_number = {page.page_number: page for page in pages}

    chapter_level = 1 if is_bookmark_based else _pick_chapter_tier(headings)

    chapter_headings = sorted(
        (h for h in headings if h.level == chapter_level), key=lambda h: h.page_number
    )
    chapter_headings = _deduplicate_same_page_headings(chapter_headings)
    chapter_headings = _merge_chapter_number_titles(
        chapter_headings, pages_by_number, clustering_font_size
    )

    # A block absorbed into a chapter title (Rule 2.6 merge, above) must not
    # also survive as its own empty sub-heading -- it was originally detected
    # as a heading candidate in its own right, one tier below chapter_level.
    consumed_ids = {id(h.extra_block) for h in chapter_headings if h.extra_block is not None}
    subheading_pool = [h for h in headings if id(h.block) not in consumed_ids]

    # Batch 14: a Part/Book/Volume tier, only meaningful when font-clustering
    # picked chapter_level itself -- see `_pick_part_tier`.
    part_headings: list[Heading] = list(llm_part_headings)
    if not is_bookmark_based:
        part_level = _pick_part_tier(headings, chapter_level)
        if part_level is not None:
            for h in sorted(
                (h for h in headings if h.level == part_level), key=lambda h: h.page_number
            ):
                if h not in part_headings:
                    part_headings.append(h)

    heading_titles = [h.title for h in chapter_headings]
    segmentation_pages = pages if is_bookmark_based else heading_pages
    if chapter_headings:
        chapters = _segment_chapters(
            chapter_headings,
            segmentation_pages,
            footnote_result,
            heading_titles,
            chapter_level,
            subheading_pool,
            body_font_size,
            body_left_margin,
            part_headings,
            bibliography_markers,
        )
    else:
        # No tier reached chapter status at all -- nest whatever headings
        # were found under a single "Untitled" chapter instead of discarding
        # them, rebased so the shallowest one found becomes the first level.
        baseline = min((h.level for h in subheading_pool), default=chapter_level)
        chapters = [
            _build_single_chapter(
                segmentation_pages,
                footnote_result,
                heading_titles,
                subheading_pool,
                baseline - 1,
                body_font_size,
                body_left_margin,
                bibliography_markers,
            )
        ]

    # Whatever front/back-zone pages a chapter didn't already claim (e.g. a
    # "Preface" bookmark that became its own chapter) get preserved as named
    # sections instead of silently vanishing from the vault.
    covered_pages = {
        page_number
        for chapter in chapters
        for start, end in chapter.page_spans
        for page_number in range(start, end + 1)
    }
    front_matter = _collect_matter_sections(
        [p for p in front_pages if p.page_number not in covered_pages],
        footnote_result,
        heading_titles,
        FRONT_MATTER_LABELS,
        "front",
        body_font_size,
        body_left_margin,
        bibliography_markers,
    )
    back_matter = _collect_matter_sections(
        [p for p in back_pages if p.page_number not in covered_pages],
        footnote_result,
        heading_titles,
        BACK_MATTER_LABELS,
        "back",
        body_font_size,
        body_left_margin,
        bibliography_markers,
    )

    metadata = BookMetadata(
        title=manifest.title,
        author=manifest.author,
        extra={"llm_review": review_result.model_dump()} if review_result.attempted else {},
    )
    return DocumentTree(
        metadata=metadata, front_matter=front_matter, chapters=chapters, back_matter=back_matter
    )


def _split_zones(
    pages: list[PageData], zone_map: list[ZoneEntry]
) -> tuple[list[PageData], list[PageData], list[PageData]]:
    """Splits `pages` into (front_matter, body, back_matter) per Stage 1's
    zone detection. Falls back to treating every page as body when no zones
    were detected, or when a zone map exists but leaves no page tagged
    "body" at all -- either way, no page should silently disappear from
    heading/chapter processing because of this split."""

    def pages_in(zone_type: str) -> list[PageData]:
        ranges = [(z.start_page, z.end_page) for z in zone_map if z.zone_type == zone_type]
        return [p for p in pages if any(start <= p.page_number <= end for start, end in ranges)]

    if not zone_map:
        return [], pages, []

    front_pages = pages_in("front_matter")
    back_pages = pages_in("back_matter")
    body_pages = pages_in("body")
    if not body_pages:
        claimed = {p.page_number for p in front_pages} | {p.page_number for p in back_pages}
        body_pages = [p for p in pages if p.page_number not in claimed]

    return front_pages, body_pages, back_pages


PART_LABEL_RE = re.compile(r"^(?:part|book|volume)\b", re.IGNORECASE)
"""Batch 14: whether a tier is a Part/Book/Volume division rather than the
chapter tier itself can't be told apart from occurrence counts alone -- "2
Parts, 4 Chapters" and "4 Chapters, 40 Subheadings" both look like "a
smaller-count tier sitting above a larger-count one." The one reliable
signal left is the heading's own text, gated on the same English-keyword
convention `CHAPTER_LABEL_ONLY_RE` already relies on elsewhere in this
module for chapter-label detection."""


def _looks_like_part_tier(level_headings: list[Heading]) -> bool:
    if not level_headings:
        return False
    matches = sum(1 for h in level_headings if PART_LABEL_RE.match(h.title.strip()))
    return matches / len(level_headings) >= 0.5


def _pick_chapter_tier(headings: list[Heading]) -> int:
    """Font-size tiers are ranked globally by size (1 = largest), but the
    tier that actually functions as "chapter heading" varies per book: some
    reserve the single largest size for a one-off cover title or a stray
    oversized folio number, leaving every real chapter title one tier down.
    Blindly segmenting on tier 1 in that case finds ~1 bogus "chapter" and
    dumps the entire rest of the book into it. Pick the smallest (most
    heading-like) tier with enough occurrences to plausibly be real chapter
    structure, falling back to tier 1 if nothing qualifies.

    A tier that clears the occurrence bar but reads as Part/Book/Volume
    labels (`_looks_like_part_tier`) is skipped rather than picked -- it's
    a real division, just one level above chapters, not the chapter tier
    itself (Batch 14; see `_pick_part_tier` below)."""
    counts = Counter(h.level for h in headings)
    for level in sorted(counts):
        if counts[level] < MIN_HEADINGS_FOR_CHAPTER_TIER:
            continue
        if _looks_like_part_tier([h for h in headings if h.level == level]):
            continue
        return level
    return 1


def _pick_part_tier(headings: list[Heading], chapter_level: int) -> int | None:
    """Batch 14: a font-size tier *above* `chapter_level` (i.e. a lower,
    more prominent level number) with at least `MIN_HEADINGS_FOR_CHAPTER_TIER`
    occurrences whose headings read as Part/Book/Volume labels
    (`_looks_like_part_tier`) is a real recurring division, not a one-off
    cover title or stray oversized folio number.

    Only meaningful for the font-clustering path. Bookmark-based hierarchy
    (Rule 2.1) always starts numbering at level 1 for whatever the PDF's own
    bookmarks call the top level, so there is no "level above 1" left to
    check there -- a bookmark-based book with real Parts is a known,
    documented gap (see `Mdook-docs/RULES.md`)."""
    counts = Counter(h.level for h in headings)
    candidates = sorted(
        level
        for level in counts
        if level < chapter_level
        and counts[level] >= MIN_HEADINGS_FOR_CHAPTER_TIER
        and _looks_like_part_tier([h for h in headings if h.level == level])
    )
    return candidates[0] if candidates else None


def _part_title_for_page(part_headings: list[Heading], page_number: int) -> str | None:
    """The most recent part heading at or before `page_number` -- a chapter
    belongs to whichever Part last started before it began."""
    applicable = [h for h in part_headings if h.page_number <= page_number]
    return applicable[-1].title.strip() if applicable else None


def _deduplicate_same_page_headings(h1_headings: list[Heading]) -> list[Heading]:
    """Two H1 candidates landing on the same physical page (e.g. a small
    decorative badge/icon plus the real title -- common in newsletter-style
    PDFs) would otherwise give the earlier one an inverted, empty page range
    in `_segment_chapters`. Real books essentially never start two chapters
    on the same page, so keep only the longer (more title-like) text."""
    best_by_page: dict[int, Heading] = {}
    for heading in h1_headings:
        existing = best_by_page.get(heading.page_number)
        if existing is None or len(heading.title) > len(existing.title):
            best_by_page[heading.page_number] = heading
    return sorted(best_by_page.values(), key=lambda h: h.page_number)


def _merge_chapter_number_titles(
    chapter_headings: list[Heading],
    pages_by_number: dict[int, PageData],
    body_font_size: float | None,
) -> list[Heading]:
    """A chapter number sometimes typesets as its own oversized element with
    the real title set smaller (but still visually distinct from body text)
    immediately below it -- e.g. a huge "9" with "Creative Problem Solving"
    underneath in bold heading-weight text. Font clustering only sees the
    number as the size outlier, leaving the chapter titled just "9". Detect a
    bare number/roman-numeral/"Chapter N" heading and absorb the very next
    text block on the page as the real title, provided it looks like a title
    (not body prose) and not itself another bare label."""
    merged: list[Heading] = []
    for heading in chapter_headings:
        if heading.block is not None and CHAPTER_LABEL_ONLY_RE.match(heading.title.strip()):
            page = pages_by_number.get(heading.page_number)
            title_block = _find_adjacent_title_block(heading.block, page, body_font_size)
            if title_block is not None:
                heading = Heading(
                    level=heading.level,
                    title=f"{heading.title.strip()} {title_block.text.strip()}",
                    page_number=heading.page_number,
                    block=heading.block,
                    extra_block=title_block,
                )
        merged.append(heading)
    return merged


def _find_adjacent_title_block(
    number_block: TextBlock, page: PageData | None, body_font_size: float | None
) -> TextBlock | None:
    if page is None:
        return None
    text_blocks = [b for b in page.blocks if isinstance(b, TextBlock)]
    index = next((i for i, b in enumerate(text_blocks) if b is number_block), None)
    if index is None or index + 1 >= len(text_blocks):
        return None

    candidate = text_blocks[index + 1]
    gap = candidate.bbox[1] - number_block.bbox[3]
    if gap < 0 or gap > number_block.font_size * MAX_TITLE_MERGE_GAP_RATIO:
        return None

    stripped = candidate.text.strip()
    if not stripped or len(stripped.split()) > MAX_TITLE_MERGE_WORDS:
        return None
    if CHAPTER_LABEL_ONLY_RE.match(stripped):
        return None  # don't chain into another bare label (e.g. a page number)

    # Require something distinct from ordinary body prose -- otherwise a
    # genuinely bare-numeral chapter title ("IX") would swallow the opening
    # words of its first paragraph.
    if body_font_size is not None and candidate.font_size <= body_font_size + 0.5:
        if not candidate.is_bold:
            return None
    return candidate


def _segment_chapters(
    h1_headings: list[Heading],
    pages: list[PageData],
    footnote_result: FootnoteDetectionResult,
    heading_titles: list[str],
    chapter_level: int,
    all_headings: list[Heading],
    body_font_size: float | None,
    body_left_margin: float | None,
    part_headings: list[Heading] | None = None,
    bibliography_markers: set[str] | None = None,
) -> list[Chapter]:
    last_page_number = max(page.page_number for page in pages)
    chapters: list[Chapter] = []
    part_headings = part_headings or []

    for i, heading in enumerate(h1_headings):
        start_page = heading.page_number
        end_page = (
            h1_headings[i + 1].page_number - 1 if i + 1 < len(h1_headings) else last_page_number
        )
        skip_ids = {id(heading.block)}
        if heading.extra_block is not None:
            skip_ids.add(id(heading.extra_block))
        subheadings = [
            h
            for h in all_headings
            if h is not heading
            and h.level > chapter_level
            and start_page <= h.page_number <= end_page
        ]
        sections = _collect_content(
            pages,
            start_page,
            end_page,
            footnote_result,
            chapter_number=i + 1,
            heading_titles=heading_titles,
            chapter_level=chapter_level,
            subheadings=subheadings,
            skip_ids=skip_ids,
            body_font_size=body_font_size,
            body_left_margin=body_left_margin,
            bibliography_markers=bibliography_markers,
        )
        chapters.append(
            Chapter(
                number=i + 1,
                title=heading.title,
                level=1,
                part_title=_part_title_for_page(part_headings, start_page),
                sections=sections,
                footnotes=_collect_footnotes(footnote_result, start_page, end_page),
                page_spans=[(start_page, end_page)],
            )
        )
    return chapters


def _build_single_chapter(
    pages: list[PageData],
    footnote_result: FootnoteDetectionResult,
    heading_titles: list[str],
    subheadings: list[Heading],
    chapter_level: int,
    body_font_size: float | None,
    body_left_margin: float | None,
    bibliography_markers: set[str] | None = None,
) -> Chapter:
    start_page = pages[0].page_number
    end_page = pages[-1].page_number
    sections = _collect_content(
        pages,
        start_page,
        end_page,
        footnote_result,
        chapter_number=1,
        heading_titles=heading_titles,
        chapter_level=chapter_level,
        subheadings=subheadings,
        skip_ids=set(),
        body_font_size=body_font_size,
        body_left_margin=body_left_margin,
        bibliography_markers=bibliography_markers,
    )
    return Chapter(
        number=1,
        title="Untitled",
        level=1,
        sections=sections,
        footnotes=_collect_footnotes(footnote_result, start_page, end_page),
        page_spans=[(start_page, end_page)],
    )


def _collect_footnotes(
    footnote_result: FootnoteDetectionResult, start_page: int, end_page: int
) -> list[Footnote]:
    return [
        fn
        for page_number in range(start_page, end_page + 1)
        for fn in footnote_result.footnotes_by_page.get(page_number, [])
    ]


def _collect_content(
    pages: list[PageData],
    start_page: int,
    end_page: int,
    footnote_result: FootnoteDetectionResult,
    chapter_number: int,
    heading_titles: list[str],
    chapter_level: int,
    subheadings: list[Heading],
    skip_ids: set[int],
    body_font_size: float | None,
    body_left_margin: float | None,
    bibliography_markers: set[str] | None = None,
) -> list[Section]:
    """Splits the chapter's page range into `Section`s at each detected
    sub-heading (any heading tier below `chapter_level`), instead of
    flattening every heading below the chapter into ordinary body text.
    Sub-heading blocks are matched by identity against `subheadings`, so a
    heading whose `block` didn't survive to this stage (e.g. an unmatched
    bookmark) simply falls through as ordinary content -- the same as before
    this nesting existed."""
    subheading_by_id = {id(h.block): h for h in subheadings if h.block is not None}

    # Text, images, tables, and sub-headings are gathered into ordered "runs"
    # so each keeps its position relative to the surrounding paragraphs
    # instead of being pulled out and dumped elsewhere.
    runs: list[tuple[str, list[tuple[int, TextBlock]] | ImageBlock | TableBlock | Heading]] = []
    current_run: list[tuple[int, TextBlock]] = []

    for page in pages:
        if not (start_page <= page.page_number <= end_page):
            continue
        if _is_toc_page(page, heading_titles):  # Rule 9.4 — discard the book's own printed TOC
            continue
        for block in page.blocks:
            if isinstance(block, TextBlock) and id(block) in skip_ids:
                continue
            if isinstance(block, TextBlock) and id(block) in subheading_by_id:
                if current_run:
                    runs.append(("text", current_run))
                    current_run = []
                runs.append(("heading", subheading_by_id[id(block)]))
                continue
            if isinstance(block, TextBlock):
                if _is_decorative(block.text):  # Rule 9.5 — dropped (Stage 4 renders "---" later)
                    continue
                current_run.append((page.page_number, block))
            elif isinstance(block, ImageBlock):
                if current_run:
                    runs.append(("text", current_run))
                    current_run = []
                runs.append(("image", block))
            elif isinstance(block, TableBlock):
                if current_run:
                    runs.append(("text", current_run))
                    current_run = []
                runs.append(("table", block))
    if current_run:
        runs.append(("text", current_run))

    sections: list[Section] = [Section(title=None, level=1, content=[])]
    epigraph_checked = False
    image_index = 0

    for kind, payload in runs:
        if kind == "heading":
            relative_level = max(payload.level - chapter_level, 1)
            sections.append(Section(title=payload.title, level=relative_level, content=[]))
            continue
        if kind == "image":
            image_index += 1
            sections[-1].content.append(_image_block_to_ref(payload, chapter_number, image_index))
            continue
        if kind == "table":
            sections[-1].content.append(_table_block_to_data(payload))
            continue

        text_blocks_with_pages = payload
        if not epigraph_checked:
            epigraph, text_blocks_with_pages = _extract_epigraph(text_blocks_with_pages)  # Rule 9.1
            epigraph_checked = True
            if epigraph is not None:
                sections[-1].content.append(epigraph)

        sections[-1].content.extend(
            _content_items_from_text_run(
                text_blocks_with_pages,
                footnote_result,
                body_font_size,
                body_left_margin,
                bibliography_markers,
            )
        )

    if len(sections) > 1 and not sections[0].content:
        # Nothing preceded the first sub-heading -- drop the empty untitled
        # lead-in section instead of rendering an orphan blank block.
        sections = sections[1:]

    return sections


def _content_items_from_text_run(
    blocks_with_pages: list[tuple[int, TextBlock]],
    footnote_result: FootnoteDetectionResult,
    body_font_size: float | None,
    body_left_margin: float | None,
    bibliography_markers: set[str] | None = None,
) -> list[SectionContent]:
    """Splits a run of raw text blocks into unbroken bullet/numbered lists,
    monospace-font code blocks, and merged paragraphs (Rules 5.1-5.4),
    classifying each merged paragraph as a block quote (Rule 9.3) or
    ordinary paragraph by its left-margin indent relative to the book's
    baseline. Shared by chapter and front/back matter content collection."""
    items: list[SectionContent] = []
    for kind, sub_payload in list_rules.split_list_run(blocks_with_pages):
        if kind == "list":
            items.append(sub_payload)
            continue
        for text_or_code, text_payload in code_rules.split_code_run(sub_payload):
            if text_or_code == "code":
                items.append(code_rules.build_code_block(text_payload))
                continue
            _append_paragraph_items(
                text_payload,
                footnote_result,
                body_font_size,
                body_left_margin,
                items,
                bibliography_markers,
            )
    return items


def _append_paragraph_items(
    blocks_with_pages: list[tuple[int, TextBlock]],
    footnote_result: FootnoteDetectionResult,
    body_font_size: float | None,
    body_left_margin: float | None,
    items: list[SectionContent],
    bibliography_markers: set[str] | None = None,
) -> None:
    merged = merge_text_blocks(
        blocks_with_pages,
        inline_marker_ids=footnote_result.inline_marker_ids,
        endnote_marker_ids=footnote_result.endnote_marker_ids,
    )
    for entry in math_rules.group_theorem_environments(merged):  # Batch 17
        if isinstance(entry, math_rules.TheoremEnvironment):
            items.append(
                CalloutBlock(
                    label=entry.label,
                    paragraphs=[t for t in entry.paragraphs if t],
                    page_number=entry.page_number,
                )
            )
            continue

        p = entry
        if not p.text:
            continue
        if bibliography_markers:
            # Batch 15: a numeric in-text citation is ordinary inline text,
            # not a discrete marker `TextBlock` -- spliced directly into the
            # merged string rather than via `merge_text_blocks`.
            p.text = citation_rules.splice_citation_links(p.text, bibliography_markers)

        equation = math_rules.detect_display_equation(p.text)
        if equation is not None:
            equation_text, numbering = equation
            items.append(
                MathBlock(
                    latex_or_text=equation_text,
                    display=True,
                    numbering=numbering,
                    page_number=p.page_number,
                )
            )
            continue
        p.text = math_rules.splice_inline_math(p.text)

        callout = callout_rules.detect_callout(p.text)
        if callout is not None:
            label, remainder = callout
            items.append(
                CalloutBlock(
                    label=label,
                    paragraphs=[remainder] if remainder else [],
                    page_number=p.page_number,
                )
            )
        elif _looks_like_block_quote(p, body_font_size, body_left_margin):
            items.append(
                BlockQuote(
                    lines=[p.text],
                    attribution=None,
                    page_number=p.page_number,
                    italic=False,
                )
            )
        else:
            items.append(Paragraph(text=p.text, page_number=p.page_number))


def _looks_like_block_quote(
    paragraph: MergedParagraph, body_font_size: float | None, body_left_margin: float | None
) -> bool:
    if body_font_size is None or body_left_margin is None:
        return False
    if len(paragraph.text.split()) < MIN_BLOCK_QUOTE_WORDS:
        return False
    indent = paragraph.x0 - body_left_margin
    min_indent = body_font_size * BLOCK_QUOTE_INDENT_RATIO
    max_indent = body_font_size * BLOCK_QUOTE_MAX_INDENT_RATIO
    return min_indent < indent <= max_indent


def _image_block_to_ref(block: ImageBlock, chapter_number: int, image_index: int) -> ImageRef:
    return ImageRef(
        source_path=block.image_path,
        caption=block.caption,
        figure_id=_figure_id(block, f"fig-{chapter_number}-{image_index}"),
    )


def _figure_id(block: ImageBlock, fallback: str) -> str:
    """Batch 16: prefer the book's own printed figure number (from a
    detected caption, Rule 7.3) over the chapter/index-based scheme, e.g.
    "Figure 3.2" -> "fig-3-2" -- a much more meaningful attachment filename
    than a purely positional one when the book already numbers its own
    figures."""
    if block.caption is None:
        return fallback
    figure_number = image_rules.extract_figure_number(block.caption)
    if figure_number is None:
        return fallback
    return f"fig-{figure_number.replace('.', '-')}"


def _table_block_to_data(block: TableBlock) -> TableData:
    return TableData(
        cells=block.cells,
        is_complex=table_rules.is_complex(block.cells, block.has_merged_cells),  # Rules 6.2-6.3
        page_number=block.page_number,
    )


def _collect_matter_sections(
    zone_pages: list[PageData],
    footnote_result: FootnoteDetectionResult,
    heading_titles: list[str],
    labels: tuple[str, ...],
    figure_prefix: str,
    body_font_size: float | None,
    body_left_margin: float | None,
    bibliography_markers: set[str] | None = None,
) -> list[Section]:
    """Shared by front- and back-matter processing: splits a zone's pages
    into named `Section`s at recognized structural labels ("Preface",
    "Glossary", ...). Front/back matter rarely uses distinct heading-sized
    type the way chapter titles do, so Rules 1.2/1.3's keyword list doubles
    as the heading signal here instead of font-size tiers."""
    if not zone_pages:
        return []

    runs: list[tuple[str, object]] = []
    current_run: list[tuple[int, TextBlock]] = []

    for page in zone_pages:
        if _is_toc_page(page, heading_titles):  # Rule 9.4 — the printed TOC often lives up front
            continue
        for block in page.blocks:
            if isinstance(block, TextBlock):
                label = _match_matter_label(block.text, labels)
                if label is not None:
                    if current_run:
                        runs.append(("text", current_run))
                        current_run = []
                    runs.append(("heading", label))
                    continue
                if _is_decorative(block.text):  # Rule 9.5
                    continue
                current_run.append((page.page_number, block))
            elif isinstance(block, ImageBlock):
                if current_run:
                    runs.append(("text", current_run))
                    current_run = []
                runs.append(("image", block))
            elif isinstance(block, TableBlock):
                if current_run:
                    runs.append(("text", current_run))
                    current_run = []
                runs.append(("table", block))
    if current_run:
        runs.append(("text", current_run))

    sections: list[Section] = [Section(title=None, level=1, content=[])]
    image_index = 0

    for kind, payload in runs:
        if kind == "heading":
            sections.append(Section(title=payload, level=1, content=[]))
            continue
        if kind == "image":
            image_index += 1
            sections[-1].content.append(
                ImageRef(
                    source_path=payload.image_path,
                    caption=payload.caption,
                    figure_id=_figure_id(payload, f"fig-{figure_prefix}-{image_index}"),
                )
            )
            continue
        if kind == "table":
            sections[-1].content.append(_table_block_to_data(payload))
            continue

        sections[-1].content.extend(
            _content_items_from_text_run(
                payload, footnote_result, body_font_size, body_left_margin, bibliography_markers
            )
        )

    if len(sections) > 1 and not sections[0].content:
        sections = sections[1:]

    return sections


def _match_matter_label(text: str, labels: tuple[str, ...]) -> str | None:
    stripped = text.strip()
    if not stripped or len(stripped.split()) > MAX_MATTER_LABEL_WORDS:
        return None
    normalized = stripped.lower().rstrip(".:").strip()
    return stripped if normalized in labels else None


def _is_toc_page(page: PageData, heading_titles: list[str]) -> bool:
    """Rule 9.4 — discard the book's own printed table of contents; the
    vault generates its own Index instead.

    Two independent signals, since ebook-derived PDFs (Gutenberg-style HTML
    exports especially) often list chapter titles with no page numbers at
    all: the classic "Title .... 123" dot-leader pattern, or a page whose
    text contains several of the book's own detected chapter titles in a
    row -- exactly what a TOC looks like once decorative title styling
    (small caps, multi-font subsetting) has fragmented its layout into a
    jumble that dot-leader matching alone would miss."""
    dot_leader_count = sum(
        1
        for block in page.blocks
        if isinstance(block, TextBlock) and TOC_LINE_RE.match(block.text.strip())
    )
    if dot_leader_count >= MIN_TOC_LINES:
        return True

    # Regression: found via real-book testing. A book whose chapter-title
    # detection degenerated to garbage (e.g. font-encoding corruption
    # producing three chapters all titled bare "H") turned this signal
    # into a false-positive machine -- a single normalized character
    # substring-matches almost any page's text, so nearly every page in
    # the book got wrongly discarded as "the printed TOC," silently
    # dropping all of its content (not just tables). Only titles with
    # enough characters to be a distinctive signal count here.
    usable_titles = [
        title
        for title in heading_titles
        if len(_normalize_for_toc_match(title)) >= MIN_TOC_TITLE_MATCH_LENGTH
    ]
    if len(usable_titles) < MIN_TOC_LINES:
        return False

    page_text = _normalize_for_toc_match(
        "".join(block.text for block in page.blocks if isinstance(block, TextBlock))
    )
    matches = sum(1 for title in usable_titles if _normalize_for_toc_match(title) in page_text)
    return matches >= MIN_TOC_LINES


def _normalize_for_toc_match(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _is_decorative(text: str) -> bool:
    """Rule 9.5 — an isolated ornament/dingbat used as a section break."""
    stripped = text.strip()
    return bool(stripped) and bool(DECORATIVE_RE.match(stripped))


def _extract_epigraph(
    blocks_with_pages: list[tuple[int, TextBlock]],
) -> tuple[BlockQuote | None, list[tuple[int, TextBlock]]]:
    """Rule 9.1 — a short italic block (optionally followed by an em-dash
    attribution line) at the very start of a chapter's content."""
    if not blocks_with_pages:
        return None, blocks_with_pages

    first_page, first_block = blocks_with_pages[0]
    if not (first_block.is_italic and len(first_block.text.split()) <= MAX_EPIGRAPH_WORDS):
        return None, blocks_with_pages

    lines = [first_block.text.strip()]
    consumed = 1
    attribution: str | None = None

    if len(blocks_with_pages) > 1:
        _, second_block = blocks_with_pages[1]
        text = second_block.text.strip()
        if text.startswith(("—", "--", "- ")):
            attribution = text.lstrip("—- ").strip()
            consumed = 2

    quote = BlockQuote(lines=lines, attribution=attribution, page_number=first_page)
    return quote, blocks_with_pages[consumed:]
