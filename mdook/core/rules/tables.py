"""Rules 6.1-6.3 — Table Detection & Complexity Classification.

Uses pdfplumber -- a separate PDF-parsing library from PyMuPDF, already a
declared dependency -- specifically for its grid-line-based table finder,
which PyMuPDF has no equivalent for. See `Mdook-docs/RULES.md` section 6.

Implements:
- Rule 6.1 (table detection: a region bounded by lines forming a grid)
- Rule 6.2/6.3 classification (has_merged_cells / complexity signal --
  the actual markdown-vs-HTML rendering choice is made in Stage 4)

Not implemented:
- Rule 6.4 (caption association) has no dedicated code here: a caption text
  block immediately above/below a table already sits adjacent to it in
  reading order once Stage 3 slots the table in by position, which reads
  correctly without any special-casing.
- Tables with no visible ruling lines (whitespace-aligned columns) aren't
  detected at all -- exactly what Rule 6.1's own condition specifies.
- Nested/spanning cell reconstruction beyond pdfplumber's own merged-cell
  detection: a `None` cell (pdfplumber's marker for a row/colspan) is
  filled by carrying the spanning cell's own value forward/across.
"""

from __future__ import annotations

from mdook.core.models import TableBlock

MIN_TABLE_ROWS = 2
MIN_TABLE_COLS = 2
MAX_SIMPLE_COLUMNS = 8
MAX_SIMPLE_CELL_CHARS = 80


def detect_tables(plumber_page: object | None) -> list[TableBlock]:
    """`plumber_page` is a `pdfplumber.page.Page`, or None if pdfplumber
    failed to open this document at all (Stage 2 degrades to "no tables
    found" rather than failing the whole page)."""
    if plumber_page is None:
        return []
    try:
        found_tables = plumber_page.find_tables()
    except Exception:
        return []  # pdfplumber's table finder can choke on unusual page content

    results: list[TableBlock] = []
    for table in found_tables:
        try:
            rows = table.extract()
        except Exception:
            continue
        if len(rows) < MIN_TABLE_ROWS or any(len(row) < MIN_TABLE_COLS for row in rows):
            continue
        cells, has_merged_cells = _normalize_cells(rows)
        results.append(
            TableBlock(
                cells=cells,
                has_merged_cells=has_merged_cells,
                bbox=tuple(table.bbox),
                page_number=plumber_page.page_number,
            )
        )
    return results


def _normalize_cells(rows: list[list[str | None]]) -> tuple[list[list[str]], bool]:
    has_merged_cells = any(cell is None for row in rows for cell in row)
    cleaned: list[list[str]] = []
    last_seen_by_column: dict[int, str] = {}

    for row in rows:
        clean_row: list[str] = []
        for column_index, cell in enumerate(row):
            if cell is None:
                # A row/colspan cell -- pdfplumber returns None for the
                # spanned-over positions rather than repeating the value.
                clean_row.append(last_seen_by_column.get(column_index, ""))
            else:
                text = " ".join(cell.split())
                clean_row.append(text)
                last_seen_by_column[column_index] = text
        cleaned.append(clean_row)

    return cleaned, has_merged_cells


def is_complex(cells: list[list[str]], has_merged_cells: bool) -> bool:
    """Rule 6.3 — merged cells, an overly long cell, or too many columns all
    push a table past what a markdown pipe table can represent faithfully."""
    if has_merged_cells:
        return True
    if any(len(row) > MAX_SIMPLE_COLUMNS for row in cells):
        return True
    return any(len(cell) > MAX_SIMPLE_CELL_CHARS for row in cells for cell in row)
