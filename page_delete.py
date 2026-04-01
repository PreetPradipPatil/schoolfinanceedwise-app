import streamlit as st
import pandas as pd
import requests
import io
from datetime import datetime

from shared import (
    render_top_ribbon, get_bearer_token,
    FINANCE_BASE_EDFI, FINANCE_BASE_IDOE,
)


def render_delete():

    render_top_ribbon(
        page_title="Financial Data Delete Verification",
        page_subtitle="Zero-Record & Blank Body Check · Ed-Fi ODS 2026 · Indiana DOE"
    )

    st.markdown(
        "<div style='margin-bottom:10px;'>"
        "<span style='font-size:11px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;color:#1a6fd4;'>Financial Data Delete</span>"
        "<div style='font-size:17px;font-weight:800;color:#0d2d5e;margin-top:1px;'>Verify Deleted Records Return Zero Count</div>"
        "<div style='width:32px;height:3px;background:#1a6fd4;border-radius:2px;margin-top:4px;'></div>"
        "<div style='font-size:12px;color:#64748b;margin-top:6px;font-weight:400;'>"
        "Provide the Record ID (path param) for each resource. GET request will be fired; "
        "pass = zero records returned &amp; blank/empty response body."
        "</div>"
        "</div>",
        unsafe_allow_html=True
    )

    # ── DELETE ENDPOINT BASE URLS (path param style) ──────────────────
    DELETE_PATH_ENDPOINTS = {
        "LocalAccount":              "https://doe-edfiods-a-v-v2026-ca.ashytree-64da9ba4.eastus.azurecontainerapps.io:443/2026/data/v3/ed-fi/LocalAccounts",
        "LocalActual":                "https://doe-edfiods-a-v-v2026-ca.ashytree-64da9ba4.eastus.azurecontainerapps.io:443/2026/data/v3/ed-fi/localActuals",
        "LocalCapitalizedEquipment": "https://doe-edfiods-a-v-v2026-ca.ashytree-64da9ba4.eastus.azurecontainerapps.io:443/2026/data/v3/idoe/LocalCapitalizedEquipment",
        "LocalSubaward":              "https://doe-edfiods-a-v-v2026-ca.ashytree-64da9ba4.eastus.azurecontainerapps.io:443/2026/data/v3/idoe/LocalSubawards",
        "LocalUnusedLeavePayment":    "https://doe-edfiods-a-v-v2026-ca.ashytree-64da9ba4.eastus.azurecontainerapps.io:443/2026/data/v3/idoe/LocalUnusedLeavePayments",
    }

    DELETE_RESOURCE_LABELS = {
        "LocalAccount":              "📋 LocalAccount",
        "LocalActual":                "📊 LocalActual",
        "LocalCapitalizedEquipment": "🖥️ LocalCapitalizedEquipment",
        "LocalSubaward":              "🤝 LocalSubaward",
        "LocalUnusedLeavePayment":    "🏖️ LocalUnusedLeavePayment",
    }

    DELETE_ID_LABELS = {
        "LocalAccount":              "Record ID for LocalAccount",
        "LocalActual":                "Record ID for LocalActual",
        "LocalCapitalizedEquipment": "Record ID for LocalCapitalizedEquipment",
        "LocalSubaward":              "Record ID for LocalSubaward",
        "LocalUnusedLeavePayment":    "Record ID for LocalUnusedLeavePayment",
    }

    DELETE_ID_DEFAULTS = {
        "LocalAccount":              "2ac566c4a09a4d9b81d02c4145d8b1d5",
        "LocalActual":                "752bc21ec874465b89b745cde4e01f8c",
        "LocalCapitalizedEquipment": "9fc553903e0d4af299ac1d689a90462d",
        "LocalSubaward":              "c9b379218ebc4706814a78854393970e",
        "LocalUnusedLeavePayment":    "2241cf98a1424dc9b81b311d1a061c58",
    }

    # ── Path Param Inputs ─────────────────────────────────────────────
    st.markdown(
        "<div style='font-size:13px;font-weight:700;color:#0d2d5e;margin-bottom:8px;'>"
        "Enter Record IDs (Path Parameters)</div>",
        unsafe_allow_html=True
    )

    del_ids = {}
    col_pairs = [
        ["LocalAccount", "LocalActual"],
        ["LocalCapitalizedEquipment", "LocalSubaward"],
        ["LocalUnusedLeavePayment"],
    ]
    for pair in col_pairs:
        cols = st.columns(len(pair))
        for ui_col, res in zip(cols, pair):
            with ui_col:
                del_ids[res] = st.text_input(
                    DELETE_ID_LABELS[res],
                    value=DELETE_ID_DEFAULTS[res],
                    key=f"del_id_{res}",
                    placeholder="e.g. 2ac566c4a09a4d9b81d02c4145d8b1d5"
                )

    # ── Resolved URLs Preview ─────────────────────────────────────────
    st.markdown("<div style='margin-top:10px;'></div>", unsafe_allow_html=True)
    with st.expander("🔗 Resolved DELETE Verification URLs (path params)", expanded=True):
        for res in DELETE_PATH_ENDPOINTS:
            rid = del_ids.get(res, "").strip()
            base = DELETE_PATH_ENDPOINTS[res]
            resolved = f"{base}/{rid}" if rid else f"{base}/<record-id>"
            st.markdown(
                f"<div style='background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px;"
                f"padding:8px 12px;margin-bottom:6px;'>"
                f"<span style='font-size:11px;font-weight:700;color:#1a6fd4;'>"
                f"{DELETE_RESOURCE_LABELS[res]}</span><br>"
                f"<code style='font-size:11px;color:#475569;word-break:break-all;'>{resolved}</code>"
                f"</div>",
                unsafe_allow_html=True
            )

    st.divider()

    run_delete_check = st.button("▶  Run Delete Verification", type="primary", key="run_delete_verify")

    if run_delete_check:
        any_id_missing = any(not del_ids.get(res, "").strip() for res in DELETE_PATH_ENDPOINTS)
        if any_id_missing:
            st.warning("⚠️ One or more Record IDs are empty. Those resources will be skipped.")

        delete_results = []
        with st.spinner("Verifying deleted records for all 5 resources…"):
            for res in DELETE_PATH_ENDPOINTS:
                rid = del_ids.get(res, "").strip()
                label = DELETE_RESOURCE_LABELS[res]
                base  = DELETE_PATH_ENDPOINTS[res]

                if not rid:
                    delete_results.append({
                        "Resource":     label,
                        "URL":          f"{base}/<not provided>",
                        "HTTP Status":  "—",
                        "Record Count": "—",
                        "Body":          "—",
                        "Status":        "⏭ Skipped",
                        "Reason":        f"⏭ Record ID not provided for {res} — skipped",
                    })
                    continue

                resolved_url = f"{base}/{rid}"
                try:
                    token = get_bearer_token()
                    r = requests.get(
                        resolved_url,
                        headers={"Authorization": f"Bearer {token}"},
                        timeout=15
                    )
                    http_status = r.status_code
                    raw_text    = r.text.strip() if r.text else ""

                    try:
                        resp_json = r.json()
                        is_list   = isinstance(resp_json, list)
                        count      = len(resp_json) if is_list else (1 if resp_json else 0)
                        is_blank  = (count == 0) or (not raw_text) or (raw_text in ("[]", "{}", "null", ""))
                    except Exception:
                        resp_json = None
                        count      = 0 if (not raw_text or raw_text in ("", "null")) else -1
                        is_blank  = count == 0

                    # PASS: 404 (record truly deleted) OR 200 with 0 records / blank body
                    if http_status == 404:
                        status = "✅ Pass"
                        reason = (
                            f"✓ HTTP 404 — Record '{rid}' does not exist in {res}. "
                            "Delete verified: record has been successfully removed from the ODS."
                        )
                    elif http_status == 200 and is_blank:
                        status = "✅ Pass"
                        reason = (
                            f"✓ HTTP 200 with zero records / blank response body — "
                            f"Delete verified for {res} (Record ID: {rid})."
                        )
                    elif http_status == 200 and not is_blank:
                        status = "❌ Fail"
                        reason = (
                            f"✗ HTTP 200 and record STILL EXISTS in {res} "
                            f"(Record ID: {rid}). Record count = {count}. "
                            "Vendor must delete this record before certification can proceed."
                        )
                    elif http_status == 410:
                        status = "✅ Pass"
                        reason = (
                            f"✓ HTTP 410 Gone — Record '{rid}' has been permanently deleted from {res}."
                        )
                    else:
                        status = "❌ Fail"
                        reason = (
                            f"✗ Unexpected HTTP {http_status} for {res} "
                            f"(Record ID: {rid}). Verify the Record ID and endpoint."
                        )

                    delete_results.append({
                        "Resource":     label,
                        "URL":          resolved_url,
                        "HTTP Status":  http_status,
                        "Record Count": count if count >= 0 else "N/A",
                        "Body":          "Blank/Empty" if is_blank else raw_text[:120],
                        "Status":        status,
                        "Reason":        reason,
                    })

                    with st.expander(f"🔍 API Debug — {label}", expanded=False):
                        st.markdown(f"**URL:** `{resolved_url}`")
                        st.caption(f"HTTP Status: {http_status}")
                        if resp_json is not None:
                            try:
                                st.json(resp_json)
                            except Exception:
                                st.write(raw_text)
                        else:
                            st.write(raw_text if raw_text else "(empty body)")

                except requests.exceptions.ConnectionError:
                    delete_results.append({
                        "Resource":     label,
                        "URL":          resolved_url,
                        "HTTP Status":  0,
                        "Record Count": "N/A",
                        "Body":          "—",
                        "Status":        "❌ Fail",
                        "Reason":        f"✗ Connection error — {res} API unreachable",
                    })
                except Exception as ex:
                    delete_results.append({
                        "Resource":     label,
                        "URL":          resolved_url,
                        "HTTP Status":  0,
                        "Record Count": "N/A",
                        "Body":          "—",
                        "Status":        "❌ Fail",
                        "Reason":        f"✗ Error: {str(ex)}",
                    })

        # ── Results Display ───────────────────────────────────────────
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(
            "<div style='margin-bottom:10px;'>"
            "<span style='font-size:11px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;color:#1a6fd4;'>"
            "Delete Verification Results</span>"
            "<div style='font-size:17px;font-weight:800;color:#0d2d5e;margin-top:1px;'>"
            "Zero-Record &amp; Blank Body Check</div>"
            "<div style='width:32px;height:3px;background:#1a6fd4;border-radius:2px;margin-top:4px;'></div>"
            "</div>",
            unsafe_allow_html=True
        )

        del_df    = pd.DataFrame(delete_results)
        total_d    = len(del_df)
        pass_d    = int((del_df["Status"] == "✅ Pass").sum())
        fail_d    = int((del_df["Status"] == "❌ Fail").sum())
        skip_d    = int((del_df["Status"] == "⏭ Skipped").sum())

        dc1, dc2, dc3, dc4 = st.columns(4)
        for col, label, val, color in [
            (dc1, "Total Resources", total_d,  "#0d2d5e"),
            (dc2, "✅ Delete Verified", pass_d, "#16a34a"),
            (dc3, "❌ Still Exists",    fail_d,  "#dc2626"),
            (dc4, "⏭ Skipped",         skip_d,  "#94a3b8"),
        ]:
            with col:
                st.markdown(
                    f"<div style='background:#f8fafc;border:1px solid #e2e8f0;"
                    f"border-top:3px solid {color};border-radius:10px;padding:14px;text-align:center;'>"
                    f"<div style='font-size:11px;font-weight:700;color:#64748b;margin-bottom:6px;"
                    f"text-transform:uppercase;'>{label}</div>"
                    f"<div style='font-size:26px;font-weight:800;color:{color};'>{val}</div>"
                    f"</div>",
                    unsafe_allow_html=True
                )

        st.markdown("<br>", unsafe_allow_html=True)

        def style_delete_df(df):
            def color_row(row):
                if row["Status"] == "✅ Pass":    return ["background-color:#f0fdf4"] * len(row)
                if row["Status"] == "⏭ Skipped": return ["background-color:#f8fafc"] * len(row)
                return ["background-color:#fef2f2"] * len(row)
            return df.style.apply(color_row, axis=1)

        display_del = del_df.drop(columns=["URL"], errors="ignore")
        st.dataframe(style_delete_df(display_del), width="stretch", hide_index=True)

        if pass_d == (total_d - skip_d) and fail_d == 0:
            st.success("🎉 All provided records verified as deleted — zero records returned for all resources.")
        else:
            st.error(
                f"⚠️ Delete verification INCOMPLETE — {fail_d} resource(s) still have data. "
                "Vendor must delete all records before certification can proceed."
            )

        # ── Download Button ───────────────────────────────────────────
        st.divider()
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            del_df.to_excel(writer, sheet_name="Delete_Results", index=False)
            del_fails = del_df[del_df["Status"] == "❌ Fail"]
            if not del_fails.empty:
                del_fails.to_excel(writer, sheet_name="Delete_Issues", index=False)

        dl_c, _sp3 = st.columns([2, 3])
        with dl_c:
            st.download_button(
                label="📥 Export Delete Verification Report",
                data=output.getvalue(),
                file_name=f"EdWise_Finance_DeleteReport_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                width="stretch",
            )
