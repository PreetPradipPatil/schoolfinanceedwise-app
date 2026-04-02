import streamlit as st
import json
import requests
import pandas as pd
from shared import render_top_ribbon, get_bearer_token

PAGE_TITLE = "JSON Body Comparator"

# ── Fixed base URL (never changes) ───────────────────────────────
BASE_URL = "https://doe-edfiods-a-v-v2026-ca.ashytree-64da9ba4.eastus.azurecontainerapps.io:443/2026/data/v3/"

# ════════════════════════════════════════════════════════════════════
# HELPERS
# ════════════════════════════════════════════════════════════════════

def _build_full_url(endpoint_path: str) -> str:
    base = BASE_URL.rstrip("/")
    path = endpoint_path.strip().lstrip("/")
    return f"{base}/{path}" if path else base


def _fetch_original_json(url: str) -> tuple:
    try:
        token = get_bearer_token()
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        resp = requests.get(url, headers=headers, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list):
            if len(data) == 0:
                return None, "API returned an empty list — no records found at this URL."
            return data[0], ""
        return data, ""
    except requests.exceptions.HTTPError as e:
        return None, f"HTTP {e.response.status_code}: {e.response.text[:300]}"
    except Exception as e:
        return None, str(e)


def _flatten(obj, prefix="") -> dict:
    items = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            full_key = f"{prefix}.{k}" if prefix else k
            if isinstance(v, (dict, list)):
                items.update(_flatten(v, full_key))
            else:
                items[full_key] = v
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            full_key = f"{prefix}[{i}]"
            if isinstance(v, (dict, list)):
                items.update(_flatten(v, full_key))
            else:
                items[full_key] = v
    else:
        items[prefix] = obj
    return items


def _get_type_label(val) -> str:
    """Return a human-readable type label for a flattened value."""
    if val is None:
        return "null"
    if isinstance(val, bool):
        return "boolean"
    if isinstance(val, int):
        return "integer"
    if isinstance(val, float):
        return "number"
    if isinstance(val, str):
        return "string"
    return type(val).__name__


def _compare(original, vendor) -> list:
    """
    Structural comparison — Status is determined by field presence and data type only.
    Original Value and Vendor Value are included for reference but do NOT affect the Status.
    """
    orig_flat = _flatten(original)
    vend_flat = _flatten(vendor)
    all_keys = sorted(set(orig_flat) | set(vend_flat))
    rows = []
    for idx, key in enumerate(all_keys, start=1):
        in_orig = key in orig_flat
        in_vend = key in vend_flat

        if not in_vend:
            rows.append({
                "Line #": idx,
                "Field": key,
                "Original Value": str(orig_flat[key]),
                "Vendor Value": "— (missing)",
                "Original Type": _get_type_label(orig_flat[key]),
                "Vendor Type": "— (missing)",
                "Status": "❌ Missing",
                "Reason": "Field is present in the original API response but absent in the vendor body.",
            })
        elif not in_orig:
            rows.append({
                "Line #": idx,
                "Field": key,
                "Original Value": "— (not expected)",
                "Vendor Value": str(vend_flat[key]),
                "Original Type": "— (not expected)",
                "Vendor Type": _get_type_label(vend_flat[key]),
                "Status": "⚠️ Extra",
                "Reason": "Field exists in the vendor body but is not present in the original API response.",
            })
        else:
            o_val = orig_flat[key]
            v_val = vend_flat[key]
            o_type = _get_type_label(o_val)
            v_type = _get_type_label(v_val)
            # Treat int and float as the same "number" family for flexibility
            o_type_norm = "number" if o_type in ("integer", "number") else o_type
            v_type_norm = "number" if v_type in ("integer", "number") else v_type

            if o_type_norm == v_type_norm:
                rows.append({
                    "Line #": idx,
                    "Field": key,
                    "Original Value": str(o_val),
                    "Vendor Value": str(v_val),
                    "Original Type": o_type,
                    "Vendor Type": v_type,
                    "Status": "✅ Match",
                    "Reason": f"Type matches ('{o_type}'). Values shown for reference only — not compared.",
                })
            else:
                rows.append({
                    "Line #": idx,
                    "Field": key,
                    "Original Value": str(o_val),
                    "Vendor Value": str(v_val),
                    "Original Type": o_type,
                    "Vendor Type": v_type,
                    "Status": "⚠️ Type Mismatch",
                    "Reason": f"Type differs — original is '{o_type}' but vendor sent '{v_type}'. Values shown for reference.",
                })
    return rows


def _color_row(row):
    s = row.get("Status", "")
    if s == "✅ Match":
        return ["background-color:#f0fdf4"] * len(row)
    if s == "⚠️ Extra":
        return ["background-color:#fffbeb"] * len(row)
    if s == "⚠️ Type Mismatch":
        return ["background-color:#fff7ed"] * len(row)
    return ["background-color:#fef2f2"] * len(row)


def _json_to_highlighted_html(json_text: str, panel_id: str, report: list = None) -> str:
    """
    Convert JSON text to dark-theme syntax-highlighted HTML with line numbers and copy button.
    Issue lines (from report) get a red left border.
    """
    import re

    # Build set of issue field leaf-names for line highlighting
    issue_fields = set()
    if report:
        for r in report:
            if r["Status"] != "✅ Match":
                leaf = r["Field"].split(".")[-1]
                leaf = re.sub(r'\[.*?\]', '', leaf).strip()
                issue_fields.add(f'"{leaf}"')

    lines = json_text.split("\n")

    def _highlight_line(line: str) -> str:
        result = ""
        last = 0
        pattern = r'("(?:\\.|[^"\\])*")(\s*:\s*)?|(\btrue\b|\bfalse\b|\bnull\b)|(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)|([{}\[\]])|([,])'
        for m in re.finditer(pattern, line):
            result += line[last:m.start()].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            tok = m.group(0)
            safe = tok.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            colon = m.group(2) or ""
            safe_colon = colon.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            if m.group(1) and m.group(2):
                key_safe = m.group(1).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                result += f'<span style="color:#93c5fd;">{key_safe}</span><span style="color:#94a3b8;">{safe_colon}</span>'
            elif m.group(1):
                result += f'<span style="color:#4ade80;">{safe}</span>'
            elif m.group(3):
                result += f'<span style="color:#fb923c;">{safe}</span>'
            elif m.group(4):
                result += f'<span style="color:#60a5fa;">{safe}</span>'
            elif m.group(5):
                result += f'<span style="color:#94a3b8;">{safe}</span>'
            elif m.group(6):
                result += f'<span style="color:#64748b;">{safe}</span>'
            else:
                result += safe
            last = m.end()
        result += line[last:].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return result

    rows_html = ""
    for i, raw_line in enumerate(lines, start=1):
        has_issue = any(f in raw_line for f in issue_fields) if issue_fields else False
        bg = "#2d1515" if has_issue else "#0f172a"
        border = "border-left:3px solid #dc2626;" if has_issue else "border-left:3px solid transparent;"
        highlighted = _highlight_line(raw_line)
        rows_html += (
            f"<div style='display:flex;align-items:flex-start;{border}background:{bg};min-height:22px;'>"
            f"<span style='min-width:42px;text-align:right;padding:1px 10px 1px 4px;"
            f"color:#475569;font-size:11px;user-select:none;flex-shrink:0;line-height:1.6;"
            f"font-family:JetBrains Mono,monospace;'>{i}</span>"
            f"<span style='white-space:pre;line-height:1.6;font-size:12px;color:#e2e8f0;"
            f"font-family:JetBrains Mono,monospace;'>{highlighted}</span>"
            f"</div>"
        )

    escaped_for_js = json_text.replace("\\", "\\\\").replace("`", "\\`").replace("$", "\\$")
    copy_js = (
        f"(function(){{var t=`{escaped_for_js}`;"
        f"navigator.clipboard.writeText(t).then(function(){{"
        f"var b=document.getElementById('cb_{panel_id}');"
        f"b.innerText='✅ Copied!';setTimeout(function(){{b.innerText='📋 Copy';}},1500);}});}})();"
    )

    html = (
        f"<div style='border:1px solid #1e293b;border-radius:10px;overflow:hidden;background:#0f172a;'>"
        f"<div style='display:flex;align-items:center;justify-content:space-between;"
        f"padding:8px 14px;background:#1e293b;border-bottom:1px solid #334155;'>"
        f"<span style='font-size:11px;color:#94a3b8;font-family:JetBrains Mono,monospace;'>JSON</span>"
        f"<button id='cb_{panel_id}' onclick=\"{copy_js}\" "
        f"style='background:#1a6fd4;color:#fff;border:none;border-radius:6px;"
        f"padding:4px 14px;font-size:11px;font-weight:600;cursor:pointer;'>📋 Copy</button>"
        f"</div>"
        f"<div style='overflow-y:auto;height:480px;padding:4px 0;'>"
        f"{rows_html}"
        f"</div>"
        f"</div>"
    )
    return html


# ── NEW: render vendor JSON textarea overlaid with line numbers ───
def _vendor_textarea_with_lines(value: str, key: str) -> str:
    display_text = value
    try:
        parsed = json.loads(value)
        if isinstance(parsed, list) and parsed:
            parsed = parsed[0]
        display_text = json.dumps(parsed, indent=2)
    except Exception:
        display_text = value

    return _json_to_highlighted_html(display_text, "vendor_preview", report=None)


# ════════════════════════════════════════════════════════════════════
# MAIN RENDER
# ════════════════════════════════════════════════════════════════════

def render_json_comparator():
    render_top_ribbon(
        page_title=PAGE_TITLE,
        page_subtitle="Vendor JSON Body Validator · Ed-Fi ODS 2026"
    )

    # ── Session state ─────────────────────────────────────────────
    if "jc_endpoint" not in st.session_state:
        st.session_state.jc_endpoint = ""
    if "jc_original" not in st.session_state:
        st.session_state.jc_original = None
    if "jc_vendor_text" not in st.session_state:
        st.session_state.jc_vendor_text = ""
    if "jc_report" not in st.session_state:
        st.session_state.jc_report = None
    if "jc_fetch_error" not in st.session_state:
        st.session_state.jc_fetch_error = ""

    # ════════════════════════════════════════════════════════════════
    # STEP 1 — Fixed base URL + editable endpoint path
    # ════════════════════════════════════════════════════════════════
    st.markdown(
        "<div style='margin-bottom:8px;'>"
        "<span style='font-size:11px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;"
        "color:#1a6fd4;'>Step 1</span>"
        "<div style='font-size:17px;font-weight:800;color:#0d2d5e;margin-top:1px;'>Enter API Endpoint</div>"
        "<div style='width:32px;height:3px;background:#1a6fd4;border-radius:2px;margin-top:4px;'></div>"
        "<div style='font-size:12px;color:#64748b;margin-top:6px;'>"
        "Base URL is fixed. Enter only the endpoint name and query parameters (e.g. "
        "<code>ed-fi/localActuals</code>)."
        "</div>"
        "</div>",
        unsafe_allow_html=True,
    )

    # Read-only base URL badge
    st.markdown(
        f"<div style='background:#f1f5f9;border:1.5px solid #cbd5e1;border-radius:8px;"
        f"padding:9px 14px;margin-bottom:8px;font-family:JetBrains Mono,monospace;font-size:12px;color:#475569;'>"
        f"<span style='color:#94a3b8;font-size:10px;font-weight:700;text-transform:uppercase;"
        f"letter-spacing:1px;display:block;margin-bottom:3px;'>🔒 Fixed Base URL</span>"
        f"{BASE_URL}"
        f"</div>",
        unsafe_allow_html=True,
    )

    ep_col, btn_col = st.columns([5, 1])
    with ep_col:
        endpoint_input = st.text_input(
            "Endpoint path",
            value=st.session_state.jc_endpoint,
            placeholder="ed-fi/localActuals",
            label_visibility="collapsed",
            key="jc_endpoint_input",
        )
    with btn_col:
        st.markdown("<div style='padding-top:4px;'>", unsafe_allow_html=True)
        fetch_clicked = st.button("🔍 Fetch", key="jc_fetch", type="primary")
        st.markdown("</div>", unsafe_allow_html=True)

    full_url = _build_full_url(endpoint_input)
    st.markdown(
        f"<div style='font-size:11px;color:#64748b;margin-top:3px;margin-bottom:4px;'>"
        f"<b>Full URL:</b>&nbsp;"
        f"<span style='font-family:JetBrains Mono,monospace;color:#1a6fd4;word-break:break-all;'>{full_url}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )

    if fetch_clicked and endpoint_input.strip():
        st.session_state.jc_endpoint = endpoint_input.strip()
        with st.spinner("Fetching original JSON from API…"):
            data, err = _fetch_original_json(full_url)
        if err:
            st.session_state.jc_fetch_error = err
            st.session_state.jc_original = None
        else:
            st.session_state.jc_original = data
            st.session_state.jc_fetch_error = ""
            st.session_state.jc_report = None

    if st.session_state.jc_fetch_error:
        st.error(f"❌ Fetch failed: {st.session_state.jc_fetch_error}")

    st.markdown("<hr style='margin:18px 0 14px;'>", unsafe_allow_html=True)

    # ════════════════════════════════════════════════════════════════
    # STEP 2 — Two-panel JSON display
    # ════════════════════════════════════════════════════════════════
    st.markdown(
        "<div style='margin-bottom:8px;background-color:white;padding:14px 16px;border-radius:10px;border:1px solid #e2e8f0;'>"
        "<span style='font-size:11px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;"
        "color:#1a6fd4;'>Step 2</span>"
        "<div style='font-size:17px;font-weight:800;color:#0d2d5e;margin-top:1px;'>Review & Compare JSON Structure</div>"
        "<div style='width:32px;height:3px;background:#1a6fd4;border-radius:2px;margin-top:4px;'></div>"
        "<div style='font-size:12px;color:#64748b;margin-top:6px;'>"
        "Left: Original API response (fetched). &nbsp;Right: Paste the vendor's JSON body, then click Match & Compare. "
        "Comparison checks <b>field presence</b> and <b>data types only</b> — exact values are ignored. "
        "Issue lines are highlighted with a 🔴 red border in both panels."
        "</div>"
        "</div>",
        unsafe_allow_html=True,
    )

    current_report = st.session_state.jc_report
    left_col, right_col = st.columns(2, gap="medium")

    # ── Left: Original ────────────────────────────────────────────
    with left_col:
        st.markdown(
            "<div style='font-size:12px;font-weight:700;color:#0d2d5e;margin-bottom:6px;'>"
            "📄 Original API Response "
            "<span style='font-size:10px;font-weight:500;color:#64748b;'>(fetched from URL above)</span>"
            "</div>",
            unsafe_allow_html=True,
        )
        if st.session_state.jc_original is not None:
            orig_text = json.dumps(st.session_state.jc_original, indent=2)
            st.markdown(
                _json_to_highlighted_html(orig_text, "orig", current_report),
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                "<div style='border:1px solid #1e293b;border-radius:10px;background:#0f172a;"
                "height:480px;display:flex;align-items:center;justify-content:center;'>"
                "<span style='color:#475569;font-size:13px;font-family:JetBrains Mono,monospace;'>"
                "// Fetch a URL above to load the original JSON here."
                "</span></div>",
                unsafe_allow_html=True,
            )

    # ── Right: Vendor ─────────────────────────────────────────────
    with right_col:
        st.markdown(
            "<div style='font-size:12px;font-weight:700;color:#0d2d5e;margin-bottom:6px;'>"
            "📋 Vendor JSON Body "
            "<span style='font-size:10px;font-weight:500;color:#64748b;'>"
            "(line numbers shown live — edit in the text box below)</span>"
            "</div>",
            unsafe_allow_html=True,
        )

        vendor_raw = st.session_state.jc_vendor_text

        if vendor_raw.strip():
            panel_report = current_report
            st.markdown(
                _json_to_highlighted_html(vendor_raw, "vendor", panel_report),
                unsafe_allow_html=True,
            )
            st.markdown(
                "<div style='font-size:11px;color:#64748b;margin-top:6px;margin-bottom:2px;'>"
                "✏️ Edit vendor JSON below (panel above updates after re-clicking Match & Compare):"
                "</div>",
                unsafe_allow_html=True,
            )
            vendor_text = st.text_area(
                "Vendor JSON",
                value=vendor_raw,
                height=160,
                label_visibility="collapsed",
                key="jc_vendor_area",
            )
        else:
            st.markdown(
                "<div style='border:1px solid #1e293b;border-radius:10px;background:#0f172a;"
                "height:300px;display:flex;align-items:center;justify-content:center;margin-bottom:8px;'>"
                "<span style='color:#475569;font-size:13px;font-family:JetBrains Mono,monospace;'>"
                "// Paste vendor JSON below — line numbers will appear here."
                "</span></div>",
                unsafe_allow_html=True,
            )
            vendor_text = st.text_area(
                "Vendor JSON",
                value=vendor_raw,
                height=180,
                placeholder='{\n  "accountIdentifier": "...",\n  "amount": 0,\n  ...\n}',
                label_visibility="collapsed",
                key="jc_vendor_area",
            )

        st.session_state.jc_vendor_text = vendor_text

    # ── Match button (centered) ───────────────────────────────────
    st.markdown("<div style='height:10px;'></div>", unsafe_allow_html=True)
    _, mid, _ = st.columns([3, 2, 3])
    with mid:
        match_clicked = st.button("⚡ Match & Compare", key="jc_match", type="primary", width="stretch")

    if match_clicked:
        if st.session_state.jc_original is None:
            st.warning("⚠️ Please fetch an original JSON body first (Step 1).")
        elif not st.session_state.jc_vendor_text.strip():
            st.warning("⚠️ Please paste the vendor's JSON body in the right panel.")
        else:
            try:
                vendor_obj = json.loads(st.session_state.jc_vendor_text)
                if isinstance(vendor_obj, list):
                    if len(vendor_obj) == 0:
                        st.error("❌ Vendor JSON is an empty list — nothing to compare.")
                        st.stop()
                    vendor_obj = vendor_obj[0]
                st.session_state.jc_report = _compare(st.session_state.jc_original, vendor_obj)
                st.rerun()
            except json.JSONDecodeError as e:
                st.error(f"❌ Invalid JSON in vendor body: {e}")
                st.session_state.jc_report = None

    st.markdown("<hr style='margin:18px 0 14px;'>", unsafe_allow_html=True)

    # ════════════════════════════════════════════════════════════════
    # STEP 3 — Structural Comparison Report
    # ════════════════════════════════════════════════════════════════
    if st.session_state.jc_report is not None:
        report = st.session_state.jc_report
        total        = len(report)
        matched      = sum(1 for r in report if r["Status"] == "✅ Match")
        missing      = sum(1 for r in report if r["Status"] == "❌ Missing")
        type_mismatch = sum(1 for r in report if r["Status"] == "⚠️ Type Mismatch")
        extra        = sum(1 for r in report if r["Status"] == "⚠️ Extra")

        st.markdown(
            "<div style='margin-bottom:8px;'>"
            "<span style='font-size:11px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;"
            "color:#1a6fd4;'>Step 3</span>"
            "<div style='font-size:17px;font-weight:800;color:#0d2d5e;margin-top:1px;'>Structural Comparison Report</div>"
            "<div style='width:32px;height:3px;background:#1a6fd4;border-radius:2px;margin-top:4px;'></div>"
            "<div style='font-size:12px;color:#64748b;margin-top:6px;'>"
            "Exact values are <b>not compared</b> — only field presence and data types are validated. "
            "The <b>Line #</b> column maps to the numbered lines in the JSON panels above — "
            "look for the 🔴 red-highlighted lines to quickly spot structural errors."
            "</div>"
            "</div>",
            unsafe_allow_html=True,
        )

        c1, c2, c3, c4, c5 = st.columns(5)
        for col_obj, label, val, color in [
            (c1, "Total Fields",     total,         "#1a6fd4"),
            (c2, "✅ Matched",       matched,       "#16a34a"),
            (c3, "❌ Missing",       missing,       "#dc2626"),
            (c4, "⚠️ Type Mismatch", type_mismatch, "#d97706"),
            (c5, "⚠️ Extra",         extra,         "#d97706"),
        ]:
            with col_obj:
                st.markdown(
                    f"<div style='background:#f8fafc;border:1px solid #e2e8f0;border-top:3px solid {color};"
                    f"border-radius:10px;padding:14px;text-align:center;'>"
                    f"<div style='font-size:11px;font-weight:700;color:#64748b;margin-bottom:6px;"
                    f"text-transform:uppercase;letter-spacing:.5px;'>{label}</div>"
                    f"<div style='font-size:26px;font-weight:800;color:{color};'>{val}</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

        st.markdown("<div style='height:14px;'></div>", unsafe_allow_html=True)

        df = pd.DataFrame(report)

        issues_count = missing + type_mismatch + extra
        tab_all, tab_issues, tab_match = st.tabs([
            f"All Fields ({total})",
            f"Issues Only ({issues_count})",
            f"Matched Only ({matched})",
        ])

        with tab_all:
            st.dataframe(
                df.style.apply(_color_row, axis=1),
                width='stretch',
                hide_index=True,
            )

        with tab_issues:
            issues_df = df[df["Status"].isin(["❌ Missing", "⚠️ Type Mismatch", "⚠️ Extra"])]
            if issues_df.empty:
                st.success("🎉 No structural issues found — all fields and types match!")
            else:
                st.dataframe(
                    issues_df.style.apply(_color_row, axis=1),
                    width='stretch',
                    hide_index=True,
                )

        with tab_match:
            match_df = df[df["Status"] == "✅ Match"]
            st.dataframe(
                match_df.style.apply(_color_row, axis=1),
                width='stretch',
                hide_index=True,
            )

        csv_bytes = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="⬇️ Download Report as CSV",
            data=csv_bytes,
            file_name="json_comparator_report.csv",
            mime="text/csv",
        )