"""Pydantic schemas shared across all pipeline stages.

These are the typed contracts between Stage 1 (Intake) through Stage 5
(Validation) described in `Mdook-docs/ARCHITECTURE.md`. Every stage takes
one of these models as input and produces another as output — no stage
mutates data belonging to an earlier stage.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, Union

from pydantic import BaseModel, Field

BBox = tuple[float, float, float, float]
"""(x0, y0, x1, y1) in PDF points."""

ZoneType = Literal["front_matter", "body", "back_matter"]
ProfileName = Literal["literature", "technical"]
FootnoteStyle = Literal["page_bottom", "endnote"]


# ---------------------------------------------------------------------------
# Stage 1 — Intake
# ---------------------------------------------------------------------------


class ZoneEntry(BaseModel):
    """A contiguous page range classified as front matter, body, or back matter."""

    start_page: int
    end_page: int
    zone_type: ZoneType


class Bookmark(BaseModel):
    """A single entry from the PDF's embedded outline/TOC tree."""

    level: int
    title: str
    page_number: int


class BookManifest(BaseModel):
    """Output of Stage 1 (Intake). Describes the book as a whole."""

    file_path: str
    title: str
    author: str
    total_pages: int
    needs_ocr: bool
    profile: ProfileName
    zone_map: list[ZoneEntry] = Field(default_factory=list)
    bookmarks: list[Bookmark] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    """Extra copyright-page metadata: ISBN, publisher, edition, etc."""


# ---------------------------------------------------------------------------
# Stage 2 — Extraction
# ---------------------------------------------------------------------------


class TextBlock(BaseModel):
    block_type: Literal["text"] = "text"
    text: str
    font_name: str
    font_size: float
    is_bold: bool = False
    is_italic: bool = False
    is_superscript: bool = False
    bbox: BBox
    page_number: int


class ImageBlock(BaseModel):
    block_type: Literal["image"] = "image"
    image_path: str
    """Path to the extracted image in a temp directory."""
    bbox: BBox
    caption: str | None = None
    page_number: int


class TableBlock(BaseModel):
    block_type: Literal["table"] = "table"
    cells: list[list[str]]
    has_merged_cells: bool = False
    bbox: BBox
    page_number: int


Block = Union[TextBlock, ImageBlock, TableBlock]


class PageData(BaseModel):
    """Output of Stage 2 (Extraction) — one entry per page."""

    page_number: int
    width: float
    height: float
    blocks: list[Block] = Field(default_factory=list)
    header_text: str | None = None
    """Populated in Stage 3 once repeating headers are detected."""
    footer_text: str | None = None
    """Populated in Stage 3 once repeating footers are detected."""
    was_ocrd: bool = False
    """True if this page's native text layer failed Stage 2's per-page
    quality check (Phase 3) and its blocks came from OCR instead of
    PyMuPDF's text extraction. Stage 5 (Validation) reports a real per-page
    OCR count from this rather than guessing from a whole-book flag."""
    is_vertical_text: bool = False
    """True if most of this page's lines run top-to-bottom (traditional
    vertical CJK typesetting) rather than left-to-right, per PyMuPDF's own
    per-line writing-direction vector (Batch 18). Column reordering and
    positional heading heuristics all assume horizontal reading and would
    scramble a vertical page, so they skip it instead — full vertical-
    layout reading-order support is out of scope; this is detect-and-
    don't-corrupt only. See `Mdook-docs/RULES.md` section 16."""
    is_blank: bool = False
    """True if this page has essentially no native text *and* no embedded
    images — recorded as intentionally blank (Batch 19) rather than routed
    through OCR and logged as an OCR failure, the way a real low-quality
    page would be. A page an author explicitly left blank between chapters
    has nothing for OCR to find; that's the expected, correct outcome, not
    an error."""


# ---------------------------------------------------------------------------
# Stage 3 — Semantic Analysis
# ---------------------------------------------------------------------------


class BookMetadata(BaseModel):
    """Front-matter-derived metadata surfaced in the vault's Index file."""

    title: str
    author: str
    isbn: str | None = None
    publisher: str | None = None
    edition: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class Paragraph(BaseModel):
    content_type: Literal["paragraph"] = "paragraph"
    text: str
    page_number: int
    """The page this paragraph starts on."""


class ImageRef(BaseModel):
    content_type: Literal["image_ref"] = "image_ref"
    source_path: str
    caption: str | None = None
    figure_id: str | None = None
    """e.g. "fig-3-2" — used to derive the attachment filename."""


class TableData(BaseModel):
    content_type: Literal["table_data"] = "table_data"
    cells: list[list[str]]
    is_complex: bool = False
    """If true, render as inline HTML instead of a markdown pipe table."""
    page_number: int
    """Stage 4 keys its page-marker callouts off this the same way it does
    for every other content item, via `getattr(item, "page_number", None)`."""


class BlockQuote(BaseModel):
    content_type: Literal["block_quote"] = "block_quote"
    lines: list[str]
    """Preserved verbatim so verse/epigraph line breaks survive rendering."""
    attribution: str | None = None
    page_number: int
    italic: bool = True
    """True for an epigraph (Rule 9.1, always italicized). A general
    indented quotation (Rule 9.3) is typically body-styled, not italic."""


class ListItem(BaseModel):
    text: str
    level: int = 0
    ordered: bool = False
    marker: str | None = None
    """The literal printed number (e.g. "1", "2") for an ordered item,
    rendered verbatim instead of a synthesized counter -- see
    `mdook.core.rules.lists` for why. None for a bullet item."""


class ListData(BaseModel):
    content_type: Literal["list_data"] = "list_data"
    items: list[ListItem] = Field(default_factory=list)
    page_number: int
    """The page the list's first item starts on -- Stage 4 keys its page-
    marker callouts off this the same way it does for every other content
    item, via `getattr(item, "page_number", None)`."""


class CodeBlock(BaseModel):
    content_type: Literal["code_block"] = "code_block"
    lines: list[str]
    """Preserved verbatim, one per source line -- code's line breaks and
    indentation are structural, unlike prose, so they must never be joined
    the way Rule 5.1 joins ordinary paragraph lines."""
    page_number: int


class CalloutBlock(BaseModel):
    content_type: Literal["callout_block"] = "callout_block"
    label: str
    """The book's own printed label ("Note", "Warning", ...), verbatim --
    see `mdook.core.rules.callouts` for how it maps to an Obsidian callout
    type at render time."""
    paragraphs: list[str]
    page_number: int


class MathBlock(BaseModel):
    content_type: Literal["math_block"] = "math_block"
    latex_or_text: str
    """Rendered inside Obsidian's native MathJax delimiters (`$$...$$` for
    a display equation, `$...$` for inline) -- not real LaTeX, just
    whatever Unicode math symbols the PDF's text layer actually contained.
    See `mdook.core.rules.math`."""
    display: bool
    numbering: str | None = None
    """A trailing "(3.14)"-style equation-number tag, preserved verbatim
    but not semantically parsed."""
    page_number: int


class VerseBlock(BaseModel):
    content_type: Literal["verse_block"] = "verse_block"
    lines: list[str]
    """Preserved verbatim lines of verse, with empty strings representing stanza breaks."""
    page_number: int
    """The page this verse block starts on."""
    is_quoted: bool = False
    """True if indented/quoted within prose (renders with '> '), False for standalone poem/verse."""
    attribution: str | None = None
    """Optional attribution (e.g. poet name), if followed by an attribution line."""


class GlossaryItem(BaseModel):
    term: str
    """The defined term, stripped of bold markers and trailing delimiters."""
    definition: str
    """The definition text, with leading/trailing delimiters stripped."""
    page_number: int
    """The page number where this glossary entry starts."""


class GlossaryBlock(BaseModel):
    content_type: Literal["glossary_block"] = "glossary_block"
    items: list[GlossaryItem] = Field(default_factory=list)
    page_number: int
    """The page number where this glossary block starts."""


SectionContent = Union[
    Paragraph,
    ImageRef,
    TableData,
    BlockQuote,
    ListData,
    CodeBlock,
    CalloutBlock,
    MathBlock,
    VerseBlock,
    GlossaryBlock,
]


class Footnote(BaseModel):
    marker: str
    """"1", "†", etc."""
    text: str
    page_number: int
    style: FootnoteStyle


class Section(BaseModel):
    title: str | None = None
    level: int
    content: list[SectionContent] = Field(default_factory=list)


class Chapter(BaseModel):
    number: int
    """Sequential, for filename ordering."""
    title: str
    """The book's own heading text, verbatim."""
    level: int
    """Always 1 today -- every `Chapter` is a top-level unit. A book's Part/
    Book/Volume grouping (Batch 14) is recorded via `part_title` below
    instead of a second chapter level, since `DocumentTree.chapters` stays
    a flat list either way and rendering only needs to know which part a
    chapter belongs to, not a nested tree."""
    part_title: str | None = None
    """The Part/Book/Volume heading (if any) that precedes this chapter --
    e.g. "Part One: The Foundation". None for the common case of a book
    with no such division. See `mdook.core.stages.semantic._pick_part_tier`."""
    sections: list[Section] = Field(default_factory=list)
    footnotes: list[Footnote] = Field(default_factory=list)
    page_spans: list[tuple[int, int]] = Field(default_factory=list)


class DocumentTree(BaseModel):
    """Output of Stage 3 (Semantic Analysis) — the whole book, structured."""

    metadata: BookMetadata
    front_matter: list[Section] = Field(default_factory=list)
    chapters: list[Chapter] = Field(default_factory=list)
    back_matter: list[Section] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Stage 5 — Validation
# ---------------------------------------------------------------------------


class ValidationReport(BaseModel):
    """Output of Stage 5 (Validation)."""

    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    total_pages: int = 0
    total_chapters: int = 0
    total_footnotes: int = 0
    total_images: int = 0
    ocr_pages: int = 0
    llm_corrections: int = 0
    processing_time_seconds: float = 0.0

    @property
    def is_clean(self) -> bool:
        return not self.errors and not self.warnings


class ConversionResult(BaseModel):
    """Final result handed back from `mdook.core.pipeline.convert`.

    Consumed by the GUI's `conversion_finished` signal to populate the
    summary area and enable the "Open Vault" button.
    """

    success: bool
    output_dir: Path
    manifest: BookManifest | None = None
    validation_report: ValidationReport | None = None
    error_message: str | None = None

    pages: int = 0
    chapters: int = 0
    footnotes: int = 0
    images: int = 0
    llm_review_applied: bool = False
