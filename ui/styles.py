"""Professional Dark Theme for the FBR Reconciliation Dashboard.
Deep full-black background, blue accents, crisp light text, subtle glow on hover.
Inspired by Bloomberg Terminal / modern trading-dashboard aesthetics.
"""

CUSTOM_CSS = """
<style>
/* ── Root tokens ────────────────────────────────────────────── */
:root {
    --bg-primary:    #0a0a0f;
    --bg-secondary:  #0d1117;
    --bg-card:       #11141a;
    --bg-card-hover: #1a1f2a;
    --bg-input:      #0a0a0f;
    --bg-tab:        #0d0f14;
    --accent:        #58a6ff;
    --accent-hover:  #79b8ff;
    --accent-glow:   rgba(88, 166, 255, 0.12);
    --green:         #3fb950;
    --green-bg:      rgba(63, 185, 80, 0.10);
    --green-border:  rgba(63, 185, 80, 0.25);
    --red:           #f85149;
    --red-bg:        rgba(248, 81, 73, 0.10);
    --red-border:    rgba(248, 81, 73, 0.25);
    --text-primary:  #f0f6fc;
    --text-secondary:#8b949e;
    --text-muted:    #6e7681;
    --border:        #21262d;
    --border-light:  #30363d;
    --border-focus:  #58a6ff;
    --radius:        12px;
    --radius-sm:     8px;
    --shadow:        0 4px 16px rgba(0, 0, 0, 0.4);
    --shadow-hover:  0 8px 24px rgba(0, 0, 0, 0.55);
    --gradient-btn:  linear-gradient(135deg, #1f6feb 0%, #58a6ff 100%);
    --gradient-btn-h: linear-gradient(135deg, #388bfd 0%, #79b8ff 100%);
}

/* ── Global override — kill all whites ──────────────────────── */
.stApp, .stApp > div, .main > div, .block-container {
    background-color: var(--bg-primary) !important;
}
.stApp > header {
    background-color: var(--bg-card) !important;
    border-bottom: 1px solid var(--border) !important;
}
.block-container {
    /* Streamlit's header toolbar is fixed/floating above the content; this
       must clear its full height with margin to spare, or the page title
       renders partially underneath it. The exact header height varies by
       rendering engine (it clipped in the pywebview desktop window at
       1.5rem despite looking fine in Chrome), so this stays generous. */
    padding-top: 4.5rem !important;
}
.st-emotion-cache-1wrcr25, .st-emotion-cache-12fmjuu, .st-emotion-cache-1avcm0n {
    background: var(--bg-primary) !important;
}

/* ── All text defaults ──────────────────────────────────────── */
html, body, .stApp, p, li, span, div:not([class*="kpi"]):not([class*="Mui"]) {
    color: var(--text-primary) !important;
}
h1, h2, h3, h4, h5, h6 {
    color: var(--text-primary) !important;
}
h2 {
    font-weight: 700 !important;
    font-size: 1.5rem !important;
    letter-spacing: -0.02em !important;
}
.stCaption, caption, .stMarkdown caption {
    color: var(--text-secondary) !important;
}

/* ── KPI Cards ──────────────────────────────────────────────── */
.kpi-card {
    background: var(--bg-card) !important;
    border-radius: var(--radius) !important;
    padding: 18px 20px !important;
    border: 1px solid var(--border) !important;
    text-align: left !important;
    transition: all 0.25s ease !important;
    box-shadow: var(--shadow) !important;
}
.kpi-card:hover {
    border-color: var(--accent) !important;
    box-shadow: var(--shadow-hover), 0 0 24px var(--accent-glow) !important;
    transform: translateY(-2px) !important;
    background: var(--bg-card-hover) !important;
}
.kpi-label {
    font-size: 12px !important;
    font-weight: 600 !important;
    color: var(--text-secondary) !important;
    text-transform: uppercase !important;
    letter-spacing: 0.05em !important;
    margin-bottom: 4px !important;
}
.kpi-value {
    font-size: 24px !important;
    font-weight: 700 !important;
    color: var(--text-primary) !important;
}
.kpi-value.positive {
    color: var(--green) !important;
}
.kpi-value.negative {
    color: var(--red) !important;
}

/* ── Status Banner ──────────────────────────────────────────── */
.status-banner {
    border-radius: var(--radius) !important;
    padding: 16px 24px !important;
    font-size: 17px !important;
    font-weight: 700 !important;
    text-align: center !important;
    transition: all 0.25s ease !important;
}
.status-banner.matched {
    background: var(--green-bg) !important;
    color: var(--green) !important;
    border: 1px solid var(--green-border) !important;
}
.status-banner.matched:hover {
    box-shadow: 0 0 24px rgba(63, 185, 80, 0.15) !important;
}
.status-banner.mismatch {
    background: var(--red-bg) !important;
    color: var(--red) !important;
    border: 1px solid var(--red-border) !important;
}
.status-banner.mismatch:hover {
    box-shadow: 0 0 24px rgba(248, 81, 73, 0.15) !important;
}

/* ── Upload Section ─────────────────────────────────────────── */
.upload-card {
    background: var(--bg-card) !important;
    border-radius: var(--radius) !important;
    padding: 14px 16px !important;
    border: 1.5px dashed var(--border) !important;
    transition: all 0.25s ease !important;
}
.upload-card:hover {
    border-color: var(--accent) !important;
    background: var(--bg-card-hover) !important;
    box-shadow: 0 0 20px var(--accent-glow) !important;
}

.section-title {
    font-size: 14px !important;
    font-weight: 700 !important;
    color: var(--accent) !important;
    margin: 0 0 8px 0 !important;
}

/* ── File Uploader — dark + compact ─────────────────────────── */
.stFileUploader {
    background: transparent !important;
    padding: 0 !important;
}
.stFileUploader > div {
    background: var(--bg-input) !important;
    border: 1px dashed var(--border) !important;
    border-radius: var(--radius-sm) !important;
    min-height: unset !important;
    padding: 6px 10px !important;
}
.stFileUploader > div:hover {
    border-color: var(--accent) !important;
}
.stFileUploader [data-testid="stMarkdownContainer"] {
    color: var(--text-secondary) !important;
    font-size: 13px !important;
}
.stFileUploader [data-testid="fileUploaderButton"] > button {
    background: var(--bg-card) !important;
    border: 1px solid var(--border-light) !important;
    color: var(--text-primary) !important;
    border-radius: 6px !important;
    font-size: 13px !important;
    padding: 4px 12px !important;
}
.stFileUploader [data-testid="fileUploaderButton"] > button:hover {
    border-color: var(--accent) !important;
    background: var(--bg-card-hover) !important;
}
.stFileUploader [data-testid="fileUploaderButton"] svg {
    fill: var(--accent) !important;
}

/* ── Primary Button ─────────────────────────────────────────── */
div.stButton > button {
    background: var(--gradient-btn) !important;
    color: white !important;
    border: none !important;
    border-radius: var(--radius-sm) !important;
    padding: 0.5em 1.3em !important;
    font-weight: 600 !important;
    transition: all 0.25s ease !important;
    box-shadow: 0 2px 8px rgba(31, 111, 235, 0.3) !important;
}
div.stButton > button:hover {
    background: var(--gradient-btn-h) !important;
    box-shadow: 0 4px 18px rgba(88, 166, 255, 0.4) !important;
    transform: translateY(-1px) !important;
}
div.stButton > button:active {
    transform: translateY(0) !important;
}
div.stButton > button:disabled {
    opacity: 0.4 !important;
    cursor: not-allowed !important;
    box-shadow: none !important;
}

/* ── Secondary / Download Button ────────────────────────────── */
div.stDownloadButton > button {
    background: transparent !important;
    color: var(--accent) !important;
    border: 1.5px solid var(--accent) !important;
    border-radius: var(--radius-sm) !important;
    font-weight: 600 !important;
    transition: all 0.25s ease !important;
}
div.stDownloadButton > button:hover {
    background: rgba(88, 166, 255, 0.08) !important;
    box-shadow: 0 0 14px var(--accent-glow) !important;
}

/* ── Tabs ───────────────────────────────────────────────────── */
.stTabs {
    background: transparent !important;
}
.stTabs [data-baseweb="tab-list"] {
    gap: 6px !important;
    background: transparent !important;
    border-bottom: 1px solid var(--border) !important;
    padding: 0 !important;
}
.stTabs [data-baseweb="tab"] {
    background: transparent !important;
    color: var(--text-secondary) !important;
    border-radius: 6px 6px 0 0 !important;
    padding: 8px 16px !important;
    font-size: 14px !important;
    font-weight: 500 !important;
    border: none !important;
    border-bottom: 2px solid transparent !important;
    transition: all 0.2s ease !important;
    margin-bottom: -1px !important;
}
.stTabs [data-baseweb="tab"]:hover {
    color: var(--text-primary) !important;
    background: rgba(255,255,255,0.03) !important;
}
.stTabs [aria-selected="true"] {
    color: var(--accent) !important;
    border-bottom: 2px solid var(--accent) !important;
    background: transparent !important;
}
/* ── Tab content panel ────────────────────────────────────────── */
.stTabs [data-baseweb="tab-panel"] {
    background: var(--bg-tab) !important;
    border: 1px solid var(--border) !important;
    border-top: none !important;
    border-radius: 0 0 var(--radius-sm) var(--radius-sm) !important;
    padding: 20px !important;
}

/* ── Data Table ─────────────────────────────────────────────── */
.stDataFrame {
    border-radius: var(--radius-sm) !important;
    overflow: hidden !important;
}
.stDataFrame > div {
    background: transparent !important;
}
.stDataFrame [data-testid="StyledDataFrameScroll"] {
    background: var(--bg-tab) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius-sm) !important;
}
.stDataFrame [data-testid="StyledDataFrameColHeader"] {
    background: var(--bg-secondary) !important;
    color: var(--accent) !important;
    border-bottom: 1px solid var(--border) !important;
    font-weight: 600 !important;
    font-size: 13px !important;
}
.stDataFrame [data-testid="StyledDataFrameDataCell"] {
    background: transparent !important;
    color: var(--text-primary) !important;
    border-bottom: 1px solid var(--border) !important;
    transition: background 0.15s ease !important;
    font-size: 13px !important;
}
.stDataFrame [data-testid="StyledDataFrameDataCell"]:hover {
    background: var(--bg-card-hover) !important;
}
.stDataFrame [data-testid="StyledDataFrameDataRow"]:nth-child(even) [data-testid="StyledDataFrameDataCell"] {
    background: rgba(255, 255, 255, 0.015) !important;
}
.stDataFrame [data-testid="StyledDataFrameDataRow"]:nth-child(even) [data-testid="StyledDataFrameDataCell"]:hover {
    background: var(--bg-card-hover) !important;
}
.stDataFrame svg {
    fill: var(--text-secondary) !important;
}
.stDataFrame [data-testid="StyledDataFrameToolbar"] {
    background: var(--bg-tab) !important;
    border-bottom: 1px solid var(--border) !important;
}

/* ── Text Input / Search ────────────────────────────────────── */
.stTextInput > div > div {
    background: var(--bg-input) !important;
    border: 1px solid var(--border-light) !important;
    border-radius: var(--radius-sm) !important;
    transition: all 0.2s ease !important;
}
.stTextInput > div > div:focus-within {
    border-color: var(--border-focus) !important;
    box-shadow: 0 0 0 2px var(--accent-glow) !important;
}
.stTextInput input, .stTextInput input::placeholder {
    color: var(--text-primary) !important;
}
.stTextInput svg {
    fill: var(--text-secondary) !important;
}

/* ── Selectbox ──────────────────────────────────────────────── */
.stSelectbox > div > div {
    background: var(--bg-input) !important;
    border: 1px solid var(--border-light) !important;
    border-radius: var(--radius-sm) !important;
    color: var(--text-primary) !important;
    transition: all 0.2s ease !important;
}
.stSelectbox > div > div:focus-within {
    border-color: var(--border-focus) !important;
    box-shadow: 0 0 0 2px var(--accent-glow) !important;
}
.stSelectbox [data-baseweb="select"] {
    background: transparent !important;
}
.stSelectbox svg {
    fill: var(--text-secondary) !important;
}

/* ── Multiselect ────────────────────────────────────────────── */
.stMultiSelect > div > div {
    background: var(--bg-input) !important;
    border: 1px solid var(--border-light) !important;
    border-radius: var(--radius-sm) !important;
    transition: all 0.2s ease !important;
}
.stMultiSelect > div > div:focus-within {
    border-color: var(--border-focus) !important;
    box-shadow: 0 0 0 2px var(--accent-glow) !important;
}
.stMultiSelect svg {
    fill: var(--text-secondary) !important;
}
.stMultiSelect [data-baseweb="tag"] {
    background: var(--bg-card) !important;
    color: var(--text-primary) !important;
    border: 1px solid var(--border) !important;
}

/* ── Number Input (pagination) ──────────────────────────────── */
.stNumberInput > div > div {
    background: var(--bg-input) !important;
    border: 1px solid var(--border-light) !important;
    border-radius: var(--radius-sm) !important;
    transition: all 0.2s ease !important;
}
.stNumberInput > div > div:focus-within {
    border-color: var(--border-focus) !important;
    box-shadow: 0 0 0 2px var(--accent-glow) !important;
}
.stNumberInput input {
    color: var(--text-primary) !important;
}
.stNumberInput button {
    background: var(--bg-card) !important;
    border: 1px solid var(--border-light) !important;
    color: var(--text-primary) !important;
}
.stNumberInput svg {
    fill: var(--text-secondary) !important;
}

/* ── Alert / Info / Warning / Error / Success ──────────────── */
.stAlert {
    border-radius: var(--radius-sm) !important;
    padding: 12px 16px !important;
}
.stAlert > div > div {
    color: inherit !important;
}
.stInfo {
    background: rgba(88, 166, 255, 0.08) !important;
    border: 1px solid rgba(88, 166, 255, 0.2) !important;
    color: var(--accent) !important;
}
.stWarning {
    background: rgba(187, 128, 9, 0.10) !important;
    border: 1px solid rgba(187, 128, 9, 0.25) !important;
    color: #d29922 !important;
}
.stError {
    background: var(--red-bg) !important;
    border: 1px solid var(--red-border) !important;
    color: var(--red) !important;
}
.stSuccess {
    background: var(--green-bg) !important;
    border: 1px solid var(--green-border) !important;
    color: var(--green) !important;
}
.stAlert svg {
    fill: currentColor !important;
}

/* ── Expander ───────────────────────────────────────────────── */
.streamlit-expanderHeader {
    background: var(--bg-card) !important;
    color: var(--text-primary) !important;
    border-radius: var(--radius-sm) !important;
    border: 1px solid var(--border) !important;
    font-weight: 500 !important;
}
.streamlit-expanderHeader:hover {
    border-color: var(--accent) !important;
    background: var(--bg-card-hover) !important;
}
.streamlit-expanderHeader svg {
    fill: var(--text-secondary) !important;
}
.streamlit-expanderContent {
    background: var(--bg-tab) !important;
    border: 1px solid var(--border) !important;
    border-top: none !important;
    border-radius: 0 0 var(--radius-sm) var(--radius-sm) !important;
    padding: 12px 16px !important;
}

/* ── Spinner ────────────────────────────────────────────────── */
.stSpinner {
    color: var(--accent) !important;
}

/* ── Code block (technical details) ─────────────────────────── */
.stCodeBlock, .stCodeBlock pre {
    background: var(--bg-card) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius-sm) !important;
    color: var(--text-primary) !important;
}

/* ── Markdown text area ─────────────────────────────────────── */
.stMarkdown {
    color: var(--text-primary) !important;
}
.stMarkdown p {
    color: var(--text-primary) !important;
}

/* ── Write (blank lines) ──────────────────────────────────── */
.stWrite {
    color: transparent !important;
}

/* ── Data table caption ─────────────────────────────────────── */
.stDataFrame + div .stCaption,
.stCaption, .element-container .stCaption {
    color: var(--text-muted) !important;
    font-size: 12px !important;
}

/* ── Radio (hidden, but keep dark) ─────────────────────────── */
.stRadio > div {
    background: transparent !important;
    color: var(--text-primary) !important;
}

/* ── Checkbox ──────────────────────────────────────────────── */
.stCheckbox > div {
    background: transparent !important;
}
.stCheckbox label {
    color: var(--text-primary) !important;
}

/* ── Catch-all for any leftover Streamlit whiteness ────────── */
.css-1kyxreq, .css-1r6slb0, .css-1dp5vir, .css-18ni7ap,
.css-1cpxqw2, .css-dh2k0n, .css-6qob1r, .css-1v3fvcr,
.css-1qg05tj, .css-1q1n0ol, .css-1y4p8pa, .css-1y0f1oi,
.css-k1ih3n, .css-1vq0elg, .css-1offfwp, .css-1bv1cbm,
.css-1wrcr25, .css-12fmjuu, .css-1avcm0n {
    background: transparent !important;
    background-color: transparent !important;
}

/* ═══════════════════════════════════════════════════════════════
   Dashboard surfaces — hero, panels, match bar, findings, stepper
   ═══════════════════════════════════════════════════════════════ */

/* ── Hero: the headline finding ─────────────────────────────── */
.hero {
    display: flex !important;
    align-items: center !important;
    gap: 18px !important;
    padding: 20px 24px !important;
    border-radius: var(--radius) !important;
    border: 1px solid var(--border) !important;
    background: var(--bg-card) !important;
}
.hero.ok {
    border-color: var(--green-border) !important;
    background: linear-gradient(135deg, rgba(63,185,80,0.10), rgba(63,185,80,0.02)) !important;
}
.hero.warn {
    border-color: rgba(210,153,34,0.30) !important;
    background: linear-gradient(135deg, rgba(210,153,34,0.10), rgba(210,153,34,0.02)) !important;
}
.hero.bad {
    border-color: var(--red-border) !important;
    background: linear-gradient(135deg, rgba(248,81,73,0.10), rgba(248,81,73,0.02)) !important;
}
.hero-icon { font-size: 32px !important; line-height: 1 !important; flex: none !important; }
.hero-title {
    font-size: 20px !important;
    font-weight: 700 !important;
    letter-spacing: -0.01em !important;
    margin-bottom: 3px !important;
}
.hero.ok   .hero-title { color: var(--green) !important; }
.hero.warn .hero-title { color: #d29922 !important; }
.hero.bad  .hero-title { color: var(--red) !important; }
.hero-sub { font-size: 13.5px !important; color: var(--text-secondary) !important; }

/* ── Panel ──────────────────────────────────────────────────── */
.panel {
    background: var(--bg-card) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius) !important;
    padding: 18px 22px !important;
    margin-bottom: 4px !important;
}
.panel-head {
    display: flex !important;
    justify-content: space-between !important;
    align-items: baseline !important;
    margin-bottom: 14px !important;
}
.panel-title {
    font-size: 12px !important;
    font-weight: 700 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.06em !important;
    color: var(--text-secondary) !important;
    margin-bottom: 14px !important;
}
.panel-head .panel-title { margin-bottom: 0 !important; }
.panel-figure {
    font-size: 13px !important;
    font-weight: 600 !important;
    color: var(--text-primary) !important;
}
.panel-figure .muted { color: var(--text-muted) !important; font-weight: 400 !important; }

/* ── Match-quality bar ──────────────────────────────────────── */
.match-bar {
    display: flex !important;
    height: 10px !important;
    border-radius: 999px !important;
    overflow: hidden !important;
    background: var(--bg-primary) !important;
    border: 1px solid var(--border) !important;
}
.match-seg { height: 100% !important; transition: opacity .2s ease !important; }
.match-seg:hover { opacity: 0.75 !important; }
.match-legend {
    display: flex !important;
    flex-wrap: wrap !important;
    gap: 8px 18px !important;
    margin-top: 12px !important;
}
.legend-item {
    display: flex !important;
    align-items: center !important;
    gap: 7px !important;
    font-size: 12.5px !important;
    color: var(--text-secondary) !important;
}
.legend-dot { width: 9px !important; height: 9px !important; border-radius: 3px !important; flex: none !important; }
.legend-count { color: var(--text-primary) !important; font-weight: 700 !important; }

/* ── Difference attribution rows ────────────────────────────── */
.exp-row {
    display: flex !important;
    justify-content: space-between !important;
    align-items: baseline !important;
    gap: 16px !important;
    padding: 7px 0 !important;
    font-size: 13.5px !important;
}
.exp-label { color: var(--text-secondary) !important; }
.exp-amount {
    font-variant-numeric: tabular-nums !important;
    font-weight: 600 !important;
    color: var(--text-primary) !important;
    white-space: nowrap !important;
}
.exp-amount.neg { color: var(--red) !important; }
.exp-amount.pos { color: var(--green) !important; }
.exp-amount.mut { color: var(--text-muted) !important; }
.exp-row.total {
    border-top: 1px solid var(--border-light) !important;
    margin-top: 6px !important;
    padding-top: 11px !important;
}
.exp-row.total .exp-label { color: var(--text-primary) !important; font-weight: 600 !important; }
.exp-row.grand {
    border-top: 2px solid var(--accent) !important;
    margin-top: 8px !important;
    padding-top: 12px !important;
    font-size: 14.5px !important;
}
.exp-row.grand .exp-label { color: var(--text-primary) !important; font-weight: 700 !important; }
.exp-heading {
    font-size: 11.5px !important;
    font-weight: 700 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.05em !important;
    color: var(--text-muted) !important;
    margin: 14px 0 2px 0 !important;
}
.exp-count {
    display: inline-block !important;
    min-width: 20px !important;
    padding: 1px 6px !important;
    margin-right: 7px !important;
    border-radius: 5px !important;
    background: var(--bg-primary) !important;
    border: 1px solid var(--border-light) !important;
    color: var(--text-primary) !important;
    font-size: 11.5px !important;
    font-weight: 700 !important;
    text-align: center !important;
}
.exp-badge {
    display: inline-block !important;
    margin-left: 10px !important;
    padding: 2px 9px !important;
    border-radius: 999px !important;
    font-size: 11px !important;
    font-weight: 700 !important;
    letter-spacing: 0.02em !important;
    vertical-align: middle !important;
}
.exp-badge.ok  { background: var(--green-bg) !important; color: var(--green) !important; border: 1px solid var(--green-border) !important; }
.exp-badge.bad { background: var(--red-bg) !important;   color: var(--red) !important;   border: 1px solid var(--red-border) !important; }
.exp-note {
    font-size: 12.5px !important;
    color: var(--text-muted) !important;
    margin-top: 14px !important;
    line-height: 1.55 !important;
}

/* ── Finding cards (action list) ────────────────────────────── */
.finding {
    display: flex !important;
    align-items: center !important;
    gap: 14px !important;
    padding: 11px 14px !important;
    margin-bottom: 8px !important;
    background: var(--bg-primary) !important;
    border: 1px solid var(--border) !important;
    border-left: 3px solid var(--red) !important;
    border-radius: var(--radius-sm) !important;
    transition: all .2s ease !important;
}
.finding:hover {
    background: var(--bg-card-hover) !important;
    transform: translateX(2px) !important;
}
.finding .f-main { flex: 1 !important; min-width: 0 !important; }
.finding .f-title {
    font-size: 13.5px !important;
    font-weight: 600 !important;
    color: var(--text-primary) !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
    white-space: nowrap !important;
}
.finding .f-meta { font-size: 12px !important; color: var(--text-muted) !important; margin-top: 2px !important; }
.finding .f-amt {
    font-size: 14px !important;
    font-weight: 700 !important;
    font-variant-numeric: tabular-nums !important;
    white-space: nowrap !important;
}

/* ── KPI card extras ────────────────────────────────────────── */
.kpi-hint {
    font-size: 11px !important;
    color: var(--text-muted) !important;
    margin-top: 5px !important;
}
.kpi-card.compact { padding: 14px 16px !important; }
.kpi-card.compact .kpi-value { font-size: 20px !important; }

/* ── Progress stepper ───────────────────────────────────────── */
.stepper { display: flex !important; align-items: center !important; margin: 4px 0 10px 0 !important; }
.stepper .node { display: flex !important; align-items: center !important; gap: 8px !important; flex: none !important; }
.stepper .dot {
    width: 22px !important; height: 22px !important;
    border-radius: 50% !important;
    display: flex !important; align-items: center !important; justify-content: center !important;
    font-size: 11px !important; font-weight: 700 !important;
    background: var(--bg-card) !important;
    border: 1.5px solid var(--border-light) !important;
    color: var(--text-muted) !important;
    flex: none !important;
    transition: all .25s ease !important;
}
.stepper .lbl { font-size: 12.5px !important; color: var(--text-muted) !important; white-space: nowrap !important; }
.stepper .node.done .dot { background: var(--green) !important; border-color: var(--green) !important; color: #06130a !important; }
.stepper .node.done .lbl { color: var(--text-secondary) !important; }
.stepper .node.active .dot {
    background: var(--accent) !important; border-color: var(--accent) !important; color: #04121f !important;
    box-shadow: 0 0 0 4px var(--accent-glow) !important;
}
.stepper .node.active .lbl { color: var(--text-primary) !important; font-weight: 600 !important; }
.stepper .link { flex: 1 !important; height: 2px !important; background: var(--border) !important; margin: 0 10px !important; min-width: 12px !important; }
.stepper .link.done { background: var(--green) !important; }

/* ── Empty state ────────────────────────────────────────────── */
.empty-state {
    padding: 26px !important;
    text-align: center !important;
    color: var(--text-muted) !important;
    font-size: 13.5px !important;
    background: var(--bg-primary) !important;
    border: 1px dashed var(--border-light) !important;
    border-radius: var(--radius-sm) !important;
}

/* ── Page header ────────────────────────────────────────────── */
.page-head { margin-bottom: 4px !important; }
.page-title {
    font-size: 24px !important;
    font-weight: 700 !important;
    letter-spacing: -0.02em !important;
    color: var(--text-primary) !important;
}
.page-sub { font-size: 13.5px !important; color: var(--text-secondary) !important; margin-top: 4px !important; }

/* ── Catch-all for MUI/Popover backgrounds ──────────────────── */
div[data-baseweb="popover"] div, div[data-baseweb="menu"] div {
    background: var(--bg-card) !important;
    border: 1px solid var(--border) !important;
    color: var(--text-primary) !important;
}
div[data-baseweb="popover"] li, div[data-baseweb="menu"] li {
    color: var(--text-primary) !important;
}
div[data-baseweb="popover"] li:hover, div[data-baseweb="menu"] li:hover {
    background: var(--bg-card-hover) !important;
}
</style>
"""


def inject_css(st):
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
