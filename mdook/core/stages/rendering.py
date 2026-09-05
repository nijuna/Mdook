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
    ImageRef,
    ListData,
    MathBlock,
    Paragraph,
    Section,
    SectionContent,
    TableData,
)
from mdook.core.rules.callouts import obsidian_callout_type
from mdook.core.rules.citations import BIBLIOGRAPHY_SECTION_LABELS, CITATION_MARKER_SENTINEL
from mdook.core.rules.footnotes import NOTE_SECTION_LABELS
from mdook.core.rules.paragraphs import ENDNOTE_MARKER_SENTINEL, FOOTNOTE_MARKER_SENTINEL

INVALID_FILENAME_CHARS_RE = re.compile(r'[\\/:*?"<>|]')
FOOTNOTE_SENTINEL_RE = re.compile(f"{FOOTNOTE_MARKER_SENTINEL}(.+?){FOOTNOTE_MARKER_SENTINEL}")
ENDNOTE_SENTINEL_RE = re.compile(f"{ENDNOTE_MARKER_SENTINEL}(.+?){ENDNOTE_MARKER_SENTINEL}")
CITATION_SENTINEL_RE = re.compile(f"{CITATION_MARKER_SENTINEL}(.+?){CITATION_MARKER_SENTINEL}")
BACK_MATTER_STEM = "99 - Back Matter"


@dataclass
class RenderResult:
    vault_dir: Path
    index_path: Path
    chapter_paths: list[Path] = field(default_factory=list)
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

    # Computed up front (before any file is rendered) so an inline endnote
    # reference (Rule 4.3) spliced into chapter or front-matter text can
    # link to the Notes section's file, whichever order things get written
    # in -- an endnote marker only ever gets detected if a Notes/Endnotes
    # back-matter section actually exists, so this is never a dangling link.
    back_matter_stem = BACK_MATTER_STEM if tree.back_matter else None

    front_matter_path: Path | None = None
    if tree.front_matter:
        body, used = _render_matter(
            "Front Matter", tree.front_matter, manifest, attachments_dir, back_matter_stem
        )
        front_matter_path = vault_dir / "00 - Front Matter.md"
        front_matter_path.write_text(body, encoding="utf-8")
        attachment_filenames.update(used)

    chapter_paths: list[Path] = []
    for chapter in tree.chapters:
        filename = f"{chapter.number:02d} - {_sanitize_filename(chapter.title)}.md"
        path = vault_dir / filename
        body, used_attachments = _render_chapter(
            chapter, manifest, attachments_dir, back_matter_stem
        )
        path.write_text(body, encoding="utf-8")
        chapter_paths.append(path)
        attachment_filenames.update(used_attachments)

    back_matter_path: Path | None = None
    if tree.back_matter:
        body, used = _render_matter(
            "Back Matter",
            tree.back_matter,
            manifest,
            attachments_dir,
            back_matter_stem,
            is_back_matter_file=True,
        )
        back_matter_path = vault_dir / f"{BACK_MATTER_STEM}.md"
        back_matter_path.write_text(body, encoding="utf-8")
        attachment_filenames.update(used)

    index_path = vault_dir / f"{_sanitize_filename(manifest.title)} - Index.md"
    index_path.write_text(
        _render_index(tree, manifest, chapter_paths, front_matter_path, back_matter_path),
        encoding="utf-8",
    )

    return RenderResult(
        vault_dir=vault_dir,
        index_path=index_path,
        chapter_paths=chapter_paths,
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
    back_matter_path: Path | None,
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
    if back_matter_path is not None:
        body.append(f"- [[{back_matter_path.stem}|Back Matter]]")

    return "\n".join(frontmatter + body) + "\n"


# ---------------------------------------------------------------------------
# Chapter / front-matter / back-matter files
# ---------------------------------------------------------------------------


def _render_chapter(
    chapter: Chapter, manifest: BookManifest, attachments_dir: Path, back_matter_stem: str | None
) -> tuple[str, set[str]]:
    footnotes_by_page = _group_footnotes_by_page(chapter.footnotes)
    lines, used_attachments = _render_sections(
        chapter.sections,
        footnotes_by_page,
        page_label=lambda page: f"p. {page} · {manifest.title}, Ch. {chapter.number}",
        attachments_dir=attachments_dir,
        back_matter_stem=back_matter_stem,
        is_back_matter_file=False,
    )
    return "\n".join([f"# {chapter.title}", ""] + lines).rstrip() + "\n", used_attachments


def _render_matter(
    title: str,
    sections: list[Section],
    manifest: BookManifest,
    attachments_dir: Path,
    back_matter_stem: str | None,
    is_back_matter_file: bool = False,
) -> tuple[str, set[str]]:
    """Front/back matter has no per-section footnote list the way a
    `Chapter` does (Rule 4.4's page-bottom definitions aren't threaded this
    far for these zones yet), so an inline marker spliced into this text by
    Stage 3 will render as `[^n]` with no matching definition -- Stage 5
    surfaces that as an orphan-marker warning rather than silently dropping
    it. Footnotes inside front/back matter are rare enough that this is an
    acceptable gap for now."""
    lines, used_attachments = _render_sections(
        sections,
        footnotes_by_page={},
        page_label=lambda page: f"p. {page} · {manifest.title}",
        attachments_dir=attachments_dir,
        back_matter_stem=back_matter_stem,
        is_back_matter_file=is_back_matter_file,
    )
    return "\n".join([f"# {title}", ""] + lines).rstrip() + "\n", used_attachments


def _render_sections(
    sections: list[Section],
    footnotes_by_page: dict[int, list[Footnote]],
    page_label,
    attachments_dir: Path,
    back_matter_stem: str | None,
    is_back_matter_file: bool,
) -> tuple[list[str], set[str]]:
    lines: list[str] = []
    used_attachments: set[str] = set()
    current_page: int | None = None

    for section in sections:
        if section.title:
            # The file's own "#" (H1) title consumes level 0; section.level=1
            # is the first tier below it ("##" / H2), level=2 is "###" / H3.
            lines.append(f"{'#' * (section.level + 1)} {section.title}")
            lines.append("")

        # Rule 4.3/4.4: only the back-matter file's own Notes/Endnotes
        # section gets `^note-N` block anchors -- an ordinary numbered list
        # elsewhere (a recipe's steps, a glossary aside) must not be tagged.
        # Batch 15 extends the same mechanism to `^ref-N` anchors on a
        # Bibliography/References section.
        anchor_prefix: str | None = None
        if is_back_matter_file and section.title is not None:
            normalized_title = _normalize_matter_title(section.title)
            if normalized_title in NOTE_SECTION_LABELS:
                anchor_prefix = "note"
            elif normalized_title in BIBLIOGRAPHY_SECTION_LABELS:
                anchor_prefix = "ref"

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
                    item, attachments_dir, used_attachments, back_matter_stem, anchor_prefix
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
    back_matter_stem: str | None,
    anchor_prefix: str | None,
) -> list[str]:
    if isinstance(item, Paragraph):
        return [_render_inline_markers(item.text, back_matter_stem)]
    if isinstance(item, BlockQuote):
        template = "> *{}*" if item.italic else "> {}"
        quote_lines = [
            template.format(_render_inline_markers(line, back_matter_stem)) for line in item.lines
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
        return _render_list(item, back_matter_stem, anchor_prefix)
    if isinstance(item, CodeBlock):
        return ["```", *item.lines, "```"]
    if isinstance(item, CalloutBlock):
        callout_type = obsidian_callout_type(item.label)
        lines = [f"> [!{callout_type}] {item.label}"]
        lines.extend(
            f"> {_render_inline_markers(p, back_matter_stem)}" for p in item.paragraphs if p
        )
        return lines
    if isinstance(item, MathBlock):
        if item.display:
            lines = ["$$", item.latex_or_text, "$$"]
            if item.numbering:
                lines.append(f"({item.numbering})")
            return lines
        return [f"${item.latex_or_text}$"]
    return []


def _render_list(
    list_data: ListData, back_matter_stem: str | None, anchor_prefix: str | None
) -> list[str]:
    lines: list[str] = []
    for item in list_data.items:
        indent = "    " * item.level
        text = _render_inline_markers(item.text, back_matter_stem)
        marker = f"{item.marker}." if item.ordered and item.marker else "-"
        line = f"{indent}{marker} {text}"
        if anchor_prefix is not None and item.ordered and item.marker:
            # Rule 4.3/4.4 (and its Batch 15 extension to `^ref-N`): gives an
            # inline endnote/citation reference elsewhere in the vault
            # something to link to.
            line += f" ^{anchor_prefix}-{item.marker}"
        lines.append(line)
    return lines


def _render_inline_markers(text: str, back_matter_stem: str | None) -> str:
    text = _render_footnote_markers(text)
    text = _render_endnote_markers(text, back_matter_stem)
    return _render_citation_markers(text, back_matter_stem)


def _render_footnote_markers(text: str) -> str:
    """Rule 4.4 — turn a Rule 4.2 sentinel-wrapped marker into `[^n]`."""
    return FOOTNOTE_SENTINEL_RE.sub(lambda m: f"[^{m.group(1)}]", text)


def _render_endnote_markers(text: str, back_matter_stem: str | None) -> str:
    """Rule 4.3/4.4 — turn a sentinel-wrapped endnote reference into a
    wiki-link at the Notes section's `^note-N` block anchor, since Obsidian
    footnotes are file-scoped and can't point at a definition living in a
    different file. `back_matter_stem` is only None if no endnote marker
    was ever detected in the first place, so the sentinel can't appear."""
    if back_matter_stem is None:
        return text
    return ENDNOTE_SENTINEL_RE.sub(
        lambda m: f"[[{back_matter_stem}#^note-{m.group(1)}|{m.group(1)}]]", text
    )


def _render_citation_markers(text: str, back_matter_stem: str | None) -> str:
    """Batch 15 — turn a sentinel-wrapped numeric citation into a wiki-link
    at the Bibliography/References section's `^ref-N` block anchor, the
    same mechanism `_render_endnote_markers` uses for `^note-N`.
    `back_matter_stem` is only None if no citation was ever spliced in the
    first place, so the sentinel can't appear."""
    if back_matter_stem is None:
        return text
    return CITATION_SENTINEL_RE.sub(
        lambda m: f"[[{back_matter_stem}#^ref-{m.group(1)}|{m.group(1)}]]", text
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
