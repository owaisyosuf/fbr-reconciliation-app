"""FBR vs Local Sales Tax Reconciliation Tool.

Streamlit app: upload an FBR export + a Local (Annex C) export, auto-apply the
two processing skills, sum the 'Sales Tax / FED in ST Mode' column in each,
compare, and reconcile row by row. See README.md for details.

Row-level reconciliation runs as part of the pipeline rather than behind a
button: when the totals disagree, "which invoices account for it" is the actual
question being asked, so the answer is on screen as soon as processing ends.
"""
from __future__ import annotations

import streamlit as st

from ui.styles import inject_css
from ui.components import (
    render_hero,
    render_kpi_row,
    render_stat_cards,
    render_match_bar,
    render_explained_panel,
    render_findings,
    render_progress,
    render_data_table,
    render_error,
)
from skills.fbr_skill import apply_fbr_skill
from skills.local_skill import apply_local_skill
from services.totals import calculate_tax_total
from services.comparison import compare_totals
from services.sheet_reader import read_visible_dataframe
from processors.reconciliation import reconcile, DEFAULT_TOLERANCE
from reports.excel_report import build_reconciliation_report
from utils.file_helpers import save_upload, new_output_path
from utils.validators import validate_file_type, validate_readable_excel, check_duplicates
from utils.exceptions import ReconciliationError
from utils.logging_config import get_logger

logger = get_logger("app")

st.set_page_config(
    page_title="FBR vs Local Sales Tax Reconciliation",
    page_icon="📊",
    layout="wide",
)
inject_css(st)

PIPELINE_STEPS = [
    "Uploading", "Processing Skills", "Updating Sheets",
    "Calculating Totals", "Reconciling Rows", "Completed",
]

# ---------------------------------------------------------------------------
# Session state defaults
# ---------------------------------------------------------------------------
defaults = {
    "processed": False,
    "fbr_output_path": None,
    "local_output_path": None,
    "fbr_total_result": None,
    "local_total_result": None,
    "comparison": None,
    "reconciliation": None,
    "recon_error": None,
    "report_path": None,
    "duplicate_warnings": [],
}
for k, v in defaults.items():
    st.session_state.setdefault(k, v)

# A user setting rather than a result, so Reset / re-processing keeps it.
st.session_state.setdefault("tolerance", DEFAULT_TOLERANCE)


def reset_results():
    for k, v in defaults.items():
        st.session_state[k] = v


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.markdown(
    """<div class="page-head">
         <div class="page-title">📊 FBR vs Local Sales Tax Reconciliation</div>
         <div class="page-sub">Upload the monthly FBR export and the Local (Annex C)
         export — the processing skills run automatically, totals are compared, and
         every row is reconciled to show exactly what accounts for any difference.</div>
       </div>""",
    unsafe_allow_html=True,
)
st.write("")

# ---------------------------------------------------------------------------
# Step 1 — Upload
# ---------------------------------------------------------------------------
col1, col2 = st.columns(2)
with col1:
    st.markdown('<div class="upload-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">📄 Upload FBR Excel</div>', unsafe_allow_html=True)
    fbr_file = st.file_uploader(
        "FBR export (.xlsx)", type=["xlsx", "xls", "xlsm"], key="fbr_upload",
        label_visibility="collapsed",
    )
    st.markdown("</div>", unsafe_allow_html=True)

with col2:
    st.markdown('<div class="upload-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">📄 Upload Local Excel</div>', unsafe_allow_html=True)
    local_file = st.file_uploader(
        "Local Annex C export (.xlsx/.xls)", type=["xlsx", "xls", "xlsm"], key="local_upload",
        label_visibility="collapsed",
    )
    st.markdown("</div>", unsafe_allow_html=True)

st.write("")

both_uploaded = fbr_file is not None and local_file is not None
start_col, reset_col = st.columns([1, 1])
with start_col:
    start_clicked = st.button("▶️ Start Processing", disabled=not both_uploaded,
                              use_container_width=True)
with reset_col:
    if st.button("🔄 Reset", use_container_width=True):
        reset_results()
        st.rerun()

if not both_uploaded:
    st.info("Upload both files to enable processing.")

# ---------------------------------------------------------------------------
# Steps 2-5 — Process, Update Sheets, Calculate Totals, Reconcile
# ---------------------------------------------------------------------------
if start_clicked and both_uploaded:
    reset_results()
    progress_placeholder = st.empty()
    render_progress(st, progress_placeholder, 0, PIPELINE_STEPS)

    try:
        # -- Uploading --
        validate_file_type(fbr_file.name)
        validate_file_type(local_file.name)
        fbr_input_path = save_upload(fbr_file, "fbr")
        local_input_path = save_upload(local_file, "local")
        validate_readable_excel(str(fbr_input_path))
        validate_readable_excel(str(local_input_path))
        render_progress(st, progress_placeholder, 1, PIPELINE_STEPS)

        # -- Processing Skills / Updating Sheets --
        fbr_output_path = new_output_path("fbr_updated")
        local_output_path = new_output_path("local_updated")
        apply_fbr_skill(fbr_input_path, fbr_output_path)
        render_progress(st, progress_placeholder, 2, PIPELINE_STEPS)
        apply_local_skill(local_input_path, local_output_path)
        render_progress(st, progress_placeholder, 3, PIPELINE_STEPS)

        # -- Calculating Totals --
        fbr_total_result = calculate_tax_total(fbr_output_path, "FBR")
        local_total_result = calculate_tax_total(local_output_path, "Local")
        comparison = compare_totals(fbr_total_result.total, local_total_result.total)

        # Light duplicate check on the visible/display data (warning only).
        fbr_display_df = read_visible_dataframe(fbr_output_path)
        local_display_df = read_visible_dataframe(local_output_path)
        dup_warnings = []
        fbr_dupe_keys = [c for c in fbr_display_df.columns
                         if "date" in c.lower() or "buyer" in c.lower()]
        local_dupe_keys = [c for c in local_display_df.columns
                           if "date" in c.lower() or "name" in c.lower()]
        n_fbr_dupes = check_duplicates(fbr_display_df, fbr_dupe_keys) if fbr_dupe_keys else 0
        n_local_dupes = check_duplicates(local_display_df, local_dupe_keys) if local_dupe_keys else 0
        if n_fbr_dupes:
            dup_warnings.append(f"FBR file: {n_fbr_dupes} possible duplicate rows detected.")
        if n_local_dupes:
            dup_warnings.append(f"Local file: {n_local_dupes} possible duplicate rows detected.")
        render_progress(st, progress_placeholder, 4, PIPELINE_STEPS)

        # -- Reconciling Rows -- a failure here shouldn't lose the totals.
        recon_result, recon_error = None, None
        try:
            recon_result = reconcile(fbr_output_path, local_output_path,
                                     tolerance=st.session_state["tolerance"])
        except Exception as exc:  # noqa: BLE001
            logger.exception("Row-level reconciliation failed")
            recon_error = str(exc)
        render_progress(st, progress_placeholder, 5, PIPELINE_STEPS)

        st.session_state.update({
            "processed": True,
            "fbr_output_path": str(fbr_output_path),
            "local_output_path": str(local_output_path),
            "fbr_total_result": fbr_total_result,
            "local_total_result": local_total_result,
            "comparison": comparison,
            "reconciliation": recon_result,
            "recon_error": recon_error,
            "duplicate_warnings": dup_warnings,
        })

    except ReconciliationError as exc:
        render_error(st, exc)
        st.stop()
    except Exception as exc:  # noqa: BLE001 - surface unexpected errors gracefully too
        logger.exception("Unexpected error during processing")
        st.error(f"⚠️ Something went wrong while processing your files: {exc}")
        st.stop()

# ---------------------------------------------------------------------------
# Step 6 — Results Dashboard
# ---------------------------------------------------------------------------
if st.session_state["processed"]:
    comparison = st.session_state["comparison"]
    fbr_total_result = st.session_state["fbr_total_result"]
    local_total_result = st.session_state["local_total_result"]
    recon = st.session_state["reconciliation"]

    for w in st.session_state["duplicate_warnings"]:
        st.warning(f"⚠️ {w}")
    if st.session_state["recon_error"]:
        st.warning(
            "⚠️ Totals were compared, but row-level reconciliation couldn't run: "
            f"{st.session_state['recon_error']}"
        )

    st.write("")
    tab_summary, tab_recon, tab_fbr, tab_local, tab_download = st.tabs(
        ["Summary", "Reconciliation", "Updated FBR Sheet", "Updated Local Sheet", "Download"]
    )

    # -- Summary: the answer, top to bottom --------------------------------
    with tab_summary:
        render_hero(st, comparison, recon)
        st.write("")
        render_kpi_row(st, comparison.fbr_total, comparison.local_total,
                       comparison.difference, comparison.matched)
        st.write("")

        if recon is not None:
            render_match_bar(st, recon)
            st.write("")
            left, right = st.columns([1, 1])
            with left:
                render_explained_panel(st, comparison, recon)
            with right:
                render_findings(st, recon)
            st.write("")

        st.caption(
            f"FBR: {fbr_total_result.row_count} rows summed from "
            f"'{fbr_total_result.column_header}' • Local: {local_total_result.row_count} rows "
            f"summed from '{local_total_result.column_header}'."
        )

    # -- Reconciliation: the full row-level detail -------------------------
    with tab_recon:
        if recon is None:
            st.markdown(
                '<div class="empty-state">Row-level reconciliation is unavailable '
                'for these files.</div>', unsafe_allow_html=True
            )
        else:
            # Tolerance is adjustable here rather than only at upload time —
            # the right value depends on how the two systems happened to round,
            # which you can only judge after seeing the result.
            tol_col, note_col = st.columns([1, 3])
            with tol_col:
                tol = st.number_input(
                    "Match tolerance (₨)", min_value=0.0, max_value=100.0,
                    value=float(st.session_state["tolerance"]), step=0.5, format="%.2f",
                    key="tolerance_input",
                    help="Largest sales-tax gap still treated as the same invoice. "
                         "The tax-exclusive value gets a proportionally larger "
                         "allowance. 0 = exact amounts only.",
                )
            with note_col:
                st.caption(
                    f"Rows whose sales tax differs by up to **₨{st.session_state['tolerance']:,.2f}** "
                    "(and value by up to "
                    f"**₨{max(st.session_state['tolerance'] * 10, 1.0):,.2f}**) are treated as the "
                    "same invoice. Raise it if genuine pairs show as missing; lower it if "
                    "unrelated invoices are being paired. Changing it re-matches immediately — "
                    "totals are never altered, only how rows are paired."
                )

            if abs(tol - float(st.session_state["tolerance"])) > 1e-9:
                st.session_state["tolerance"] = tol
                with st.spinner("Re-matching rows…"):
                    try:
                        st.session_state["reconciliation"] = reconcile(
                            st.session_state["fbr_output_path"],
                            st.session_state["local_output_path"],
                            tolerance=tol,
                        )
                        st.session_state["recon_error"] = None
                    except Exception as exc:  # noqa: BLE001
                        logger.exception("Re-matching failed")
                        st.session_state["recon_error"] = str(exc)
                st.rerun()

            st.write("")
            summary = dict(recon.summary)
            summary.pop("Difference Explained", None)
            render_stat_cards(st, list(summary.items()))
            st.write("")

            st.caption(
                "Rows are paired on **buyer NTN + amounts**, never on date — FBR's "
                "*Invoice Date* is the portal filing date (invoices arrive batched, so "
                "many share one date) while the Local *Date* is the true invoice date, "
                "so the two never line up. Split invoices — several rows on one side "
                "summing to one on the other — and paisa-level rounding are matched "
                "automatically; CANCELLED / nil rows are set aside rather than counted "
                "as missing. **Matched (Amount Only)** means the amounts agree but the "
                "two registrations don't — usually a sole proprietor filing under a CNIC "
                "in one report and a business NTN in the other. Worth a glance."
            )
            st.write("")

            statuses = list(recon.detail["Status"].unique())
            exceptions_only = [s for s in statuses if s != "Matched"]
            chosen = st.multiselect(
                "Show statuses", statuses,
                default=exceptions_only or statuses,
                key="recon_status_filter",
                help="Defaults to exceptions only — clear or add 'Matched' to see every row.",
            )
            view = recon.detail[recon.detail["Status"].isin(chosen)] if chosen else recon.detail
            render_data_table(st, view, key="recon_table")

    with tab_fbr:
        st.markdown('<div class="section-title">Updated FBR Sheet</div>', unsafe_allow_html=True)
        render_data_table(st, read_visible_dataframe(st.session_state["fbr_output_path"]),
                          key="fbr_table")

    with tab_local:
        st.markdown('<div class="section-title">Updated Local Sheet</div>', unsafe_allow_html=True)
        render_data_table(st, read_visible_dataframe(st.session_state["local_output_path"]),
                          key="local_table")

    with tab_download:
        st.markdown('<div class="section-title">Downloads</div>', unsafe_allow_html=True)
        dl1, dl2, dl3 = st.columns(3)
        with dl1:
            with open(st.session_state["fbr_output_path"], "rb") as f:
                st.download_button(
                    "⬇️ Updated FBR Excel", f, file_name="FBR_Updated.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )
        with dl2:
            with open(st.session_state["local_output_path"], "rb") as f:
                st.download_button(
                    "⬇️ Updated Local Excel", f, file_name="Local_Updated.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )
        with dl3:
            if st.button("📑 Generate Reconciliation Report", use_container_width=True):
                report_path = new_output_path("reconciliation_report")
                build_reconciliation_report(comparison, recon, report_path)
                st.session_state["report_path"] = str(report_path)

            if st.session_state["report_path"]:
                with open(st.session_state["report_path"], "rb") as f:
                    st.download_button(
                        "⬇️ Reconciliation Report", f, file_name="Reconciliation_Report.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                    )
