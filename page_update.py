import streamlit as st
import pandas as pd
import requests
import io
from datetime import datetime

from shared import (
    render_top_ribbon, get_bearer_token, extract_nested, strip_descriptor_code,
    FINANCE_BASE_EDFI, FINANCE_BASE_IDOE,
)


def render_update():

    render_top_ribbon(
        page_title="Financial Data Update Verification",
        page_subtitle="Updated Field Match Check · Ed-Fi ODS 2026 · Indiana DOE"
    )

    st.markdown(
        "<div style='margin-bottom:10px;'>"
        "<span style='font-size:11px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;color:#1a6fd4;'>"
        "Financial Data Update</span>"
        "<div style='font-size:17px;font-weight:800;color:#0d2d5e;margin-top:1px;'>"
        "Verify Updated Fields in API Response</div>"
        "<div style='width:32px;height:3px;background:#1a6fd4;border-radius:2px;margin-top:4px;'></div>"
        "<div style='font-size:12px;color:#64748b;margin-top:6px;font-weight:400;'>"
        "Enter only the fields that were updated (leave blank if not changed). "
        "The GET response will be checked — if the field value in the response matches exactly, result is PASS."
        "</div>"
        "</div>",
        unsafe_allow_html=True
    )

    # ── UPDATE ENDPOINT BASE URLS (query param style, same as verification) ──
    UPDATE_GET_ENDPOINTS = {
        "LocalAccount":              "https://doe-edfiods-a-v-v2026-ca.ashytree-64da9ba4.eastus.azurecontainerapps.io:443/2026/data/v3/ed-fi/LocalAccounts?accountIdentifier={AccountIdentifier}",
        "LocalActual":                "https://doe-edfiods-a-v-v2026-ca.ashytree-64da9ba4.eastus.azurecontainerapps.io:443/2026/data/v3/ed-fi/localActuals?accountIdentifier={AccountIdentifier}",
        "LocalCapitalizedEquipment": "https://doe-edfiods-a-v-v2026-ca.ashytree-64da9ba4.eastus.azurecontainerapps.io:443/2026/data/v3/idoe/LocalCapitalizedEquipment?accountIdentifier={AccountIdentifier}",
        "LocalSubaward":              "https://doe-edfiods-a-v-v2026-ca.ashytree-64da9ba4.eastus.azurecontainerapps.io:443/2026/data/v3/idoe/LocalSubawards?accountIdentifier={AccountIdentifier}",
        "LocalUnusedLeavePayment":    "https://doe-edfiods-a-v-v2026-ca.ashytree-64da9ba4.eastus.azurecontainerapps.io:443/2026/data/v3/idoe/LocalUnusedLeavePayments?accountIdentifier={AccountIdentifier}",
    }

    # Updated fields per resource
    UPDATE_FIELDS = {
        "LocalAccount": [
            "accountName",
        ],
        "LocalActual": [
            "amount",
            "financialCollectionDescriptor",
        ],
        "LocalCapitalizedEquipment": [
            "financialCollectionDescriptor",
            "capitalizedThreshold",
            "equipmentDescription",
            "equipmentType",
            "paymentAmount",
            "perUnitCost",
            "acquisitionDate",
        ],
        "LocalSubaward": [
            "financialCollectionDescriptor",
            "contractNumberOfYears",
            "departmentName",
            "first50k",
            "excess50k",
            "expenditureAmount",
            "subawardAmount",
            "vendorOrganizationName",
        ],
        "LocalUnusedLeavePayment": [
            "financialCollectionDescriptor",
            "directUnusedLeavePaymentAmount",
            "indirectUnusedLeavePaymentAmount",
            "employeeName",
            "jobTitle",
            "paymentDate",
        ],
    }

    UPDATE_RESOURCE_LABELS = {
        "LocalAccount":              "📋 LocalAccount",
        "LocalActual":                "📊 LocalActual",
        "LocalCapitalizedEquipment": "🖥️ LocalCapitalizedEquipment",
        "LocalSubaward":              "🤝 LocalSubaward",
        "LocalUnusedLeavePayment":    "🏖️ LocalUnusedLeavePayment",
    }

    # ── Account Identifier input (shared) ─────────────────────────────
    upd_acc_id = st.text_input(
        "AccountIdentifier (for GET lookup)",
        value="S-1394-25110-940-5170-51",
        key="upd_acc_id",
        placeholder="e.g. S-1394-25110-940-5170-51"
    )

    st.markdown("<div style='margin-top:12px;'></div>", unsafe_allow_html=True)

    # ── Per-resource tabs for updated field inputs ────────────────────
    upd_tabs = st.tabs([
        "📋 LocalAccount",
        "📊 LocalActual",
        "🖥️ LocalCapitalizedEquipment",
        "🤝 LocalSubaward",
        "🏖️ LocalUnusedLeavePayment",
    ])

    upd_inputs = {}   # { res: { field: value_string } }

    for tab_widget, res in zip(upd_tabs, UPDATE_FIELDS.keys()):
        with tab_widget:
            st.markdown(
                f"<div style='font-size:11px;font-weight:700;color:#64748b;margin-bottom:8px;'>"
                f"Enter only updated fields — leave blank if field was NOT changed</div>",
                unsafe_allow_html=True
            )
            fields = UPDATE_FIELDS[res]
            upd_inputs[res] = {}
            cols_per_row = 2
            for i in range(0, len(fields), cols_per_row):
                row_fields = fields[i:i + cols_per_row]
                row_cols   = st.columns(len(row_fields))
                for ui_col, fld in zip(row_cols, row_fields):
                    with ui_col:
                        upd_inputs[res][fld] = st.text_input(
                            fld,
                            value="",
                            key=f"upd_{res}_{fld}",
                            placeholder=f"Updated value for {fld}"
                        )

    st.divider()

    # ── Resolved GET URLs preview ─────────────────────────────────────
    with st.expander("🔗 Resolved GET URLs for Update Verification", expanded=False):
        for res in UPDATE_GET_ENDPOINTS:
            resolved = UPDATE_GET_ENDPOINTS[res].replace(
                "{AccountIdentifier}", upd_acc_id.strip() or "<AccountIdentifier>"
            )
            st.markdown(
                f"<div style='background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px;"
                f"padding:8px 12px;margin-bottom:6px;'>"
                f"<span style='font-size:11px;font-weight:700;color:#1a6fd4;'>"
                f"{UPDATE_RESOURCE_LABELS[res]}</span><br>"
                f"<code style='font-size:11px;color:#475569;word-break:break-all;'>{resolved}</code>"
                f"</div>",
                unsafe_allow_html=True
            )

    run_update_check = st.button("▶  Run Update Verification", type="primary", key="run_update_verify")

    if run_update_check:
        if not upd_acc_id.strip():
            st.error("❌ Please enter AccountIdentifier.")
            st.stop()

        # Check if any fields were actually entered
        all_upd_fields_entered = {
            res: {k: v for k, v in flds.items() if v.strip()}
            for res, flds in upd_inputs.items()
        }
        total_fields_entered = sum(len(v) for v in all_upd_fields_entered.values())
        if total_fields_entered == 0:
            st.warning("⚠️ No updated field values entered. Please fill in at least one field.")
            st.stop()

        update_results_all = []

        with st.spinner("Fetching API responses and verifying updated fields…"):
            for res in UPDATE_GET_ENDPOINTS:
                entered_fields = all_upd_fields_entered.get(res, {})
                if not entered_fields:
                    # No fields entered for this resource — skip
                    update_results_all.append({
                        "Resource":        UPDATE_RESOURCE_LABELS[res],
                        "Field":            "—",
                        "Expected Value":  "—",
                        "API Value":       "—",
                        "Status":          "⏭ Skipped",
                        "Reason":          f"⏭ No updated fields entered for {res}",
                    })
                    continue

                # Build GET URL
                get_url = UPDATE_GET_ENDPOINTS[res].replace(
                    "{AccountIdentifier}", upd_acc_id.strip()
                )

                try:
                    token = get_bearer_token()
                    r = requests.get(
                        get_url,
                        headers={"Authorization": f"Bearer {token}"},
                        timeout=15
                    )

                    with st.expander(f"🔍 API Debug — {UPDATE_RESOURCE_LABELS[res]}", expanded=False):
                        st.markdown(f"**URL:** `{get_url}`")
                        st.caption(f"HTTP Status: {r.status_code}")
                        try:
                            st.json(r.json())
                        except Exception:
                            st.write(r.text)

                    if r.status_code != 200:
                        for fld in entered_fields:
                            update_results_all.append({
                                "Resource":        UPDATE_RESOURCE_LABELS[res],
                                "Field":           fld,
                                "Expected Value": entered_fields[fld],
                                "API Value":       "—",
                                "Status":          "❌ Fail",
                                "Reason":          (
                                    f"✗ HTTP {r.status_code} — could not fetch {res}. "
                                    "Endpoint may be unreachable or AccountIdentifier not found."
                                ),
                            })
                        continue

                    try:
                        resp_data = r.json()
                    except Exception:
                        for fld in entered_fields:
                            update_results_all.append({
                                "Resource":        UPDATE_RESOURCE_LABELS[res],
                                "Field":           fld,
                                "Expected Value": entered_fields[fld],
                                "API Value":       "—",
                                "Status":          "❌ Fail",
                                "Reason":          "✗ Could not parse API response as JSON.",
                            })
                        continue

                    records = resp_data if isinstance(resp_data, list) else resp_data.get("value", [])
                    if not records:
                        for fld in entered_fields:
                            update_results_all.append({
                                "Resource":        UPDATE_RESOURCE_LABELS[res],
                                "Field":           fld,
                                "Expected Value": entered_fields[fld],
                                "API Value":       "—",
                                "Status":          "❌ Fail",
                                "Reason":          (
                                    f"✗ HTTP 200 but zero records returned for {res}. "
                                    "Cannot verify updated fields — no data in response."
                                ),
                            })
                        continue

                    # Use first record (or all if multiple)
                    api_rec = records[0] if isinstance(records, list) else records

                    for fld, expected_val in entered_fields.items():
                        expected_str = expected_val.strip()
                        if not expected_str:
                            continue

                        # Extract field value using nested helper
                        api_val = extract_nested(api_rec, fld)
                        if api_val is None:
                            # Try flattened
                            flat = pd.json_normalize(api_rec).to_dict(orient="records")[0]
                            matched_keys = [k for k in flat if k.split(".")[-1] == fld]
                            api_val = flat.get(matched_keys[0]) if matched_keys else None

                        if api_val is None:
                            update_results_all.append({
                                "Resource":        UPDATE_RESOURCE_LABELS[res],
                                "Field":           fld,
                                "Expected Value": expected_str,
                                "API Value":       "Not Found in Response",
                                "Status":          "❌ Fail",
                                "Reason":          (
                                    f"✗ Field '{fld}' not found in {res} API response. "
                                    "The field may not exist or may be nested differently."
                                ),
                            })
                            continue

                        # Normalize for comparison
                        api_val_str = strip_descriptor_code(str(api_val).strip())
                        exp_val_cmp = strip_descriptor_code(expected_str)

                        # Numeric comparison for numeric-looking values
                        try:
                            if float(api_val_str) == float(exp_val_cmp):
                                match = True
                            else:
                                match = False
                        except Exception:
                            match = (api_val_str.lower() == exp_val_cmp.lower())

                        if match:
                            update_results_all.append({
                                "Resource":        UPDATE_RESOURCE_LABELS[res],
                                "Field":           fld,
                                "Expected Value": expected_str,
                                "API Value":       api_val_str,
                                "Status":          "✅ Pass",
                                "Reason":          (
                                    f"✓ Field '{fld}' in {res} API response matches expected updated value "
                                    f"'{api_val_str}' — update verified successfully."
                                ),
                            })
                        else:
                            update_results_all.append({
                                "Resource":        UPDATE_RESOURCE_LABELS[res],
                                "Field":           fld,
                                "Expected Value": expected_str,
                                "API Value":       api_val_str,
                                "Status":          "❌ Fail",
                                "Reason":          (
                                    f"✗ Field '{fld}' mismatch in {res} — "
                                    f"expected '{expected_str}' but API returned '{api_val_str}'. "
                                    "Vendor update did not reflect correctly in the ODS."
                                ),
                            })

                except requests.exceptions.ConnectionError:
                    for fld in entered_fields:
                        update_results_all.append({
                            "Resource":        UPDATE_RESOURCE_LABELS[res],
                            "Field":           fld,
                            "Expected Value": entered_fields[fld],
                            "API Value":       "—",
                            "Status":          "❌ Fail",
                            "Reason":          f"✗ Connection error — {res} API unreachable",
                        })
                except Exception as ex:
                    for fld in entered_fields:
                        update_results_all.append({
                            "Resource":        UPDATE_RESOURCE_LABELS[res],
                            "Field":           fld,
                            "Expected Value": entered_fields[fld],
                            "API Value":       "—",
                            "Status":          "❌ Fail",
                            "Reason":          f"✗ Error: {str(ex)}",
                        })

        # ── Update Results Display ────────────────────────────────────
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(
            "<div style='margin-bottom:10px;'>"
            "<span style='font-size:11px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;color:#1a6fd4;'>"
            "Update Verification Results</span>"
            "<div style='font-size:17px;font-weight:800;color:#0d2d5e;margin-top:1px;'>"
            "Updated Field Match Check</div>"
            "<div style='width:32px;height:3px;background:#1a6fd4;border-radius:2px;margin-top:4px;'></div>"
            "</div>",
            unsafe_allow_html=True
        )

        upd_df   = pd.DataFrame(update_results_all)
        total_u  = len(upd_df)
        pass_u   = int((upd_df["Status"] == "✅ Pass").sum())
        fail_u   = int((upd_df["Status"] == "❌ Fail").sum())
        skip_u   = int((upd_df["Status"] == "⏭ Skipped").sum())

        uc1, uc2, uc3, uc4 = st.columns(4)
        for col, label, val, color in [
            (uc1, "Total Resources Checked", total_u,  "#0d2d5e"),
            (uc2, "✅ Match (Pass)",       pass_u,   "#16a34a"),
            (uc3, "❌ Mismatch (Fail)",    fail_u,   "#dc2626"),
            (uc4, "⏭ Skipped",             skip_u,   "#94a3b8"),
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

        # Per-resource breakdown tabs
        upd_res_tabs = st.tabs([
            "📋 LocalAccount",
            "📊 LocalActual",
            "🖥️ LocalCapitalizedEquipment",
            "🤝 LocalSubaward",
            "🏖️ LocalUnusedLeavePayment",
        ])
        for tab_widget, res in zip(upd_res_tabs, UPDATE_FIELDS.keys()):
            with tab_widget:
                res_label = UPDATE_RESOURCE_LABELS[res]
                subset    = upd_df[upd_df["Resource"] == res_label]
                if subset.empty:
                    st.info(f"No fields checked for {res}.")
                else:
                    def style_upd_df(df):
                        def color_row(row):
                            if row["Status"] == "✅ Pass":    return ["background-color:#f0fdf4"] * len(row)
                            if row["Status"] == "⏭ Skipped": return ["background-color:#f8fafc"] * len(row)
                            return ["background-color:#fef2f2"] * len(row)
                        return df.style.apply(color_row, axis=1)
                    st.dataframe(
                        style_upd_df(subset.reset_index(drop=True)),
                        width="stretch",
                        hide_index=True
                    )

        st.markdown("<br>", unsafe_allow_html=True)

        if fail_u == 0 and pass_u > 0:
            st.success(
                f"🎉 All {pass_u} updated field(s) verified — API response matches expected values for all resources."
            )
        elif fail_u > 0:
            st.error(
                f"⚠️ Update verification INCOMPLETE — {fail_u} field(s) did not match. "
                "Vendor must ensure all updated values are correctly posted to the ODS."
            )
        else:
            st.info("No fields were verified — please enter updated values and re-run.")

        # ── Download Button ───────────────────────────────────────────
        st.divider()
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            upd_df.to_excel(writer, sheet_name="Update_Results", index=False)
            upd_fails = upd_df[upd_df["Status"] == "❌ Fail"]
            if not upd_fails.empty:
                upd_fails.to_excel(writer, sheet_name="Update_Issues", index=False)

        dl_c, _sp3 = st.columns([2, 3])
        with dl_c:
            st.download_button(
                label="📥 Export Update Verification Report",
                data=output.getvalue(),
                file_name=f"EdWise_Finance_UpdateReport_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                width="stretch",
            )
