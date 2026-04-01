import streamlit as st
import pandas as pd
import requests
import io
import urllib.parse
from datetime import datetime

from shared import (
    render_top_ribbon, get_bearer_token, RESET_ENDPOINTS,
    FINANCE_BASE_EDFI, FINANCE_BASE_IDOE,
)


def render_reset():
    # Dynamic ribbon for Financial Data Reset page
    render_top_ribbon(
        page_title="Financial Data Reset",
        page_subtitle="Zero-Count Verification · Ed-Fi ODS 2026 · Indiana DOE"
    )

    st.markdown(
        "<div style='margin-bottom:10px;'>"
        "<span style='font-size:11px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;color:#1a6fd4;'>Financial Data Reset</span>"
        "<div style='font-size:17px;font-weight:800;color:#0d2d5e;margin-top:1px;'>Reset Vendor Finance Data</div>"
        "<div style='width:32px;height:3px;background:#1a6fd4;border-radius:2px;margin-top:4px;'></div>"
        "<div style='font-size:12px;color:#64748b;margin-top:6px;font-weight:400;'>"
        "After vendor resets data, verify that all records return zero count. "
        "Provide EducationOrganizationId, FiscalYear, and FinancialCollectionDescriptor as query parameters."
        "</div>"
        "</div>",
        unsafe_allow_html=True
    )

    # Reset Query Parameters
    rc1, rc2, rc3 = st.columns(3)

    with rc1:
        reset_edorg = st.text_input(
            "EducationOrganizationId",
            value="1094950000",
            key="reset_edorg",
            placeholder="e.g. 1094950000"
        )

    with rc2:
        reset_fy = st.text_input(
            "FiscalYear",
            value="2025",
            key="reset_fy",
            placeholder="e.g. 2025"
        )

    with rc3:
        reset_descriptor = st.text_input(
            "FinancialCollectionDescriptor",
            value="uri://doe.in.gov/FinancialCollectionDescriptor#1",
            key="reset_descriptor",
            placeholder="e.g. uri://doe.in.gov/FinancialCollectionDescriptor#1"
        )

    # Encode the descriptor for URL
    reset_descriptor_encoded = urllib.parse.quote(reset_descriptor, safe='')

    # Divider line
    st.divider()

    # Submit button
    if st.button("Submit Reset"):
        base_url = "https://doe-edfiods-a-v-v2026-ca.ashytree-64da9ba4.eastus.azurecontainerapps.io:443/2026/data/v3/ed-fi/localActuals"
        resolved = (
            f"{base_url}?educationOrganizationId={reset_edorg}"
            f"&fiscalYear={reset_fy}"
            f"&financialCollectionDescriptor={reset_descriptor_encoded}"
            f"&totalCount=true"
        )

        st.write("Resolved URL:")
        st.code(resolved)

    # Reset resources config
    RESET_RESOURCES = [
        ("LocalActual",               "📊 LocalActual",               RESET_ENDPOINTS["LocalActual"]),
        ("LocalCapitalizedEquipment", "🖥️ LocalCapitalizedEquipment", RESET_ENDPOINTS["LocalCapitalizedEquipment"]),
        ("LocalSubaward",             "🤝 LocalSubaward",             RESET_ENDPOINTS["LocalSubaward"]),
        ("LocalUnusedLeavePayment",   "🏖️ LocalUnusedLeavePayment",   RESET_ENDPOINTS["LocalUnusedLeavePayment"]),
    ]

    with st.expander("⚙️ Reset API Endpoints (resolved with query params)", expanded=True):
        for res_key, res_label, base_url in RESET_RESOURCES:
            resolved = (
                f"{base_url}"
                f"?educationOrganizationId={reset_edorg}"
                f"&fiscalYear={reset_fy}"
                f"&financialCollectionDescriptor={reset_descriptor_encoded}"
            )
            st.markdown(
                f"<div style='background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px;padding:8px 12px;margin-bottom:6px;'>"
                f"<span style='font-size:11px;font-weight:700;color:#1a6fd4;'>{res_label}</span><br>"
                f"<code style='font-size:11px;color:#475569;word-break:break-all;'>{resolved}</code>"
                f"</div>", unsafe_allow_html=True)

    st.divider()

    run_reset_check = st.button("▶  Run Reset Verification", type="primary")

    if run_reset_check:
        if not reset_edorg.strip() or not reset_fy.strip() or not reset_descriptor.strip():
            st.error("❌ Please provide EducationOrganizationId, FiscalYear, and FinancialCollectionDescriptor.")
        else:
            reset_results = []
            with st.spinner("Checking reset status for all resources…"):
                for res_key, res_label, base_url in RESET_RESOURCES:
                    resolved_url = (
                        f"{base_url}"
                        f"?educationOrganizationId={reset_edorg.strip()}"
                        f"&fiscalYear={reset_fy.strip()}"
                        f"&financialCollectionDescriptor={reset_descriptor_encoded}"
                        f"&totalCount=true"
                    )
                    try:
                        token = get_bearer_token()
                        r = requests.get(resolved_url, headers={"Authorization": f"Bearer {token}"}, timeout=15)
                        http_status = r.status_code
                        try:
                            resp_data = r.json()
                            records = resp_data if isinstance(resp_data, list) else resp_data.get("value", [])
                            count = len(records) if isinstance(records, list) else 0
                            total_count_header = r.headers.get("Total-Count", None)
                            if total_count_header is not None:
                                count = int(total_count_header)
                        except Exception:
                            count = -1
                            resp_data = {}

                        if http_status == 200 and count == 0:
                            status = "✅ Pass"
                            reason = f"✓ Data reset verified — API returned 0 records for {res_label} with the given parameters. Reset is complete."
                        elif http_status == 200 and count > 0:
                            status = "❌ Fail"
                            reason = f"✗ Reset INCOMPLETE — API returned {count} record(s) for {res_label}. Vendor must post all records with zero values or delete before this check passes."
                        elif http_status == 200 and count == -1:
                            status = "⚠️ Flag"
                            reason = f"⚠️ HTTP 200 but could not parse record count for {res_label}. Manual verification recommended."
                        else:
                            status = "❌ Fail"
                            reason = f"✗ API returned HTTP {http_status} for {res_label} — endpoint may be unreachable or parameters are incorrect."

                        reset_results.append({
                            "Resource": res_label,
                            "URL": resolved_url,
                            "HTTP Status": http_status,
                            "Record Count": count if count >= 0 else "N/A",
                            "Status": status,
                            "Reason": reason,
                        })

                        with st.expander(f"🔍 API Debug — {res_label}", expanded=False):
                            st.markdown(f"**URL:** `{resolved_url}`")
                            st.caption(f"HTTP Status: {http_status} | Records: {count}")
                            try: st.json(resp_data)
                            except Exception: st.write(resp_data)

                    except requests.exceptions.ConnectionError:
                        reset_results.append({"Resource": res_label, "URL": resolved_url, "HTTP Status": 0, "Record Count": "N/A", "Status": "❌ Fail", "Reason": f"✗ Connection error — {res_label} API unreachable"})
                    except Exception as e:
                        reset_results.append({"Resource": res_label, "URL": resolved_url, "HTTP Status": 0, "Record Count": "N/A", "Status": "❌ Fail", "Reason": f"✗ Error: {str(e)}"})

            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown(
                "<div style='margin-bottom:10px;'>"
                "<span style='font-size:11px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;color:#1a6fd4;'>Reset Verification Results</span>"
                "<div style='font-size:17px;font-weight:800;color:#0d2d5e;margin-top:1px;'>Zero-Count Verification</div>"
                "<div style='width:32px;height:3px;background:#1a6fd4;border-radius:2px;margin-top:4px;'></div>"
                "</div>", unsafe_allow_html=True)

            reset_df = pd.DataFrame(reset_results)
            total_r = len(reset_df)
            pass_r = int((reset_df["Status"] == "✅ Pass").sum())
            fail_r = int((reset_df["Status"] == "❌ Fail").sum())
            flag_r = int((reset_df["Status"] == "⚠️ Flag").sum())

            rc1s, rc2s, rc3s, rc4s = st.columns(4)
            for col, label, val, color in [
                (rc1s, "Total Resources", total_r, "#0d2d5e"),
                (rc2s, "✅ Reset Complete", pass_r, "#16a34a"),
                (rc3s, "❌ Still Has Data", fail_r, "#dc2626"),
                (rc4s, "⚠️ Flagged", flag_r, "#d97706"),
            ]:
                with col:
                    st.markdown(
                        f"<div style='background:#f8fafc;border:1px solid #e2e8f0;border-top:3px solid {color};"
                        f"border-radius:10px;padding:14px;text-align:center;'>"
                        f"<div style='font-size:11px;font-weight:700;color:#64748b;margin-bottom:6px;text-transform:uppercase;'>{label}</div>"
                        f"<div style='font-size:26px;font-weight:800;color:{color};'>{val}</div>"
                        f"</div>", unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)

            def style_reset_df(df):
                def color_row(row):
                    if row["Status"] == "✅ Pass": return ["background-color:#f0fdf4"] * len(row)
                    if row["Status"] == "⚠️ Flag": return ["background-color:#fffbeb"] * len(row)
                    return ["background-color:#fef2f2"] * len(row)
                return df.style.apply(color_row, axis=1)

            display_reset = reset_df.drop(columns=["URL"], errors="ignore")
            st.dataframe(style_reset_df(display_reset), width="stretch", hide_index=True)

            if pass_r == total_r:
                st.success("🎉 All resources verified — Financial Data Reset is COMPLETE. All records returned zero count.")
            else:
                st.error(f"⚠️ Reset verification INCOMPLETE — {fail_r} resource(s) still have data. Vendor must complete the reset before certification can proceed.")

            # ── Download Button ───────────────────────────────────────────
            st.divider()
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                reset_df.to_excel(writer, sheet_name="Reset_Results", index=False)
                reset_fails = reset_df[reset_df["Status"] != "✅ Pass"]
                if not reset_fails.empty:
                    reset_fails.to_excel(writer, sheet_name="Reset_Issues", index=False)

            dl_c, _sp3 = st.columns([2, 3])
            with dl_c:
                st.download_button(
                    label="📥 Export Reset Verification Report",
                    data=output.getvalue(),
                    file_name=f"EdWise_Finance_ResetReport_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    width="stretch",
                )
