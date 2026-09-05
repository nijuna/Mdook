"""Synthetic PDF fixtures for pipeline/stage tests.

Real book fixtures (`tests/fixtures/sample_literary.pdf`, etc.) come later
per `Mdook-docs/ROADMAP.md`. For now these are built programmatically with
PyMuPDF so tests don't depend on external files or copyrighted material.
"""

from __future__ import annotations

from pathlib import Path

import pymupdf
import pytest

PAGE_WIDTH = 400
PAGE_HEIGHT = 600
BODY_FONT_SIZE = 11
HEADING_FONT_SIZE = 24
RUNNING_FOOTER = "Sample Book"


def build_bookmarked_pdf(path: Path, chapters: int = 3, pages_per_chapter: int = 2) -> None:
    """A book with an embedded outline/TOC — exercises the Rule 2.1 path."""
    doc = pymupdf.open()
    toc = []
    page_number = 1
    for chapter_index in range(1, chapters + 1):
        title = f"Chapter {chapter_index}"
        for page_in_chapter in range(pages_per_chapter):
            page = doc.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            y = 100.0
            if page_in_chapter == 0:
                page.insert_text((72, y), title, fontsize=HEADING_FONT_SIZE, fontname="helv")
                toc.append([1, title, page_number])
                y += 60
            for line in range(6):
                page.insert_text(
                    (72, y),
                    f"Body text line {line} of {title}.",
                    fontsize=BODY_FONT_SIZE,
                    fontname="helv",
                )
                y += 20
            page.insert_text((180, PAGE_HEIGHT - 20), RUNNING_FOOTER, fontsize=8, fontname="helv")
            page_number += 1
    doc.set_toc(toc)
    doc.save(str(path))
    doc.close()


def build_unbookmarked_pdf(path: Path, chapters: int = 2, pages_per_chapter: int = 3) -> None:
    """A book with no outline/TOC — exercises the Rules 2.2/2.3 font-clustering path."""
    doc = pymupdf.open()
    for chapter_index in range(1, chapters + 1):
        title = f"THE {chapter_index} STORY"
        for page_in_chapter in range(pages_per_chapter):
            page = doc.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            y = 100.0
            if page_in_chapter == 0:
                page.insert_text((72, y), title, fontsize=HEADING_FONT_SIZE, fontname="helv")
                y += 60
            for line in range(6):
                page.insert_text(
                    (72, y),
                    f"Body text line {line} of chapter {chapter_index}.",
                    fontsize=BODY_FONT_SIZE,
                    fontname="helv",
                )
                y += 20
            page.insert_text((180, PAGE_HEIGHT - 20), RUNNING_FOOTER, fontsize=8, fontname="helv")
    doc.save(str(path))
    doc.close()


def add_solid_image(page, rect: tuple[float, float, float, float]) -> None:
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 50, 50))
    pix.set_rect(pix.irect, (200, 30, 30))
    page.insert_image(pymupdf.Rect(*rect), stream=pix.tobytes("png"))


def add_grid_table(page, rect: tuple[float, float, float, float], rows: list[list[str]]) -> None:
    """Draws a ruled grid (outer border + internal gridlines) and fills each
    cell with text -- pdfplumber's default table finder needs actual line
    drawing operators, not just visually-aligned text, to detect a table."""
    x0, y0, x1, y1 = rect
    page.draw_rect(pymupdf.Rect(x0, y0, x1, y1))
    n_rows, n_cols = len(rows), len(rows[0])
    col_w = (x1 - x0) / n_cols
    row_h = (y1 - y0) / n_rows
    for i in range(1, n_cols):
        page.draw_line((x0 + i * col_w, y0), (x0 + i * col_w, y1))
    for i in range(1, n_rows):
        page.draw_line((x0, y0 + i * row_h), (x1, y0 + i * row_h))
    for r in range(n_rows):
        for c in range(n_cols):
            page.insert_text((x0 + c * col_w + 5, y0 + r * row_h + 20), rows[r][c], fontsize=10)


@pytest.fixture
def bookmarked_pdf(tmp_path: Path) -> Path:
    path = tmp_path / "bookmarked.pdf"
    build_bookmarked_pdf(path)
    return path


@pytest.fixture
def unbookmarked_pdf(tmp_path: Path) -> Path:
    path = tmp_path / "unbookmarked.pdf"
    build_unbookmarked_pdf(path)
    return path
