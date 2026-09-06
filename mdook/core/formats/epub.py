"""Stage 1-3 Ingestion for EPUB3 / EPUB2 Documents.

Directly ingests EPUB packages into `mdook.core.models.DocumentTree` and
`mdook.core.models.BookManifest`, bypassing PDF-specific extraction and
heuristic clustering. See `Mdook-docs/ROADMAP.md` (Phase 4).

Features:
- Reads EPUB container, OPF manifest/spine, Dublin Core metadata.
- Extracts navigation hierarchy (nav.xhtml / toc.ncx) into bookmarks & chapters.
- Extracts embedded images to a temporary cache for Stage 4 attachment copying.
- Maps semantic XHTML tags into DocumentTree content items:
  * h1-h6 -> Chapter titles and Section hierarchy
  * p -> Paragraph (with inline bold, italic, code, links)
  * blockquote -> BlockQuote (with optional attribution)
  * ul/ol/li -> ListData with ListItem
  * table/tr/th/td -> TableData (detects merged cells -> is_complex)
  * pre/code -> CodeBlock (verbatim line preservation)
  * img -> ImageRef (linked to extracted asset)
  * aside/div (callouts) -> CalloutBlock
  * math/span.math -> MathBlock
  * epub:type footnote/noteref & <a href="#fn..."> -> Footnote & sentinels
- Classifies front matter, body chapters, and back matter divisions.
- Auto-detects literature vs technical profile if profile is 'auto'.
"""

from __future__ import annotations

import logging
import re
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import unquote

import ebooklib
from bs4 import BeautifulSoup, NavigableString, Tag
from ebooklib import epub

from mdook.core.models import (
    BlockQuote,
    BookManifest,
    Bookmark,
    BookMetadata,
    CalloutBlock,
    Chapter,
    CodeBlock,
    DocumentTree,
    Footnote,
    ImageRef,
    ListData,
    ListItem,
    MathBlock,
    Paragraph,
    ProfileName,
    Section,
    SectionContent,
    TableData,
    ZoneEntry,
)
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


class EpubIngester:
    """Parses an EPUB file directly into a BookManifest and DocumentTree."""

    def __init__(self, epub_path: Path, profile_override: str = "auto") -> None:
        self.epub_path = epub_path
        self.profile_override = profile_override
        self.temp_img_dir = Path(tempfile.mkdtemp(prefix="mdook_epub_img_"))
        self.image_path_map: dict[str, Path] = {}
        self.footnotes_by_id: dict[str, str] = {}
        self.table_count = 0
        self.code_count = 0
        self.math_count = 0
        self.numbered_headings_count = 0

    def ingest(self) -> tuple[BookManifest, DocumentTree]:
        book = epub.read_epub(str(self.epub_path), options={"ignore_ncx": False})

        metadata = self._extract_metadata(book)
        self._extract_images(book)
        bookmarks = self._extract_toc_bookmarks(book)

        front_matter: list[Section] = []
        chapters: list[Chapter] = []
        back_matter: list[Section] = []

        spine_docs = self._collect_spine_documents(book)
        page_counter = 1

        for doc_item in spine_docs:
            content_bytes = doc_item.get_content()
            soup = BeautifulSoup(content_bytes, "html.parser")

            # Extract footnote definitions in this document
            self._extract_footnote_definitions(soup)

            doc_title = self._determine_doc_title(doc_item, soup)
            division = self._classify_division(doc_item, soup, doc_title)

            sections, doc_footnotes = self._parse_html_body(soup, page_counter, doc_title=doc_title)

            if not sections and not doc_footnotes:
                continue

            if division == "front_matter":
                for sec in sections:
                    if sec.title is None:
                        sec.title = doc_title
                    front_matter.append(sec)
            elif division == "back_matter":
                for sec in sections:
                    if sec.title is None:
                        sec.title = doc_title
                    back_matter.append(sec)
            else:
                chapter_num = len(chapters) + 1
                chapter = Chapter(
                    number=chapter_num,
                    title=doc_title or f"Chapter {chapter_num}",
                    level=1,
                    sections=sections,
                    footnotes=doc_footnotes,
                    page_spans=[(page_counter, page_counter)],
                )
                chapters.append(chapter)
                page_counter += 1

        # Fallback: if everything fell into front_matter and no chapters exist
        if not chapters and front_matter:
            for idx, sec in enumerate(front_matter, start=1):
                chapters.append(
                    Chapter(
                        number=idx,
                        title=sec.title or f"Section {idx}",
                        level=1,
                        sections=[sec],
                        page_spans=[(idx, idx)],
                    )
                )
            front_matter = []

        total_pages = max(len(chapters), 1)

        # Profile resolution
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

        manifest_meta: dict[str, Any] = {}
        if metadata.isbn:
            manifest_meta["isbn"] = metadata.isbn
        if metadata.publisher:
            manifest_meta["publisher"] = metadata.publisher
        manifest_meta.update(metadata.extra)

        manifest = BookManifest(
            file_path=str(self.epub_path),
            title=metadata.title,
            author=metadata.author,
            total_pages=total_pages,
            needs_ocr=False,
            profile=resolved_profile,
            zone_map=zone_map,
            bookmarks=bookmarks or None,
            metadata=manifest_meta,
        )

        tree = DocumentTree(
            metadata=metadata,
            front_matter=front_matter,
            chapters=chapters,
            back_matter=back_matter,
        )

        return manifest, tree

    # -----------------------------------------------------------------------
    # Metadata & Assets
    # -----------------------------------------------------------------------

    def _extract_metadata(self, book: epub.EpubBook) -> BookMetadata:
        def get_dc(name: str) -> str | None:
            entries = book.get_metadata("DC", name)
            if entries and entries[0]:
                val = entries[0][0]
                return str(val).strip() if val else None
            return None

        title = get_dc("title") or self.epub_path.stem
        author = get_dc("creator") or "Unknown"
        publisher = get_dc("publisher")

        extra: dict[str, Any] = {}
        raw_date = get_dc("date")
        if raw_date:
            m = re.search(r"\b(\d{4})\b", raw_date)
            if m:
                extra["year"] = int(m.group(1))

        isbn = None
        for entry in book.get_metadata("DC", "identifier"):
            ident = str(entry[0]).strip()
            if "isbn" in ident.lower() or re.match(r"^(?:97[89])?\d{9}[\dX]$", ident):
                isbn = ident
                break
        if not isbn and book.get_metadata("DC", "identifier"):
            isbn = str(book.get_metadata("DC", "identifier")[0][0]).strip()

        language = get_dc("language")
        if language:
            extra["language"] = language
        description = get_dc("description")
        if description:
            extra["description"] = description

        return BookMetadata(
            title=title,
            author=author,
            isbn=isbn,
            publisher=publisher,
            extra=extra,
        )

    def _extract_images(self, book: epub.EpubBook) -> None:
        """Extract embedded image files to temp_img_dir for Stage 4 attachment copying."""
        for item in book.get_items_of_type(ebooklib.ITEM_IMAGE):
            file_name = item.get_name()
            dest_file = self.temp_img_dir / Path(file_name).name
            try:
                dest_file.write_bytes(item.get_content())
                self.image_path_map[file_name] = dest_file
                self.image_path_map[Path(file_name).name] = dest_file
                self.image_path_map[unquote(file_name)] = dest_file
                self.image_path_map[unquote(Path(file_name).name)] = dest_file
            except Exception as exc:
                logger.debug("Failed extracting image %s: %s", file_name, exc)

    def _extract_toc_bookmarks(self, book: epub.EpubBook) -> list[Bookmark]:
        """Flatten EPUB TOC hierarchy into a list of Bookmark objects."""
        bookmarks: list[Bookmark] = []

        def walk_toc(entries: list[Any], level: int = 1) -> None:
            for item in entries:
                if isinstance(item, (list, tuple)):
                    if len(item) == 2 and isinstance(item[0], epub.Section):
                        section, sub_items = item
                        bookmarks.append(
                            Bookmark(
                                level=level,
                                title=section.title,
                                page_number=len(bookmarks) + 1,
                            )
                        )
                        walk_toc(sub_items, level=level + 1)
                    else:
                        walk_toc(list(item), level=level)
                elif isinstance(item, epub.Link):
                    bookmarks.append(
                        Bookmark(
                            level=level,
                            title=item.title,
                            page_number=len(bookmarks) + 1,
                        )
                    )
                elif isinstance(item, epub.Section):
                    bookmarks.append(
                        Bookmark(
                            level=level,
                            title=item.title,
                            page_number=len(bookmarks) + 1,
                        )
                    )

        try:
            walk_toc(book.toc)
        except Exception as exc:
            logger.debug("Error reading EPUB TOC: %s", exc)

        return bookmarks

    def _collect_spine_documents(self, book: epub.EpubBook) -> list[epub.EpubHtml]:
        """Collect HTML spine items in linear reading order, excluding nav doc."""
        documents: list[epub.EpubHtml] = []
        for item in book.spine:
            item_id = item[0] if isinstance(item, tuple) else item
            doc = book.get_item_with_id(item_id)
            if not doc or not isinstance(doc, epub.EpubHtml):
                continue
            # Skip pure nav documents (nav.xhtml, toc.ncx)
            file_name = doc.get_name().lower()
            if "nav" in file_name and ("toc" in file_name or file_name.endswith("nav.xhtml")):
                continue
            documents.append(doc)

        if not documents:
            # Fallback to all document items if spine is empty
            documents = [
                d
                for d in book.get_items_of_type(ebooklib.ITEM_DOCUMENT)
                if isinstance(d, epub.EpubHtml)
            ]
        return documents

    # -----------------------------------------------------------------------
    # Footnote Definitions & Division Classification
    # -----------------------------------------------------------------------

    def _extract_footnote_definitions(self, soup: BeautifulSoup) -> None:
        """Find footnote definition elements, record their text by ID, and remove them."""
        # Standard EPUB3: <aside epub:type="footnote" id="...">
        # Common pattern: <div class="footnote" id="...">, <li id="fn...">
        candidates: list[Tag] = []
        for tag in soup.find_all(["aside", "div", "li", "p"]):
            epub_type = tag.get("epub:type", "")
            tag_id = tag.get("id") or ""
            classes = tag.get("class") or []
            class_str = " ".join(classes).lower()

            is_fn = (
                "footnote" in epub_type
                or "endnote" in epub_type
                or "footnote" in class_str
                or "endnote" in class_str
                or (tag_id.startswith(("fn", "note-", "footnote-")) and tag.name in ("aside", "li"))
            )
            if is_fn and tag_id:
                candidates.append(tag)

        for tag in candidates:
            tag_id = tag["id"]
            text = tag.get_text().strip()
            # Clean leading markers like "[1]", "1." from definition text
            cleaned_text = re.sub(r"^(?:\[\d+\]|\d+[\.:\s]+|\^|\*)\s*", "", text).strip()
            self.footnotes_by_id[tag_id] = cleaned_text or text
            tag.decompose()

    def _determine_doc_title(self, doc_item: epub.EpubHtml, soup: BeautifulSoup) -> str:
        h1 = soup.find(["h1", "h2"])
        if h1 and h1.get_text().strip():
            return h1.get_text().strip()
        if doc_item.title and doc_item.title.strip():
            return doc_item.title.strip()
        name = Path(doc_item.get_name()).stem
        name_clean = re.sub(r"[-_]", " ", name).strip().title()
        return name_clean

    def _classify_division(
        self, doc_item: epub.EpubHtml, soup: BeautifulSoup, doc_title: str
    ) -> str:
        """Classifies document as 'front_matter', 'body', or 'back_matter'."""
        body_tag = soup.find("body")
        epub_type = (body_tag.get("epub:type", "") if body_tag else "").lower()
        title_lower = doc_title.lower().strip()

        for label in FRONT_MATTER_LABELS:
            if label in epub_type or title_lower == label or title_lower.startswith(f"{label} "):
                return "front_matter"

        for label in BACK_MATTER_LABELS:
            if label in epub_type or title_lower == label or title_lower.startswith(f"{label} "):
                return "back_matter"

        return "body"

    # -----------------------------------------------------------------------
    # HTML to DocumentTree Content Parsing
    # -----------------------------------------------------------------------

    def _parse_html_body(
        self, soup: BeautifulSoup, page_number: int, doc_title: str = ""
    ) -> tuple[list[Section], list[Footnote]]:
        """Transforms the HTML body into structured Section objects and Footnotes."""
        body = soup.find("body") or soup
        sections: list[Section] = []
        current_section = Section(title=None, level=2, content=[])
        doc_footnotes: list[Footnote] = []
        seen_footnotes: set[str] = set()

        for element in body.children:
            if isinstance(element, NavigableString):
                text = str(element).strip()
                if text:
                    current_section.content.append(Paragraph(text=text, page_number=page_number))
                continue

            if not isinstance(element, Tag):
                continue

            # Heading elements: h1-h6
            if element.name in ("h1", "h2", "h3", "h4", "h5", "h6"):
                heading_level = int(element.name[1])
                heading_text = element.get_text().strip()
                if not heading_text:
                    continue

                if NUMBERED_HEADING_RE.match(heading_text):
                    self.numbered_headings_count += 1

                # If H1 matches document/chapter title, don't duplicate as a sub-section
                if heading_level == 1 and doc_title and heading_text.lower() == doc_title.lower():
                    continue

                if current_section.content or current_section.title:
                    sections.append(current_section)
                current_section = Section(title=heading_text, level=heading_level, content=[])
                continue

            # Block elements
            content_item, fn_refs = self._parse_block_element(element, page_number)
            if content_item:
                current_section.content.append(content_item)

            for marker, fn_id in fn_refs:
                if marker not in seen_footnotes:
                    seen_footnotes.add(marker)
                    fn_text = self.footnotes_by_id.get(fn_id) or self.footnotes_by_id.get(
                        marker, ""
                    )
                    if not fn_text:
                        fn_text = f"Footnote {marker}"
                    doc_footnotes.append(
                        Footnote(
                            marker=marker,
                            text=fn_text,
                            page_number=page_number,
                            style="page_bottom",
                        )
                    )

        if current_section.content or current_section.title:
            sections.append(current_section)

        return sections, doc_footnotes

    def _parse_block_element(
        self, tag: Tag, page_number: int
    ) -> tuple[SectionContent | None, list[tuple[str, str]]]:
        """Parses an individual block-level HTML tag into SectionContent."""
        fn_refs: list[tuple[str, str]] = []

        # 1. Paragraph <p>
        if tag.name == "p":
            text, refs = self._html_to_markdown_inline(tag)
            fn_refs.extend(refs)
            text = text.strip()
            if not text:
                return None, fn_refs
            return Paragraph(text=text, page_number=page_number), fn_refs

        # 2. BlockQuote <blockquote>
        if tag.name == "blockquote":
            lines: list[str] = []
            attribution: str | None = None
            for child in tag.find_all(["p", "div"]):
                child_classes = " ".join(child.get("class") or []).lower()
                if "attribution" in child_classes or "author" in child_classes:
                    attribution = child.get_text().strip()
                else:
                    t, refs = self._html_to_markdown_inline(child)
                    fn_refs.extend(refs)
                    if t.strip():
                        lines.append(t.strip())
            cite = tag.find("cite")
            if cite and not attribution:
                attribution = cite.get_text().strip()
            if not lines:
                t, refs = self._html_to_markdown_inline(tag)
                fn_refs.extend(refs)
                lines = [line.strip() for line in t.splitlines() if line.strip()]
            if not lines:
                return None, fn_refs
            return (
                BlockQuote(
                    lines=lines,
                    attribution=attribution,
                    page_number=page_number,
                    italic=True,
                ),
                fn_refs,
            )

        # 3. Lists <ul>, <ol>
        if tag.name in ("ul", "ol"):
            ordered = tag.name == "ol"
            items: list[ListItem] = []
            for idx, li in enumerate(tag.find_all("li", recursive=False), start=1):
                li_text, refs = self._html_to_markdown_inline(li)
                fn_refs.extend(refs)
                items.append(
                    ListItem(
                        text=li_text.strip(),
                        level=0,
                        ordered=ordered,
                        marker=str(idx) if ordered else None,
                    )
                )
            if not items:
                return None, fn_refs
            return ListData(items=items, page_number=page_number), fn_refs

        # 4. Table <table>
        if tag.name == "table":
            self.table_count += 1
            rows: list[list[str]] = []
            is_complex = False
            for tr in tag.find_all("tr"):
                row_cells: list[str] = []
                for cell in tr.find_all(["th", "td"]):
                    colspan = int(cell.get("colspan", 1))
                    rowspan = int(cell.get("rowspan", 1))
                    if colspan > 1 or rowspan > 1:
                        is_complex = True
                    cell_text, refs = self._html_to_markdown_inline(cell)
                    fn_refs.extend(refs)
                    row_cells.append(cell_text.strip().replace("\n", " "))
                if row_cells:
                    rows.append(row_cells)
            if not rows:
                return None, fn_refs
            return TableData(cells=rows, is_complex=is_complex, page_number=page_number), fn_refs

        # 5. CodeBlock <pre>, <code>
        if tag.name == "pre" or (tag.name == "div" and "highlight" in (tag.get("class") or [])):
            self.code_count += 1
            code_el = tag.find("code") or tag
            code_text = code_el.get_text()
            lines = code_text.splitlines()
            return CodeBlock(lines=lines, page_number=page_number), fn_refs

        # 6. Image <img>
        if tag.name == "img":
            img_ref = self._build_image_ref(tag)
            return img_ref, fn_refs

        # 7. Figure <figure>
        if tag.name == "figure":
            img_tag = tag.find("img")
            if img_tag:
                img_ref = self._build_image_ref(img_tag)
                figcaption = tag.find("figcaption")
                if figcaption and img_ref:
                    img_ref.caption = figcaption.get_text().strip()
                return img_ref, fn_refs

        # 8. Callout <aside>, <div class="callout|note|warning">
        classes = " ".join(tag.get("class") or []).lower()
        if tag.name == "aside" or any(
            c in classes for c in ("callout", "note", "warning", "tip", "important", "caution")
        ):
            label = "Note"
            for candidate in ("warning", "tip", "caution", "important", "info", "note"):
                if candidate in classes:
                    label = candidate.capitalize()
                    break
            paragraphs: list[str] = []
            for p in tag.find_all("p"):
                pt, refs = self._html_to_markdown_inline(p)
                fn_refs.extend(refs)
                if pt.strip():
                    paragraphs.append(pt.strip())
            if not paragraphs:
                text, refs = self._html_to_markdown_inline(tag)
                fn_refs.extend(refs)
                paragraphs = [text.strip()] if text.strip() else []
            if paragraphs:
                return CalloutBlock(
                    label=label, paragraphs=paragraphs, page_number=page_number
                ), fn_refs

        # 9. Math <math> or <span class="math">
        if tag.name == "math" or "math" in classes:
            self.math_count += 1
            math_text = tag.get_text().strip()
            display = tag.get("display") == "block" or "display" in classes
            return MathBlock(
                latex_or_text=math_text,
                display=display,
                numbering=None,
                page_number=page_number,
            ), fn_refs

        # 10. Generic <div> / <section> wrapper: process inner block elements
        # If div contains text directly without child tags
        child_tags = [c for c in tag.children if isinstance(c, Tag)]
        if not child_tags:
            text, refs = self._html_to_markdown_inline(tag)
            fn_refs.extend(refs)
            text = text.strip()
            if text:
                return Paragraph(text=text, page_number=page_number), fn_refs
            return None, fn_refs

        return None, fn_refs

    # -----------------------------------------------------------------------
    # Inline HTML to Markdown Conversion
    # -----------------------------------------------------------------------

    def _html_to_markdown_inline(self, element: Tag) -> tuple[str, list[tuple[str, str]]]:
        """Convert inline HTML tags to Markdown and extract footnote links."""
        parts: list[str] = []
        fn_refs: list[tuple[str, str]] = []

        for child in element.children:
            if isinstance(child, NavigableString):
                parts.append(str(child))
                continue

            if not isinstance(child, Tag):
                continue

            tag_name = child.name
            href = child.get("href", "")
            epub_type = child.get("epub:type", "")

            # Footnote link check
            is_footnote_link = (
                "noteref" in epub_type
                or "footnote" in epub_type
                or (href and ("#fn" in href or "#footnote" in href or "#note" in href))
            )

            if is_footnote_link:
                marker = child.get_text().strip("[]^ ")
                fn_id = href.split("#")[-1] if "#" in href else marker
                marker = marker or fn_id
                fn_refs.append((marker, fn_id))
                parts.append(f"{FOOTNOTE_MARKER_SENTINEL}{marker}{FOOTNOTE_MARKER_SENTINEL}")
                continue

            if tag_name in ("b", "strong"):
                inner, refs = self._html_to_markdown_inline(child)
                fn_refs.extend(refs)
                parts.append(f"**{inner}**")
            elif tag_name in ("i", "em"):
                inner, refs = self._html_to_markdown_inline(child)
                fn_refs.extend(refs)
                parts.append(f"*{inner}*")
            elif tag_name == "code":
                parts.append(f"`{child.get_text()}`")
            elif tag_name in ("s", "strike", "del"):
                inner, refs = self._html_to_markdown_inline(child)
                fn_refs.extend(refs)
                parts.append(f"~~{inner}~~")
            elif tag_name == "a":
                inner, refs = self._html_to_markdown_inline(child)
                fn_refs.extend(refs)
                if href and not href.startswith("#"):
                    parts.append(f"[{inner}]({href})")
                else:
                    parts.append(inner)
            elif tag_name == "br":
                parts.append("\n")
            elif tag_name == "sup":
                inner, refs = self._html_to_markdown_inline(child)
                fn_refs.extend(refs)
                parts.append(f"^{inner}^")
            elif tag_name == "sub":
                inner, refs = self._html_to_markdown_inline(child)
                fn_refs.extend(refs)
                parts.append(f"~{inner}~")
            else:
                inner, refs = self._html_to_markdown_inline(child)
                fn_refs.extend(refs)
                parts.append(inner)

        raw = "".join(parts)
        # Normalize consecutive spaces, but preserve newlines
        cleaned = re.sub(r"[ \t]+", " ", raw)
        return cleaned, fn_refs

    def _build_image_ref(self, img_tag: Tag) -> ImageRef | None:
        src = img_tag.get("src", "")
        if not src:
            return None

        clean_src = unquote(src).split("#")[0].split("?")[0]
        local_path = (
            self.image_path_map.get(clean_src)
            or self.image_path_map.get(Path(clean_src).name)
            or self.image_path_map.get(src)
        )
        if not local_path:
            return None

        alt = img_tag.get("alt", "").strip() or None
        return ImageRef(
            source_path=str(local_path),
            caption=alt,
            figure_id=Path(clean_src).stem,
        )

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

        if self.code_count >= 3:
            score += 3
        elif self.code_count >= 1:
            score += 1

        if self.table_count >= 2:
            score += 2
        elif self.table_count == 1:
            score += 1

        if self.math_count >= 2:
            score += 3
        elif self.math_count == 1:
            score += 1

        detected: ProfileName = "technical" if score >= 3 else "literature"
        logger.info("EPUB profile auto-detected as '%s' (score=%d)", detected, score)
        return detected


def parse_epub(
    epub_path: Path, profile_override: str = "auto"
) -> tuple[BookManifest, DocumentTree]:
    """Public entry point for EPUB ingestion."""
    ingester = EpubIngester(epub_path, profile_override=profile_override)
    return ingester.ingest()
