"""
Process an FBR "Annex C" (Local Sales) report (.xls or .xlsx) into a clean,
formatted workbook:

  - Works on a COPY only; the source file is never modified.
  - Dynamically detects header rows by searching for known tax column headers.
  - Dynamically MAPS the 7 kept fields (Name, Number, Date, HS Code, Qty,
    Value Of Sales Excluding Sales Tax, Sales Tax / FED In ST Mode) to
    whatever columns actually carry them, by reading header text -- not by
    assuming a fixed column position. The FBR portal exports at least two
    different Annex C layouts (an 18-column one with a stacked, multi-row
    header, and a 35+ column "invoice register" one with a single header
    row), and column counts/order can also shift between those depending on
    which optional columns (e.g. "Sale Origination Province of Supplier")
    a given download happens to include. All other columns are HIDDEN (not
    deleted).
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

from utils.validators import is_tax_column_header, normalize_header

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
# Row-level detection helpers (find the header block / data extent)
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
) -> tuple[Optional[int], Optional[int], Optional[str], Optional[str], Optional[int]]:
    """Scan the first *max_scan* rows to locate the header block, data start,
    and extract any title / period text.

    Some Annex C exports have a multi-row header (sub-labels on row N,
    column names on row N+1, etc). This function identifies the LAST
    header-like row and treats that as the definitive header row (the one
    whose labels line up 1:1 with the data columns below it); it also
    reports the FIRST header-like row, since fields like "Value of Sales"
    can be labelled a row or two above that.

    Returns
        (header_row, data_start_row, period_text, title_text, first_header_row)
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
        return None, None, period_text, title_text, None

    # Find first non-empty row after the header.
    data_start = None
    for r in range(header_row + 1, ws.max_row + 1):
        for c in range(1, ws.max_column + 1):
            if ws.cell(row=r, column=c).value not in (None, ""):
                data_start = r
                break
        if data_start is not None:
            break

    return header_row, data_start, period_text, title_text, first_header


# ---------------------------------------------------------------------------
# Column-level detection: map logical fields to whatever column actually
# carries them, regardless of the raw report's layout.
# ---------------------------------------------------------------------------

def _combined_header_texts(ws, first_header_row: int, header_row: int, maxcol: int) -> list[str]:
    """One search string per column, built by concatenating every non-empty
    header-block cell top-to-bottom. A field's label and the column it
    actually sits above aren't always on the same row (e.g. "Qty" and
    "Value of Sales..." can be one or two rows apart), so a single field can
    only be found reliably by looking at the whole block, not one row.
    """
    texts = ["" for _ in range(maxcol)]
    for r in range(first_header_row, header_row + 1):
        for c in range(1, maxcol + 1):
            v = _cell_text(ws.cell(row=r, column=c).value)
            if v:
                texts[c - 1] = (texts[c - 1] + " " + v).strip()
    return texts


def _to_num(val) -> Optional[float]:
    if val is None or val == "":
        return None
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        try:
            return float(val.replace(",", "").strip())
        except ValueError:
            return None
    return None


def _numeric_score(ws, col: Optional[int], data_start: int, data_end: int, sample: int = 25) -> float:
    """Fraction of sampled data rows in *col* that hold a numeric value."""
    if not col:
        return 0.0
    checked = numeric = 0
    for r in range(data_start, min(data_end, data_start + sample - 1) + 1):
        v = ws.cell(row=r, column=col).value
        if v is None or v == "":
            continue
        checked += 1
        if _to_num(v) is not None:
            numeric += 1
    return numeric / checked if checked else 0.0


def _numeric_shift(ws, candidate: Optional[int], data_start: int, data_end: int,
                    maxcol: int, min_score: float = 0.6) -> int:
    """0 if *candidate*'s own data is already predominantly numeric,
    otherwise the smallest offset to a nearby column whose data is. Some
    Annex C exports label "Value of Sales" / "Sales Tax" a column to the
    left of where the actual figures live (the label sits over what looks
    like a merged header cell, but the numbers are one column over).
    """
    if not candidate:
        return 0
    if _numeric_score(ws, candidate, data_start, data_end) >= min_score:
        return 0
    for delta in (1, -1, 2, -2):
        c = candidate + delta
        if 1 <= c <= maxcol and _numeric_score(ws, c, data_start, data_end) >= min_score:
            return delta
    return 0


def _resolve_value_tax_cols(ws, value_raw: Optional[int], tax_raw: Optional[int],
                             data_start: int, data_end: int, maxcol: int) -> tuple[Optional[int], Optional[int]]:
    """Turn the header-text-derived Value/Tax candidates into actual data
    columns. Both labels come from the same header block, so if one needs
    shifting to reach numeric data the other almost always needs the exact
    same shift -- correcting them independently can make both land on the
    same (wrong) column, since a shifted-Tax candidate can coincidentally
    sit on top of real (but different-field) numeric data.
    """
    delta = _numeric_shift(ws, value_raw, data_start, data_end, maxcol)
    value_col = value_raw + delta if value_raw else None
    tax_col = tax_raw + delta if tax_raw else None

    if tax_col and value_col and tax_col == value_col:
        # The shared shift collided the two -- fall back to shifting Tax
        # independently, away from wherever Value ended up.
        for d in (1, -1, 2, -2):
            c = tax_raw + d
            if c != value_col and 1 <= c <= maxcol and _numeric_score(ws, c, data_start, data_end) >= 0.6:
                tax_col = c
                break

    if value_col and tax_col and value_col != tax_col:
        value_col, tax_col = _maybe_swap_value_tax(ws, value_col, tax_col, data_start, data_end)

    return value_col, tax_col


def _maybe_swap_value_tax(ws, value_col: int, tax_col: int,
                           data_start: int, data_end: int, sample: int = 25) -> tuple[int, int]:
    """Sales tax is always smaller than the value it's charged on. If the
    detected columns disagree with that on most sampled rows, they're
    swapped -- correct it rather than trust the header order.
    """
    pairs = []
    for r in range(data_start, min(data_end, data_start + sample - 1) + 1):
        v, t = _to_num(ws.cell(row=r, column=value_col).value), _to_num(ws.cell(row=r, column=tax_col).value)
        if v is not None and t is not None:
            pairs.append((v, t))
    if not pairs:
        return value_col, tax_col
    tax_larger = sum(1 for v, t in pairs if t > v)
    if tax_larger > len(pairs) * 0.7:
        return tax_col, value_col
    return value_col, tax_col


def _fallback_value_tax_cols(ws, data_start: int, data_end: int, maxcol: int,
                              claimed: set[int]) -> tuple[Optional[int], Optional[int]]:
    """Last resort when no header text identifies Value or Sales Tax at all
    (some exports drop the extra label rows those live under entirely).
    These reports consistently place Value immediately followed by Sales
    Tax as the final substantive columns, so use the last two adjacent,
    predominantly-numeric columns not already claimed by another field.
    """
    numeric_cols = [
        c for c in range(1, maxcol + 1)
        if c not in claimed and _numeric_score(ws, c, data_start, data_end) >= 0.6
    ]
    if len(numeric_cols) < 2 or numeric_cols[-1] != numeric_cols[-2] + 1:
        return None, None
    return _maybe_swap_value_tax(ws, numeric_cols[-2], numeric_cols[-1], data_start, data_end)


def _find_field_col(
    header_texts: list[str],
    predicate,
    prefer=None,
    avoid=None,
) -> Optional[int]:
    """Return the best 1-based column whose combined header text satisfies
    *predicate*, narrowing to *prefer* and away from *avoid* only when doing
    so still leaves at least one candidate (so e.g. "avoid seller" never
    throws away the only match when nothing else qualifies).
    """
    candidates = [i + 1 for i, text in enumerate(header_texts) if predicate(text)]
    if not candidates:
        return None
    if prefer:
        preferred = [c for c in candidates if prefer(header_texts[c - 1])]
        if preferred:
            candidates = preferred
    if avoid:
        kept = [c for c in candidates if not avoid(header_texts[c - 1])]
        if kept:
            candidates = kept
    return candidates[0]


def resolve_columns(ws, first_header_row: int, header_row: int, data_start: int, maxcol: int) -> dict:
    """Map the logical Annex C fields to actual column numbers by reading
    header text, so the report's real layout (column count/order) never has
    to match a fixed template. Returns a dict with keys
    name/number/date/hscode/qty/value/tax/regno -- value/tax/regno are
    always resolved (or a ValueError is raised); the rest may be None if the
    report genuinely doesn't carry that field.
    """
    header_texts = _combined_header_texts(ws, first_header_row, header_row, maxcol)
    data_end = ws.max_row

    def has_tokens(text, required):
        tokens = set(normalize_header(text).split())
        return required.issubset(tokens)

    def has_any(text, options):
        tokens = set(normalize_header(text).split())
        return bool(tokens & options)

    def contains(text, sub):
        return sub in normalize_header(text)

    def has(word):
        return lambda text: word in set(normalize_header(text).split())

    regno_col = _find_field_col(
        header_texts, lambda t: "registration" in set(normalize_header(t).split()),
        prefer=has("buyer"), avoid=has("seller"),
    )
    name_col = _find_field_col(
        header_texts, has("name"), prefer=has("buyer"), avoid=has("seller"),
    )
    number_col = _find_field_col(
        header_texts,
        lambda t: has_any(t, {"number"}) or has_tokens(t, {"invoice", "no"}),
        avoid=has("ref"),
    )
    date_col = _find_field_col(header_texts, has("date"), prefer=has("invoice"))
    hscode_col = _find_field_col(
        header_texts, lambda t: has_tokens(t, {"hs", "code"}), avoid=has("description"),
    )
    qty_col = _find_field_col(header_texts, lambda t: has_any(t, {"qty", "quantity"}))

    value_raw = _find_field_col(
        header_texts,
        lambda t: contains(t, "value of sales") and not is_tax_column_header(t),
    )
    tax_raw = _find_field_col(header_texts, is_tax_column_header)

    value_col, tax_col = _resolve_value_tax_cols(ws, value_raw, tax_raw, data_start, data_end, maxcol)

    if value_col is None and tax_col is None:
        # Neither field has any recognisable header text at all (some
        # exports drop those label rows). Fall back to position.
        claimed = {c for c in (regno_col, name_col, number_col, date_col, hscode_col, qty_col) if c}
        value_col, tax_col = _fallback_value_tax_cols(ws, data_start, data_end, maxcol, claimed)

    missing = [
        label for label, col in (("Registration No", regno_col), ("Value", value_col), ("Tax", tax_col))
        if col is None
    ]
    if missing:
        raise ValueError(
            f"Could not locate the {', '.join(missing)} column(s) in the Annex C file. "
            f"Header text found: {[t for t in header_texts if t]}"
        )
    if _numeric_score(ws, value_col, data_start, data_end) < 0.3 or _numeric_score(ws, tax_col, data_start, data_end) < 0.3:
        raise ValueError(
            "Found headers for the Value / Sales Tax columns, but the data beneath them "
            "isn't numeric -- the file's layout doesn't match what this app expects."
        )

    return {
        "regno": regno_col, "name": name_col, "number": number_col, "date": date_col,
        "hscode": hscode_col, "qty": qty_col, "value": value_col, "tax": tax_col,
    }


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
    header_row, data_start, period_text, title_text, first_header_row = find_header_data_end(ws)
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
    # 3. Map fields to actual columns (must happen before the header block
    #    above the data is deleted).
    # -----------------------------------------------------------------------
    resolved = resolve_columns(ws, first_header_row, header_row, data_start, maxcol)
    name_col = resolved["name"]
    number_col = resolved["number"]
    date_col = resolved["date"]
    hscode_col = resolved["hscode"]
    qty_col = resolved["qty"]
    value_col = resolved["value"]
    tax_col = resolved["tax"]

    VISIBLE_COLS = [c for c in (name_col, number_col, date_col, hscode_col, qty_col, value_col, tax_col) if c]

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
    header_labels = {value_col: "Value Of Sales Excluding Sales Tax", tax_col: "Sales Tax / FED In ST Mode"}
    if name_col:
        header_labels[name_col] = "Name"
    if number_col:
        header_labels[number_col] = "Number"
    if date_col:
        header_labels[date_col] = "Date"
    if hscode_col:
        header_labels[hscode_col] = "HS Code"
    if qty_col:
        header_labels[qty_col] = "Qty"
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
            if c == name_col:
                cell.alignment = Alignment(horizontal="left", vertical="center")
            elif c == date_col:
                cell.alignment = Alignment(horizontal="center", vertical="center")
                cell.number_format = "dd-mmm-yyyy"
            elif c == qty_col:
                cell.alignment = Alignment(horizontal="center", vertical="center")
                cell.number_format = "#,##0"
            elif c in (value_col, tax_col):
                cell.alignment = Alignment(horizontal="right", vertical="center")
                cell.number_format = "#,##0.00"
            else:
                cell.alignment = Alignment(horizontal="center", vertical="center")

    # -----------------------------------------------------------------------
    # 10. Totals row (SUM formulas).
    # -----------------------------------------------------------------------
    TOTAL_ROW = actual_data_end + 1
    total_label_col = name_col or VISIBLE_COLS[0]
    ws.cell(row=TOTAL_ROW, column=total_label_col).value = "Total"
    ws.cell(row=TOTAL_ROW, column=total_label_col).font = Font(name="Calibri", size=11, bold=True)
    ws.cell(row=TOTAL_ROW, column=total_label_col).alignment = Alignment(horizontal="left", vertical="center")

    value_letter = get_column_letter(value_col)
    tax_letter = get_column_letter(tax_col)
    ws.cell(row=TOTAL_ROW, column=value_col).value = (
        f"=SUM({value_letter}{DATA_START}:{value_letter}{actual_data_end})"
    )
    ws.cell(row=TOTAL_ROW, column=tax_col).value = (
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
        if c in (value_col, tax_col):
            cell.number_format = "#,##0.00"
            cell.alignment = Alignment(horizontal="right", vertical="center")
        elif c == qty_col:
            cell.alignment = Alignment(horizontal="center", vertical="center")

    # -----------------------------------------------------------------------
    # 11. Column widths & hide everything not in VISIBLE_COLS.
    # -----------------------------------------------------------------------
    widths = {}
    if name_col:
        widths[name_col] = 32
    if number_col:
        widths[number_col] = 12
    if date_col:
        widths[date_col] = 13
    if hscode_col:
        widths[hscode_col] = 14
    if qty_col:
        widths[qty_col] = 8
    widths[value_col] = 20
    widths[tax_col] = 20
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
