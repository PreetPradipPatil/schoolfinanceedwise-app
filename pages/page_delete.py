import streamlit as st
import pandas as pd
import requests
import io
from datetime import datetime

from shared import (
    render_top_ribbon, get_bearer_token,
    FINANCE_BASE_EDFI, FINANCE_BASE_IDOE,
    FINANCE_API_ENDPOINT_TEMPLATES,
)


def render_delete():

    render_top_ribbon(
        page_title="Financial Data Delete Verification",
        page_subtitle="Zero-Record & Blank Body Check · Ed-Fi ODS 2026 · Indiana DOE"
    )

    st.markdown(
        "<div style='margin-bottom:10px;'>"
        "<span style='font-size:11px;font-weight:700;letter-spacing:1.5px;"
        "text-transform:uppercase;color:#1a6fd4;'>Financial Data Delete</span>"
        "<div style='font-size:17px;font-weight:800;color:#0d2d5e;margin-top:1px;'>"
        "Verify Deleted Records Return Zero Count</div>"
        "<div style='width:32px;height:3px;background:#1a6fd4;border-radius:2px;margin-top:4px;'></div>"
        "<div style='font-size:12px;color:#64748b;margin-top:6px;font-weight:400;'>"
        "Provide the Account Identifier(s) for each resource. A GET request is fired using "
        "<code>?accountIdentifier=</code> (query param). "
        "<b>Pass</b> = zero records returned / blank response body."
        "</div>"
        "</div>",
        unsafe_allow_html=True,
    )

    # ── Default Account Identifiers ───────────────────────────────────────
    # LocalAccount  : 3 identifiers (one per row scenario)
    # LocalActual   : 3 identifiers
    # Equipment     : 1 (Capitalized Equipment identifier)
    # Subaward      : 1 (Subaward identifier)
    # UnusedLeave   : 1 (Unused Leave Payment identifier)
    DEFAULTS = {
        "LocalAccount": [
            "2-0760-45400-735-0000-00",   # Local Capitalized Equipment related
            "4-5840-60115-931-0000-00",   # Local Subaward related
            "2-0300-27100-125-0000-00",   # Local Unused Leave Payment related
        ],
        "LocalActual": [
            "2-0760-45400-735-0000-00",
            "4-5840-60115-931-0000-00",
            "2-0300-27100-125-0000-00",
        ],
        "LocalCapitalizedEquipment": ["2-0760-45400-735-0000-00"],
        "LocalSubaward":             ["4-5840-60115-931-0000-00"],
        "LocalUnusedLeavePayment":   ["2-0300-27100-125-0000-00"],
    }

    DELETE_RESOURCE_LABELS = {
        "LocalAccount":              "📋 LocalAccount",
        "LocalActual":               "📊 LocalActual",
        "LocalCapitalizedEquipment": "🖥️ LocalCapitalizedEquipment",
        "LocalSubaward":             "🤝 LocalSubaward",
        "LocalUnusedLeavePayment":   "🏖️ LocalUnusedLeavePayment",
    }

    # ── Input Section ─────────────────────────────────────────────────────
    st.markdown(
        "<div style='font-size:13px;font-weight:700;color:#0d2d5e;margin-bottom:8px;'>"
        "Enter Account Identifiers</div>",
        unsafe_allow_html=True,
    )

    del_account_ids = {}   # res -> list[str]

    # LocalAccount — 3 inputs side-by-side
    for res in ["LocalAccount", "LocalActual"]:
        st.markdown(
            f"<div style='font-size:12px;font-weight:700;color:#1a6fd4;"
            f"margin-top:10px;margin-bottom:4px;'>{DELETE_RESOURCE_LABELS[res]}</div>",
            unsafe_allow_html=True,
        )
        cols = st.columns(3)
        ids = []
        for i, col in enumerate(cols):
            with col:
                val = st.text_input(
                    f"Account ID #{i + 1}",
                    value=DEFAULTS[res][i],
                    key=f"del_aid_{res}_{i}",
                    placeholder="e.g. 2-0760-45400-735-0000-00",
                )
                ids.append(val)
        del_account_ids[res] = ids

    # Equipment / Subaward / UnusedLeave — 1 input each, side-by-side
    st.markdown("<div style='margin-top:10px;'></div>", unsafe_allow_html=True)
    single_resources = ["LocalCapitalizedEquipment", "LocalSubaward", "LocalUnusedLeavePayment"]
    cols3 = st.columns(3)
    for col_ui, res in zip(cols3, single_resources):
        with col_ui:
            st.markdown(
                f"<div style='font-size:12px;font-weight:700;color:#1a6fd4;"
                f"margin-bottom:4px;'>{DELETE_RESOURCE_LABELS[res]}</div>",
                unsafe_allow_html=True,
            )
            val = st.text_input(
                "Account ID",
                value=DEFAULTS[res][0],
                key=f"del_aid_{res}_0",
                placeholder="e.g. 2-0760-45400-735-0000-00",
            )
            del_account_ids[res] = [val]

    # ── Resolved URLs Preview ─────────────────────────────────────────────
    st.markdown("<div style='margin-top:10px;'></div>", unsafe_allow_html=True)
    with st.expander("🔗 Resolved DELETE Verification URLs (query params)", expanded=True):
        for res, ids in del_account_ids.items():
            template = FINANCE_API_ENDPOINT_TEMPLATES.get(res, "")
            st.markdown(
                f"<div style='font-size:11px;font-weight:700;color:#1a6fd4;"
                f"margin-bottom:2px;margin-top:6px;'>{DELETE_RESOURCE_LABELS[res]}</div>",
                unsafe_allow_html=True,
            )
            for aid in ids:
                aid = aid.strip()
                if aid and template:
                    resolved = template.format(AccountIdentifier=aid)
                elif template:
                    resolved = f"{template} — (Account ID not provided)"
                else:
                    resolved = "(template not loaded — ensure init_credentials() has been called)"
                st.markdown(
                    f"<div style='background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px;"
                    f"padding:6px 12px;margin-bottom:4px;'>"
                    f"<code style='font-size:11px;color:#475569;word-break:break-all;'>{resolved}</code>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

    st.divider()

    run_delete_check = st.button("▶  Run Delete Verification", type="primary", key="run_delete_verify")

    if run_delete_check:
        delete_results = []
        total_requests = sum(len(ids) for ids in del_account_ids.values())

        with st.spinner(f"Verifying deleted records for {total_requests} account identifier(s)…"):
            for res, ids in del_account_ids.items():
                label    = DELETE_RESOURCE_LABELS[res]
                template = FINANCE_API_ENDPOINT_TEMPLATES.get(res, "")

                for idx, account_id in enumerate(ids, start=1):
                    account_id = account_id.strip()
                    id_label   = f"{label} #{idx}" if len(ids) > 1 else label

                    # ── Skip if no input ──────────────────────────────────────
                    if not account_id:
                        delete_results.append({
                            "Resource":     id_label,
                            "AccountIdentifier": "—",
                            "URL":          "—",
                            "HTTP Status":  "—",
                            "Record Count": "—",
                            "Body":         "—",
                            "Status":       "⏭ Skipped",
                            "Reason":       f"⏭ Account Identifier not provided for {res} #{idx} — skipped",
                        })
                        continue

                    if not template:
                        delete_results.append({
                            "Resource":     id_label,
                            "AccountIdentifier": account_id,
                            "URL":          "—",
                            "HTTP Status":  "—",
                            "Record Count": "—",
                            "Body":         "—",
                            "Status":       "❌ Fail",
                            "Reason":       (
                                "✗ URL template not available — "
                                "ensure init_credentials() has been called before render_delete()."
                            ),
                        })
                        continue

                    resolved_url = template.format(AccountIdentifier=account_id)

                    try:
                        token = get_bearer_token()
                        r = requests.get(
                            resolved_url,
                            headers={"Authorization": f"Bearer {token}"},
                            timeout=15,
                        )
                        http_status = r.status_code
                        raw_text    = r.text.strip() if r.text else ""

                        # ── Parse response ────────────────────────────────────
                        try:
                            resp_json = r.json()
                            is_list   = isinstance(resp_json, list)
                            count     = len(resp_json) if is_list else (1 if resp_json else 0)
                            is_blank  = (
                                count == 0
                                or not raw_text
                                or raw_text in ("[]", "{}", "null", "")
                            )
                        except Exception:
                            resp_json = None
                            count     = 0 if (not raw_text or raw_text in ("", "null")) else -1
                            is_blank  = count == 0

                        # ── Determine pass / fail ─────────────────────────────
                        # PASS conditions:
                        #   • HTTP 404 → record not found (deleted)
                        #   • HTTP 410 → permanently deleted
                        #   • HTTP 200 with 0 records / empty body → deleted
                        # FAIL conditions:
                        #   • HTTP 200 with data still present
                        #   • Any other unexpected status
                        if http_status == 404:
                            status = "✅ Pass"
                            reason = (
                                f"✓ HTTP 404 — AccountIdentifier '{account_id}' does not exist "
                                f"in {res}. Delete verified: record successfully removed from ODS."
                            )
                        elif http_status == 410:
                            status = "✅ Pass"
                            reason = (
                                f"✓ HTTP 410 Gone — AccountIdentifier '{account_id}' "
                                f"has been permanently deleted from {res}."
                            )
                        elif http_status == 200 and is_blank:
                            status = "✅ Pass"
                            reason = (
                                f"✓ HTTP 200 — Zero records returned / blank response body. "
                                f"Delete verified for {res} (AccountIdentifier: {account_id})."
                            )
                        elif http_status == 200 and not is_blank:
                            status = "❌ Fail"
                            reason = (
                                f"✗ HTTP 200 — Record STILL EXISTS in {res} "
                                f"(AccountIdentifier: {account_id}). "
                                f"Record count = {count}. "
                                "Vendor must delete this record before certification can proceed."
                            )
                        else:
                            status = "❌ Fail"
                            reason = (
                                f"✗ Unexpected HTTP {http_status} for {res} "
                                f"(AccountIdentifier: {account_id}). "
                                "Verify the Account Identifier and endpoint configuration."
                            )

                        delete_results.append({
                            "Resource":          id_label,
                            "AccountIdentifier": account_id,
                            "URL":               resolved_url,
                            "HTTP Status":       http_status,
                            "Record Count":      count if count >= 0 else "N/A",
                            "Body":              "Blank/Empty" if is_blank else raw_text[:120],
                            "Status":            status,
                            "Reason":            reason,
                        })

                        with st.expander(
                            f"🔍 API Debug — {id_label} ({account_id})", expanded=False
                        ):
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
                            "Resource":          id_label,
                            "AccountIdentifier": account_id,
                            "URL":               resolved_url,
                            "HTTP Status":       0,
                            "Record Count":      "N/A",
                            "Body":              "—",
                            "Status":            "❌ Fail",
                            "Reason":            f"✗ Connection error — {res} API unreachable",
                        })
                    except Exception as ex:
                        delete_results.append({
                            "Resource":          id_label,
                            "AccountIdentifier": account_id,
                            "URL":               resolved_url,
                            "HTTP Status":       0,
                            "Record Count":      "N/A",
                            "Body":              "—",
                            "Status":            "❌ Fail",
                            "Reason":            f"✗ Error: {str(ex)}",
                        })

        # ── Results Display ───────────────────────────────────────────────
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(
            "<div style='margin-bottom:10px;'>"
            "<span style='font-size:11px;font-weight:700;letter-spacing:1.5px;"
            "text-transform:uppercase;color:#1a6fd4;'>Delete Verification Results</span>"
            "<div style='font-size:17px;font-weight:800;color:#0d2d5e;margin-top:1px;'>"
            "Zero-Record &amp; Blank Body Check</div>"
            "<div style='width:32px;height:3px;background:#1a6fd4;border-radius:2px;margin-top:4px;'></div>"
            "</div>",
            unsafe_allow_html=True,
        )

        del_df  = pd.DataFrame(delete_results)
        total_d = len(del_df)
        pass_d  = int((del_df["Status"] == "✅ Pass").sum())
        fail_d  = int((del_df["Status"] == "❌ Fail").sum())
        skip_d  = int((del_df["Status"] == "⏭ Skipped").sum())

        dc1, dc2, dc3, dc4 = st.columns(4)
        for col, lbl, val, color in [
            (dc1, "Total Checks",      total_d, "#0d2d5e"),
            (dc2, "✅ Delete Verified", pass_d,  "#16a34a"),
            (dc3, "❌ Still Exists",    fail_d,  "#dc2626"),
            (dc4, "⏭ Skipped",         skip_d,  "#94a3b8"),
        ]:
            with col:
                st.markdown(
                    f"<div style='background:#f8fafc;border:1px solid #e2e8f0;"
                    f"border-top:3px solid {color};border-radius:10px;"
                    f"padding:14px;text-align:center;'>"
                    f"<div style='font-size:11px;font-weight:700;color:#64748b;"
                    f"margin-bottom:6px;text-transform:uppercase;'>{lbl}</div>"
                    f"<div style='font-size:26px;font-weight:800;color:{color};'>{val}</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

        st.markdown("<br>", unsafe_allow_html=True)

        def style_delete_df(df):
            def color_row(row):
                if row["Status"] == "✅ Pass":
                    return ["background-color:#f0fdf4"] * len(row)
                if row["Status"] == "⏭ Skipped":
                    return ["background-color:#f8fafc"] * len(row)
                return ["background-color:#fef2f2"] * len(row)
            return df.style.apply(color_row, axis=1)

        display_del = del_df.drop(columns=["URL"], errors="ignore")
        st.dataframe(style_delete_df(display_del), use_container_width=True, hide_index=True)

        if fail_d == 0 and pass_d > 0:
            st.success(
                "🎉 All provided records verified as deleted — "
                "zero records returned for all account identifiers."
            )
        elif fail_d > 0:
            st.error(
                f"⚠️ Delete verification INCOMPLETE — {fail_d} account identifier(s) still have data. "
                "Vendor must delete all records before certification can proceed."
            )

        # ── Download Button ───────────────────────────────────────────────
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
                use_container_width=True,
            )