from pathlib import Path

import pdfplumber
import pymupdf

from mdook.core.rules.tables import detect_tables, is_complex


def _build_grid_table_pdf(path: Path, rows: list[list[str]]) -> None:
    doc = pymupdf.open()
    page = doc.new_page(width=400, height=300)
    x0, y0, x1, y1 = 50, 50, 350, 200
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
    doc.save(str(path))
    doc.close()


def test_detect_tables_extracts_grid_ruled_table(tmp_path: Path) -> None:
    rows = [["Name", "Age", "City"], ["Alice", "30", "NYC"], ["Bob", "25", "LA"]]
    pdf_path = tmp_path / "table.pdf"
    _build_grid_table_pdf(pdf_path, rows)

    with pdfplumber.open(pdf_path) as pdf:
        tables = detect_tables(pdf.pages[0])

    assert len(tables) == 1
    assert tables[0].cells == rows
    assert tables[0].has_merged_cells is False
    assert tables[0].page_number == 1


def test_detect_tables_returns_empty_for_none_page() -> None:
    assert detect_tables(None) == []


def test_is_complex_flags_merged_cells() -> None:
    assert is_complex([["a", "b"]], has_merged_cells=True) is True


def test_is_complex_flags_too_many_columns() -> None:
    row = [str(i) for i in range(10)]
    assert is_complex([row], has_merged_cells=False) is True


def test_is_complex_flags_long_cell_content() -> None:
    long_cell = "x" * 100
    assert is_complex([["short", long_cell]], has_merged_cells=False) is True


def test_simple_table_is_not_complex() -> None:
    rows = [["Name", "Age"], ["Alice", "30"]]
    assert is_complex(rows, has_merged_cells=False) is False
