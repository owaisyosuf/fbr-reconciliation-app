"""Reusable Streamlit UI components for the reconciliation dashboard.

The design goal is that the *answer* — why the two totals differ and what the
user has to act on — is visible without clicking anything. Totals alone say
"these don't match"; the components here say "here is exactly what accounts for
it, and here are the invoices to look at".
"""
from __future__ import annotations

import html

# Status -> (foreground, background). Shared by the legend, the pills, and the
# table styler so a status looks identical wherever it appears.
STATUS_COLORS: dict[str, tuple[str, str]] = {
    "Matched":                 ("#3fb950", "rgba(63, 185, 80, 0.13)"),
    "Matched (Rounding)":      ("#58a6ff", "rgba(88, 166, 255, 0.13)"),
    "Matched (Split Invoice)": ("#a371f7", "rgba(163, 113, 247, 0.13)"),
    "Matched (Amount Only)":   ("#2dd4bf", "rgba(45, 212, 191, 0.13)"),
    "Mismatch":                ("#f85149", "rgba(248, 81, 73, 0.13)"),
    "Missing in Local":        ("#d29922", "rgba(210, 153, 34, 0.15)"),
    "Missing in FBR":          ("#d29922", "rgba(210, 153, 34, 0.15)"),
    "Cancelled / Zero":        ("#8b949e", "rgba(139, 148, 158, 0.13)"),
}

# Order used for the segmented match-quality bar.
BAR_ORDER = [
    "Matched",
    "Matched (Rounding)",
    "Matched (Split Invoice)",
    "Matched (Amount Only)",
    "Mismatch",
    "Missing in FBR",
    "Missing in Local",
    "Cancelled / Zero",
]

_MATCH_STATUSES = (
    "Matched", "Matched (Rounding)", "Matched (Split Invoice)", "Matched (Amount Only)",
)


def _esc(value) -> str:
    return html.escape(str(value))


def _money(value: float) -> str:
    return f"{value:,.2f}"


def _signed(value: float) -> str:
    return f"{value:+,.2f}"


# ---------------------------------------------------------------------------
# Headline
# ---------------------------------------------------------------------------
def render_hero(st, comparison, recon=None):
    """The single most important sentence on the page.

    Escalates from "matched" through "explained" to "unexplained": a mismatch
    whose every rupee is attributed to named invoices is a very different
    situation from one that doesn't add up, and the banner says which it is.
    """
    diff = comparison.difference

    if comparison.matched:
        tone, icon = "ok", "✅"
        title = "Totals match"
        sub = "The FBR and Local sales-tax totals agree to the paisa. No action needed."
    elif recon is None:
        tone, icon = "bad", "❌"
        title = f"Mismatch of {_money(abs(diff))}"
        sub = ("FBR is higher" if diff > 0 else "Local is higher") + \
              " — open the Reconciliation tab to see which invoices account for it."
    else:
        explained = recon.summary.get("Difference Explained", 0.0)
        fully = abs(explained - diff) < 0.01
        causes = ", ".join(
            f"{b['count']} {b.get('phrase', b['cause'])}" for b in recon.breakdown
        ) or "no attributable cause"
        if fully:
            tone, icon = "warn", "🔎"
            title = f"Mismatch of {_money(abs(diff))} — fully explained"
            sub = f"Every rupee is accounted for: {causes}."
        else:
            tone, icon = "bad", "❌"
            title = f"Mismatch of {_money(abs(diff))} — partly unexplained"
            sub = (f"{_money(abs(diff - explained))} could not be attributed to any "
                   "invoice. Check that both files cover the same period.")

    st.markdown(
        f"""<div class="hero {tone}">
              <div class="hero-icon">{icon}</div>
              <div>
                <div class="hero-title">{_esc(title)}</div>
                <div class="hero-sub">{_esc(sub)}</div>
              </div>
            </div>""",
        unsafe_allow_html=True,
    )


def render_status_banner(st, matched: bool):
    """Kept for backwards compatibility; render_hero is the richer version."""
    cls, text = ("matched", "✅ Your amount is matched.") if matched else \
                ("mismatch", "❌ Amount mismatch detected.")
    st.markdown(f'<div class="status-banner {cls}">{text}</div>', unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# KPIs
# ---------------------------------------------------------------------------
def render_kpi_row(st, fbr_total: float, local_total: float, difference: float, matched: bool):
    kpis = [
        ("FBR Total", _money(fbr_total), "", "Sales Tax / FED in ST Mode"),
        ("Local Total", _money(local_total), "", "Sales Tax / FED in ST Mode"),
        ("Difference", _money(difference), "positive" if matched else "negative", "FBR − Local"),
        ("Status", "✅ Matched" if matched else "❌ Mismatch",
         "positive" if matched else "negative", "1-paisa tolerance"),
    ]
    for col, (label, value, cls, hint) in zip(st.columns(4), kpis):
        with col:
            st.markdown(
                f"""<div class="kpi-card">
                      <div class="kpi-label">{_esc(label)}</div>
                      <div class="kpi-value {cls}">{_esc(value)}</div>
                      <div class="kpi-hint">{_esc(hint)}</div>
                    </div>""",
                unsafe_allow_html=True,
            )


def render_stat_cards(st, items: list[tuple[str, object]], per_row: int = 4):
    """Compact count cards, wrapped so they never squeeze below readability."""
    for start in range(0, len(items), per_row):
        chunk = items[start:start + per_row]
        cols = st.columns(per_row)
        for col, (label, value) in zip(cols, chunk):
            with col:
                shown = f"{value:,}" if isinstance(value, int) else _esc(value)
                fg = STATUS_COLORS.get(label, ("", ""))[0]
                style = f' style="color:{fg}"' if fg else ""
                st.markdown(
                    f"""<div class="kpi-card compact">
                          <div class="kpi-label">{_esc(label)}</div>
                          <div class="kpi-value"{style}>{shown}</div>
                        </div>""",
                    unsafe_allow_html=True,
                )


# ---------------------------------------------------------------------------
# Match-quality bar
# ---------------------------------------------------------------------------
def render_match_bar(st, recon):
    """A single glance at how much of the data reconciled cleanly."""
    detail = recon.detail
    if detail.empty:
        return

    counts = detail["Status"].value_counts().to_dict()
    total = sum(counts.values())
    if not total:
        return

    segments, legend = [], []
    for status in BAR_ORDER:
        n = counts.get(status, 0)
        if not n:
            continue
        fg = STATUS_COLORS.get(status, ("#8b949e", ""))[0]
        pct = n / total * 100
        segments.append(
            f'<div class="match-seg" style="width:{pct:.4f}%;background:{fg}" '
            f'title="{_esc(status)}: {n}"></div>'
        )
        legend.append(
            f'<div class="legend-item"><span class="legend-dot" style="background:{fg}"></span>'
            f'<span class="legend-count">{n}</span> {_esc(status)}</div>'
        )

    matched = sum(counts.get(s, 0) for s in _MATCH_STATUSES)
    pct_matched = matched / total * 100

    st.markdown(
        f"""<div class="panel">
              <div class="panel-head">
                <div class="panel-title">Match quality</div>
                <div class="panel-figure">{matched} of {total} lines matched
                  <span class="muted">({pct_matched:.1f}%)</span></div>
              </div>
              <div class="match-bar">{''.join(segments)}</div>
              <div class="match-legend">{''.join(legend)}</div>
            </div>""",
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Difference attribution
# ---------------------------------------------------------------------------
def render_explained_panel(st, comparison, recon):
    """Walk from the two totals down to the named causes of the gap.

    This is the panel that answers "why don't these match?" — the question the
    totals alone can't.
    """
    diff = comparison.difference
    explained = recon.summary.get("Difference Explained", 0.0)
    fully = abs(explained - diff) < 0.01

    rows = [
        f'<div class="exp-row"><span class="exp-label">FBR Total</span>'
        f'<span class="exp-amount">{_money(comparison.fbr_total)}</span></div>',
        f'<div class="exp-row"><span class="exp-label">Local Total</span>'
        f'<span class="exp-amount">{_money(comparison.local_total)}</span></div>',
        f'<div class="exp-row total"><span class="exp-label">Difference (FBR − Local)</span>'
        f'<span class="exp-amount {"pos" if abs(diff) < 0.01 else "neg"}">{_money(diff)}</span></div>',
    ]

    if recon.breakdown:
        rows.append('<div class="exp-heading">Accounted for by</div>')
        for line in recon.breakdown:
            cls = {"bad": "neg", "muted": "mut"}.get(line["tone"], "")
            rows.append(
                f'<div class="exp-row"><span class="exp-label">'
                f'<span class="exp-count">{line["count"]}</span> {_esc(line["cause"])}</span>'
                f'<span class="exp-amount {cls}">{_signed(line["amount"])}</span></div>'
            )

    badge = ('<span class="exp-badge ok">✓ Fully reconciled</span>' if fully
             else '<span class="exp-badge bad">Unexplained remainder</span>')
    rows.append(
        f'<div class="exp-row grand"><span class="exp-label">Total explained {badge}</span>'
        f'<span class="exp-amount">{_money(explained)}</span></div>'
    )

    note = ("Every row in both files is accounted for, so the figures above are the "
            "complete set of differences."
            if fully else
            f"{_money(abs(diff - explained))} of the difference could not be traced to "
            "any invoice — the two files may not cover the same period.")
    rows.append(f'<div class="exp-note">{_esc(note)}</div>')

    st.markdown(
        f'<div class="panel"><div class="panel-title">Why the totals differ</div>'
        f'{"".join(rows)}</div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Action list
# ---------------------------------------------------------------------------
def render_findings(st, recon, limit: int = 8):
    """The specific invoices a person has to do something about."""
    detail = recon.detail
    if detail.empty:
        return

    actionable = detail[detail["Status"].isin(
        ["Mismatch", "Missing in FBR", "Missing in Local"]
    )]
    if actionable.empty:
        st.markdown(
            '<div class="panel"><div class="panel-title">Action required</div>'
            '<div class="empty-state">✅ Nothing to action — every invoice on both '
            'sides has a counterpart.</div></div>',
            unsafe_allow_html=True,
        )
        return

    def _num(*values):
        """First value that's a real number (pandas uses NaN, not None, for
        missing numerics)."""
        for v in values:
            if v is None or v != v:
                continue
            try:
                return float(v)
            except (TypeError, ValueError):
                continue
        return None

    cards = []
    for _, row in actionable.head(limit).iterrows():
        status = row["Status"]
        fg = STATUS_COLORS.get(status, ("#f85149", ""))[0]
        amount = _num(row["FBR Amount"], row["Local Amount"]) if status != "Mismatch" \
            else _num(row["Difference"])
        where = (f'FBR row {row["FBR Row #"]}' if row["FBR Row #"]
                 else f'Local row {row["Local Row #"]}')
        value = _num(row["FBR Value"], row["Local Value"])
        meta = f'{status} · {where}'
        if value is not None:
            meta += f' · value {_money(value)}'
        cards.append(
            f'<div class="finding" style="border-left-color:{fg}">'
            f'<div class="f-main"><div class="f-title">{_esc(row["Buyer"] or "—")}</div>'
            f'<div class="f-meta">{_esc(meta)}</div></div>'
            f'<div class="f-amt" style="color:{fg}">'
            f'{_money(amount) if amount is not None else "—"}</div></div>'
        )

    more = ""
    if len(actionable) > limit:
        more = (f'<div class="exp-note">+ {len(actionable) - limit} more — '
                'see the Reconciliation tab for the full list.</div>')

    st.markdown(
        f'<div class="panel"><div class="panel-head">'
        f'<div class="panel-title">Action required</div>'
        f'<div class="panel-figure">{len(actionable)} invoice(s)</div></div>'
        f'{"".join(cards)}{more}</div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Progress stepper
# ---------------------------------------------------------------------------
def render_progress(st, step_placeholder, step_index: int, steps: list[str]):
    """Horizontal stepper. step_index is the 0-based currently active step."""
    parts = []
    for i, step in enumerate(steps):
        state = "done" if i < step_index else ("active" if i == step_index else "")
        mark = "✓" if i < step_index else str(i + 1)
        parts.append(
            f'<div class="node {state}"><span class="dot">{mark}</span>'
            f'<span class="lbl">{_esc(step)}</span></div>'
        )
        if i < len(steps) - 1:
            parts.append(f'<div class="link {"done" if i < step_index else ""}"></div>')
    step_placeholder.markdown(
        f'<div class="stepper">{"".join(parts)}</div>', unsafe_allow_html=True
    )


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------
def _status_styler(col):
    out = []
    for value in col:
        fg, bg = STATUS_COLORS.get(str(value), ("", ""))
        out.append(f"color:{fg};background-color:{bg};font-weight:600" if fg else "")
    return out


def _difference_styler(col):
    out = []
    for value in col:
        try:
            num = float(value)
        except (TypeError, ValueError):
            out.append("")
            continue
        if abs(num) < 0.005:
            out.append("color:#3fb950")
        else:
            out.append("color:#f85149;font-weight:600")
    return out


def render_data_table(st, df, key: str, page_size: int = 25):
    """Searchable, filterable, paginated table with status colouring."""
    if df is None or df.empty:
        st.markdown('<div class="empty-state">No rows to display.</div>',
                    unsafe_allow_html=True)
        return

    search_col, filter_col = st.columns([2, 2])
    with search_col:
        query = st.text_input("🔍 Search", key=f"{key}_search",
                              placeholder="Search all columns…")
    with filter_col:
        filter_column = st.selectbox(
            "Filter column", options=["(none)"] + list(df.columns), key=f"{key}_filter_col"
        )

    filtered = df.copy()
    if query:
        mask = filtered.apply(
            lambda row: row.astype(str).str.contains(query, case=False, na=False).any(), axis=1
        )
        filtered = filtered[mask]

    if filter_column != "(none)":
        unique_vals = sorted(filtered[filter_column].dropna().astype(str).unique().tolist())
        chosen = st.multiselect(f"Values for '{filter_column}'", options=unique_vals,
                                key=f"{key}_filter_vals")
        if chosen:
            filtered = filtered[filtered[filter_column].astype(str).isin(chosen)]

    total_rows = len(filtered)
    total_pages = max(1, (total_rows - 1) // page_size + 1)
    page = st.number_input("Page", min_value=1, max_value=total_pages, value=1, step=1,
                           key=f"{key}_page")
    start = (page - 1) * page_size
    page_df = filtered.iloc[start:start + page_size]

    styled = page_df.style
    if "Status" in page_df.columns:
        styled = styled.apply(_status_styler, subset=["Status"])
    if "Difference" in page_df.columns:
        styled = styled.apply(_difference_styler, subset=["Difference"])
    numeric_cols = [c for c in ("FBR Value", "Local Value", "FBR Amount",
                                "Local Amount", "Difference") if c in page_df.columns]
    if numeric_cols:
        styled = styled.format("{:,.2f}", subset=numeric_cols, na_rep="—")

    st.caption(
        f"Showing rows {min(start + 1, total_rows)}–{min(start + page_size, total_rows)} "
        f"of {total_rows:,}"
    )
    st.dataframe(styled, use_container_width=True, hide_index=True)


def render_error(st, err) -> None:
    """Render a ReconciliationError (or generic exception) as a friendly message."""
    message = getattr(err, "message", str(err))
    detail = getattr(err, "detail", "")
    st.error(f"⚠️ {message}")
    if detail:
        with st.expander("Technical details"):
            st.code(detail)
