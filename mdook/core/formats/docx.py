"""Stage 1-3 Ingestion for DOCX Manuscripts.

Directly ingests DOCX manuscripts into `mdook.core.models.DocumentTree` and
`mdook.core.models.BookManifest`, bypassing PDF-specific extraction and
heuristic clustering. See `Mdook-docs/ROADMAP.md` (Phase 4).

Features:
- Reads DOCX package properties (title, author, revision date, comments).
- Extracts embedded media (images) and relationship maps.
- Parses Word footnotes from word/footnotes.xml.
- Maps Word heading styles (Heading 1-6) into Chapter and Section hierarchies.
- Maps paragraph styles:
  * Normal / Body Text -> Paragraph (with bold, italic, strikethrough, code, hyperlinks)
  * Heading 1 -> Chapter boundary (or Front/Back matter)
  * Heading 2-6 -> Section hierarchy
  * Quote / Intense Quote -> BlockQuote
  * List Bullet / List Number -> ListData with ListItem
  * Code / Preformatted / Monospace runs -> CodeBlock
- Maps Word tables into TableData (detects merged cells -> is_complex).
- Maps inline images and drawings into ImageRef.
- Classifies front matter, body chapters, and back matter divisions.
- Auto-detects literature vs technical profile when profile is 'auto'.
"""

from __future__ import annotations

import logging
import re
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Any

import docx
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.hyperlink import Hyperlink
from docx.text.paragraph import Paragraph as DocxParagraph
from docx.text.run import Run

from mdook.core.models import (
    BlockQuote,
    BookManifest,
    Bookmark,
    BookMetadata,
    Chapter,
    CodeBlock,
    DocumentTree,
    Footnote,
    ImageRef,
    ListData,
    ListItem,
    Paragraph,
    ProfileName,
    Section,
    TableData,
    ZoneEntry,
)
from mdook.core.rules.code import is_monospace_font
from mdook.core.rules.paragraphs import FOOTNOTE_MARKER_SENTINEL

logger = logging.getLogger(__name__)

FRONT_MATTER_LABELS = frozenset(
    {
        "cover",
        "title",
        "titlepage",
        "title page",
        "copyright",
        "dedication",
        "preface",
        "foreword",
        "prologue",
        "halftitle",
        "frontmatter",
        "contents",
        "table of contents",
        "toc",
    }
)

BACK_MATTER_LABELS = frozenset(
    {
        "epilogue",
        "afterword",
        "appendix",
        "appendices",
        "bibliography",
        "references",
        "glossary",
        "index",
        "colophon",
        "acknowledgments",
        "acknowledgements",
        "about the author",
        "backmatter",
    }
)

NUMBERED_HEADING_RE = re.compile(r"^\s*\d+\.\d+(?:\.\d+)*\.?\s+\S")
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


class DocxIngester:
    """Parses a DOCX manuscript file directly into BookManifest and DocumentTree."""

    def __init__(self, docx_path: Path, profile_override: str = "auto") -> None:
        self.docx_path = docx_path
        self.profile_override = profile_override
        self.temp_img_dir = Path(tempfile.mkdtemp(prefix="mdook_docx_img_"))
        self.footnotes_by_id: dict[str, str] = {}
        self.rel_map: dict[str, str] = {}
        self.image_path_map: dict[str, Path] = {}
        self.table_count = 0
        self.code_count = 0
        self.math_count = 0
        self.numbered_headings_count = 0

    def ingest(self) -> tuple[BookManifest, DocumentTree]:
        self._extract_package_assets()

        doc = docx.Document(str(self.docx_path))
        metadata = self._extract_metadata(doc)

        front_matter: list[Section] = []
        chapters: list[Chapter] = []
        back_matter: list[Section] = []
        bookmarks: list[Bookmark] = []

        # Current state while traversing blocks
        current_division = "body"
        current_chapter_title: str | None = None
        current_chapter_sections: list[Section] = []
        current_section = Section(title=None, level=2, content=[])
        current_footnotes: list[Footnote] = []
        seen_footnote_ids: set[str] = set()
        page_counter = 1

        def flush_chapter() -> None:
            nonlocal current_chapter_title, current_chapter_sections, current_section
            nonlocal current_footnotes, seen_footnote_ids, page_counter
            if current_section.content or current_section.title:
                current_chapter_sections.append(current_section)
                current_section = Section(title=None, level=2, content=[])

            if current_chapter_sections or current_chapter_title or current_footnotes:
                if current_division == "front_matter":
                    for sec in current_chapter_sections:
                        if sec.title is None:
                            sec.title = current_chapter_title or "Front Matter"
                        front_matter.append(sec)
                elif current_division == "back_matter":
                    for sec in current_chapter_sections:
                        if sec.title is None:
                            sec.title = current_chapter_title or "Back Matter"
                        back_matter.append(sec)
                else:
                    ch_num = len(chapters) + 1
                    ch_title = current_chapter_title or f"Chapter {ch_num}"
                    chapters.append(
                        Chapter(
                            number=ch_num,
                            title=ch_title,
                            level=1,
                            sections=current_chapter_sections,
                            footnotes=current_footnotes,
                            page_spans=[(page_counter, page_counter)],
                        )
                    )
                    page_counter += 1

                current_chapter_title = None
                current_chapter_sections = []
                current_footnotes = []
                seen_footnote_ids = set()

        for block in doc.iter_inner_content():
            if isinstance(block, DocxParagraph):
                style_name = (block.style.name or "").lower().strip()
                p_text = block.text.strip()

                # 1. Heading 1 -> Chapter Boundary / Division Boundary
                if style_name == "heading 1":
                    flush_chapter()
                    current_chapter_title = p_text
                    current_division = self._classify_division(p_text)
                    bookmarks.append(
                        Bookmark(
                            level=1,
                            title=p_text,
                            page_number=page_counter,
                        )
                    )
                    if NUMBERED_HEADING_RE.match(p_text):
                        self.numbered_headings_count += 1
                    continue

                # 2. Heading 2..6 -> Sub-section Boundary
                if style_name.startswith("heading ") and style_name[8:].isdigit():
                    heading_level = int(style_name[8:])
                    if current_section.content or current_section.title:
                        current_chapter_sections.append(current_section)
                    current_section = Section(title=p_text, level=heading_level, content=[])
                    bookmarks.append(
                        Bookmark(
                            level=heading_level,
                            title=p_text,
                            page_number=page_counter,
                        )
                    )
                    if NUMBERED_HEADING_RE.match(p_text):
                        self.numbered_headings_count += 1
                    continue

                # Check for embedded drawings/images in this paragraph
                img_refs = self._extract_paragraph_images(block)
                for img_ref in img_refs:
                    current_section.content.append(img_ref)

                # Paragraph content items
                content_item, fn_refs = self._parse_paragraph(block, page_counter)
                if content_item:
                    current_section.content.append(content_item)

                for fn_id in fn_refs:
                    if fn_id not in seen_footnote_ids:
                        seen_footnote_ids.add(fn_id)
                        fn_text = self.footnotes_by_id.get(fn_id, f"Footnote {fn_id}")
                        current_footnotes.append(
                            Footnote(
                                marker=fn_id,
                                text=fn_text,
                                page_number=page_counter,
                                style="page_bottom",
                            )
                        )

            elif isinstance(block, Table):
                self.table_count += 1
                table_item = self._parse_table(block, page_counter)
                if table_item:
                    current_section.content.append(table_item)

        flush_chapter()

        # Fallback: if no chapters created (e.g. document had no Heading 1)
        if not chapters:
            if front_matter:
                for idx, sec in enumerate(front_matter, start=1):
                    chapters.append(
                        Chapter(
                            number=idx,
                            title=sec.title or f"Chapter {idx}",
                            level=1,
                            sections=[sec],
                            page_spans=[(idx, idx)],
                        )
                    )
                front_matter = []
            elif back_matter:
                for idx, sec in enumerate(back_matter, start=1):
                    chapters.append(
                        Chapter(
                            number=idx,
                            title=sec.title or f"Chapter {idx}",
                            level=1,
                            sections=[sec],
                            page_spans=[(idx, idx)],
                        )
                    )
                back_matter = []

        total_pages = max(len(chapters), 1)

        # Resolve profile
        resolved_profile = self._resolve_profile(bookmarks)

        # Build BookManifest
        zone_map: list[ZoneEntry] = []
        if front_matter:
            zone_map.append(ZoneEntry(start_page=1, end_page=1, zone_type="front_matter"))
        if chapters:
            zone_map.append(ZoneEntry(start_page=1, end_page=total_pages, zone_type="body"))
        if back_matter:
            zone_map.append(
                ZoneEntry(start_page=total_pages, end_page=total_pages, zone_type="back_matter")
            )

        manifest = BookManifest(
            file_path=str(self.docx_path),
            title=metadata.title,
            author=metadata.author,
            total_pages=total_pages,
            needs_ocr=False,
            profile=resolved_profile,
            zone_map=zone_map,
            bookmarks=bookmarks or None,
            metadata={
                "isbn": metadata.isbn,
                "publisher": metadata.publisher,
                **metadata.extra,
            },
        )

        tree = DocumentTree(
            metadata=metadata,
            front_matter=front_matter,
            chapters=chapters,
            back_matter=back_matter,
        )

        return manifest, tree

    # -----------------------------------------------------------------------
    # Package XML & Assets Extraction
    # -----------------------------------------------------------------------

    def _extract_package_assets(self) -> None:
        """Read footnotes, images, and relationships from the DOCX zip package."""
        try:
            with zipfile.ZipFile(self.docx_path, "r") as zf:
                # 1. Parse word/_rels/document.xml.rels
                if "word/_rels/document.xml.rels" in zf.namelist():
                    rels_data = zf.read("word/_rels/document.xml.rels")
                    root = ET.fromstring(rels_data)
                    for rel in root.findall(f"{{{REL_NS}}}Relationship"):
                        r_id = rel.get("Id", "")
                        target = rel.get("Target", "")
                        if r_id and target:
                            self.rel_map[r_id] = target

                # 2. Extract images in word/media/
                for name in zf.namelist():
                    if name.startswith("word/media/"):
                        dest_file = self.temp_img_dir / Path(name).name
                        dest_file.write_bytes(zf.read(name))
                        self.image_path_map[name] = dest_file
                        self.image_path_map[Path(name).name] = dest_file
                        # Also map relative targets like "media/image1.png"
                        rel_target = name.removeprefix("word/")
                        self.image_path_map[rel_target] = dest_file

                # 3. Parse word/footnotes.xml
                if "word/footnotes.xml" in zf.namelist():
                    fn_data = zf.read("word/footnotes.xml")
                    root = ET.fromstring(fn_data)
                    for fn_elem in root.findall(f"{{{W_NS}}}footnote"):
                        fn_id = fn_elem.get(f"{{{W_NS}}}id")
                        fn_type = fn_elem.get(f"{{{W_NS}}}type")
                        if fn_type in ("separator", "continuationSeparator") or not fn_id:
                            continue
                        text = "".join(fn_elem.itertext()).strip()
                        cleaned_text = re.sub(
                            r"^(?:\[\d+\]|\d+[\.:\s]+|\^|\*)\s*", "", text
                        ).strip()
                        self.footnotes_by_id[fn_id] = cleaned_text or text

        except Exception as exc:
            logger.debug("Error extracting DOCX package assets: %s", exc)

    def _extract_metadata(self, doc: docx.Document) -> BookMetadata:
        props = doc.core_properties
        title = (props.title or "").strip() or self.docx_path.stem
        author = (props.author or "").strip() or "Unknown"

        extra: dict[str, Any] = {}
        if props.comments:
            extra["comments"] = props.comments
        if props.created:
            extra["created"] = str(props.created)
            extra["year"] = props.created.year

        return BookMetadata(
            title=title,
            author=author,
            extra=extra,
        )

    def _classify_division(self, title: str) -> str:
        title_clean = title.lower().strip()
        for label in FRONT_MATTER_LABELS:
            if title_clean == label or title_clean.startswith(f"{label} "):
                return "front_matter"
        for label in BACK_MATTER_LABELS:
            if title_clean == label or title_clean.startswith(f"{label} "):
                return "back_matter"
        return "body"

    # -----------------------------------------------------------------------
    # Paragraph & Table Parsing
    # -----------------------------------------------------------------------

    def _parse_paragraph(self, p: DocxParagraph, page_number: int) -> tuple[Any | None, list[str]]:
        style_name = (p.style.name or "").lower().strip()
        fn_refs: list[str] = []

        # Check for footnotes in paragraph xml
        for fn_ref in p._element.xpath(".//w:footnoteReference"):
            fn_id = fn_ref.get(qn("w:id"))
            if fn_id and fn_id in self.footnotes_by_id:
                fn_refs.append(fn_id)

        # Build inline markdown text
        parts: list[str] = []
        is_all_monospace = True
        has_runs = False

        for item in p.iter_inner_content():
            if isinstance(item, Hyperlink):
                inner_text = "".join(self._format_run(r) for r in item.runs) or item.text
                if item.url:
                    parts.append(f"[{inner_text}]({item.url})")
                else:
                    parts.append(inner_text)
                has_runs = True
                is_all_monospace = False
            elif isinstance(item, Run):
                has_runs = True
                if not item.font.name or not is_monospace_font(item.font.name):
                    is_all_monospace = False
                parts.append(self._format_run(item))

        # Check footnote markers and splice sentinels
        if fn_refs:
            for fn_id in fn_refs:
                parts.append(f"{FOOTNOTE_MARKER_SENTINEL}{fn_id}{FOOTNOTE_MARKER_SENTINEL}")

        full_text = "".join(parts).strip()
        if not full_text:
            return None, fn_refs

        # Style: Quote / Blockquote
        if "quote" in style_name:
            lines = [full_text]
            return BlockQuote(lines=lines, page_number=page_number, italic=True), fn_refs

        # Style: List Item
        if "list" in style_name or style_name.startswith("bullet"):
            ordered = "number" in style_name
            item = ListItem(
                text=full_text,
                level=0,
                ordered=ordered,
                marker="1" if ordered else None,
            )
            return ListData(items=[item], page_number=page_number), fn_refs

        # Style: Code block
        if "code" in style_name or "preformatted" in style_name or (has_runs and is_all_monospace):
            self.code_count += 1
            lines = p.text.splitlines() or [p.text]
            return CodeBlock(lines=lines, page_number=page_number), fn_refs

        # Normal prose paragraph
        return Paragraph(text=full_text, page_number=page_number), fn_refs

    def _format_run(self, r: Run) -> str:
        text = r.text
        if not text:
            return ""

        if r.font.name and is_monospace_font(r.font.name):
            text = f"`{text}`"
        if r.bold:
            text = f"**{text}**"
        if r.italic:
            text = f"*{text}*"
        if r.font.strike:
            text = f"~~{text}~~"
        if r.font.superscript:
            text = f"^{text}^"
        if r.font.subscript:
            text = f"~{text}~"
        return text

    def _extract_paragraph_images(self, p: DocxParagraph) -> list[ImageRef]:
        """Detect drawings and inline blips in a paragraph and map to ImageRef."""
        images: list[ImageRef] = []
        for blip in p._element.xpath(".//a:blip"):
            embed_id = blip.get(qn("r:embed"))
            if not embed_id or embed_id not in self.rel_map:
                continue
            target = self.rel_map[embed_id]
            local_path = (
                self.image_path_map.get(target)
                or self.image_path_map.get(Path(target).name)
                or self.image_path_map.get(f"word/{target}")
            )
            if local_path and local_path.exists():
                images.append(
                    ImageRef(
                        source_path=str(local_path),
                        figure_id=Path(target).stem,
                    )
                )
        return images

    def _parse_table(self, table: Table, page_number: int) -> TableData | None:
        rows: list[list[str]] = []
        is_complex = False

        for row in table.rows:
            row_cells: list[str] = []
            for cell in row.cells:
                # Detect merged cells via gridSpan or vMerge in cell XML
                grid_span = cell._tc.xpath(".//w:gridSpan")
                v_merge = cell._tc.xpath(".//w:vMerge")
                if grid_span or v_merge:
                    is_complex = True
                cell_text = cell.text.strip().replace("\n", " ")
                row_cells.append(cell_text)
            if row_cells:
                rows.append(row_cells)

        if not rows:
            return None
        return TableData(cells=rows, is_complex=is_complex, page_number=page_number)

    def _resolve_profile(self, bookmarks: list[Bookmark]) -> ProfileName:
        if self.profile_override in ("literature", "technical"):
            return self.profile_override  # type: ignore[return-value]

        score = 0
        if self.numbered_headings_count >= 2:
            score += 3
        elif self.numbered_headings_count == 1:
            score += 1

        if any(NUMBERED_HEADING_RE.match(bm.title) for bm in bookmarks):
            score += 3

        if self.code_count >= 2:
            score += 3
        elif self.code_count == 1:
            score += 1

        if self.table_count >= 2:
            score += 2
        elif self.table_count == 1:
            score += 1

        detected: ProfileName = "technical" if score >= 3 else "literature"
        logger.info("DOCX profile auto-detected as '%s' (score=%d)", detected, score)
        return detected


def parse_docx(
    docx_path: Path, profile_override: str = "auto"
) -> tuple[BookManifest, DocumentTree]:
    """Public entry point for DOCX manuscript ingestion."""
    ingester = DocxIngester(docx_path, profile_override=profile_override)
    return ingester.ingest()
