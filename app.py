import streamlit as st
from auth import render_login_page, render_logout_button, is_logged_in

# ── Import shared module and page renderers ───────────────────────
import shared
from pages.page_cap_equipment import render_cap_equipment
from pages.page_subawards import render_subawards
from pages.page_unused_leave import render_unused_leave
from pages.page_reset import render_reset
from pages.page_delete import render_delete
from pages.page_update import render_update
from pages.page_json_comparator import render_json_comparator


st.set_page_config(
    page_title="EdWise | School Finance Certification",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)


st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');

:root { 
    --bg-primary:#f8fafc; 
    --bg-secondary:#ffffff; 
    --text-primary:#1e293b; 
    --border-color:#e2e8f0; 
}

html, body, [class*="css"] { 
    font-family: 'Plus Jakarta Sans', sans-serif !important; 
}

.main { 
    background: var(--bg-primary) !important; 
    color: var(--text-primary) !important; 
}

.block-container { 
    padding-top:1rem !important; 
    padding-left:1.8rem !important; 
    padding-right:1.8rem !important; 
    padding-bottom:3rem !important; 
    max-width:100% !important; 
}

header[data-testid="stHeader"] { 
    display:none !important; 
}

/* ✅ REMOVE SIDEBAR TOGGLE + keyboard_double_arrow_left ICON */
button[kind="header"] { 
    display: none !important; 
}

button[kind="header"] svg {
    display: none !important;
}

[data-testid="collapsedControl"],
[data-testid="stSidebarCollapsedControl"],
[data-testid="stSidebarCollapseButton"] {
    display: none !important;
}

[data-testid="collapsedControl"] svg,
[data-testid="stSidebarCollapsedControl"] svg,
[data-testid="stSidebarCollapseButton"] svg {
    display: none !important;
}

/* Extra fallback (new versions) */
button[aria-label="Toggle sidebar"] {
    display: none !important;
}

/* Buttons */
[data-testid="stBaseButton-primary"] {
    background:#1a6fd4 !important; 
    color:#ffffff !important; 
    border:none !important;
    border-radius:8px !important; 
    font-weight:600 !important; 
    font-size:14px !important;
    white-space:nowrap !important; 
    padding:10px 20px !important;
    box-shadow:0 2px 8px rgba(26,111,212,0.28) !important; 
    justify-content:center !important;
}

[data-testid="stBaseButton-primary"]:hover { 
    background:#1558b0 !important; 
    transform:translateY(-1px) !important; 
}

/* Download button */
.stDownloadButton > button {
    background:#ffffff !important; 
    color:#1a6fd4 !important;
    border:1.5px solid #1a6fd4 !important; 
    border-radius:8px !important;
    font-weight:600 !important; 
    white-space:nowrap !important;
}

/* Inputs */
.stTextInput input {
    background:#ffffff !important; 
    border:1.5px solid #e2e8f0 !important;
    border-radius:8px !important; 
    color:#1e293b !important;
    font-family:'JetBrains Mono', monospace !important; 
    font-size:13px !important; 
    padding:10px 14px !important;
}

.stTextInput input:focus { 
    border-color:#1a6fd4 !important; 
    box-shadow:0 0 0 3px rgba(26,111,212,0.1) !important; 
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] { 
    background:#f1f5f9 !important; 
    border-radius:8px !important; 
    padding:3px !important; 
    gap:2px !important; 
}

.stTabs [data-baseweb="tab"] { 
    border-radius:6px !important; 
    font-size:13px !important; 
    font-weight:500 !important; 
    color:#64748b !important; 
    padding:7px 14px !important; 
}

.stTabs [aria-selected="true"] { 
    background:#ffffff !important; 
    color:#1a6fd4 !important; 
    font-weight:700 !important; 
    box-shadow:0 1px 3px rgba(0,0,0,0.08) !important; 
}

/* DataFrame */
[data-testid="stDataFrame"] { 
    border:1px solid #e2e8f0 !important; 
    border-radius:8px !important; 
}

/* Expander */
.streamlit-expanderHeader { 
    background:#f8fafc !important; 
    border:1px solid #e2e8f0 !important; 
    border-radius:8px !important; 
    font-size:13px !important; 
    font-weight:600 !important; 
}

/* Divider */
hr { 
    border-color:#e2e8f0 !important; 
    margin:14px 0 !important; 
}

/* Hide sidebar nav */
[data-testid="stSidebarNav"] { 
    display:none !important; 
}

</style>
""", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════
# GATE: SHOW LOGIN IF NOT AUTHENTICATED
# ════════════════════════════════════════════════════════════════════
if not is_logged_in():
    render_login_page()
    st.stop()

# ── Load vendor-specific API credentials from session ────────────
shared.init_credentials()

# ── Initialize session state ─────────────────────────────────────
shared.init_session_state()

# ════════════════════════════════════════════════════════════════════
# SIDEBAR — Navigation
# ════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown(
        "<div style='padding:14px 12px 10px;border-bottom:1px solid #e2e8f0;margin-bottom:4px;'>"
        "<div style='font-size:15px;font-weight:800;color:#0d2d5e;'>🎓&nbsp; EdWise Group</div>"
        "<div style='font-size:10px;font-weight:600;color:#94a3b8;letter-spacing:1.5px;text-transform:uppercase;margin-top:2px;'>School Finance Portal</div>"
        "</div>", unsafe_allow_html=True)

    # ── Section label: Verification ───────────────────────────────
    st.markdown(
        "<div style='padding:10px 12px 3px;margin-top:6px;font-size:10px;font-weight:700;"
        "color:#94a3b8;letter-spacing:2px;text-transform:uppercase;'>Data Verification</div>",
        unsafe_allow_html=True,
    )

    # ── Local Capitalized Equipment ───────────────────────────────
    is_cap_eq = st.session_state.get("fin_active_tab") == "cap_equipment"
    if is_cap_eq:
        st.markdown("<div style='background:#eff6ff;border-left:3px solid #1a6fd4;margin:0;padding:0;'>", unsafe_allow_html=True)
    if st.button("🖥️  Local Capitalized Equipment", key="nav_cap_equipment", width="stretch"):
        st.session_state.fin_active_tab = "cap_equipment"
        st.rerun()
    if is_cap_eq:
        st.markdown("</div>", unsafe_allow_html=True)

    # ── Local Subawards ───────────────────────────────────────────
    is_sub = st.session_state.get("fin_active_tab") == "subawards"
    if is_sub:
        st.markdown("<div style='background:#eff6ff;border-left:3px solid #1a6fd4;margin:0;padding:0;'>", unsafe_allow_html=True)
    if st.button("🤝  Local Subawards", key="nav_subawards", width="stretch"):
        st.session_state.fin_active_tab = "subawards"
        st.rerun()
    if is_sub:
        st.markdown("</div>", unsafe_allow_html=True)

    # ── Local Unused Leave Payment ────────────────────────────────
    is_ul = st.session_state.get("fin_active_tab") == "unused_leave"
    if is_ul:
        st.markdown("<div style='background:#eff6ff;border-left:3px solid #1a6fd4;margin:0;padding:0;'>", unsafe_allow_html=True)
    if st.button("🏖️  Local Unused Leave Payment", key="nav_unused_leave", width="stretch"):
        st.session_state.fin_active_tab = "unused_leave"
        st.rerun()
    if is_ul:
        st.markdown("</div>", unsafe_allow_html=True)


    # ── Section label: Data Management ───────────────────────────
    st.markdown(
        "<div style='padding:10px 12px 3px;margin-top:10px;font-size:10px;font-weight:700;"
        "color:#94a3b8;letter-spacing:2px;text-transform:uppercase;'>Data Management</div>",
        unsafe_allow_html=True,
    )

    is_update = st.session_state.get("fin_active_tab") == "update_verify"
    if is_update:
        st.markdown("<div style='background:#eff6ff;border-left:3px solid #1a6fd4;margin:0;padding:0;'>", unsafe_allow_html=True)
    if st.button("✏️  Financial Data Update", key="nav_update", width="stretch"):
        st.session_state.fin_active_tab = "update_verify"
        st.rerun()
    if is_update:
        st.markdown("</div>", unsafe_allow_html=True)

    is_delete = st.session_state.get("fin_active_tab") == "delete_verify"
    if is_delete:
        st.markdown("<div style='background:#eff6ff;border-left:3px solid #1a6fd4;margin:0;padding:0;'>", unsafe_allow_html=True)
    if st.button("🗑️  Financial Data Delete", key="nav_delete", width="stretch"):
        st.session_state.fin_active_tab = "delete_verify"
        st.rerun()
    if is_delete:
        st.markdown("</div>", unsafe_allow_html=True)

    is_reset = st.session_state.get("fin_active_tab") == "reset"
    if is_reset:
        st.markdown("<div style='background:#eff6ff;border-left:3px solid #1a6fd4;margin:0;padding:0;'>", unsafe_allow_html=True)
    if st.button("🔄  Financial Data Reset", key="nav_reset", width="stretch"):
        st.session_state.fin_active_tab = "reset"
        st.rerun()
    if is_reset:
        st.markdown("</div>", unsafe_allow_html=True)
        
    # ── JSON Body Comparator ──────────────────────────────────────
    is_jc = st.session_state.get("fin_active_tab") == "json_comparator"
    if is_jc:
        st.markdown("<div style='background:#eff6ff;border-left:3px solid #1a6fd4;margin:0;padding:0;'>", unsafe_allow_html=True)
    if st.button("🔀  JSON Body Comparator", key="nav_json_comparator", width="stretch"):
        st.session_state.fin_active_tab = "json_comparator"
        st.rerun()
    if is_jc:
        st.markdown("</div>", unsafe_allow_html=True)

    # ── Single logout button — only here in sidebar nav ──────────────
    render_logout_button(sidebar=True)
    st.markdown(
        f"<div style='padding:4px 12px 8px;font-size:11px;color:#94a3b8;'>"
        f"v3.0.0 · Ed-Fi ODS 2026 · Indiana DOE</div>",
        unsafe_allow_html=True,
    )


# ════════════════════════════════════════════════════════════════════
# PAGE ROUTING
# ════════════════════════════════════════════════════════════════════
active_tab = st.session_state.get("fin_active_tab", "cap_equipment")

if active_tab == "reset":
    render_reset()
    st.stop()

if active_tab == "delete_verify":
    render_delete()
    st.stop()

if active_tab == "update_verify":
    render_update()
    st.stop()

if active_tab == "subawards":
    render_subawards()
    st.stop()

if active_tab == "unused_leave":
    render_unused_leave()
    st.stop()

if active_tab == "json_comparator":
    render_json_comparator()
    st.stop()

# Default: cap equipment page
render_cap_equipment()