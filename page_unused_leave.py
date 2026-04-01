import streamlit as st
import pandas as pd
import requests
import io
from datetime import datetime

from shared import (
    render_top_ribbon, _result_heading, _stat_card,
    get_bearer_token, build_resolved_url, fetch_api_single, extract_nested,
    safe_df_for_display, strip_descriptor_code, style_validation_df, prep_display_df,
    propagate_query_params_to_all,
    run_finance_validation, run_business_rules_for_resource,
    run_fund_classification_validations, run_lifecycle_validations,
    run_duplicate_detection, run_descriptor_consistency_check,
    FINANCE_COLS, FINANCE_SAMPLE_DEFAULTS, FINANCE_NESTED, FINANCE_API_ENDPOINT_TEMPLATES,
    FINANCE_BASE_EDFI, FINANCE_BASE_IDOE,
)

# Resources needed for this page
PAGE_RESOURCES = ["LocalAccount", "LocalActual", "LocalUnusedLeavePayment"]
PAGE_TITLE = "Local Unused Leave Payment Verification"


def render_unused_leave():
    render_top_ribbon(
        page_title=PAGE_TITLE,
        page_subtitle="Ed-Fi ODS 2026 · Indiana DOE"
    )

    # ════════════════════════════════════════════════════════════════════
    # STEP 1 — QUERY PARAMETERS
    # ════════════════════════════════════════════════════════════════════
    hdr_l, hdr_r = st.columns([3, 1])
    with hdr_l:
        st.markdown(
            "<div style='margin-bottom:2px;'>"
            "<span style='font-size:11px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;"
            "color:#1a6fd4;'>Step 1</span>"
            "<div style='font-size:17px;font-weight:800;color:#0d2d5e;margin-top:1px;'>Account Lookup Parameters</div>"
            "<div style='width:32px;height:3px;background:#1a6fd4;border-radius:2px;margin-top:4px;'></div>"
            "<div style='font-size:12px;color:#64748b;margin-top:6px;font-weight:400;'>"
            "Provide Account ID, Education Organization ID, and Fiscal Year. "
            "Validates: LocalAccount (Parent) → LocalActual (Parent) → LocalUnusedLeavePayment (Child)."
            "</div>"
            "</div>",
            unsafe_allow_html=True,
        )
    with hdr_r:
        st.markdown("<div style='padding-top:18px;'>", unsafe_allow_html=True)
        if st.button("+ Add New Record", key="ul_add_record", type="primary"):
            st.session_state.ul_num_records = st.session_state.get("ul_num_records", 1) + 1
            st.session_state.ul_record_data.append({"account_id": "", "edorg_id": "", "fiscal_year": "", "approved_budget": ""})
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    # Initialize session state for this page
    if "ul_num_records" not in st.session_state:
        st.session_state.ul_num_records = 1
    if "ul_record_data" not in st.session_state:
        st.session_state.ul_record_data = [{"account_id": "S-1394-25110-940-5170-51", "edorg_id": "1094950000", "fiscal_year": "2025", "approved_budget": ""}]
    if "ul_api_debug_info" not in st.session_state:
        st.session_state.ul_api_debug_info = []

    fin_pairs = []
    n = st.session_state.ul_num_records
    for row_start in range(0, n, 2):
        row_end  = min(row_start + 2, n)
        row_cols = st.columns(row_end - row_start)
        for j, col in enumerate(row_cols):
            i = row_start + j
            with col:
                st.markdown(
                    f"<div style='font-size:11px;font-weight:700;color:#1a6fd4;letter-spacing:.5px;margin-bottom:4px;"
                    f"background:#eff6ff;padding:4px 8px;border-radius:4px;display:inline-block;'>RECORD {i+1}</div>",
                    unsafe_allow_html=True,
                )
                dv     = st.session_state.ul_record_data[i] if i < len(st.session_state.ul_record_data) else {"account_id": "", "edorg_id": "", "fiscal_year": "", "approved_budget": ""}
                acc_id = st.text_input(f"Account ID {i+1}",  value=dv.get("account_id", ""),  key=f"ul_acc_{i}")
                edorg  = st.text_input(f"Edorg ID {i+1}",    value=dv.get("edorg_id", ""),    key=f"ul_edorg_{i}")
                fy     = st.text_input(f"Fiscal Year {i+1}", value=dv.get("fiscal_year", ""), key=f"ul_fy_{i}")
                budget = st.text_input(f"Approved Budget {i+1} (optional)",
                                       value=dv.get("approved_budget", ""), key=f"ul_budget_{i}",
                                       placeholder="e.g. 150000")

                prev    = st.session_state.ul_record_data[i] if i < len(st.session_state.ul_record_data) else {}
                changed = (
                    acc_id != prev.get("account_id", "")
                    or edorg != prev.get("edorg_id", "")
                    or fy != prev.get("fiscal_year", "")
                    or budget != prev.get("approved_budget", "")
                )
                if i < len(st.session_state.ul_record_data):
                    st.session_state.ul_record_data[i] = {"account_id": acc_id, "edorg_id": edorg, "fiscal_year": fy, "approved_budget": budget}
                if changed:
                    propagate_query_params_to_all(acc_id, edorg, fy, record_index=i)
                if acc_id.strip() and budget.strip():
                    try:
                        st.session_state.approved_budget_map[acc_id.strip()] = float(budget.strip())
                    except Exception:
                        pass
                if acc_id.strip():
                    fin_pairs.append((acc_id.strip(), edorg.strip(), fy.strip(), i + 1))

    st.divider()

    # ════════════════════════════════════════════════════════════════════
    # STEP 2 — SAMPLE DATA
    # ════════════════════════════════════════════════════════════════════
    st.markdown(
        "<div style='margin-bottom:10px;'>"
        "<span style='font-size:11px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;"
        "color:#1a6fd4;'>Step 2</span>"
        "<div style='font-size:17px;font-weight:800;color:#0d2d5e;margin-top:1px;'>Vendor Sample Data</div>"
        "<div style='width:32px;height:3px;background:#1a6fd4;border-radius:2px;margin-top:4px;'></div>"
        "<div style='font-size:12px;color:#64748b;margin-top:6px;font-weight:400;'>"
        "Review expected values for LocalAccount (parent), LocalActual (parent), and LocalUnusedLeavePayment (child)."
        "</div>"
        "</div>",
        unsafe_allow_html=True,
    )

    def render_editable_sample(entity_key, rows_key):
        rows   = st.session_state[rows_key]
        edited = st.data_editor(
            pd.DataFrame(rows),
            key=f"ul_editor_{entity_key}",
            width="stretch",
            num_rows="dynamic",
            hide_index=True,
        )
        st.session_state[rows_key] = edited.to_dict(orient="records")
        return edited

    fin_sample_tabs = st.tabs(["📋 LocalAccount", "📊 LocalActual", "🏖️ LocalUnusedLeavePayment"])
    finance_sample_dfs = {}
    for tab_widget, res in zip(fin_sample_tabs, PAGE_RESOURCES):
        with tab_widget:
            finance_sample_dfs[res] = render_editable_sample(res.lower(), f"finance_sample_{res}")

    st.divider()

    # ════════════════════════════════════════════════════════════════════
    # API ENDPOINTS MANAGER
    # ════════════════════════════════════════════════════════════════════
    with st.expander("⚙️ API Endpoint Configuration", expanded=False):
        hdr_c1, hdr_c2 = st.columns([0.85, 0.15], gap="small")
        with hdr_c1:
            st.markdown(
                "<span style='font-size:11px;font-weight:600;color:#64748b;'>"
                "Configured Ed-Fi ODS endpoints — URLs resolve automatically when Account ID is updated"
                "</span>",
                unsafe_allow_html=True,
            )
        with hdr_c2:
            if st.button("+ Add", key="ul_ep_add", type="primary", use_container_width=True):
                new_id = f"ul_ep_{len(st.session_state.finance_api_endpoints)+10}"
                st.session_state.finance_api_endpoints.append({
                    "id": new_id, "resource": "Custom",
                    "template": f"{FINANCE_BASE_IDOE}/",
                    "url": f"{FINANCE_BASE_IDOE}/",
                    "active": True,
                })
                st.rerun()

        st.markdown("<div style='margin:6px 0;'></div>", unsafe_allow_html=True)
        to_delete   = []
        fetch_ep_id = None

        page_endpoints = [ep for ep in st.session_state.finance_api_endpoints if ep.get("resource") in PAGE_RESOURCES]
        for idx, ep in enumerate(page_endpoints):
            col1, col2, col3 = st.columns([0.85, 0.08, 0.07], gap="small")
            ep_obj = next((e for e in st.session_state.finance_api_endpoints if e.get("id") == ep.get("id")), None)
            with col1:
                if ep_obj:
                    new_url = st.text_input(
                        label=f"ul_ep_url_{idx}",
                        value=ep_obj["url"],
                        key=f"ul_ep_url_{ep.get('id', idx)}",
                        label_visibility="collapsed",
                        placeholder="https://...",
                    )
                    if new_url != ep_obj["url"]:
                        ep_obj["url"] = new_url
            with col2:
                if st.button("📊", key=f"ul_ep_fetch_{ep.get('id', idx)}", use_container_width=True, help="Fetch Data"):
                    fetch_ep_id = ep.get("id", idx)
            with col3:
                if st.button("🗑️", key=f"ul_ep_del_{ep.get('id', idx)}", use_container_width=True):
                    to_delete.append(ep.get("id", idx))

        if to_delete:
            st.session_state.finance_api_endpoints = [e for e in st.session_state.finance_api_endpoints if e.get("id") not in to_delete]
            st.rerun()

        if fetch_ep_id:
            endpoint_to_fetch = next((ep for ep in st.session_state.finance_api_endpoints if ep.get("id") == fetch_ep_id), None)
            if endpoint_to_fetch:
                st.markdown("<div style='margin:12px 0;'></div>", unsafe_allow_html=True)
                st.divider()
                fetch_url = endpoint_to_fetch.get("url", "")
                with st.expander(f"📊 Live Data: {endpoint_to_fetch.get('resource', 'Custom')}", expanded=True):
                    st.markdown(f"**URL:** `{fetch_url}`")
                    if not fetch_url:
                        st.warning("⚠️ No URL configured for this endpoint.")
                    else:
                        try:
                            token = get_bearer_token()
                            r   = requests.get(fetch_url, headers={"Authorization": f"Bearer {token}"}, timeout=15)
                            st.caption(f"HTTP Status: {r.status_code}")
                            try:
                                resp_data = r.json()
                                records   = resp_data if isinstance(resp_data, list) else resp_data.get("value", resp_data)
                                if isinstance(records, list) and len(records) > 0:
                                    st.success(f"✅ {len(records)} record(s) returned")
                                    st.json(resp_data)
                                elif isinstance(records, list) and len(records) == 0:
                                    st.warning("⚠️ HTTP 200 but 0 records returned — AccountIdentifier may not exist in the system")
                                    st.json(resp_data)
                                else:
                                    st.json(resp_data)
                            except Exception:
                                st.write(r.text)
                        except requests.exceptions.ConnectionError as e:
                            st.error(f"❌ Connection Error: {str(e)}")
                        except requests.exceptions.Timeout:
                            st.error("❌ Request timed out — API may be unreachable")
                        except Exception as e:
                            st.error(f"❌ Error: {str(e)}")

    st.divider()

    # ════════════════════════════════════════════════════════════════════
    # STEP 3 — FETCH & VALIDATE
    # ════════════════════════════════════════════════════════════════════
    btn_c, _sp2 = st.columns([2, 3])
    with btn_c:
        st.markdown(
            "<div style='margin-bottom:8px;'>"
            "<span style='font-size:11px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;"
            "color:#1a6fd4;'>Step 3</span>"
            "<div style='font-size:17px;font-weight:800;color:#0d2d5e;margin-top:1px;'>Fetch &amp; Validate</div>"
            "<div style='width:32px;height:3px;background:#1a6fd4;border-radius:2px;margin-top:4px;'></div>"
            "<div style='font-size:12px;color:#64748b;margin-top:6px;margin-bottom:12px;font-weight:400;'>"
            "Pull live data from the Ed-Fi ODS and run validations for LocalAccount, LocalActual, and LocalUnusedLeavePayment."
            "</div>"
            "</div>",
            unsafe_allow_html=True,
        )
        run = st.button("▶  Run Unused Leave Payment Validation", type="primary", width="stretch")

    if run:
        if not fin_pairs:
            st.error("❌ Please enter at least one Account Identifier.")
        else:
            st.session_state.ul_api_debug_info = []
            st.session_state.finance_api_debug_info = []
            finance_target_dfs = {res: [] for res in PAGE_RESOURCES}

            def make_null(res_name, rec_num, status="SKIPPED"):
                cols = FINANCE_COLS[res_name]
                row  = {c: "" for c in cols}
                row["_api_status"] = status
                row["_record_num"] = rec_num
                df = pd.DataFrame([row])
                for c in cols:
                    df[c] = df[c].astype(object)
                return df

            with st.spinner(f"Fetching data for {len(fin_pairs)} record(s)…"):
                for acc_id, edorg_id, fiscal_year, rec_num in fin_pairs:
                    for res in PAGE_RESOURCES:
                        ep_obj = next(
                            (e for e in st.session_state.finance_api_endpoints
                             if e.get("resource") == res and e.get("active", True)),
                            None,
                        )
                        if not ep_obj or not acc_id:
                            finance_target_dfs[res].append(make_null(res, rec_num, "SKIPPED"))
                            continue

                        url = build_resolved_url(ep_obj["template"], acc_id)
                        cols_list = FINANCE_COLS[res]
                        nested    = FINANCE_NESTED.get(res, {})
                        df_r, fetch_status = fetch_api_single(
                            url, cols_list, nested=nested,
                            desc_cols=["FinancialCollectionDescriptor"],
                            show_debug=True,
                            debug_label=f"{res} | Record {rec_num} | {acc_id}",
                        )

                        if df_r is None:
                            df_r = make_null(res, rec_num, fetch_status)
                        else:
                            df_r["_record_num"] = rec_num
                            for c in cols_list:
                                if c in df_r.columns:
                                    df_r[c] = df_r[c].astype(object)

                        finance_target_dfs[res].append(df_r)

            qpm = {
                rec_num: {
                    "AccountIdentifier":      acc_id,
                    "EducationOrganizationId": edorg_id,
                    "FiscalYear":             fiscal_year,
                }
                for acc_id, edorg_id, fiscal_year, rec_num in fin_pairs
            }
            st.session_state["ul_query_params_map"] = qpm

            for res in PAGE_RESOURCES:
                parts = finance_target_dfs[res]
                all_cols = FINANCE_COLS[res] + ["_api_status", "_record_num"]
                aligned = []
                for p in parts:
                    p_clean = p.dropna(axis=1, how="all") if not p.empty else p
                    for col in all_cols:
                        if col not in p_clean.columns:
                            p_clean[col] = ""
                    aligned.append(p_clean[all_cols])
                st.session_state[f"ul_target_{res}"] = pd.concat(aligned, ignore_index=True)
            st.success(f"✅ Data fetched for {len(fin_pairs)} record(s).")

    # ════════════════════════════════════════════════════════════════════
    # RESULTS
    # ════════════════════════════════════════════════════════════════════
    if all(f"ul_target_{res}" in st.session_state for res in PAGE_RESOURCES):

        # ── Result 1: API Response ────────────────────────────────────────
        _result_heading(
            "Result 1 · API Response",
            "Vendor-Submitted Data",
            "Raw records returned from the ODS API. 🔴 NOT FOUND = HTTP error &nbsp;·&nbsp; 🟡 EMPTY = valid request but no records posted.",
        )

        def highlight_api_status(df):
            def row_style(row):
                status = row.get("_api_status", "FOUND")
                if status == "NOT_FOUND":
                    return ["background-color:#fee2e2;color:#dc2626;font-weight:600"] * len(row)
                if status == "EMPTY_RESPONSE":
                    return ["background-color:#fef9c3;color:#b45309;font-weight:600"] * len(row)
                return [""] * len(row)
            return df.style.apply(row_style, axis=1)

        problem_recs = []
        for res in PAGE_RESOURCES:
            df_t = st.session_state[f"ul_target_{res}"]
            if "_api_status" in df_t.columns:
                for status_val, label in [("NOT_FOUND", "🔴 NOT FOUND"), ("EMPTY_RESPONSE", "🟡 EMPTY RESPONSE")]:
                    nf = df_t[df_t["_api_status"] == status_val]
                    if not nf.empty and "_record_num" in nf.columns:
                        for rn in sorted(nf["_record_num"].unique()):
                            problem_recs.append(f"Record {rn} — {res} [{label}]")
        if problem_recs:
            st.error("Issues detected: " + "  |  ".join(problem_recs))

        target_tabs = st.tabs(["📋 LocalAccount", "📊 LocalActual", "🏖️ LocalUnusedLeavePayment"])
        for tab_widget, res in zip(target_tabs, PAGE_RESOURCES):
            with tab_widget:
                df_t         = st.session_state[f"ul_target_{res}"]
                display_cols = [c for c in df_t.columns if not c.startswith("_")]
                show_df      = df_t[display_cols + ["_api_status"]].copy() if "_api_status" in df_t.columns else df_t[display_cols].copy()
                show_df      = safe_df_for_display(show_df)
                st.dataframe(highlight_api_status(show_df), width="stretch", hide_index=True)

        st.divider()

        # ── Result 2: Field Validation ────────────────────────────────────
        _result_heading(
            "Result 2 · Data Quality",
            "Field-Level Validation",
            "Each field verified against query parameters, format rules, Ed-Fi dimension code APIs, and AccountIdentifier structure (Section-Fund-Function-Object-OperationalUnit-SubCategory).",
        )

        qpm = st.session_state.get("ul_query_params_map", {})

        # Enrich qpm with LocalAccount row data for AccountIdentifier structure validation
        acct_df = st.session_state.get("ul_target_LocalAccount", pd.DataFrame())
        enriched_qpm = {}
        for rec_num, params in qpm.items():
            row_data = params.copy()
            if not acct_df.empty and "_record_num" in acct_df.columns:
                matching = acct_df[acct_df["_record_num"] == rec_num]
                if not matching.empty:
                    row_data["_local_account_row"] = matching.iloc[0].to_dict()
            enriched_qpm[rec_num] = row_data

        finance_val_dfs = {}
        for res in PAGE_RESOURCES:
            df_t = st.session_state[f"ul_target_{res}"]
            finance_val_dfs[res] = run_finance_validation(df_t, enriched_qpm)

        def entity_status_fin(vdf):
            if vdf.empty:
                return "❌ FAIL"
            n = int((vdf["Status"] == "❌ Invalid").sum())
            return "✅ PASS" if n == 0 else f"❌ FAIL ({n})"

        fin_stat_cols = st.columns(3)
        res_labels = {
            "LocalAccount": "Account",
            "LocalActual": "Actual",
            "LocalUnusedLeavePayment": "Unused Leave",
        }
        for ui_col, res in zip(fin_stat_cols, PAGE_RESOURCES):
            vdf     = finance_val_dfs[res]
            status  = entity_status_fin(vdf)
            is_pass = status.startswith("✅")
            top_c   = "#16a34a" if is_pass else "#dc2626"
            bg_c    = "#f0fdf4" if is_pass else "#fef2f2"
            pill_bg = "#dcfce7" if is_pass else "#fee2e2"
            pill_fg = "#16a34a" if is_pass else "#dc2626"
            total   = len(vdf)
            valid   = int((vdf["Status"] == "✅ Valid").sum()) if not vdf.empty else 0
            invalid = int((vdf["Status"] == "❌ Invalid").sum()) if not vdf.empty else 0
            with ui_col:
                short_name = res_labels.get(res, res.replace("Local", ""))
                st.markdown(
                    f"<div style='background:{bg_c};border:1px solid #e2e8f0;border-top:3px solid {top_c};"
                    f"border-radius:10px;padding:18px;'>"
                    f"<div style='font-size:12px;font-weight:700;color:#64748b;margin-bottom:12px;'>{short_name}</div>"
                    f"<div style='display:flex;justify-content:space-between;margin-bottom:5px;'>"
                    f"<span style='font-size:12px;color:#94a3b8;'>Total Fields</span>"
                    f"<span style='font-size:20px;font-weight:800;color:#0d2d5e;'>{total}</span></div>"
                    f"<div style='display:flex;justify-content:space-between;margin-bottom:5px;'>"
                    f"<span style='font-size:12px;color:#16a34a;'>✅ Valid</span>"
                    f"<span style='font-size:16px;font-weight:700;color:#16a34a;'>{valid}</span></div>"
                    f"<div style='display:flex;justify-content:space-between;margin-bottom:14px;'>"
                    f"<span style='font-size:12px;color:#dc2626;'>❌ Invalid</span>"
                    f"<span style='font-size:16px;font-weight:700;color:#dc2626;'>{invalid}</span></div>"
                    f"<span style='background:{pill_bg};color:{pill_fg};font-size:12px;font-weight:700;"
                    f"padding:4px 14px;border-radius:50px;'>{status}</span>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

        st.markdown("<br>", unsafe_allow_html=True)
        val_tabs = st.tabs(["📋 LocalAccount", "📊 LocalActual", "🏖️ LocalUnusedLeavePayment"])
        for tab_widget, res in zip(val_tabs, PAGE_RESOURCES):
            with tab_widget:
                vdf = finance_val_dfs[res]
                if vdf.empty:
                    st.warning(f"No data for {res}")
                else:
                    st.dataframe(style_validation_df(prep_display_df(vdf)), width="stretch", hide_index=True)

        st.divider()

        # Collect target dfs for cross validations
        all_target_dfs = {res: st.session_state[f"ul_target_{res}"] for res in PAGE_RESOURCES}

        # ── Result 3: Business Rules — LocalUnusedLeavePayment ────────────
        _result_heading(
            "Result 3 · Financial Integrity",
            "Business Rule Validation — Local Unused Leave Payment",
            "Core calculations: Direct + Indirect amounts · PaymentDate sequence · Reasonability & anomaly checks",
        )

        biz_df = run_business_rules_for_resource("LocalUnusedLeavePayment",
                                                  st.session_state["ul_target_LocalUnusedLeavePayment"])

        def biz_status(bdf):
            if bdf.empty:
                return "⏭ N/A"
            fails = int((bdf["Status"] == "❌ Fail").sum())
            return "✅ PASS" if fails == 0 else f"❌ FAIL ({fails})"

        total  = len(biz_df)
        passes = int((biz_df["Status"] == "✅ Pass").sum()) if not biz_df.empty else 0
        fails  = int((biz_df["Status"] == "❌ Fail").sum()) if not biz_df.empty else 0
        flags  = int((biz_df["Status"] == "⚠️ Flag").sum()) if not biz_df.empty else 0

        b1, b2, b3, b4 = st.columns(4)
        for col, label, val, color in [
            (b1, "Rules Checked", total, "#0d2d5e"),
            (b2, "✅ Pass", passes, "#16a34a"),
            (b3, "❌ Fail", fails, "#dc2626"),
            (b4, "⚠️ Flag", flags, "#d97706"),
        ]:
            _stat_card(col, label, val, color)
        st.markdown("<br>", unsafe_allow_html=True)

        if biz_df.empty:
            st.info("No business rules evaluated — records may not have been fetched.")
        else:
            st.dataframe(style_validation_df(prep_display_df(biz_df)), width="stretch", hide_index=True)

        st.divider()

        # ── Result 4: Fund Classification ─────────────────────────────────
        _result_heading(
            "Result 4 · Fund & Classification",
            "Fund Code Purpose Alignment & ObjectCode Classification",
            "Capital funds must not be used for payroll/leave. ObjectCode must align with leave payment type.",
        )

        fund_class_df = run_fund_classification_validations(all_target_dfs)

        if fund_class_df.empty:
            st.info("No fund classification data available.")
        else:
            fc_pass  = int((fund_class_df["Status"] == "✅ Pass").sum())
            fc_fail  = int((fund_class_df["Status"] == "❌ Fail").sum())
            fc_flag  = int((fund_class_df["Status"] == "⚠️ Flag").sum())
            fc_total = len(fund_class_df)
            f1, f2, f3, f4 = st.columns(4)
            for col, label, val, color in [
                (f1, "Total Checks", fc_total, "#0d2d5e"),
                (f2, "✅ Pass", fc_pass, "#16a34a"),
                (f3, "❌ Fail", fc_fail, "#dc2626"),
                (f4, "⚠️ Flag", fc_flag, "#d97706"),
            ]:
                _stat_card(col, label, val, color)
            st.markdown("<br>", unsafe_allow_html=True)
            st.dataframe(style_validation_df(prep_display_df(fund_class_df)), width="stretch", hide_index=True)

        st.divider()

        # ── Result 5: Duplicate Detection ─────────────────────────────────
        _result_heading(
            "Result 5 · Duplicate Detection",
            "Duplicate Leave Payment Check",
            "Same employee leave payment must not appear multiple times. Financial values must not be double-counted.",
        )

        dup_df = run_duplicate_detection(all_target_dfs)

        if dup_df.empty:
            st.info("No duplicate detection data available.")
        else:
            dup_pass  = int((dup_df["Status"] == "✅ Pass").sum())
            dup_fail  = int((dup_df["Status"] == "❌ Fail").sum())
            dup_flag  = int((dup_df["Status"] == "⚠️ Flag").sum())
            dup_total = len(dup_df)
            d1, d2, d3, d4 = st.columns(4)
            for col, label, val, color in [
                (d1, "Total Checks", dup_total, "#0d2d5e"),
                (d2, "✅ Pass", dup_pass, "#16a34a"),
                (d3, "❌ Fail", dup_fail, "#dc2626"),
                (d4, "⚠️ Flag", dup_flag, "#d97706"),
            ]:
                _stat_card(col, label, val, color)
            st.markdown("<br>", unsafe_allow_html=True)
            st.dataframe(style_validation_df(prep_display_df(dup_df)), width="stretch", hide_index=True)

        st.divider()

        # ── Result 6: Lifecycle ───────────────────────────────────────────
        _result_heading(
            "Result 6 · Lifecycle & Process",
            "Transaction Lifecycle: Account → Actual → Unused Leave Payment",
            "LocalUnusedLeavePayment must have a corresponding LocalAccount and LocalActual foundation.",
        )

        lifecycle_df = run_lifecycle_validations(all_target_dfs)

        if lifecycle_df.empty:
            st.info("No lifecycle data available.")
        else:
            lc_pass  = int((lifecycle_df["Status"] == "✅ Pass").sum())
            lc_fail  = int((lifecycle_df["Status"] == "❌ Fail").sum())
            lc_skip  = int((lifecycle_df["Status"] == "⏭ Skipped").sum())
            lc_total = len(lifecycle_df)
            l1, l2, l3, l4 = st.columns(4)
            for col, label, val, color in [
                (l1, "Total Checks", lc_total, "#0d2d5e"),
                (l2, "✅ Pass", lc_pass, "#16a34a"),
                (l3, "❌ Fail", lc_fail, "#dc2626"),
                (l4, "⏭ Skipped", lc_skip, "#94a3b8"),
            ]:
                _stat_card(col, label, val, color)
            st.markdown("<br>", unsafe_allow_html=True)
            st.dataframe(style_validation_df(prep_display_df(lifecycle_df)), width="stretch", hide_index=True)

        st.divider()

        # ── Result 7: Descriptor Consistency ─────────────────────────────
        _result_heading(
            "Result 7 · Reporting Consistency",
            "FinancialCollectionDescriptor Consistency",
            "FinancialCollectionDescriptor must be consistent across all related records for the same account.",
        )

        desc_consistency_df = run_descriptor_consistency_check(all_target_dfs)

        if desc_consistency_df.empty:
            st.info("No descriptor consistency data available.")
        else:
            dc_pass  = int((desc_consistency_df["Status"] == "✅ Pass").sum())
            dc_fail  = int((desc_consistency_df["Status"] == "❌ Fail").sum())
            d1, d2, d3 = st.columns(3)
            for col, label, val, color in [
                (d1, "Total Checks", len(desc_consistency_df), "#0d2d5e"),
                (d2, "✅ Pass", dc_pass, "#16a34a"),
                (d3, "❌ Fail", dc_fail, "#dc2626"),
            ]:
                _stat_card(col, label, val, color)
            st.markdown("<br>", unsafe_allow_html=True)
            st.dataframe(style_validation_df(prep_display_df(desc_consistency_df)), width="stretch", hide_index=True)

        st.divider()

        # ── API Debug ─────────────────────────────────────────────────────
        with st.expander("🔍 Validation API Call Log", expanded=False):
            st.markdown(
                "<span style='font-size:11px;font-weight:600;color:#64748b;'>"
                "Dimension code and descriptor lookups performed during validation"
                "</span>",
                unsafe_allow_html=True,
            )
            debug_list = st.session_state.get("finance_api_debug_info", [])
            if debug_list:
                for label, full_url, status_code, items in debug_list:
                    found = status_code == 200 and len(items) > 0
                    badge = "✅ FOUND" if found else "❌ NOT FOUND"
                    with st.expander(f"📊 {label}  [{badge}]", expanded=False):
                        st.markdown(f"**Full URL:** `{full_url}`")
                        st.caption(f"HTTP Status: {status_code}  |  Records returned: {len(items)}")
                        if items:
                            try:
                                st.json(items if isinstance(items, list) else list(items))
                            except Exception:
                                st.write(items)
                        else:
                            st.info("No records returned from this API call.")
            else:
                st.info("ℹ️ No code/descriptor API validation calls to display for this run.")

        st.divider()

        # ── Export ────────────────────────────────────────────────────────
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            summary_rows = []
            for res in PAGE_RESOURCES:
                vdf = finance_val_dfs[res]
                summary_rows.append({
                    "Resource": res,
                    "Total Fields": len(vdf),
                    "Valid": int((vdf["Status"] == "✅ Valid").sum()) if not vdf.empty else 0,
                    "Invalid": int((vdf["Status"] == "❌ Invalid").sum()) if not vdf.empty else 0,
                    "Field Validation Status": entity_status_fin(vdf),
                })
            for sr in summary_rows:
                if sr["Resource"] == "LocalUnusedLeavePayment":
                    sr["Business Rules Checked"] = len(biz_df)
                    sr["Business Rules Pass"]    = int((biz_df["Status"] == "✅ Pass").sum()) if not biz_df.empty else 0
                    sr["Business Rules Fail"]    = int((biz_df["Status"] == "❌ Fail").sum()) if not biz_df.empty else 0
                    sr["Business Rule Status"]   = biz_status(biz_df)

            pd.DataFrame(summary_rows).to_excel(writer, sheet_name="Summary", index=False)
            for res in PAGE_RESOURCES:
                st.session_state[f"ul_target_{res}"].to_excel(writer, sheet_name=f"Target_{res[:15]}", index=False)
                if not finance_val_dfs[res].empty:
                    finance_val_dfs[res].to_excel(writer, sheet_name=f"FieldVal_{res[:13]}", index=False)
            if not biz_df.empty:
                biz_df.to_excel(writer, sheet_name="BizRules_UnusedLeave", index=False)
            if not fund_class_df.empty:
                fund_class_df.to_excel(writer, sheet_name="Fund_Classification", index=False)
            if not dup_df.empty:
                dup_df.to_excel(writer, sheet_name="Duplicate_Detection", index=False)
            if not lifecycle_df.empty:
                lifecycle_df.to_excel(writer, sheet_name="Lifecycle", index=False)
            if not desc_consistency_df.empty:
                desc_consistency_df.to_excel(writer, sheet_name="Descriptor_Consistency", index=False)

        dl_c, _sp3 = st.columns([2, 3])
        with dl_c:
            st.download_button(
                label="📥 Export Full Certification Report",
                data=output.getvalue(),
                file_name=f"EdWise_UnusedLeave_CertReport_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                width="stretch",
            )
