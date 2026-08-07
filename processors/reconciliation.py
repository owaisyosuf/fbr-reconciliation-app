"""Phase 2 (optional) -- row-level reconciliation between the processed FBR
and Local workbooks.

Matching strategy
-----------------
The two reports do NOT share a usable date. FBR's "Invoice Date" is the date
the invoice was *filed/uploaded* to the FBR portal (invoices get batched, so a
whole week's sales can land on one date), while the Local Annex C "Date" is the
real invoice date. Keying on date therefore flags almost every row as missing.

They also don't share an invoice number: FBR carries its own portal reference
(``1234567890123AB4C5DEF678901-1``) while Local carries the company's own
serial (``14870``).

What they *do* share is the buyer's NTN (FBR "Buyer Registration No" vs Local
"Registration No" -- same number, different formatting) plus the money columns.
So rows are paired by buyer identity + amounts, in tiers, one-to-one:

1. ``Matched``                -- same buyer, same value, same tax (exact)
2. ``Matched (Rounding)``     -- same buyer, amounts agree within tolerance
                                 (the two systems round differently, e.g.
                                 66,101.69 vs 66,102.00)
3. ``Mismatch``               -- same buyer and value, but the tax differs
4. ``Matched (Split Invoice)``-- N rows on one side sum to 1 row on the other
                                 (one system consolidates what the other splits)
5. ``Missing in FBR`` /
   ``Missing in Local``       -- genuinely unpaired after all of the above
6. ``Cancelled / Zero``       -- zero-amount or CANCELLED rows, reported
                                 separately so they don't inflate "missing"

Every tier consumes rows one-to-one, so a duplicated key can never fan out into
a cartesian product (the old outer-merge did, which is why counts exceeded the
input row counts).
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from itertools import combinations
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook

from utils.validators import is_tax_column_header, normalize_header
from utils.logging_config import get_logger

logger = get_logger(__name__)

# Default tolerance, in rupees, on the *sales-tax* amount: the largest gap
# between two rows still considered the same invoice line. The two systems
# round differently (FBR keeps paisa, the local ledger often rounds to the
# rupee), so a small allowance is required or genuine pairs read as missing.
DEFAULT_TOLERANCE = 2.00

# The tax-exclusive value is the larger, more sensitive number: at the ~18%
# sales-tax rate a 1-rupee tax difference corresponds to roughly 5.5 rupees of
# value, so the value allowance is scaled up rather than shared. Keeping it
# generous is safe because a pair must satisfy *both* the value and the tax
# test, and the tax is the figure actually being reconciled.
VALUE_TOLERANCE_FACTOR = 10.0

# Largest number of rows on one side allowed to sum to a single row on the
# other when detecting split/consolidated invoices.
MAX_GROUP_SIZE = 4


def _tolerances(tolerance: float) -> tuple[float, float]:
    """(value tolerance, tax tolerance) for a user-supplied tax tolerance."""
    tax_tol = max(float(tolerance), 0.0)
    return max(tax_tol * VALUE_TOLERANCE_FACTOR, 1.0), tax_tol


# ---------------------------------------------------------------------------
# Sheet -> DataFrame
# ---------------------------------------------------------------------------
def _sheet_to_dataframe(path: Path) -> pd.DataFrame:
    """Read a processed workbook into a DataFrame, auto-detecting the header
    row (row 1 for FBR-skill output, row 3 for Local-skill output) and
    stopping before the Total row.
    """
    wb = load_workbook(path, data_only=False)
    ws = wb.active

    header_row_idx = None
    headers = None
    for r in range(1, min(ws.max_row, 15) + 1):
        row_vals = [ws.cell(row=r, column=c).value for c in range(1, ws.max_column + 1)]
        if any(is_tax_column_header(v) for v in row_vals):
            header_row_idx = r
            headers = row_vals
            break
    if header_row_idx is None:
        wb.close()
        raise ValueError("Could not locate a header row containing the tax column.")

    tax_col_positions = [i for i, h in enumerate(headers) if is_tax_column_header(h)]

    records = []
    excel_rows = []
    for r in range(header_row_idx + 1, ws.max_row + 1):
        row_vals = [ws.cell(row=r, column=c).value for c in range(1, ws.max_column + 1)]
        if not tax_col_positions:
            continue
        # Skip the Total row: its tax cell holds a formula string.
        tax_val = row_vals[tax_col_positions[0]]
        if isinstance(tax_val, str) and tax_val.strip().startswith("="):
            continue
        if all(v is None or v == "" for v in row_vals):
            continue
        records.append(row_vals)
        excel_rows.append(r)

    wb.close()

    # Header labels repeat in the Local export (two merged "Type" columns), so
    # de-duplicate before building the frame -- duplicate names make df[col]
    # return a DataFrame instead of a Series.
    clean_headers = []
    seen: dict[str, int] = {}
    for i, h in enumerate(headers):
        name = normalize_header(h) or f"col_{i}"
        if name in seen:
            seen[name] += 1
            name = f"{name}_{seen[name]}"
        else:
            seen[name] = 0
        clean_headers.append(name)

    df = pd.DataFrame(records, columns=clean_headers)
    df["_excel_row"] = excel_rows
    return df


def _find_col(df: pd.DataFrame, *candidates: str) -> str | None:
    for cand in candidates:
        for col in df.columns:
            if cand in col:
                return col
    return None


# ---------------------------------------------------------------------------
# Value normalisation
# ---------------------------------------------------------------------------
def _to_number(val):
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        s = val.replace(",", "").strip()
        try:
            return float(s)
        except ValueError:
            return None
    return None


def _to_date_str(val):
    if val is None or val == "":
        return ""
    try:
        return pd.to_datetime(val).strftime("%Y-%m-%d")
    except Exception:
        return str(val).strip()


def _normalize_ntn(val) -> str:
    """Reduce a buyer registration to a comparable key.

    FBR writes the bare registration (``1234567``, ``A987654``); Annex C writes
    the same registration with a trailing check digit (``1234567-8``,
    ``A987654-3``). The check digit always follows a hyphen, so splitting there
    is exact — inferring it from the total length is not, because registrations
    are not all the same width (``A987654`` is six digits, so ``A987654-3``
    would otherwise read as the seven-digit NTN ``9876543`` and never match).
    """
    if val is None:
        return ""
    text = str(val).strip()
    if "-" in text:
        text = text.rsplit("-", 1)[0]
    digits = re.sub(r"[^0-9]", "", text)
    return digits.lstrip("0")


def _clean_name(val) -> str:
    if val is None:
        return ""
    return re.sub(r"\s+", " ", str(val).strip().lstrip(".")).strip()


# ---------------------------------------------------------------------------
# Row model
# ---------------------------------------------------------------------------
@dataclass
class _Row:
    excel_row: int
    ntn: str
    name: str
    date: str
    value: float
    tax: float

    @property
    def is_void(self) -> bool:
        """CANCELLED / nil-value lines carry no tax and shouldn't be reported
        as missing on the other side."""
        return abs(self.value) < 0.005 and abs(self.tax) < 0.005


def _extract_rows(df: pd.DataFrame, side: str) -> list[_Row]:
    ntn_col = _find_col(df, "buyer registration", "registration no", "registration")
    name_col = _find_col(df, "buyer name", "name")
    date_col = _find_col(df, "invoice date", "date")
    # "Value of Sales Excluding Sales Tax" also contains the words "sales tax",
    # so the tax column must be identified by the token matcher, not substring
    # search, or both resolve to the value column.
    tax_col = next((c for c in df.columns if is_tax_column_header(c)), None)
    value_col = next(
        (c for c in df.columns if "value of sales" in c and not is_tax_column_header(c)),
        None,
    )

    if value_col is None or tax_col is None:
        raise ValueError(
            f"{side} sheet is missing the value / sales-tax columns needed for "
            "row-level reconciliation."
        )

    rows: list[_Row] = []
    for _, rec in df.iterrows():
        value = _to_number(rec[value_col])
        tax = _to_number(rec[tax_col])
        if value is None and tax is None:
            continue
        rows.append(_Row(
            excel_row=int(rec["_excel_row"]),
            ntn=_normalize_ntn(rec[ntn_col]) if ntn_col else "",
            name=_clean_name(rec[name_col]) if name_col else "",
            date=_to_date_str(rec[date_col]) if date_col else "",
            value=round(value or 0.0, 2),
            tax=round(tax or 0.0, 2),
        ))
    logger.info("%s: extracted %d rows (ntn column=%s)", side, len(rows), ntn_col)
    return rows


# ---------------------------------------------------------------------------
# Matching tiers
# ---------------------------------------------------------------------------
def _match_exact(fbr: list[_Row], local: list[_Row], keyfn):
    """One-to-one pairing on an exact key. Consumes from both lists."""
    buckets: dict = defaultdict(list)
    for r in local:
        buckets[keyfn(r)].append(r)

    pairs, leftover_f = [], []
    for r in fbr:
        bucket = buckets.get(keyfn(r))
        if bucket:
            pairs.append((r, bucket.pop(0)))
        else:
            leftover_f.append(r)

    leftover_l = [r for b in buckets.values() for r in b]
    return pairs, leftover_f, leftover_l


def _match_tolerant(fbr: list[_Row], local: list[_Row], tolerance: float, *,
                    require_tax: bool, require_ntn: bool = True):
    """Pair rows whose amounts agree within tolerance, closest match first.

    ``require_tax=True`` also demands the tax agree (a rounding match);
    ``False`` pairs on value alone so a genuine tax discrepancy surfaces as a
    Mismatch rather than as two "missing" rows.

    ``require_ntn=False`` drops the buyer-identity requirement. That is only
    safe as a late tier, once every identity-backed pairing has been made --
    it exists because a sole proprietor commonly files under a 13-digit CNIC in
    one report and a 7-digit business NTN in the other (personal name vs trading
    name), which no amount of registration normalising can reconcile.
    """
    value_tol, tax_tol = _tolerances(tolerance)

    by_ntn: dict = defaultdict(list)
    for r in local:
        by_ntn[r.ntn if require_ntn else ""].append(r)

    pairs, leftover_f = [], []
    for r in fbr:
        if require_ntn:
            # A blank NTN identifies nobody -- pairing on amounts alone here
            # would let an approximate match beat the exact-amount tier below.
            candidates = by_ntn.get(r.ntn, []) if r.ntn else []
        else:
            candidates = by_ntn[""]

        best, best_delta = None, None
        for cand in candidates:
            if abs(cand.value - r.value) > value_tol:
                continue
            if require_tax and abs(cand.tax - r.tax) > tax_tol:
                continue
            delta = abs(cand.value - r.value) + abs(cand.tax - r.tax)
            if best_delta is None or delta < best_delta:
                best, best_delta = cand, delta
        if best is not None:
            candidates.remove(best)
            pairs.append((r, best))
        else:
            leftover_f.append(r)

    leftover_l = [r for b in by_ntn.values() for r in b]
    return pairs, leftover_f, leftover_l


def _match_groups(fbr: list[_Row], local: list[_Row], tolerance: float):
    """Detect split/consolidated invoices: N rows on one side summing to a
    single row on the other, for the same buyer.
    """
    value_tol, tax_tol = _tolerances(tolerance)

    by_ntn_f: dict = defaultdict(list)
    by_ntn_l: dict = defaultdict(list)
    for r in fbr:
        by_ntn_f[r.ntn].append(r)
    for r in local:
        by_ntn_l[r.ntn].append(r)

    groups: list[tuple[list[_Row], list[_Row]]] = []

    for ntn in set(by_ntn_f) & set(by_ntn_l):
        if not ntn:
            continue  # blank NTN carries no identity -- too risky to group on
        fs, ls = by_ntn_f[ntn], by_ntn_l[ntn]

        def _consume(many: list[_Row], one_side: list[_Row], many_is_fbr: bool):
            progressed = True
            while progressed:
                progressed = False
                for single in list(one_side):
                    found = None
                    max_n = min(MAX_GROUP_SIZE, len(many))
                    for n in range(2, max_n + 1):
                        tol_v = value_tol * n
                        tol_t = tax_tol * n
                        for combo in combinations(many, n):
                            if abs(sum(c.value for c in combo) - single.value) > tol_v:
                                continue
                            if abs(sum(c.tax for c in combo) - single.tax) > tol_t:
                                continue
                            found = combo
                            break
                        if found:
                            break
                    if found:
                        side_f = list(found) if many_is_fbr else [single]
                        side_l = [single] if many_is_fbr else list(found)
                        groups.append((side_f, side_l))
                        for c in found:
                            many.remove(c)
                        one_side.remove(single)
                        progressed = True

        _consume(fs, ls, many_is_fbr=True)   # several FBR rows -> one Local row
        _consume(ls, fs, many_is_fbr=False)  # one FBR row -> several Local rows

    leftover_f = [r for b in by_ntn_f.values() for r in b]
    leftover_l = [r for b in by_ntn_l.values() for r in b]
    return groups, leftover_f, leftover_l


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------
@dataclass
class ReconciliationResult:
    detail: pd.DataFrame
    summary: dict = field(default_factory=dict)
    # Ordered "what accounts for the gap" lines; amounts sum to the header
    # difference (FBR total - Local total).
    breakdown: list = field(default_factory=list)


def _compute_breakdown(detail: pd.DataFrame) -> list[dict]:
    """Attribute the FBR-vs-Local difference to concrete, nameable causes."""
    if detail.empty:
        return []

    def _sum(df, col):
        return round(df[col].fillna(0).sum(), 2)

    lines = []

    missing_local = detail[detail["Status"] == "Missing in Local"]
    if len(missing_local):
        lines.append({
            "cause": "In FBR but not in Local",
            "phrase": "invoices in FBR with no Local counterpart",
            "count": len(missing_local),
            "amount": _sum(missing_local, "FBR Amount"),
            "tone": "bad",
        })

    missing_fbr = detail[detail["Status"] == "Missing in FBR"]
    if len(missing_fbr):
        lines.append({
            "cause": "In Local but not in FBR",
            "phrase": "invoices in Local with no FBR counterpart",
            "count": len(missing_fbr),
            "amount": -_sum(missing_fbr, "Local Amount"),
            "tone": "bad",
        })

    mismatch = detail[detail["Status"] == "Mismatch"]
    if len(mismatch):
        lines.append({
            "cause": "Tax differs on paired invoices",
            "phrase": "paired invoices where the tax differs",
            "count": len(mismatch),
            "amount": _sum(mismatch, "Difference"),
            "tone": "bad",
        })

    for status, label, phrase in (
        ("Matched (Rounding)", "Rounding differences", "rounding differences"),
        ("Matched (Split Invoice)", "Split-invoice residual", "split-invoice residuals"),
        ("Matched (Amount Only)", "Amount-only pairings", "amount-only pairings"),
    ):
        subset = detail[detail["Status"] == status]
        amount = _sum(subset, "Difference")
        if len(subset) and abs(amount) >= 0.005:
            lines.append({
                "cause": label, "phrase": phrase, "count": len(subset),
                "amount": amount, "tone": "muted",
            })

    return lines


def _detail_row(fbr_rows, local_rows, status, basis):
    fbr_val = sum(r.value for r in fbr_rows) if fbr_rows else None
    local_val = sum(r.value for r in local_rows) if local_rows else None
    fbr_tax = sum(r.tax for r in fbr_rows) if fbr_rows else None
    local_tax = sum(r.tax for r in local_rows) if local_rows else None
    diff = round(fbr_tax - local_tax, 2) if fbr_tax is not None and local_tax is not None else None
    buyer = (fbr_rows or local_rows)[0].name

    return {
        "Buyer": buyer,
        "FBR Row #": ", ".join(str(r.excel_row) for r in fbr_rows) if fbr_rows else None,
        "Local Row #": ", ".join(str(r.excel_row) for r in local_rows) if local_rows else None,
        "FBR Date": ", ".join(sorted({r.date for r in fbr_rows})) if fbr_rows else None,
        "Local Date": ", ".join(sorted({r.date for r in local_rows})) if local_rows else None,
        "FBR Value": round(fbr_val, 2) if fbr_val is not None else None,
        "Local Value": round(local_val, 2) if local_val is not None else None,
        "FBR Amount": round(fbr_tax, 2) if fbr_tax is not None else None,
        "Local Amount": round(local_tax, 2) if local_tax is not None else None,
        "Difference": diff,
        "Status": status,
        "Match Basis": basis,
    }


STATUS_ORDER = [
    "Mismatch",
    "Missing in FBR",
    "Missing in Local",
    "Matched (Amount Only)",
    "Matched (Split Invoice)",
    "Matched (Rounding)",
    "Cancelled / Zero",
    "Matched",
]

MATCHED_STATUSES = (
    "Matched", "Matched (Rounding)", "Matched (Split Invoice)", "Matched (Amount Only)",
)


def reconcile(fbr_path: Path, local_path: Path,
              tolerance: float = DEFAULT_TOLERANCE) -> ReconciliationResult:
    """Pair every row across the two workbooks.

    ``tolerance`` is in rupees and applies to the sales-tax amount; the
    tax-exclusive value gets a proportionally larger allowance (see
    ``VALUE_TOLERANCE_FACTOR``).
    """
    fbr_rows = _extract_rows(_sheet_to_dataframe(Path(fbr_path)), "FBR")
    local_rows = _extract_rows(_sheet_to_dataframe(Path(local_path)), "Local")

    detail_rows = []

    # Void (CANCELLED / nil) lines are set aside up front so they never count
    # as a missing counterpart on the other side.
    voids_f = [r for r in fbr_rows if r.is_void]
    voids_l = [r for r in local_rows if r.is_void]
    fbr_left = [r for r in fbr_rows if not r.is_void]
    local_left = [r for r in local_rows if not r.is_void]

    # Tier 1 -- same buyer, identical value and tax.
    pairs, fbr_left, local_left = _match_exact(
        fbr_left, local_left, lambda r: (r.ntn, r.value, r.tax)
    )
    for f, l in pairs:
        detail_rows.append(_detail_row([f], [l], "Matched", "Buyer NTN + Value + Tax"))

    # Tier 2 -- same buyer, amounts agree within tolerance.
    pairs, fbr_left, local_left = _match_tolerant(
        fbr_left, local_left, tolerance, require_tax=True
    )
    for f, l in pairs:
        status = "Matched" if abs(f.tax - l.tax) < 0.005 else "Matched (Rounding)"
        detail_rows.append(_detail_row([f], [l], status, "Buyer NTN + amounts (tolerance)"))

    # Tier 3 -- identical amounts but the buyer NTN is blank/unmatched.
    pairs, fbr_left, local_left = _match_exact(
        fbr_left, local_left, lambda r: (r.value, r.tax)
    )
    for f, l in pairs:
        detail_rows.append(_detail_row([f], [l], "Matched", "Value + Tax"))

    # Tier 4 -- split / consolidated invoices.
    groups, fbr_left, local_left = _match_groups(fbr_left, local_left, tolerance)
    for gf, gl in groups:
        detail_rows.append(
            _detail_row(gf, gl, "Matched (Split Invoice)", f"{len(gf)} FBR ↔ {len(gl)} Local")
        )

    # Tier 5 -- same buyer and value, but the tax differs: a real discrepancy.
    # Runs before the identity-free tier so a buyer's own tax error is reported
    # as a Mismatch rather than hidden by a lookalike from another buyer.
    pairs, fbr_left, local_left = _match_tolerant(
        fbr_left, local_left, tolerance, require_tax=False
    )
    for f, l in pairs:
        detail_rows.append(_detail_row([f], [l], "Mismatch", "Buyer NTN + Value (tax differs)"))

    # Tier 6 -- amounts agree within tolerance but the registrations don't.
    # Flagged distinctly: the pairing is sound arithmetically but unverified by
    # identity, so it's surfaced for review rather than silently "Matched".
    pairs, fbr_left, local_left = _match_tolerant(
        fbr_left, local_left, tolerance, require_tax=True, require_ntn=False
    )
    for f, l in pairs:
        detail_rows.append(
            _detail_row([f], [l], "Matched (Amount Only)", "Amounts agree, buyer ID differs")
        )

    # Whatever survives is genuinely unpaired.
    for r in fbr_left:
        detail_rows.append(_detail_row([r], [], "Missing in Local", "No counterpart"))
    for r in local_left:
        detail_rows.append(_detail_row([], [r], "Missing in FBR", "No counterpart"))
    for r in voids_f:
        detail_rows.append(_detail_row([r], [], "Cancelled / Zero", "Nil amount"))
    for r in voids_l:
        detail_rows.append(_detail_row([], [r], "Cancelled / Zero", "Nil amount"))

    detail = pd.DataFrame(detail_rows)
    if not detail.empty:
        detail["_order"] = detail["Status"].map(
            {s: i for i, s in enumerate(STATUS_ORDER)}
        ).fillna(len(STATUS_ORDER))
        detail = (
            detail.sort_values(by=["_order", "Buyer"], na_position="last")
            .drop(columns=["_order"])
            .reset_index(drop=True)
        )

    def _count(*statuses):
        if detail.empty:
            return 0
        return int(detail["Status"].isin(statuses).sum())

    summary = {
        "Matched": _count(*MATCHED_STATUSES),
        "Mismatch": _count("Mismatch"),
        "Missing in FBR": _count("Missing in FBR"),
        "Missing in Local": _count("Missing in Local"),
        "Cancelled / Zero": _count("Cancelled / Zero"),
        "Total Rows Compared": len(detail),
    }

    # A correct reconciliation must explain the header-level difference exactly.
    fbr_total = round(sum(r.tax for r in fbr_rows), 2)
    local_total = round(sum(r.tax for r in local_rows), 2)
    explained = round(detail["Difference"].fillna(0).sum(), 2) if not detail.empty else 0.0
    unpaired = round(
        sum(r.tax for r in fbr_left) - sum(r.tax for r in local_left), 2
    )
    summary["Difference Explained"] = round(explained + unpaired, 2)

    summary["FBR Rows"] = len(fbr_rows)
    summary["Local Rows"] = len(local_rows)

    logger.info(
        "Reconciliation summary: %s (FBR total %.2f, Local total %.2f, diff %.2f)",
        summary, fbr_total, local_total, round(fbr_total - local_total, 2),
    )

    return ReconciliationResult(
        detail=detail, summary=summary, breakdown=_compute_breakdown(detail)
    )
