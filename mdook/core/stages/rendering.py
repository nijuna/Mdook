"""Stage 4 — Rendering.

Input: `mdook.core.models.DocumentTree` + `mdook.core.models.BookManifest` +
an output directory path.
Output: files on disk — the Obsidian vault.

Implements the conventions from `Mdook-docs/ARCHITECTURE.md` ("Stage 4"):
- Index file with YAML frontmatter and a linked chapter list
- Chapter files: `# Title` heading, page markers as collapsed callouts
  (Rule 3.3), footnotes as `[^n]` syntax (Rule 4.4), images as `![[...]]`
  (Rule 7.5), tables as markdown pipe tables or inline HTML (Rules 6.2-6.3)

Simplifications:
- Page-marker callouts synthesize "p. N · Book Title, Ch. C" rather than
  quoting the book's original running header/footer text verbatim, since
  that text isn't threaded through `DocumentTree` (only `PageData`, which
  Stage 4's documented input doesn't include). Front/back matter files use
  just "p. N · Book Title" (no chapter number, since they aren't chapters).
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from mdook.core.models import (
    BlockQuote,
    BookManifest,
    CalloutBlock,
    Chapter,
    CodeBlock,
    DocumentTree,
    Footnote,
    GlossaryBlock,
    ImageRef,
    ListData,
    MathBlock,
    Paragraph,
    Section,
    SectionContent,
    TableData,
    VerseBlock,
)
from mdook.core.rules.callouts import obsidian_callout_type
from mdook.core.rules.citations import BIBLIOGRAPHY_SECTION_LABELS, CITATION_MARKER_SENTINEL
from mdook.core.rules.footnotes import NOTE_SECTION_LABELS
from mdook.core.rules.paragraphs import ENDNOTE_MARKER_SENTINEL, FOOTNOTE_MARKER_SENTINEL

INVALID_FILENAME_CHARS_RE = re.compile(r'[\\/:*?"<>|]')
FOOTNOTE_SENTINEL_RE = re.compile(f"{FOOTNOTE_MARKER_SENTINEL}(.+?){FOOTNOTE_MARKER_SENTINEL}")
ENDNOTE_SENTINEL_RE = re.compile(f"{ENDNOTE_MARKER_SENTINEL}(.+?){ENDNOTE_MARKER_SENTINEL}")
CITATION_SENTINEL_RE = re.compile(f"{CITATION_MARKER_SENTINEL}(.+?){CITATION_MARKER_SENTINEL}")
BACK_MATTER_STEM = "Back Matter"


@dataclass
class BackMatterDivision:
    title: str
    filename: str
    stem: str
    sections: list[Section]


def _split_back_matter(sections: list[Section]) -> list[BackMatterDivision]:
    if not sections:
        return []

    divisions: list[BackMatterDivision] = []
    used_stems: set[str] = set()

    def make_unique_stem(base_title: str) -> tuple[str, str]:
        sanitized = _sanitize_filename(base_title) or "Back Matter"
        candidate = sanitized
        count = 2
        while candidate.lower() in used_stems:
            candidate = f"{sanitized} {count}"
            count += 1
        used_stems.add(candidate.lower())
        return candidate, f"{candidate}.md"

    current_title: str | None = None
    current_sections: list[Section] = []

    for section in sections:
        if section.level == 1 or not current_sections:
            if current_sections:
                stem, filename = make_unique_stem(current_title or "Back Matter")
                divisions.append(
                    BackMatterDivision(
                        title=current_title or "Back Matter",
                        filename=filename,
                        stem=stem,
                        sections=current_sections,
                    )
                )
            current_title = section.title
            current_sections = [section]
        else:
            current_sections.append(section)

    if current_sections:
        stem, filename = make_unique_stem(current_title or "Back Matter")
        divisions.append(
            BackMatterDivision(
                title=current_title or "Back Matter",
                filename=filename,
                stem=stem,
                sections=current_sections,
            )
        )

    return divisions


@dataclass
class RenderResult:
    vault_dir: Path
    index_path: Path
    chapter_paths: list[Path] = field(default_factory=list)
    back_matter_paths: list[Path] = field(default_factory=list)
    attachments_dir: Path = field(default_factory=Path)
    attachment_filenames: set[str] = field(default_factory=set)


def render_vault(tree: DocumentTree, manifest: BookManifest, output_dir: Path) -> RenderResult:
    """Writes the vault into `output_dir / {book title}/`, matching the
    layout in `Mdook-docs/ARCHITECTURE.md` ("Output Vault Structure") --
    `output_dir` is the folder the user picked to hold vaults, not the vault
    itself, so a book's files never land loose alongside unrelated content
    (or another book's files) in that folder."""
    vault_dir = output_dir / _sanitize_filename(manifest.title)
    vault_dir.mkdir(parents=True, exist_ok=True)
    attachments_dir = vault_dir / "attachments"

    attachment_filenames: set[str] = set()

    back_matter_divisions = _split_back_matter(tree.back_matter)

    # Computed up front so inline endnote and citation references spliced into
    # chapters or front-matter can link directly to their dedicated files.
    notes_stem: str | None = None
    bibliography_stem: str | None = None
    for div in back_matter_divisions:
        normalized = _normalize_matter_title(div.title)
        if notes_stem is None and normalized in NOTE_SECTION_LABELS:
            notes_stem = div.stem
        if bibliography_stem is None and normalized in BIBLIOGRAPHY_SECTION_LABELS:
            bibliography_stem = div.stem

    # Fallback to generic Back Matter division if no keyword-labeled division was found
    if notes_stem is None:
        for div in back_matter_divisions:
            if _normalize_matter_title(div.title) in ("back matter", "untitled"):
                notes_stem = div.stem
                break
    if bibliography_stem is None:
        for div in back_matter_divisions:
            if _normalize_matter_title(div.title) in ("back matter", "untitled"):
                bibliography_stem = div.stem
                break

    front_matter_path: Path | None = None
    if tree.front_matter:
        body, used = _render_matter(
            "Front Matter",
            tree.front_matter,
            manifest,
            attachments_dir,
            notes_stem=notes_stem,
            bibliography_stem=bibliography_stem,
        )
        front_matter_path = vault_dir / "00 - Front Matter.md"
        front_matter_path.write_text(body, encoding="utf-8")
        attachment_filenames.update(used)

    chapter_paths: list[Path] = []
    for chapter in tree.chapters:
        filename = f"{chapter.number:02d} - {_sanitize_filename(chapter.title)}.md"
        path = vault_dir / filename
        body, used_attachments = _render_chapter(
            chapter,
            manifest,
            attachments_dir,
            notes_stem=notes_stem,
            bibliography_stem=bibliography_stem,
        )
        path.write_text(body, encoding="utf-8")
        chapter_paths.append(path)
        attachment_filenames.update(used_attachments)

    back_matter_files: list[tuple[str, Path]] = []
    back_matter_paths: list[Path] = []
    for div in back_matter_divisions:
        path = vault_dir / div.filename
        body, used = _render_back_matter_division(
            div,
            manifest,
            attachments_dir,
            notes_stem=notes_stem,
            bibliography_stem=bibliography_stem,
        )
        path.write_text(body, encoding="utf-8")
        back_matter_files.append((div.title, path))
        back_matter_paths.append(path)
        attachment_filenames.update(used)

    index_path = vault_dir / f"{_sanitize_filename(manifest.title)} - Index.md"
    index_path.write_text(
        _render_index(tree, manifest, chapter_paths, front_matter_path, back_matter_files),
        encoding="utf-8",
    )

    return RenderResult(
        vault_dir=vault_dir,
        index_path=index_path,
        chapter_paths=chapter_paths,
        back_matter_paths=back_matter_paths,
        attachments_dir=attachments_dir,
        attachment_filenames=attachment_filenames,
    )


# ---------------------------------------------------------------------------
# Index file
# ---------------------------------------------------------------------------


def _render_index(
    tree: DocumentTree,
    manifest: BookManifest,
    chapter_paths: list[Path],
    front_matter_path: Path | None,
    back_matter_files: list[tuple[str, Path]] | Path | None,
) -> str:
    frontmatter = ["---", f"title: {tree.metadata.title}", f"author: {tree.metadata.author}"]
    if tree.metadata.isbn:
        frontmatter.append(f"isbn: {tree.metadata.isbn}")
    if tree.metadata.publisher:
        frontmatter.append(f"publisher: {tree.metadata.publisher}")
    if tree.metadata.edition:
        frontmatter.append(f"edition: {tree.metadata.edition}")
    frontmatter.append(f"profile: {manifest.profile}")
    frontmatter.append(f"converted: {date.today().isoformat()}")
    frontmatter.append("---")
    frontmatter.append("")

    body = [f"# {tree.metadata.title}", ""]
    if front_matter_path is not None:
        body.append(f"- [[{front_matter_path.stem}|Front Matter]]")
    current_part: str | None = None
    for chapter, path in zip(tree.chapters, chapter_paths, strict=True):
        if chapter.part_title != current_part:
            current_part = chapter.part_title
            if current_part is not None:
                body.append("")
                body.append(f"## {current_part}")
        body.append(f"- [[{path.stem}|{chapter.title}]]")

    if back_matter_files:
        files: list[tuple[str, Path]]
        if isinstance(back_matter_files, Path):
            files = [("Back Matter", back_matter_files)]
        else:
            files = back_matter_files
        body.append("")
        body.append("## Back Matter")
        for title, path in files:
            body.append(f"- [[{path.stem}|{title}]]")

    return "\n".join(frontmatter + body) + "\n"


# ---------------------------------------------------------------------------
# Chapter / front-matter / back-matter files
# ---------------------------------------------------------------------------


def _render_chapter(
    chapter: Chapter,
    manifest: BookManifest,
    attachments_dir: Path,
    notes_stem: str | None,
    bibliography_stem: str | None,
) -> tuple[str, set[str]]:
    footnotes_by_page = _group_footnotes_by_page(chapter.footnotes)
    lines, used_attachments = _render_sections(
        chapter.sections,
        footnotes_by_page,
        page_label=lambda page: f"p. {page} · {manifest.title}, Ch. {chapter.number}",
        attachments_dir=attachments_dir,
        notes_stem=notes_stem,
        bibliography_stem=bibliography_stem,
        anchor_prefix=None,
        skip_first_heading=False,
    )
    return "\n".join([f"# {chapter.title}", ""] + lines).rstrip() + "\n", used_attachments


def _render_matter(
    title: str,
    sections: list[Section],
    manifest: BookManifest,
    attachments_dir: Path,
    notes_stem: str | None = None,
    bibliography_stem: str | None = None,
    back_matter_stem: str | None = None,
    is_back_matter_file: bool = False,
) -> tuple[str, set[str]]:
    """Front matter has no per-section footnote list the way a `Chapter`
    does, so an inline marker spliced into this text by Stage 3 will render
    as `[^n]` with no matching definition -- Stage 5 surfaces that as an
    orphan-marker warning rather than silently dropping it."""
    effective_notes = notes_stem or back_matter_stem
    effective_bib = bibliography_stem or back_matter_stem
    lines, used_attachments = _render_sections(
        sections,
        footnotes_by_page={},
        page_label=lambda page: f"p. {page} · {manifest.title}",
        attachments_dir=attachments_dir,
        notes_stem=effective_notes,
        bibliography_stem=effective_bib,
        anchor_prefix=None,
        skip_first_heading=False,
    )
    return "\n".join([f"# {title}", ""] + lines).rstrip() + "\n", used_attachments


def _render_back_matter_division(
    division: BackMatterDivision,
    manifest: BookManifest,
    attachments_dir: Path,
    notes_stem: str | None,
    bibliography_stem: str | None,
) -> tuple[str, set[str]]:
    normalized_title = _normalize_matter_title(division.title)
    anchor_prefix: str | None = None
    if normalized_title in NOTE_SECTION_LABELS:
        anchor_prefix = "note"
    elif normalized_title in BIBLIOGRAPHY_SECTION_LABELS:
        anchor_prefix = "ref"

    lines, used_attachments = _render_sections(
        division.sections,
        footnotes_by_page={},
        page_label=lambda page: f"p. {page} · {manifest.title}",
        attachments_dir=attachments_dir,
        notes_stem=notes_stem,
        bibliography_stem=bibliography_stem,
        anchor_prefix=anchor_prefix,
        skip_first_heading=True,
    )
    return "\n".join([f"# {division.title}", ""] + lines).rstrip() + "\n", used_attachments


def _render_sections(
    sections: list[Section],
    footnotes_by_page: dict[int, list[Footnote]],
    page_label,
    attachments_dir: Path,
    notes_stem: str | None,
    bibliography_stem: str | None,
    anchor_prefix: str | None = None,
    skip_first_heading: bool = False,
) -> tuple[list[str], set[str]]:
    lines: list[str] = []
    used_attachments: set[str] = set()
    current_page: int | None = None

    for idx, section in enumerate(sections):
        if section.title:
            if idx == 0 and skip_first_heading:
                pass
            else:
                heading_level = max(section.level, 2) if skip_first_heading else section.level + 1
                lines.append(f"{'#' * heading_level} {section.title}")
                lines.append("")

        for item in section.content:
            item_page = getattr(item, "page_number", None)
            if item_page is not None and item_page != current_page:
                if current_page is not None:
                    lines.extend(
                        _render_footnote_definitions(footnotes_by_page.get(current_page, []))
                    )
                lines.append(f"> [!quote]- {page_label(item_page)}")
                lines.append("")
                current_page = item_page

            lines.extend(
                _render_content_item(
                    item,
                    attachments_dir,
                    used_attachments,
                    notes_stem=notes_stem,
                    bibliography_stem=bibliography_stem,
                    anchor_prefix=anchor_prefix,
                )
            )
            lines.append("")

    if current_page is not None:
        lines.extend(_render_footnote_definitions(footnotes_by_page.get(current_page, [])))

    return lines, used_attachments


def _normalize_matter_title(title: str) -> str:
    return " ".join(title.strip().lower().split()).rstrip(".:")


def _group_footnotes_by_page(footnotes: list[Footnote]) -> dict[int, list[Footnote]]:
    footnotes_by_page: dict[int, list[Footnote]] = defaultdict(list)
    for footnote in footnotes:
        footnotes_by_page[footnote.page_number].append(footnote)
    return footnotes_by_page


def _render_content_item(
    item: SectionContent,
    attachments_dir: Path,
    used_attachments: set[str],
    notes_stem: str | None,
    bibliography_stem: str | None,
    anchor_prefix: str | None,
) -> list[str]:
    if isinstance(item, Paragraph):
        return [
            _render_inline_markers(
                item.text, notes_stem=notes_stem, bibliography_stem=bibliography_stem
            )
        ]
    if isinstance(item, BlockQuote):
        template = "> *{}*" if item.italic else "> {}"
        quote_lines = [
            template.format(
                _render_inline_markers(
                    line, notes_stem=notes_stem, bibliography_stem=bibliography_stem
                )
            )
            for line in item.lines
        ]
        if item.attribution:
            quote_lines.append(f"> — {item.attribution}")
        return quote_lines
    if isinstance(item, ImageRef):
        filename = _copy_attachment(item, attachments_dir)
        used_attachments.add(filename)
        rendered = [f"![[{filename}]]"]
        if item.caption:
            rendered.append(f"*{item.caption}*")
        return rendered
    if isinstance(item, TableData):
        return _render_table(item)
    if isinstance(item, ListData):
        return _render_list(
            item,
            notes_stem=notes_stem,
            bibliography_stem=bibliography_stem,
            anchor_prefix=anchor_prefix,
        )
    if isinstance(item, CodeBlock):
        return ["```", *item.lines, "```"]
    if isinstance(item, CalloutBlock):
        callout_type = obsidian_callout_type(item.label)
        lines = [f"> [!{callout_type}] {item.label}"]
        lines.extend(
            f"> {_render_inline_markers(p, notes_stem, bibliography_stem)}"
            for p in item.paragraphs
            if p
        )
        return lines
    if isinstance(item, MathBlock):
        if item.display:
            lines = ["$$", item.latex_or_text, "$$"]
            if item.numbering:
                lines.append(f"({item.numbering})")
            return lines
        return [f"${item.latex_or_text}$"]
    if isinstance(item, VerseBlock):
        return _render_verse(item, notes_stem=notes_stem, bibliography_stem=bibliography_stem)
    if isinstance(item, GlossaryBlock):
        return _render_glossary_block(
            item, notes_stem=notes_stem, bibliography_stem=bibliography_stem
        )
    return []


def _render_glossary_block(
    item: GlossaryBlock,
    notes_stem: str | None = None,
    bibliography_stem: str | None = None,
) -> list[str]:
    lines: list[str] = []
    for entry in item.items:
        rendered_def = _render_inline_markers(
            entry.definition, notes_stem=notes_stem, bibliography_stem=bibliography_stem
        )
        if rendered_def:
            lines.append(f"**{entry.term}** — {rendered_def}")
        else:
            lines.append(f"**{entry.term}**")
        lines.append("")
    if lines and lines[-1] == "":
        lines.pop()
    return lines


def _render_verse(
    item: VerseBlock,
    notes_stem: str | None = None,
    bibliography_stem: str | None = None,
    back_matter_stem: str | None = None,
) -> list[str]:
    effective_notes = notes_stem or back_matter_stem
    effective_bib = bibliography_stem or back_matter_stem
    rendered_lines: list[str] = []
    prefix = "> " if item.is_quoted else ""
    for line in item.lines:
        if not line:
            rendered_lines.append(prefix.rstrip())
        else:
            processed = _render_inline_markers(
                line, notes_stem=effective_notes, bibliography_stem=effective_bib
            )
            rendered_lines.append(f"{prefix}{processed}  ")
    if item.attribution:
        rendered_lines.append(f"{prefix}— {item.attribution}")
    return rendered_lines


def _render_list(
    list_data: ListData,
    notes_stem: str | None,
    bibliography_stem: str | None,
    anchor_prefix: str | None,
) -> list[str]:
    lines: list[str] = []
    for item in list_data.items:
        indent = "    " * item.level
        text = _render_inline_markers(
            item.text, notes_stem=notes_stem, bibliography_stem=bibliography_stem
        )
        marker = f"{item.marker}." if item.ordered and item.marker else "-"
        line = f"{indent}{marker} {text}"
        if anchor_prefix is not None and item.ordered and item.marker:
            line += f" ^{anchor_prefix}-{item.marker}"
        lines.append(line)
    return lines


def _render_inline_markers(
    text: str,
    notes_stem: str | None = None,
    bibliography_stem: str | None = None,
    back_matter_stem: str | None = None,
) -> str:
    if back_matter_stem is not None:
        effective_notes = notes_stem or back_matter_stem
        effective_bib = bibliography_stem or back_matter_stem
    elif bibliography_stem is not None:
        effective_notes = notes_stem
        effective_bib = bibliography_stem
    else:
        effective_notes = notes_stem
        effective_bib = notes_stem

    text = _render_footnote_markers(text)
    text = _render_endnote_markers(text, effective_notes)
    return _render_citation_markers(text, effective_bib)


def _render_footnote_markers(text: str) -> str:
    """Rule 4.4 — turn a Rule 4.2 sentinel-wrapped marker into `[^n]`."""
    return FOOTNOTE_SENTINEL_RE.sub(lambda m: f"[^{m.group(1)}]", text)


def _render_endnote_markers(text: str, notes_stem: str | None) -> str:
    """Rule 4.3/4.4 — turn a sentinel-wrapped endnote reference into a
    wiki-link at the Notes section's `^note-N` block anchor, since Obsidian
    footnotes are file-scoped and can't point at a definition living in a
    different file."""
    if notes_stem is None:
        return text
    return ENDNOTE_SENTINEL_RE.sub(
        lambda m: f"[[{notes_stem}#^note-{m.group(1)}|{m.group(1)}]]", text
    )


def _render_citation_markers(text: str, bibliography_stem: str | None) -> str:
    """Batch 15 — turn a sentinel-wrapped numeric citation into a wiki-link
    at the Bibliography/References section's `^ref-N` block anchor, the
    same mechanism `_render_endnote_markers` uses for `^note-N`."""
    if bibliography_stem is None:
        return text
    return CITATION_SENTINEL_RE.sub(
        lambda m: f"[[{bibliography_stem}#^ref-{m.group(1)}|{m.group(1)}]]", text
    )


def _render_footnote_definitions(footnotes: list[Footnote]) -> list[str]:
    if not footnotes:
        return []
    lines = [f"[^{fn.marker}]: {fn.text}" for fn in footnotes]
    lines.append("")
    return lines


def _copy_attachment(image_ref: ImageRef, attachments_dir: Path) -> str:
    attachments_dir.mkdir(parents=True, exist_ok=True)
    source = Path(image_ref.source_path)
    extension = source.suffix or ".png"
    filename = f"{image_ref.figure_id or source.stem}{extension}"
    destination = attachments_dir / filename
    if source.exists() and not destination.exists():
        destination.write_bytes(source.read_bytes())
    return filename


def _render_table(table: TableData) -> list[str]:
    if not table.cells:
        return []
    if table.is_complex:
        rows = "".join(
            "<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in table.cells
        )
        return [f"<table>{rows}</table>"]

    header, *body_rows = table.cells
    lines = [
        "| " + " | ".join(header) + " |",
        "|" + "|".join(["---"] * len(header)) + "|",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in body_rows)
    return lines


def _sanitize_filename(text: str) -> str:
    cleaned = INVALID_FILENAME_CHARS_RE.sub("", text).strip()
    return cleaned or "Untitled"
