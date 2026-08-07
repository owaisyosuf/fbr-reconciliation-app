# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run the app (venv is committed-adjacent but gitignored; create if missing)
./venv/bin/streamlit run app.py --server.headless true --server.port 8501

# First-time setup
python3 -m venv venv && ./venv/bin/pip install -r requirements.txt
```

Streamlit takes ~20s to bind the port on WSL. Wait for the listener rather
than assuming failure: `until curl -sf -o /dev/null http://localhost:8501; do sleep 2; done`

`soffice` (LibreOffice) must be on `PATH` — it converts legacy `.xls` Local
exports to `.xlsx`. Without it, only `.xlsx` uploads work.

There is no test suite, linter, or formatter configured. See **Verifying a
change** below for how correctness is actually established.

## Architecture

A five-stage pipeline wired together in `app.py`; each stage is a module that
can be driven directly from Python without the UI.

```
upload → save_upload() copy → 2 skills → calculate_tax_total() ×2
       → compare_totals() → reconcile() → dashboard
```

**Originals are never modified.** `utils/file_helpers.save_upload` copies every
upload into `/tmp/fbr_reconciliation_work/` first; everything downstream
operates on those copies. That directory is also where a real pair of files can
be found after the user has run the app once — useful for reproducing a bug.

**Skills are isolated and reusable.** `skills/fbr_processing/` and
`skills/local_processing/` hold the original, unmodified standalone scripts.
`skills/fbr_skill.py` / `skills/local_skill.py` are thin wrappers that call into
them and translate failures into `utils/exceptions` types the UI can render.
Change formatting behaviour in the bundled scripts, not the wrappers.

**The two reports have different shapes.** FBR output lands its header on row 1;
Local output on row 3. Nothing hardcodes those numbers — `services/totals.py`,
`services/sheet_reader.py` and `processors/reconciliation.py` each scan the
first 15 rows for a header matching `utils.validators.is_tax_column_header`.

**Totals are computed in Python, not by a spreadsheet engine.**
`services/totals.py` sums raw numeric cell values via openpyxl and skips the
Total row's `=SUM()` formula string, so the comparison is available immediately.

**`processors/reconciliation.py` is where the domain complexity lives.** It
pairs individual invoice rows and attributes the entire header-level difference
to named causes. Read its module docstring before changing it.

## Domain traps

These are non-obvious, cost real debugging, and will silently produce
plausible-but-wrong output if reintroduced.

**Never match rows on date.** FBR's `Invoice Date` is the date the invoice was
*filed* on the FBR portal — invoices arrive batched, so dozens share one date.
The Local Annex C `Date` is the real invoice date. They cannot agree. A
`(date, value)` key reported ~200 of ~250 rows as missing.

**Resolve the tax column with the token matcher, never a substring search.**
`"Value of Sales Excluding Sales Tax"` contains the words *sales tax*, so
`_find_col(df, "sales tax")` returns the **value** column and the app silently
compares value against value. Use `is_tax_column_header()`; for the value
column, exclude headers that satisfy it.

**Normalise registrations by splitting on the hyphen, not by length.** FBR
writes the bare registration, Annex C appends a check digit after a hyphen.
Registrations are not all the same width, so a length rule mangles the short
ones and the same buyer becomes two entities.

**Pair one-to-one.** An outer merge on a duplicated key fans out into a
cartesian product — result rows exceeded input rows before this was fixed.
Every tier in `reconcile()` consumes rows from both sides.

**The Local export repeats header labels** (two merged `Type` columns).
`_sheet_to_dataframe` de-duplicates them; without that, `df[col]` returns a
DataFrame instead of a Series.

## Verifying a change

`reconcile()` returns a `Difference Explained` figure. **It must equal
`FBR total − Local total` exactly** — that invariant is what makes the row-level
detail trustworthy, and the UI shows a green banner only when it holds. Any
change to matching must preserve it, and must keep every input row accounted
for in the detail frame.

```python
from pathlib import Path
from processors.reconciliation import reconcile
from services.totals import calculate_tax_total

fp, lp = Path("/tmp/fbr_reconciliation_work/fbr_updated_X.xlsx"), Path(".../local_updated_Y.xlsx")
diff = calculate_tax_total(fp, "FBR").total - calculate_tax_total(lp, "Local").total
r = reconcile(fp, lp, tolerance=2.0)
assert abs(diff - r.summary["Difference Explained"]) < 0.01
```

Reconciling a file against **itself** must yield 100% matched, zero missing,
zero mismatch, and a 0.00 difference — a fast regression check that catches most
matching bugs.

## Tolerance

`reconcile(..., tolerance=…)` is a rupee allowance on the *sales-tax* amount
(default `2.00`); the tax-exclusive value gets `VALUE_TOLERANCE_FACTOR` (10×)
more, because at the ~18% rate a 1-rupee tax gap is ~5.5 rupees of value. A pair
must satisfy both tests. It is exposed as a live control in the Reconciliation
tab. **It only changes how rows are paired — totals are read from the workbooks
and never altered by it.**

## Sensitive data

Real FBR/Annex C exports carry buyer names, NTNs, CNICs and invoice values.
`.gitignore` excludes `*.xls*`, `*.csv` and `*.log` (the app logs totals and row
counts). Keep worked examples in docs and comments as obviously-fake
placeholders rather than values copied from a real file.
