"""Stage 5 — Validation.

Input: the rendered vault (`mdook.core.stages.rendering.RenderResult`) +
`mdook.core.models.DocumentTree` + `mdook.core.models.BookManifest`.
Output: `mdook.core.models.ValidationReport`.

Implements the checks from `Mdook-docs/ARCHITECTURE.md` ("Stage 5"):
footnote integrity, image integrity, heading hierarchy sanity, page
continuity, and chapter file size warnings. Reads the files actually
written to disk rather than re-deriving everything from the tree, so it
validates what a reader would actually open in Obsidian.
"""

from __future__ import annotations

import re
from pathlib import Path

from mdook.core.models import BookManifest, DocumentTree, PageData, ValidationReport
from mdook.core.stages.rendering import RenderResult

MIN_CHAPTER_FILE_SIZE = 500
MAX_CHAPTER_FILE_SIZE = 200_000

IMAGE_REF_RE = re.compile(r"!\[\[([^\]]+)\]\]")
FOOTNOTE_DEFINITION_RE = re.compile(r"^\[\^([^\]]+)\]:", re.MULTILINE)
FOOTNOTE_USAGE_RE = re.compile(r"\[\^([^\]]+)\](?!:)")
HEADING_RE = re.compile(r"^(#{1,6})\s+\S", re.MULTILINE)


def run_validation(
    tree: DocumentTree,
    manifest: BookManifest,
    render_result: RenderResult,
    pages: list[PageData] | None = None,
    processing_time_seconds: float = 0.0,
) -> ValidationReport:
    pages = pages or []
    errors: list[str] = []
    warnings: list[str] = []

    _check_footnote_integrity(render_result, warnings)
    _check_image_integrity(render_result, errors, warnings)
    _check_heading_hierarchy(render_result, warnings)
    _check_page_continuity(tree, manifest, warnings)
    _check_chapter_file_sizes(render_result, warnings)

    llm_review = tree.metadata.extra.get("llm_review") if tree.metadata else None
    llm_corrections = (
        len(llm_review.get("corrections_applied", []))
        if isinstance(llm_review, dict) and llm_review.get("success")
        else 0
    )

    return ValidationReport(
        errors=errors,
        warnings=warnings,
        total_pages=manifest.total_pages,
        total_chapters=len(tree.chapters),
        total_footnotes=sum(len(chapter.footnotes) for chapter in tree.chapters),
        total_images=len(render_result.attachment_filenames),
        ocr_pages=sum(page.was_ocrd for page in pages),
        llm_corrections=llm_corrections,
        processing_time_seconds=processing_time_seconds,
    )


def _check_footnote_integrity(render_result: RenderResult, warnings: list[str]) -> None:
    for path in render_result.chapter_paths:
        text = path.read_text(encoding="utf-8")
        definitions = set(FOOTNOTE_DEFINITION_RE.findall(text))
        usages = set(FOOTNOTE_USAGE_RE.findall(text))

        for marker in sorted(usages - definitions):
            warnings.append(f"{path.name}: footnote marker [^{marker}] has no matching definition.")
        for marker in sorted(definitions - usages):
            warnings.append(f"{path.name}: footnote definition [^{marker}] is never referenced.")


def _check_image_integrity(
    render_result: RenderResult, errors: list[str], warnings: list[str]
) -> None:
    referenced: set[str] = set()
    for path in render_result.chapter_paths:
        referenced.update(IMAGE_REF_RE.findall(path.read_text(encoding="utf-8")))

    for filename in sorted(referenced):
        if not (render_result.attachments_dir / filename).exists():
            errors.append(f"Referenced image '{filename}' is missing from attachments/.")

    if render_result.attachments_dir.exists():
        on_disk = {p.name for p in render_result.attachments_dir.iterdir() if p.is_file()}
        for filename in sorted(on_disk - referenced):
            warnings.append(f"Image '{filename}' exists in attachments/ but is never referenced.")


def _check_heading_hierarchy(render_result: RenderResult, warnings: list[str]) -> None:
    for path in render_result.chapter_paths:
        text = path.read_text(encoding="utf-8")
        levels = [len(match.group(1)) for match in HEADING_RE.finditer(text)]

        previous: int | None = None
        for level in levels:
            if previous is not None and level > previous + 1:
                warnings.append(f"{path.name}: heading level jumps from H{previous} to H{level}.")
            previous = level


def _check_page_continuity(tree: DocumentTree, manifest: BookManifest, warnings: list[str]) -> None:
    covered: set[int] = set()
    for chapter in tree.chapters:
        for start, end in chapter.page_spans:
            covered.update(range(start, end + 1))
    for zone in manifest.zone_map:
        if zone.zone_type in ("front_matter", "back_matter"):
            covered.update(range(zone.start_page, zone.end_page + 1))

    missing = sorted(set(range(1, manifest.total_pages + 1)) - covered)
    if missing:
        warnings.append(
            f"{len(missing)} page(s) not included in any chapter or "
            f"front/back matter section: {_format_page_ranges(missing)}"
        )


def _format_page_ranges(pages: list[int]) -> str:
    ranges: list[str] = []
    start = prev = pages[0]
    for page in pages[1:]:
        if page == prev + 1:
            prev = page
            continue
        ranges.append(f"{start}-{prev}" if start != prev else str(start))
        start = prev = page
    ranges.append(f"{start}-{prev}" if start != prev else str(start))
    return ", ".join(ranges)


def _check_chapter_file_sizes(render_result: RenderResult, warnings: list[str]) -> None:
    for path in render_result.chapter_paths:
        size = _file_size(path)
        if size < MIN_CHAPTER_FILE_SIZE:
            warnings.append(f"{path.name}: only {size} bytes -- possible extraction failure.")
        elif size > MAX_CHAPTER_FILE_SIZE:
            warnings.append(f"{path.name}: {size} bytes -- possible merge error.")


def _file_size(path: Path) -> int:
    return path.stat().st_size
