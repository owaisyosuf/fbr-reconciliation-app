"""Builds the downloadable Reconciliation Report workbook with tabs:
Summary, Matched, Mismatched, Missing, Totals/Difference.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from services.comparison import ComparisonResult
from processors.reconciliation import ReconciliationResult

NAVY = "1F4E78"
LIGHT_BAND = "F2F6FB"
GREEN = "1E7B34"
RED = "B00020"

thin = Side(style="thin", color="B7B7B7")
BORDER = Border(left=thin, right=thin, top=thin, bottom=thin)
HEADER_FONT = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
HEADER_FILL = PatternFill("solid", start_color=NAVY, end_color=NAVY)
BODY_FONT = Font(name="Calibri", size=11)


def _write_dataframe(ws, df: pd.DataFrame, start_row: int = 1):
    if df is None or df.empty:
        ws.cell(row=start_row, column=1, value="No rows in this category.").font = BODY_FONT
        return

    for c, col_name in enumerate(df.columns, start=1):
        cell = ws.cell(row=start_row, column=c, value=str(col_name))
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = BORDER

    for i, (_, row) in enumerate(df.iterrows()):
        r = start_row + 1 + i
        banded = i % 2 == 1
        for c, col_name in enumerate(df.columns, start=1):
            val = row[col_name]
            if pd.isna(val):
                val = None
            cell = ws.cell(row=r, column=c, value=val)
            cell.font = BODY_FONT
            cell.border = BORDER
            if banded:
                cell.fill = PatternFill("solid", start_color=LIGHT_BAND, end_color=LIGHT_BAND)
            if isinstance(val, (int, float)):
                cell.number_format = "#,##0.00"
                cell.alignment = Alignment(horizontal="right", vertical="center")

    for c, col_name in enumerate(df.columns, start=1):
        max_len = max([len(str(col_name))] + [len(str(v)) for v in df[col_name].astype(str)])
        ws.column_dimensions[get_column_letter(c)].width = min(max(12, max_len + 2), 40)

    ws.freeze_panes = ws.cell(row=start_row + 1, column=1)


def build_reconciliation_report(
    comparison: ComparisonResult,
    reconciliation: ReconciliationResult | None,
    output_path: Path,
) -> Path:
    wb = Workbook()

    # --- Summary tab ---
    ws_summary = wb.active
    ws_summary.title = "Summary"
    ws_summary["A1"] = "FBR vs Local Sales Tax Reconciliation -- Summary"
    ws_summary["A1"].font = Font(name="Calibri", size=14, bold=True)
    ws_summary.merge_cells("A1:C1")

    status_color = GREEN if comparison.matched else RED
    rows = [
        ("FBR Total", comparison.fbr_total),
        ("Local Total", comparison.local_total),
        ("Difference", comparison.difference),
        ("Status", comparison.status_label),
    ]
    for i, (label, val) in enumerate(rows, start=3):
        ws_summary.cell(row=i, column=1, value=label).font = Font(name="Calibri", bold=True)
        cell = ws_summary.cell(row=i, column=2, value=val)
        cell.font = Font(name="Calibri", bold=(label == "Status"),
                          color=status_color if label == "Status" else "000000")
        if isinstance(val, (int, float)):
            cell.number_format = "#,##0.00"

    if reconciliation is not None:
        ws_summary.cell(row=8, column=1, value="Row-Level Reconciliation Breakdown").font = Font(
            name="Calibri", bold=True, size=12
        )
        for i, (label, val) in enumerate(reconciliation.summary.items(), start=9):
            ws_summary.cell(row=i, column=1, value=label).font = Font(name="Calibri")
            ws_summary.cell(row=i, column=2, value=val).font = Font(name="Calibri")

    ws_summary.column_dimensions["A"].width = 28
    ws_summary.column_dimensions["B"].width = 20

    if reconciliation is not None and not reconciliation.detail.empty:
        detail = reconciliation.detail
        # "Matched" covers the exact, rounding, and split-invoice variants.
        matched = detail[detail["Status"].str.startswith("Matched")]
        mismatched = detail[detail["Status"] == "Mismatch"]
        missing = detail[detail["Status"].isin(["Missing in FBR", "Missing in Local"])]
        cancelled = detail[detail["Status"] == "Cancelled / Zero"]
        # Everything an accountant actually has to look at, in one tab.
        exceptions = detail[~detail["Status"].eq("Matched")]

        _write_dataframe(wb.create_sheet("Exceptions"), exceptions)
        _write_dataframe(wb.create_sheet("Matched"), matched)
        _write_dataframe(wb.create_sheet("Mismatched"), mismatched)
        _write_dataframe(wb.create_sheet("Missing"), missing)
        _write_dataframe(wb.create_sheet("Cancelled"), cancelled)

    ws_totals = wb.create_sheet("Totals-Difference")
    totals_df = pd.DataFrame([
        {"Metric": "FBR Total", "Value": comparison.fbr_total},
        {"Metric": "Local Total", "Value": comparison.local_total},
        {"Metric": "Difference (FBR - Local)", "Value": comparison.difference},
        {"Metric": "Status", "Value": comparison.status_label},
    ])
    _write_dataframe(ws_totals, totals_df)

    wb.save(output_path)
    return output_path
