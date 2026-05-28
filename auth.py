"""
EdWise Group — Finance Authentication Module
File: auth.py
Usage: Import in School Finance pages only.
"""

import streamlit as st
import hashlib
import uuid

# ─────────────────────────────────────────────────────────────────
# VENDOR REGISTRY
# ─────────────────────────────────────────────────────────────────
VENDOR_DISPLAY_NAMES = {
    "vendor_joshua_academy": "Joshua Academy(1094950000)",
    "vendor_tyler_tech": "Tyler Tech(1053300000)",
    "vendor_low_associates": "Low Associates(1037850000)",
}

# Module identifier for Finance
_MODULE = "finance"


def _hash_password(pwd: str) -> str:
    return hashlib.sha256(pwd.encode()).hexdigest()


def _load_vendor_credentials(vendor_key: str) -> dict:
    """Load vendor-specific API credentials for School Finance."""
    try:
        block = st.secrets["vendors"][vendor_key]
        return {
            "token_url": block["token_url"],
            "api_key": block["api_key"],
            "api_secret": block["api_secret"],
            "finance_base_edfi": block["finance_base_edfi"],
            "finance_base_idoe": block["finance_base_idoe"],
        }
    except Exception as e:
        st.error(f"❌ Could not load API credentials for vendor '{vendor_key}': {e}")
        return {}


def _validate_login(vendor_key: str, username: str, password: str) -> tuple[bool, str]:
    """Validate username and password against secrets.toml."""
    try:
        block = st.secrets["vendors"][vendor_key]
        stored_u = block.get("username", "")
        stored_ph = block.get("password_hash", "")

        if username.strip() == stored_u and _hash_password(password) == stored_ph:
            return True, ""
        return False, "Incorrect username or password."
    except KeyError:
        return False, f"Vendor configuration not found for '{vendor_key}'."
    except Exception as e:
        return False, f"Login error: {e}"


def render_login_page():
    """Renders the full-screen login UI for Student Verification."""
    module_label = "SF Vendor Certification"
    module_icon = "🎓"

    # ── Page styling ──────────────────────────────
    st.markdown("""
    <style>
    .main { background: #f1f5f9 !important; }
    .block-container { max-width: 480px !important; margin: auto !important; padding-top: 4rem !important; }
    header[data-testid="stHeader"] { display: none !important; }
    section[data-testid="stSidebar"] { display: none !important; }
    </style>
    """, unsafe_allow_html=True)

    # ── Header ─────────────────────────────────────
    st.markdown(
        f"""
        <div style='text-align:center;margin-bottom:28px;'>
          <div style='display:inline-flex;align-items:center;justify-content:center;
                      width:64px;height:64px;background:#dae1f2;border-radius:14px;
                      font-size:32px;margin-bottom:14px;'>
            {module_icon}
          </div>
          <div style='font-size:22px;font-weight:800;color:#0d2d5e;'>EdWise Group</div>
          <div style='font-size:13px;color:#64748b;margin-top:4px;'>
            {module_label} &nbsp;·&nbsp; Ed-Fi ODS 2026 &nbsp;·&nbsp; Indiana DOE
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Login Card ─────────────────────────────────
    with st.container():
        st.markdown(
            "<div style='font-size:16px;font-weight:700;color:#0d2d5e;margin-bottom:18px;'>Sign in to continue</div>",
            unsafe_allow_html=True,
        )

        # Vendor selection
        vendor_options = {v: k for k, v in VENDOR_DISPLAY_NAMES.items()}
        vendor_label = st.selectbox(
            "Select Your Organization",
            options=list(VENDOR_DISPLAY_NAMES.values()),
            index=0,
        )
        vendor_key = vendor_options[vendor_label]

        username = st.text_input("Username", placeholder="Enter your username")
        password = st.text_input("Password", type="password", placeholder="Enter your password")

        col_btn, col_msg = st.columns([1, 2])
        with col_btn:
            login_clicked = st.button("Sign In", type="primary", use_container_width=True)

        if login_clicked:
            if not username or not password:
                st.error("Please enter both username and password.")
            else:
                ok, err = _validate_login(vendor_key, username, password)
                if ok:
                    creds = _load_vendor_credentials(vendor_key)
                    if creds:
                        st.session_state.logged_in = True
                        st.session_state.current_vendor = vendor_key
                        st.session_state.vendor_name = vendor_label
                        st.session_state.vendor_creds = creds
                        # Clear finance-specific token
                        st.session_state.pop("token_info_finance", None)
                        st.rerun()
                    else:
                        st.error("Credentials loaded but API config is missing. Contact admin.")
                else:
                    st.error(f"❌ {err}")

        st.markdown("</div>", unsafe_allow_html=True)

    # Footer
    st.markdown(
        "<div style='text-align:center;margin-top:20px;font-size:11px;color:#94a3b8;'>"
        "EdWise Group &nbsp;·&nbsp; v3.0.0 &nbsp;·&nbsp; Ed-Fi ODS 2026 &nbsp;·&nbsp; Indiana DOE"
        "</div>",
        unsafe_allow_html=True,
    )


def render_logout_button(sidebar=False):
    """
    Renders a logout button in Streamlit (sidebar or main page)
    with a unique key to avoid StreamlitDuplicateElementKey errors.
    """
    vendor_name = st.session_state.get("vendor_name", "Unknown")
    container = st.sidebar if sidebar else st

    container.markdown(
        f"<div style='padding:10px 12px 6px;border-top:1px solid #e2e8f0;margin-top:8px;'>"
        f"<div style='font-size:11px;font-weight:700;color:#64748b;'>Signed in as</div>"
        f"<div style='font-size:12px;font-weight:600;color:#0d2d5e;margin-top:2px;'>{vendor_name}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )

    # Use a unique ID to prevent duplicate key errors
    key_name = f"logout_btn_finance_{'sidebar' if sidebar else 'main'}_{uuid.uuid4().hex[:6]}"

    with (st.sidebar if sidebar else st):
        if st.button("🔓 Sign Out", key="logout_btn_finance", use_container_width=True):
            for key in ["logged_in", "current_vendor", "vendor_name", "vendor_creds", "token_info_finance"]:
                st.session_state.pop(key, None)
            st.rerun()


def is_logged_in() -> bool:
    return st.session_state.get("logged_in", False)


def get_vendor_creds() -> dict:
    return st.session_state.get("vendor_creds", {})


def get_vendor_name() -> str:
    return st.session_state.get("vendor_name", "Demo User")