# FBR vs Local Sales Tax Reconciliation Tool

A Streamlit app that automates the daily reconciliation between an **FBR**
export (Baber Tyre Corporation's monthly "Domestic Invoices" report) and a
**Local** export (FBR "Annex C" local sales report), by auto-applying two
Claude Skills, summing the `Sales Tax / FED in ST Mode` column in each, and
flagging a match or mismatch.

## Quick start

```bash
pip install -r requirements.txt
streamlit run app.py
```

LibreOffice (`soffice`) must be installed and on `PATH` — it's used to
convert legacy `.xls` Local exports to `.xlsx` before processing.

## How it works

1. **Upload** — drop in the FBR file and the Local (Annex C) file.
2. **Process** — Skill 01 (FBR) and Skill 02 (Local) run automatically:
   cleaning, hiding non-essential columns, converting text-formatted numbers,
   applying consistent styling, and adding a live `=SUM()` Total row to each.
3. **Calculate Totals** — the `Sales Tax / FED in ST Mode` column is summed
   directly from the processed workbook (header text is matched flexibly, so
   minor spacing/casing differences between the two report types don't
   matter).
4. **Compare** — ✅ *Matched* if totals agree (within a 1-paisa rounding
   tolerance), otherwise ❌ *Mismatch* with the difference shown
   (`FBR Total - Local Total`).
5. **Reconcile** — every row is paired automatically (see *Phase 2 row
   matching* below). This runs as part of the pipeline rather than behind a
   button: when the totals disagree, "which invoices account for it" is the
   actual question, so the answer is on screen as soon as processing ends.
6. **Output** — the **Summary** tab leads with the finding, not just the
   numbers:
   - a headline banner that distinguishes *matched* / *mismatch fully
     explained* / *mismatch partly unexplained*;
   - KPI cards for both totals, the difference, and status;
   - a **match-quality bar** segmenting every line by status;
   - **Why the totals differ** — a walk from the two totals down to the named
     causes, whose amounts sum to the difference exactly;
   - **Action required** — the specific buyers, rows, and amounts to chase.

   The **Reconciliation** tab holds the full row-level table (status-coloured,
   searchable, filterable, paginated, defaulting to exceptions only), and
   **Download** exports both updated files plus a multi-tab Reconciliation
   Report (Summary, Exceptions, Matched, Mismatched, Missing, Cancelled,
   Totals/Difference).

## Project layout

```
app.py                          Streamlit entry point / UI wiring
ui/
  styles.py                     Professional Accounting Dashboard theme (CSS)
  components.py                 Hero banner, KPI cards, match-quality bar, difference
                                attribution panel, action list, stepper, data table
skills/
  fbr_skill.py                  Skill 01 wrapper (Baber Tyre FBR formatter)
  local_skill.py                Skill 02 wrapper (Annex C / Local processor)
  fbr_processing/                Bundled Skill 01 script (format_sales_tax_report.py)
  local_processing/              Bundled Skill 02 script (process_annex_c.py)
services/
  totals.py                     Sums the tax column from a processed workbook
  comparison.py                 FBR vs Local comparison logic
  sheet_reader.py                Reads visible columns back into a DataFrame for display
processors/
  reconciliation.py             Phase 2 row-level reconciliation
reports/
  excel_report.py               Multi-tab Reconciliation Report generator
utils/
  file_helpers.py                Safe upload persistence (originals are never modified)
  validators.py                  File type / column / empty-sheet / duplicate checks
  exceptions.py                  User-friendly error types
  logging_config.py              Centralized logging
requirements.txt
README.md
```

## Design notes

- **Skills are isolated and reusable.** `skills/fbr_processing/` and
  `skills/local_processing/` hold the original, unmodified skill scripts.
  `skills/fbr_skill.py` and `skills/local_skill.py` are thin wrappers that
  call into them and translate failures into friendly, UI-ready errors.
  Update the underlying skill logic independently of the app/UI code.
- **Originals are never touched.** Uploads are copied into a scratch temp
  directory (`utils/file_helpers.py`) before any processing happens.
- **Totals are computed in Python, not by opening the file in Excel.**
  `services/totals.py` sums raw numeric cell values (skipping the `=SUM()`
  formula in the Total row), so the comparison is available immediately
  without depending on a spreadsheet engine to recalculate first.
- **Flexible column matching.** The FBR file's kept column is literally
  named `Sales Tax/ FED in ST Mode`; the Local file's merged header may come
  out slightly differently depending on the source export's exact wording.
  `utils/validators.is_tax_column_header` matches by normalized token set
  (`sales`, `tax`, `fed`, ...) rather than an exact string, so both are
  recognized correctly.
- **Phase 2 row matching — never on date.** FBR's `Invoice Date` is the date
  the invoice was *filed* on the FBR portal (invoices arrive batched — a whole
  week's sales can share one date), while the Local Annex C `Date` is the real
  invoice date. They genuinely don't agree, so any key involving date flags
  almost every row as missing. The two files also don't share an invoice
  number: FBR carries its own portal reference
  (`1234567890123AB4C5DEF678901-1`), Local carries the company serial
  (`14870`).

  What they *do* share is the **buyer's NTN** — FBR writes `1234567`, Annex C
  writes the same NTN as `1234567-8` (7 digits + check digit), so
  `_normalize_ntn` reduces both to bare digits. Rows are then paired
  **one-to-one** in tiers:

  | Tier | Basis | Status |
  |---|---|---|
  | 1 | Buyer NTN + value + tax, exact | `Matched` |
  | 2 | Buyer NTN, amounts within tolerance | `Matched (Rounding)` |
  | 3 | Value + tax exact (blank/unknown NTN) | `Matched` |
  | 4 | N rows one side sum to 1 row on the other | `Matched (Split Invoice)` |
  | 5 | Buyer NTN + value agree, tax doesn't | `Mismatch` |
  | 6 | Amounts agree within tolerance, registrations don't | `Matched (Amount Only)` |
  | 7 | No counterpart left | `Missing in FBR` / `Missing in Local` |

  Tier 6 exists because a sole proprietor commonly files under a 13-digit CNIC
  in one report and a 7-digit business NTN in the other — the same taxpayer
  trading under a personal name in one system and a business name in the other.
  No amount of registration normalising reconciles those two numbers, so the
  tier pairs on amounts alone. It runs last, after every identity-backed
  pairing, and gets its own status rather than plain `Matched` because the
  pairing is arithmetically sound but unverified — worth a glance.

- **Registration normalising.** FBR writes the bare registration (`1234567`,
  `A987654`); Annex C writes it with a trailing check digit (`1234567-8`,
  `A987654-3`). `_normalize_ntn` splits on the **hyphen**, not on total length:
  registrations are not all the same width, so `A987654-3` would otherwise read
  as the seven-digit NTN `9876543` and never match FBR's `A987654`.

- **Tolerance is a setting, not a constant.** `reconcile(..., tolerance=…)`
  takes a rupee allowance on the *sales-tax* amount (default `2.00`); the
  tax-exclusive value gets `VALUE_TOLERANCE_FACTOR` (10×) more, because at the
  ~18% rate a 1-rupee tax gap corresponds to ~5.5 rupees of value. A pair must
  satisfy **both** tests. The Reconciliation tab exposes it as a live control —
  the right value depends on how the two systems happened to round, which you
  can only judge after seeing the result. Changing it re-matches rows only;
  the totals are read from the workbooks and never altered.

  Zero-amount and `CANCELLED` lines are set aside as `Cancelled / Zero` so they
  don't inflate the missing counts. Because every tier consumes rows
  one-to-one, a repeated key can't fan out into a cartesian product — the row
  counts in the result always tie back to the row counts in the inputs.

- **The row detail must explain the header difference.** `reconcile()` returns
  a `Difference Explained` figure; the UI shows a green confirmation only when
  it equals `FBR Total − Local Total` to the paisa. If it doesn't, the
  row-level detail is incomplete and the banner says so rather than quietly
  showing a plausible-looking table.

## Error handling

Friendly messages (with a "Technical details" expander) are shown for:
- Wrong file type / invalid or unreadable Excel file
- Missing `Sales Tax / FED in ST Mode` column
- Empty sheets (no data rows)
- Possible duplicate records (warning, not a hard stop)
- Unexpected/corrupt data during Skill processing
