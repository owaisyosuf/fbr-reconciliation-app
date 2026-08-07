"""
Process an FBR "Annex C" (Local Sales) report (.xls or .xlsx) into a clean,
formatted workbook:

  - Works on a COPY only; the source file is never modified.
  - Dynamically detects header rows by searching for known tax column headers.
  - Keeps only: Name, Number, Date, HS Code, Qty,
    Value Of Sales Excluding Sales Tax, Sales Tax / FED In ST Mode
    -> all other columns are HIDDEN (not deleted).
  - Applies Calibri font throughout, banded rows, a bold header,
    frozen header row, and sensible number formats.
  - Adds a Total row with SUM formulas for Value and Sales Tax / FED.

Usage:
    python process_annex_c.py <input.xls|input.xlsx> [output.xlsx]
"""
from __future__ import annotations

import re
import sys
import tempfile
from pathlib import Path
from typing import Optional

from openpyxl import load_workbook
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from openpyxl.utils import get_column_letter

# 1-based column positions used for the 7 kept columns.
COL_REGNO = 1      # Registration No
COL_NAME = 3       # Name
COL_NUMBER = 9     # Document / Invoice Number
COL_DATE = 10      # Date
COL_HSCODE = 11    # HS Code Description
COL_QTY = 15       # Qty
COL_VALUE = 17     # Value Of Sales Excluding Sales Tax
COL_TAX = 18       # Sales Tax / FED In ST Mode

VISIBLE_COLS = [COL_NAME, COL_NUMBER, COL_DATE, COL_HSCODE, COL_QTY, COL_VALUE, COL_TAX]

# Search keywords for header detection (case-insensitive).
TAX_KEYWORDS = ["sales tax", "fed", "st mode"]
HEADER_KEYWORDS = [
    "sales tax", "fed", "st mode", "value of sales",
    "hs code", "registration no", "particulars",
]

STYLE = {
    "header_fill": PatternFill("solid", start_color="1F4E78", end_color="1F4E78"),
    "header_font": Font(name="Calibri", size=11, bold=True, color="FFFFFF"),
    "title_font": Font(name="Calibri", size=14, bold=True),
    "period_font": Font(name="Calibri", size=11, italic=True),
    "total_fill": PatternFill("solid", start_color="D9E2F3", end_color="D9E2F3"),
    "band_fill": PatternFill("solid", start_color="F2F6FB", end_color="F2F6FB"),
    "thin_border": Border(
        left=Side(style="thin", color="B7B7B7"),
        right=Side(style="thin", color="B7B7B7"),
        top=Side(style="thin", color="B7B7B7"),
        bottom=Side(style="thin", color="B7B7B7"),
    ),
}


# ---------------------------------------------------------------------------
# Detection helpers
# ---------------------------------------------------------------------------

def _cell_text(val) -> str:
    if val is None:
        return ""
    return str(val).strip()


def _is_tax_header(val) -> bool:
    """Check if a cell value looks like a sales-tax column header."""
    text = _cell_text(val).lower()
    return any(kw in text for kw in TAX_KEYWORDS)


def _is_any_header(val) -> bool:
    """Check if a cell value looks like any of the known report headers."""
    text = _cell_text(val).lower()
    return any(kw in text for kw in HEADER_KEYWORDS)


def find_header_data_end(
    ws, max_scan: int = 25,
) -> tuple[Optional[int], Optional[int], Optional[str], Optional[str]]:
    """Scan the first *max_scan* rows to locate the header block, data start,
    and extract any title / period text.

    Some Annex C exports have a two-row header (sub-labels on row N,
    column names on row N+1).  This function identifies the LAST
    consecutive header-like row and treats that as the definitive header.

    Returns
        (header_row, data_start_row, period_text, title_text)
    """
    period_text = None
    title_text = None

    # Scan header region looking for date-range / title / header markers.
    first_header = None
    last_header = None

    for r in range(1, min(ws.max_row, max_scan) + 1):
        row_has_header = False
        for c in range(1, ws.max_column + 1):
            val = _cell_text(ws.cell(row=r, column=c).value)
            if not val:
                continue
            # Period / date range
            if re.search(r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)", val, re.I):
                period_text = val
            if re.search(r"from\s*:", val, re.I) or re.search(r"\d{2}-[a-z]{3}-\d{4}", val, re.I):
                period_text = val
            # Annex title
            if "annex" in val.lower():
                title_text = val
            # Header-like content (column names)
            if _is_any_header(val):
                row_has_header = True

        if row_has_header:
            if first_header is None:
                first_header = r
            last_header = r

    # Use the last header row as the definitive header.
    header_row = last_header if last_header is not None else first_header

    if header_row is None:
        return None, None, period_text, title_text

    # Find first non-empty row after the header.
    data_start = None
    for r in range(header_row + 1, ws.max_row + 1):
        for c in range(1, ws.max_column + 1):
            if ws.cell(row=r, column=c).value not in (None, ""):
                data_start = r
                break
        if data_start is not None:
            break

    return header_row, data_start, period_text, title_text


def read_data_rows(ws, header_row: int, data_start: int):
    """Yield all non-empty data rows from *data_start* to end-of-sheet.
    Each yielded row is a list of values for the 7 visible columns
    (in the order of *VISIBLE_COLS*).
    """
    for r in range(data_start, ws.max_row + 1):
        vals = [ws.cell(row=r, column=c).value for c in range(1, ws.max_column + 1)]
        # Skip fully blank rows.
        if all(v is None or v == "" for v in vals):
            continue
        yield [vals[c - 1] for c in VISIBLE_COLS]


# ---------------------------------------------------------------------------
# .xls reader (via xlrd) → openpyxl workbook
# ---------------------------------------------------------------------------

def read_xls_to_openpyxl(xls_path: Path) -> object:
    """Read a legacy .xls file with xlrd and return a new openpyxl Workbook
    populated with the same cell values (rounded to 2dp for numeric cells).
    """
    import xlrd  # noqa: PLC0415 — optional dependency, only needed for .xls

    from openpyxl import Workbook as NewWorkbook

    src = xlrd.open_workbook(str(xls_path))
    src_ws = src.sheet_by_index(0)

    wb = NewWorkbook()
    ws = wb.active
    ws.title = "Annex C"

    for r in range(src_ws.nrows):
        for c in range(src_ws.ncols):
            val = src_ws.cell_value(r, c)
            if src_ws.cell_type(r, c) in (2,):  # XL_CELL_NUMBER = 2
                val = round(val, 2)
            ws.cell(row=r + 1, column=c + 1).value = val

    return wb


# ---------------------------------------------------------------------------
# Main process function
# ---------------------------------------------------------------------------

def process(input_path: str, output_path: str | None = None):
    src = Path(input_path).resolve()
    if not src.exists():
        raise FileNotFoundError(src)

    is_xls = src.suffix.lower() == ".xls"

    if is_xls:
        # Read legacy .xls with xlrd, build an openpyxl workbook.
        wb = read_xls_to_openpyxl(src)
    else:
        wb = load_workbook(str(src))

    ws = wb.active
    ws.title = "Annex C"

    # Ensure we know the full extent.
    maxcol = ws.max_column

    # -----------------------------------------------------------------------
    # 1. Remove fully blank rows (backwards to keep indices stable).
    # -----------------------------------------------------------------------
    for r in range(ws.max_row, 0, -1):
        if _row_is_blank(ws, r, maxcol):
            ws.delete_rows(r, 1)

    # -----------------------------------------------------------------------
    # 2. Detect header and data rows.
    # -----------------------------------------------------------------------
    header_row, data_start, period_text, title_text = find_header_data_end(ws)
    if header_row is None:
        raise ValueError(
            "Could not locate the header row in the Annex C file. "
            f"Scanned the first {min(ws.max_row, 25)} rows for known column headers."
        )
    if data_start is None:
        raise ValueError(
            "No data rows found after the header row in the Annex C file."
        )

    # -----------------------------------------------------------------------
    # 4. Normalise the data region: delete everything above the header row,
    #    then collapse so header becomes row 3.
    # -----------------------------------------------------------------------
    if header_row > 1:
        ws.delete_rows(1, header_row - 1)
        header_row = 1
        data_start = data_start - (header_row - 1)  # adjusted — recalc below

    # Re-scan for data start after row deletions.
    data_start = None
    for r in range(header_row + 1, ws.max_row + 1):
        if not _row_is_blank(ws, r, maxcol):
            data_start = r
            break
    if data_start is None:
        raise ValueError("No data rows found after row cleanup.")

    DATA_END = ws.max_row

    # -----------------------------------------------------------------------
    # 5. Title / period rows (rows 1-2 after the deleted header region above).
    # -----------------------------------------------------------------------
    # Insert two rows at top for title and period text.
    ws.insert_rows(1, 2)
    ws.cell(row=1, column=1).value = title_text or "Annex C"
    ws.cell(row=2, column=1).value = period_text or ""
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=maxcol)
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=maxcol)
    ws.row_dimensions[1].height = 22
    ws.row_dimensions[2].height = 18

    # Header row shifted to row 3, data starts at row 4.
    HEADER_ROW = 3
    DATA_START = 4
    # Adjust data: everything that was at data_start..DATA_END is now at
    # row shifted by +2 (because we inserted 2 rows).
    actual_data_start = data_start + 2
    actual_data_end = DATA_END + 2

    # -----------------------------------------------------------------------
    # 6. Ensure visible column headers are set on HEADER_ROW.
    # -----------------------------------------------------------------------
    header_labels = {
        COL_NAME: "Name",
        COL_NUMBER: "Number",
        COL_DATE: "Date",
        COL_HSCODE: "HS Code",
        COL_QTY: "Qty",
        COL_VALUE: "Value Of Sales Excluding Sales Tax",
        COL_TAX: "Sales Tax / FED In ST Mode",
    }
    for c, label in header_labels.items():
        ws.cell(row=HEADER_ROW, column=c).value = label

    # -----------------------------------------------------------------------
    # 7. Font: Calibri everywhere.
    # -----------------------------------------------------------------------
    for row in ws.iter_rows(min_row=1, max_row=ws.max_row, min_col=1, max_col=maxcol):
        for cell in row:
            cell.font = Font(name="Calibri", size=11)

    ws.cell(row=1, column=1).font = STYLE["title_font"]
    ws.cell(row=1, column=1).alignment = Alignment(horizontal="center", vertical="center")
    ws.cell(row=2, column=1).font = STYLE["period_font"]
    ws.cell(row=2, column=1).alignment = Alignment(horizontal="center", vertical="center")

    # -----------------------------------------------------------------------
    # 8. Header row styling.
    # -----------------------------------------------------------------------
    for c in VISIBLE_COLS:
        cell = ws.cell(row=HEADER_ROW, column=c)
        cell.font = STYLE["header_font"]
        cell.fill = STYLE["header_fill"]
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = STYLE["thin_border"]
    ws.row_dimensions[HEADER_ROW].height = 30

    # -----------------------------------------------------------------------
    # 9. Data rows: borders, banding, alignment, number formats.
    # -----------------------------------------------------------------------
    for i, r in enumerate(range(DATA_START, actual_data_end + 1)):
        banded = (i % 2 == 1)
        for c in VISIBLE_COLS:
            cell = ws.cell(row=r, column=c)
            cell.border = STYLE["thin_border"]
            if banded:
                cell.fill = STYLE["band_fill"]
            if c == COL_NAME:
                cell.alignment = Alignment(horizontal="left", vertical="center")
            elif c == COL_DATE:
                cell.alignment = Alignment(horizontal="center", vertical="center")
                cell.number_format = "dd-mmm-yyyy"
            elif c in (COL_QTY,):
                cell.alignment = Alignment(horizontal="center", vertical="center")
                cell.number_format = "#,##0"
            elif c in (COL_VALUE, COL_TAX):
                cell.alignment = Alignment(horizontal="right", vertical="center")
                cell.number_format = "#,##0.00"
            else:
                cell.alignment = Alignment(horizontal="center", vertical="center")

    # -----------------------------------------------------------------------
    # 10. Totals row (SUM formulas).
    # -----------------------------------------------------------------------
    TOTAL_ROW = actual_data_end + 1
    ws.cell(row=TOTAL_ROW, column=COL_NAME).value = "Total"
    ws.cell(row=TOTAL_ROW, column=COL_NAME).font = Font(name="Calibri", size=11, bold=True)
    ws.cell(row=TOTAL_ROW, column=COL_NAME).alignment = Alignment(horizontal="left", vertical="center")

    value_letter = get_column_letter(COL_VALUE)
    tax_letter = get_column_letter(COL_TAX)
    ws.cell(row=TOTAL_ROW, column=COL_VALUE).value = (
        f"=SUM({value_letter}{DATA_START}:{value_letter}{actual_data_end})"
    )
    ws.cell(row=TOTAL_ROW, column=COL_TAX).value = (
        f"=SUM({tax_letter}{DATA_START}:{tax_letter}{actual_data_end})"
    )

    for c in VISIBLE_COLS:
        cell = ws.cell(row=TOTAL_ROW, column=c)
        cell.font = Font(name="Calibri", size=11, bold=True)
        cell.border = Border(
            left=STYLE["thin_border"].left,
            right=STYLE["thin_border"].right,
            top=Side(style="double", color="1F4E78"),
            bottom=STYLE["thin_border"].bottom,
        )
        cell.fill = STYLE["total_fill"]
        if c in (COL_VALUE, COL_TAX):
            cell.number_format = "#,##0.00"
            cell.alignment = Alignment(horizontal="right", vertical="center")
        elif c == COL_QTY:
            cell.alignment = Alignment(horizontal="center", vertical="center")

    # -----------------------------------------------------------------------
    # 11. Column widths & hide everything not in VISIBLE_COLS.
    # -----------------------------------------------------------------------
    widths = {COL_NAME: 32, COL_NUMBER: 12, COL_DATE: 13, COL_HSCODE: 14,
              COL_QTY: 8, COL_VALUE: 20, COL_TAX: 20}
    for c in range(1, maxcol + 1):
        letter = get_column_letter(c)
        if c in VISIBLE_COLS:
            ws.column_dimensions[letter].width = widths.get(c, 14)
            ws.column_dimensions[letter].hidden = False
        else:
            ws.column_dimensions[letter].hidden = True

    # -----------------------------------------------------------------------
    # 12. Freeze header, remove gridlines.
    # -----------------------------------------------------------------------
    ws.freeze_panes = ws.cell(row=DATA_START, column=1)
    ws.sheet_view.showGridLines = False
    wb.calculation.fullCalcOnLoad = True

    if output_path is None:
        output_dir = Path(tempfile.mkdtemp(prefix="annex_c_"))
        output_path = str(output_dir / (src.stem + "_processed.xlsx"))

    wb.save(output_path)
    return output_path, DATA_START, actual_data_end, TOTAL_ROW


def _row_is_blank(ws, r: int, maxcol: int) -> bool:
    for c in range(1, maxcol + 1):
        v = ws.cell(row=r, column=c).value
        if v not in (None, ""):
            return False
    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python process_annex_c.py <input.xls|.xlsx> [output.xlsx]")
        sys.exit(1)
    inp = sys.argv[1]
    outp = sys.argv[2] if len(sys.argv) > 2 else None
    result_path, data_start, data_end, total_row = process(inp, outp)
    print(f"Saved: {result_path}")
    print(f"Data rows: {data_start}-{data_end}, Total row: {total_row}")
