import streamlit as st
import pandas as pd
import requests
import re
import io
import base64
from datetime import datetime, timedelta, timezone
from auth import render_logout_button
import urllib.parse

# ── Import shared auth module ─────────────────────────────────────
from auth import render_login_page, render_logout_button, is_logged_in, get_vendor_creds, get_vendor_name

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
_creds             = get_vendor_creds()
FINANCE_TOKEN_URL  = _creds.get("token_url", "")
FINANCE_API_KEY    = _creds.get("api_key", "")
FINANCE_API_SECRET = _creds.get("api_secret", "")
FINANCE_BASE_EDFI  = _creds.get("finance_base_edfi", "")
FINANCE_BASE_IDOE  = _creds.get("finance_base_idoe", "")


FINANCE_CODE_APIS = {
    "FunctionCode":        f"{FINANCE_BASE_EDFI}/functionDimensions?fiscalYear=2025&code={{code}}",
    "FundCode":            f"{FINANCE_BASE_EDFI}/fundDimensions?fiscalYear=2025&code={{code}}",
    "ObjectCode":          f"{FINANCE_BASE_EDFI}/objectDimensions?fiscalYear=2025&code={{code}}",
    "OperationalUnitCode": f"{FINANCE_BASE_EDFI}/operationalUnitDimensions?fiscalYear=2025&code={{code}}",
    "SectionCode":         f"{FINANCE_BASE_IDOE}/sectionDimensions?fiscalYear=2025&code={{code}}",
    "SubCategoryCode":     f"{FINANCE_BASE_IDOE}/subCategoryDimensions?fiscalYear=2025&code={{code}}",
}

CHART_OF_ACCOUNTS_URL               = f"{FINANCE_BASE_EDFI}/chartOfAccounts?fiscalYear=2025"
FINANCIAL_COLLECTION_DESCRIPTOR_URL = f"{FINANCE_BASE_EDFI}/financialCollectionDescriptors"

# ── Code digit length rules ────────────────────────
CODE_LENGTH_RULES = {
    "FundCode":            4,
    "ObjectCode":          3,
    "OperationalUnitCode": 4,
    "SubCategoryCode":     2,
    "SectionCode":         1,
    "FunctionCode":        5,
}

# ── Financial Data Reset URLs ──────────────────────────────────────
RESET_ENDPOINTS = {
    "LocalActual":               f"{FINANCE_BASE_EDFI}/localActuals",
    "LocalCapitalizedEquipment": f"{FINANCE_BASE_IDOE}/localCapitalizedEquipment",
    "LocalSubaward":             f"{FINANCE_BASE_IDOE}/localSubawards",
    "LocalUnusedLeavePayment":   f"{FINANCE_BASE_IDOE}/localUnusedLeavePayments",
}

# ════════════════════════════════════════════════════════════════════
# FUND CLASSIFICATION RULES (Section 6)
# Capital fund codes should NOT be used for leave/payroll payments
# ════════════════════════════════════════════════════════════════════
CAPITAL_FUND_CODES = {"4200", "4300", "4400", "4500", "4600", "4700", "4800", "4900"}
PAYROLL_OBJECT_CODES = {"100", "110", "120", "130", "140", "150", "160", "170", "180", "190",
                        "200", "210", "220", "230", "240", "250", "260", "270", "280", "290"}
CAPITAL_FUNCTION_CODES = {"4000", "4100", "4200", "4300"}

# RecordIdentifier is mandatory only for these 3 resources
RECORD_IDENTIFIER_RESOURCES = {"LocalCapitalizedEquipment", "LocalSubaward", "LocalUnusedLeavePayment"}

# ════════════════════════════════════════════════════════════════════
# FINANCE RESOURCES & COLUMNS
# ════════════════════════════════════════════════════════════════════
FINANCE_RESOURCES = [
    "LocalAccount",
    "LocalActual",
    "LocalCapitalizedEquipment",
    "LocalSubaward",
    "LocalUnusedLeavePayment",
]

FINANCE_COLS = {
    "LocalAccount": [
        "AccountIdentifier","EducationOrganizationId","FiscalYear","AccountName",
        "ChartOfAccountIdentifier","ChartOfAccountEducationOrganizationId",
        "FunctionCode","FundCode","ObjectCode","OperationalUnitCode","SectionCode","SubCategoryCode",
    ],
    "LocalActual": [
        "AccountIdentifier","EducationOrganizationId","FiscalYear",
        "AsOfDate","Amount","FinancialCollectionDescriptor",
    ],
    "LocalCapitalizedEquipment": [
        "RecordIdentifier",
        "AccountIdentifier","EducationOrganizationId","FiscalYear",
        "AsOfDate","EquipmentType","EquipmentDescription","AcquisitionDate",
        "PaymentAmount","PerUnitCost","CapitalizedThreshold","FinancialCollectionDescriptor",
    ],
    "LocalSubaward": [
        "RecordIdentifier",
        "AccountIdentifier","EducationOrganizationId","FiscalYear",
        "AsOfDate","ContractNumberOfYears","DepartmentName","Excess50k",
        "ExpenditureAmount","First50k","SubawardAmount","VendorOrganizationName","FinancialCollectionDescriptor",
    ],
    "LocalUnusedLeavePayment": [
        "RecordIdentifier",
        "AccountIdentifier","EducationOrganizationId","FiscalYear",
        "AsOfDate","DirectUnusedLeavePaymentAmount","EmployeeName",
        "IndirectUnusedLeavePaymentAmount","JobTitle","PaymentDate","FinancialCollectionDescriptor",
    ],
}

FINANCE_SAMPLE_DEFAULTS = {
    "LocalAccount": {
        "AccountIdentifier": "S-1394-25110-940-5170-51",
        "EducationOrganizationId": 1094950000,
        "FiscalYear": 2025,
        "AccountName": "Local Property Taxes",
        "ChartOfAccountIdentifier": "IDOE-COA",
        "ChartOfAccountEducationOrganizationId": 1088000000,
        "FunctionCode": "25110",
        "FundCode": "1394",
        "ObjectCode": "940",
        "OperationalUnitCode": "5170",
        "SectionCode": "S",
        "SubCategoryCode": "51",
    },
    "LocalActual": {
        "AccountIdentifier": "S-1394-25110-940-5170-51",
        "EducationOrganizationId": 1094950000,
        "FiscalYear": 2025,
        "AsOfDate": "2025-10-06",
        "Amount": 10125,
        "FinancialCollectionDescriptor": "1",
    },
    "LocalCapitalizedEquipment": {
        "RecordIdentifier": "2c24fe1e-55cd-4b85-bf47-852a36c863dd",
        "AccountIdentifier": "S-1394-25110-940-5170-51",
        "EducationOrganizationId": 1094950000,
        "FiscalYear": 2025,
        "AsOfDate": "2025-10-06",
        "EquipmentType": "Bari Saxophone Eb",
        "EquipmentDescription": "Mini-bus",
        "AcquisitionDate": "2025-05-28",
        "PaymentAmount": 99645,
        "PerUnitCost": 11603,
        "CapitalizedThreshold": 5000,
        "FinancialCollectionDescriptor": "1",
    },
    "LocalSubaward": {
        "RecordIdentifier": "2c24fe1e-55cd-4b85-bf47-852a36c863dd",
        "AccountIdentifier": "S-1394-25110-940-5170-51",
        "EducationOrganizationId": 1094950000,
        "FiscalYear": 2025,
        "AsOfDate": "2025-10-06",
        "ContractNumberOfYears": 7,
        "DepartmentName": "Concord Community Schools",
        "Excess50k": 8409,
        "ExpenditureAmount": 24937,
        "First50k": 16528,
        "SubawardAmount": 12111,
        "VendorOrganizationName": "PTECH",
        "FinancialCollectionDescriptor": "1",
    },
    "LocalUnusedLeavePayment": {
        "RecordIdentifier": "2c24fe1e-55cd-4b85-bf47-852a36c863dd",
        "AccountIdentifier": "S-1394-25110-940-5170-51",
        "EducationOrganizationId": 1094950000,
        "FiscalYear": 2025,
        "AsOfDate": "2025-10-06",
        "DirectUnusedLeavePaymentAmount": 9213,
        "EmployeeName": "Vic Lilliman",
        "IndirectUnusedLeavePaymentAmount": 8162,
        "JobTitle": "EXECUTIVE ASSISTANT",
        "PaymentDate": "2025-09-03",
        "FinancialCollectionDescriptor": "1",
    },
}

FINANCE_API_ENDPOINT_TEMPLATES = {
    "LocalAccount":              f"{FINANCE_BASE_EDFI}/LocalAccounts?accountIdentifier={{AccountIdentifier}}",
    "LocalActual":               f"{FINANCE_BASE_EDFI}/localActuals?accountIdentifier={{AccountIdentifier}}",
    "LocalCapitalizedEquipment": f"{FINANCE_BASE_IDOE}/LocalCapitalizedEquipment?accountIdentifier={{AccountIdentifier}}",
    "LocalSubaward":             f"{FINANCE_BASE_IDOE}/LocalSubawards?accountIdentifier={{AccountIdentifier}}",
    "LocalUnusedLeavePayment":   f"{FINANCE_BASE_IDOE}/LocalUnusedLeavePayments?accountIdentifier={{AccountIdentifier}}",
}

FINANCE_NESTED = {
    "LocalAccount": {
        "AccountIdentifier": "accountIdentifier",
        "EducationOrganizationId": "educationOrganizationReference.educationOrganizationId",
        "FiscalYear": "fiscalYear",
        "AccountName": "accountName",
        "ChartOfAccountIdentifier": "chartOfAccountReference.accountIdentifier",
        "ChartOfAccountEducationOrganizationId": "chartOfAccountReference.educationOrganizationId",
        "FunctionCode": "_ext.idoe.functionDimensionReference.code",
        "FundCode": "_ext.idoe.fundDimensionReference.code",
        "ObjectCode": "_ext.idoe.objectDimensionReference.code",
        "OperationalUnitCode": "_ext.idoe.operationalUnitDimensionReference.code",
        "SectionCode": "_ext.idoe.sectionDimensionReference.code",
        "SubCategoryCode": "_ext.idoe.subCategoryDimensionReference.code",
    },
    "LocalActual": {
        "AccountIdentifier": "localAccountReference.accountIdentifier",
        "EducationOrganizationId": "localAccountReference.educationOrganizationId",
        "FiscalYear": "localAccountReference.fiscalYear",
        "AsOfDate": "asOfDate",
        "Amount": "amount",
        "FinancialCollectionDescriptor": "financialCollectionDescriptor",
    },
    "LocalCapitalizedEquipment": {
        "RecordIdentifier": "recordIdentifier",
        "AccountIdentifier": "localAccountReference.accountIdentifier",
        "EducationOrganizationId": "localAccountReference.educationOrganizationId",
        "FiscalYear": "localAccountReference.fiscalYear",
        "AsOfDate": "asOfDate",
        "EquipmentType": "equipmentType",
        "EquipmentDescription": "equipmentDescription",
        "AcquisitionDate": "acquisitionDate",
        "PaymentAmount": "paymentAmount",
        "PerUnitCost": "perUnitCost",
        "CapitalizedThreshold": "capitalizedThreshold",
        "FinancialCollectionDescriptor": "financialCollectionDescriptor",
    },
    "LocalSubaward": {
        "RecordIdentifier": "recordIdentifier",
        "AccountIdentifier": "localAccountReference.accountIdentifier",
        "EducationOrganizationId": "localAccountReference.educationOrganizationId",
        "FiscalYear": "localAccountReference.fiscalYear",
        "AsOfDate": "asOfDate",
        "ContractNumberOfYears": "contractNumberOfYears",
        "DepartmentName": "departmentName",
        "Excess50k": "excess50k",
        "ExpenditureAmount": "expenditureAmount",
        "First50k": "first50k",
        "SubawardAmount": "subawardAmount",
        "VendorOrganizationName": "vendorOrganizationName",
        "FinancialCollectionDescriptor": "financialCollectionDescriptor",
    },
    "LocalUnusedLeavePayment": {
        "RecordIdentifier": "recordIdentifier",
        "AccountIdentifier": "localAccountReference.accountIdentifier",
        "EducationOrganizationId": "localAccountReference.educationOrganizationId",
        "FiscalYear": "localAccountReference.fiscalYear",
        "AsOfDate": "asOfDate",
        "DirectUnusedLeavePaymentAmount": "directUnusedLeavePaymentAmount",
        "EmployeeName": "employeeName",
        "IndirectUnusedLeavePaymentAmount": "indirectUnusedLeavePaymentAmount",
        "JobTitle": "jobTitle",
        "PaymentDate": "paymentDate",
        "FinancialCollectionDescriptor": "financialCollectionDescriptor",
    },
}

# ════════════════════════════════════════════════════════════════════
# HELPERS
# ════════════════════════════════════════════════════════════════════
def build_resolved_url(template, acc_id=""):
    return template.replace("{AccountIdentifier}", acc_id)


def _is_empty(val):
    if val is None:
        return True
    if isinstance(val, float) and pd.isna(val):
        return True
    return str(val).strip().lower() in ("", "none", "nan", "null", "<na>")


def _to_float(val):
    try:
        return float(str(val).strip())
    except Exception:
        return None


def strip_descriptor_code(v):
    if isinstance(v, str) and "#" in v:
        return v.split("#")[-1]
    return v


def safe_df_for_display(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in out.columns:
        if col.startswith("_"):
            continue
        out[col] = out[col].apply(
            lambda v: "" if (v is None or (isinstance(v, float) and pd.isna(v)) or str(v).lower() in ("nan", "none", "null", "<na>"))
            else str(v)
        )
    return out


# ════════════════════════════════════════════════════════════════════
# SESSION STATE
# ════════════════════════════════════════════════════════════════════
if "finance_num_records" not in st.session_state:
    st.session_state.finance_num_records = 1
if "finance_record_data" not in st.session_state:
    st.session_state.finance_record_data = [
        {"account_id": "S-1394-25110-940-5170-51", "edorg_id": "1094950000", "fiscal_year": "2025"}
    ]
for res in FINANCE_RESOURCES:
    key = f"finance_sample_{res}"
    if key not in st.session_state:
        st.session_state[key] = [FINANCE_SAMPLE_DEFAULTS[res].copy()]

if "finance_api_endpoints" not in st.session_state:
    first_acc = st.session_state.finance_record_data[0].get("account_id", "")
    st.session_state.finance_api_endpoints = [
        {
            "id": f"fep_{i}",
            "resource": res,
            "template": FINANCE_API_ENDPOINT_TEMPLATES[res],
            "url": build_resolved_url(FINANCE_API_ENDPOINT_TEMPLATES[res], first_acc),
            "active": True,
        }
        for i, res in enumerate(FINANCE_RESOURCES)
    ]
if "finance_api_debug_info" not in st.session_state:
    st.session_state.finance_api_debug_info = []

# Budget input in session state (Section 3)
if "approved_budget_map" not in st.session_state:
    st.session_state.approved_budget_map = {}


# ════════════════════════════════════════════════════════════════════
# PROPAGATE QUERY PARAMS
# ════════════════════════════════════════════════════════════════════
def propagate_query_params_to_all(acc_id, edorg_id, fiscal_year, record_index=0):
    for res in FINANCE_RESOURCES:
        key = f"finance_sample_{res}"
        samples = st.session_state.get(key, [])
        while len(samples) <= record_index:
            samples.append(FINANCE_SAMPLE_DEFAULTS[res].copy())
        if acc_id:
            samples[record_index]["AccountIdentifier"] = acc_id
        try:
            if edorg_id:
                samples[record_index]["EducationOrganizationId"] = int(edorg_id)
        except Exception:
            pass
        try:
            if fiscal_year:
                samples[record_index]["FiscalYear"] = int(fiscal_year)
        except Exception:
            pass
        st.session_state[key] = samples

    if record_index == 0 and acc_id:
        for ep in st.session_state.finance_api_endpoints:
            ep["url"] = build_resolved_url(ep["template"], acc_id)


# ════════════════════════════════════════════════════════════════════
# API HELPERS
# ════════════════════════════════════════════════════════════════════
def get_bearer_token():
    cache_key = "token_info_finance"
    if cache_key in st.session_state:
        ti = st.session_state[cache_key]
        if datetime.now(timezone.utc) < ti["expiry"]:
            return ti["access_token"]
    enc = base64.b64encode(f"{FINANCE_API_KEY}:{FINANCE_API_SECRET}".encode()).decode()
    r = requests.post(
        FINANCE_TOKEN_URL,
        headers={"Authorization": f"Basic {enc}", "Content-Type": "application/x-www-form-urlencoded"},
        data={"grant_type": "client_credentials"},
    )
    r.raise_for_status()
    d = r.json()
    st.session_state[cache_key] = {
        "access_token": d["access_token"],
        "expiry": datetime.now(timezone.utc) + timedelta(seconds=d["expires_in"]),
    }
    return d["access_token"]


def extract_nested(record, path):
    parts = path.replace("[", ".").replace("]", "").split(".")
    val = record
    for p in parts:
        if val is None:
            return None
        if p.isdigit() and isinstance(val, list):
            val = val[int(p)] if len(val) > int(p) else None
        elif isinstance(val, dict):
            val = val.get(p)
        else:
            val = None
    return val


def fetch_api_single(url, cols, nested=None, desc_cols=None, show_debug=True, debug_label=None):
    token = get_bearer_token()
    label_text = debug_label if debug_label else url

    if show_debug:
        with st.expander(f"🔍 API Debug — {label_text}", expanded=False):
            st.markdown(f"**Full URL:** `{url}`")
            r = requests.get(url, headers={"Authorization": f"Bearer {token}"})
            st.caption(f"Status: {r.status_code}")
            try:
                st.json(r.json())
            except Exception:
                st.write(r.text)
    else:
        r = requests.get(url, headers={"Authorization": f"Bearer {token}"})

    if r.status_code != 200:
        return None, "NOT_FOUND"

    try:
        data = r.json()
    except Exception:
        return None, "NOT_FOUND"

    recs = data if isinstance(data, list) else data.get("value", [])

    if not recs:
        return None, "EMPTY_RESPONSE"

    rows = []
    for rec in recs:
        row = {}
        if nested:
            for tc, path in nested.items():
                row[tc] = extract_nested(rec, path)
        flat = pd.json_normalize(rec).to_dict(orient="records")[0]
        for col in cols:
            if col not in row:
                row[col] = flat.get(col, flat.get(col[0].lower() + col[1:], None))
        row["_api_status"] = "FOUND"
        rows.append(row)

    df = pd.DataFrame(rows)
    for c in cols:
        if c not in df.columns:
            df[c] = None
    if "_api_status" not in df.columns:
        df["_api_status"] = "FOUND"
    if desc_cols:
        for c in desc_cols:
            if c in df.columns:
                df[c] = df[c].apply(strip_descriptor_code)
    return df, "FOUND"


# ════════════════════════════════════════════════════════════════════
# CODE / DESCRIPTOR VALIDATION VIA API
# ════════════════════════════════════════════════════════════════════
def _api_lookup(full_url, debug_label):
    try:
        token = get_bearer_token()
        r = requests.get(full_url, headers={"Authorization": f"Bearer {token}"}, timeout=10)
        data = r.json() if r.status_code == 200 else {}
        items = data if isinstance(data, list) else data.get("value", [])
        found = r.status_code == 200 and len(items) > 0
        debug_entry = (debug_label, full_url, r.status_code, items)
        existing = st.session_state.finance_api_debug_info
        if not any(e[1] == full_url for e in existing):
            existing.append(debug_entry)
        return found, r.status_code, len(items)
    except Exception:
        debug_entry = (debug_label, full_url, 0, [])
        existing = st.session_state.finance_api_debug_info
        if not any(e[1] == full_url for e in existing):
            existing.append(debug_entry)
        return False, 0, 0


def check_dimension_code_via_api(field_name, code_value):
    template = FINANCE_CODE_APIS.get(field_name)
    if not template:
        return True, f"No API validation configured for {field_name}"
    full_url = template.replace("{code}", str(code_value))
    label = f"{field_name} Code Validation (code={code_value})"
    found, status, count = _api_lookup(full_url, label)
    if found:
        return True, f"✓ Code '{code_value}' found in {field_name} API (fiscalYear=2025)"
    if status == 0:
        return False, f"Connection error — {field_name} API unreachable"
    return False, f"✗ Code '{code_value}' NOT found in {field_name} API (fiscalYear=2025)"


def check_chart_of_accounts_via_api(account_identifier, edorg_id):
    full_url = (
        f"{CHART_OF_ACCOUNTS_URL}"
        f"&accountIdentifier={account_identifier}"
        f"&educationOrganizationId={edorg_id}"
    )
    label = f"ChartOfAccounts Validation (accountIdentifier={account_identifier}, edOrgId={edorg_id})"
    found, status, count = _api_lookup(full_url, label)
    if found:
        return True, f"✓ Chart of Accounts entry found — accountIdentifier='{account_identifier}', edOrgId='{edorg_id}'"
    if status == 0:
        return False, "Connection error — Chart of Accounts API unreachable"
    return False, f"✗ Chart of Accounts entry NOT found — accountIdentifier='{account_identifier}', edOrgId='{edorg_id}'"


def check_financial_collection_descriptor_via_api(raw_value):
    code_value = strip_descriptor_code(str(raw_value).strip())
    full_url = f"{FINANCIAL_COLLECTION_DESCRIPTOR_URL}?codeValue={code_value}"
    label = f"FinancialCollectionDescriptor Validation (codeValue={code_value})"
    found, status, count = _api_lookup(full_url, label)
    if found:
        return code_value, True, f"✓ Descriptor code '{code_value}' found in FinancialCollectionDescriptor API"
    if status == 0:
        return code_value, False, "Connection error — FinancialCollectionDescriptor API unreachable"
    return code_value, False, f"✗ Descriptor code '{code_value}' NOT found in FinancialCollectionDescriptor API"

# ════════════════════════════════════════════════════════════════════
# CODE LENGTH VALIDATION HELPER
# ════════════════════════════════════════════════════════════════════
def validate_code_length(field_name, val_str):
    required_len = CODE_LENGTH_RULES.get(field_name)
    if required_len is None:
        return True, None

    actual_len = len(val_str)
    if actual_len == required_len:
        return True, (
            f"✓ {field_name} '{val_str}' has correct fixed length of {required_len} digit(s). "
            f"Code length complies with ODS data posting requirement."
        )
    elif actual_len < required_len:
        expected_padded = val_str.zfill(required_len)
        return False, (
            f"✗ {field_name} '{val_str}' has {actual_len} digit(s) but must be exactly {required_len} digit(s). "
            f"Codes must be zero-padded to a fixed length of {required_len} digit(s) per ODS data posting rules. "
            f"Expected format: '{expected_padded}' (prefix with {required_len - actual_len} zero(s))."
        )
    else:
        return False, (
            f"✗ {field_name} '{val_str}' has {actual_len} digit(s) but must be exactly {required_len} digit(s). "
            f"Code exceeds the fixed length requirement of {required_len} digit(s) per ODS data posting rules."
        )

# ════════════════════════════════════════════════════════════════════
# FIELD-LEVEL VALIDATION
# ════════════════════════════════════════════════════════════════════
def validate_finance_field(field_name, value, query_params=None, resource_name=None):
    if _is_empty(value):
        if field_name == "RecordIdentifier" and resource_name in RECORD_IDENTIFIER_RESOURCES:
            return False, (
                f"❗ RecordIdentifier is a MANDATORY field for {resource_name}. "
                "A unique alphanumeric record identifier must be posted for every record in this resource. "
                "This field uniquely identifies each transaction record in the ODS."
            )
        return False, f"❗ Missing value — '{field_name}' is required but was not populated in the API response"

    val_str = str(value).strip()
    qp = query_params or {}

    if field_name == "RecordIdentifier":
        if resource_name in RECORD_IDENTIFIER_RESOURCES:
            if re.match(r"^[A-Za-z0-9\-_]+$", val_str):
                return True, (
                    f"✓ RecordIdentifier '{val_str}' is present and valid. "
                    f"This unique alphanumeric identifier correctly identifies this {resource_name} transaction record."
                )
            else:
                return False, (
                    f"✗ RecordIdentifier '{val_str}' contains invalid characters. "
                    "RecordIdentifier must be alphanumeric (letters, digits, hyphens, underscores only). "
                    f"This field is mandatory for {resource_name} and must uniquely identify each record."
                )
        else:
            return True, f"✓ RecordIdentifier '{val_str}' is present."

    if field_name == "AccountIdentifier":
        expected = str(qp.get("AccountIdentifier", "")).strip()
        if expected and val_str != expected:
            return False, (
                f"✗ Mismatch — API returned '{val_str}' but query param is '{expected}'. "
                "AccountIdentifier must match the requested query parameter exactly."
            )
        if not re.match(r"^[A-Za-z0-9\-]+$", val_str):
            return False, f"✗ Invalid format — '{val_str}' contains invalid characters (expected alphanumeric + hyphens)"
        return True, f"✓ AccountIdentifier '{val_str}' matches query param and format is valid"

    if field_name == "EducationOrganizationId":
        expected = str(qp.get("EducationOrganizationId", "")).strip()
        try: int_val = int(float(val_str))
        except Exception: return False, f"✗ Must be numeric — got '{val_str}'"
        if expected and str(int_val) != expected:
            return False, (
                f"✗ Mismatch — API returned '{int_val}' but query param is '{expected}'. "
                "EducationOrganizationId must match the requested query parameter exactly."
            )
        return True, f"✓ EducationOrganizationId '{int_val}' matches query param and is valid numeric"

    if field_name == "FiscalYear":
        expected = str(qp.get("FiscalYear", "")).strip()
        try: yr = int(float(val_str))
        except Exception: return False, f"✗ Must be numeric — got '{val_str}'"
        if not (2000 <= yr <= 2100): return False, f"✗ Year '{yr}' is out of expected range (2000–2100)"
        if expected and str(yr) != expected:
            return False, (
                f"✗ Mismatch — API returned '{yr}' but query param is '{expected}'. "
                "FiscalYear must match the requested query parameter exactly."
            )
        return True, f"✓ FiscalYear '{yr}' matches query param and is within valid range"

    if field_name == "AccountName":
        if len(val_str) == 0: return False, "✗ AccountName is empty — a non-empty text value is required"
        return True, f"✓ AccountName is a valid character string: '{val_str}'"

    if field_name == "ChartOfAccountIdentifier":
        if len(val_str) == 0: return False, "✗ ChartOfAccountIdentifier is empty"
        return True, f"✓ ChartOfAccountIdentifier '{val_str}' is a non-empty string (API cross-check done separately)"

    if field_name == "ChartOfAccountEducationOrganizationId":
        try: int(float(val_str))
        except Exception: return False, f"✗ ChartOfAccountEducationOrganizationId must be numeric — got '{val_str}'"
        return True, f"✓ ChartOfAccountEducationOrganizationId '{val_str}' is valid numeric (API cross-check done separately)"

    if field_name in CODE_LENGTH_RULES:
        length_valid, length_reason = validate_code_length(field_name, val_str)
        if not length_valid:
            return False, length_reason
        if field_name in FINANCE_CODE_APIS:
            api_valid, api_reason = check_dimension_code_via_api(field_name, val_str)
            if api_valid:
                return True, f"{length_reason} | API: {api_reason}"
            else:
                return False, f"{length_reason} | API: {api_reason}"
        return True, length_reason

    if field_name == "FinancialCollectionDescriptor":
        code_val, is_valid, reason = check_financial_collection_descriptor_via_api(val_str)
        return is_valid, reason

    if field_name in ("AsOfDate", "AcquisitionDate", "PaymentDate"):
        if re.match(r"^\d{4}-\d{2}-\d{2}$", val_str):
            try:
                datetime.strptime(val_str, "%Y-%m-%d")
                return True, f"✓ '{field_name}' is a valid date in YYYY-MM-DD format: '{val_str}'"
            except ValueError: return False, f"✗ '{val_str}' is not a real calendar date — check day/month values"
        return False, f"✗ '{field_name}' has invalid format '{val_str}' — expected YYYY-MM-DD"

    numeric_fields = {
        "Amount": "Transaction amount",
        "PaymentAmount": "Payment amount",
        "PerUnitCost": "Per-unit cost",
        "CapitalizedThreshold": "Capitalization threshold",
        "Excess50k": "Excess over $50k",
        "ExpenditureAmount": "Expenditure amount",
        "First50k": "First $50k portion",
        "SubawardAmount": "Subaward amount",
        "DirectUnusedLeavePaymentAmount": "Direct unused leave payment",
        "IndirectUnusedLeavePaymentAmount": "Indirect unused leave payment",
    }
    if field_name in numeric_fields:
        try: num = float(val_str)
        except Exception: return False, f"✗ {numeric_fields[field_name]} must be numeric — got '{val_str}'"
        if num < 0: return False, f"✗ {numeric_fields[field_name]} should be non-negative — got '{num}'"
        return True, f"✓ {numeric_fields[field_name]} is valid: {num}"

    if field_name == "ContractNumberOfYears":
        try:
            num = float(val_str)
            if num < 0 or num != int(num): return False, f"✗ ContractNumberOfYears must be a non-negative integer — got '{val_str}'"
            return True, f"✓ ContractNumberOfYears is valid non-negative integer: {int(num)}"
        except Exception: return False, f"✗ ContractNumberOfYears must be numeric — got '{val_str}'"

    char_fields = {
        "EquipmentType": "Equipment type",
        "EquipmentDescription": "Equipment description",
        "DepartmentName": "Department name",
        "VendorOrganizationName": "Vendor organization name",
        "EmployeeName": "Employee name",
        "JobTitle": "Job title",
    }
    if field_name in char_fields:
        if len(val_str) == 0: return False, f"✗ {char_fields[field_name]} is an empty string — a non-empty character value is required"
        return True, f"✓ {char_fields[field_name]} is a valid character string: '{val_str}'"

    return True, f"✓ Value present: '{val_str}'"

# ════════════════════════════════════════════════════════════════════
# SECTION 1 — CORE CALCULATION VALIDATIONS
# ════════════════════════════════════════════════════════════════════
def run_capitalized_equipment_business_rules(row, rec_num):
    results = []
    pay   = _to_float(row.get("PaymentAmount"))
    unit  = _to_float(row.get("PerUnitCost"))
    cap_t = _to_float(row.get("CapitalizedThreshold"))

    if pay is not None and unit is not None:
        if unit <= pay:
            results.append({
                "Record #": rec_num,
                "Rule": "PerUnitCost ≤ PaymentAmount",
                "Fields Involved": "PerUnitCost, PaymentAmount",
                "Values": f"PerUnitCost={unit}, PaymentAmount={pay}",
                "Status": "✅ Pass",
                "Reason": f"✓ PerUnitCost ({unit}) ≤ PaymentAmount ({pay}) — rule satisfied",
            })
        else:
            results.append({
                "Record #": rec_num,
                "Rule": "PerUnitCost ≤ PaymentAmount",
                "Fields Involved": "PerUnitCost, PaymentAmount",
                "Values": f"PerUnitCost={unit}, PaymentAmount={pay}",
                "Status": "❌ Fail",
                "Reason": f"✗ PerUnitCost ({unit}) exceeds PaymentAmount ({pay}) — per-unit cost cannot exceed total payment",
            })
    else:
        results.append({
            "Record #": rec_num,
            "Rule": "PerUnitCost ≤ PaymentAmount",
            "Fields Involved": "PerUnitCost, PaymentAmount",
            "Values": f"PerUnitCost={row.get('PerUnitCost')}, PaymentAmount={row.get('PaymentAmount')}",
            "Status": "❌ Fail",
            "Reason": "✗ Cannot evaluate — one or both values are missing or non-numeric",
        })

    if pay is not None and cap_t is not None:
        if pay >= cap_t:
            results.append({
                "Record #": rec_num,
                "Rule": "PaymentAmount ≥ CapitalizedThreshold",
                "Fields Involved": "PaymentAmount, CapitalizedThreshold",
                "Values": f"PaymentAmount={pay}, CapitalizedThreshold={cap_t}",
                "Status": "✅ Pass",
                "Reason": f"✓ PaymentAmount ({pay}) ≥ CapitalizedThreshold ({cap_t}) — asset qualifies as capitalized equipment",
            })
        else:
            results.append({
                "Record #": rec_num,
                "Rule": "PaymentAmount ≥ CapitalizedThreshold",
                "Fields Involved": "PaymentAmount, CapitalizedThreshold",
                "Values": f"PaymentAmount={pay}, CapitalizedThreshold={cap_t}",
                "Status": "❌ Fail",
                "Reason": f"✗ PaymentAmount ({pay}) < CapitalizedThreshold ({cap_t}) — asset does NOT qualify as capitalized equipment",
            })
    else:
        results.append({
            "Record #": rec_num,
            "Rule": "PaymentAmount ≥ CapitalizedThreshold",
            "Fields Involved": "PaymentAmount, CapitalizedThreshold",
            "Values": f"PaymentAmount={row.get('PaymentAmount')}, CapitalizedThreshold={row.get('CapitalizedThreshold')}",
            "Status": "❌ Fail",
            "Reason": "✗ Cannot evaluate — one or both values are missing or non-numeric",
        })

    return results


def run_subaward_business_rules(row, rec_num):
    results = []
    exp   = _to_float(row.get("ExpenditureAmount"))
    f50   = _to_float(row.get("First50k"))
    ex50  = _to_float(row.get("Excess50k"))
    sub   = _to_float(row.get("SubawardAmount"))

    if exp is not None and f50 is not None and ex50 is not None:
        total_check = round(f50 + ex50, 4)
        if abs(total_check - exp) < 0.01:
            results.append({
                "Record #": rec_num,
                "Rule": "First50k + Excess50k = ExpenditureAmount",
                "Fields Involved": "First50k, Excess50k, ExpenditureAmount",
                "Values": f"First50k={f50}, Excess50k={ex50}, Sum={total_check}, ExpenditureAmount={exp}",
                "Status": "✅ Pass",
                "Reason": f"✓ First50k ({f50}) + Excess50k ({ex50}) = {total_check} matches ExpenditureAmount ({exp})",
            })
        else:
            results.append({
                "Record #": rec_num,
                "Rule": "First50k + Excess50k = ExpenditureAmount",
                "Fields Involved": "First50k, Excess50k, ExpenditureAmount",
                "Values": f"First50k={f50}, Excess50k={ex50}, Sum={total_check}, ExpenditureAmount={exp}",
                "Status": "❌ Fail",
                "Reason": f"✗ First50k ({f50}) + Excess50k ({ex50}) = {total_check} ≠ ExpenditureAmount ({exp}). Difference: {round(total_check - exp, 4)}",
            })
    else:
        results.append({
            "Record #": rec_num,
            "Rule": "First50k + Excess50k = ExpenditureAmount",
            "Fields Involved": "First50k, Excess50k, ExpenditureAmount",
            "Values": f"First50k={row.get('First50k')}, Excess50k={row.get('Excess50k')}, ExpenditureAmount={row.get('ExpenditureAmount')}",
            "Status": "❌ Fail",
            "Reason": "✗ Cannot evaluate — one or more values are missing or non-numeric",
        })

    if f50 is not None:
        if f50 <= 50000:
            results.append({
                "Record #": rec_num,
                "Rule": "First50k ≤ 50,000",
                "Fields Involved": "First50k",
                "Values": f"First50k={f50}",
                "Status": "✅ Pass",
                "Reason": f"✓ First50k ({f50}) does not exceed the $50,000 cap",
            })
        else:
            results.append({
                "Record #": rec_num,
                "Rule": "First50k ≤ 50,000",
                "Fields Involved": "First50k",
                "Values": f"First50k={f50}",
                "Status": "❌ Fail",
                "Reason": f"✗ First50k ({f50}) exceeds the $50,000 cap — First50k must never exceed 50,000",
            })

    if exp is not None and f50 is not None and ex50 is not None:
        if exp <= 50000:
            if abs(f50 - exp) < 0.01 and abs(ex50) < 0.01:
                results.append({
                    "Record #": rec_num,
                    "Rule": "ExpenditureAmount ≤ 50k → First50k=Expenditure, Excess50k=0",
                    "Fields Involved": "ExpenditureAmount, First50k, Excess50k",
                    "Values": f"ExpenditureAmount={exp}, First50k={f50}, Excess50k={ex50}",
                    "Status": "✅ Pass",
                    "Reason": f"✓ ExpenditureAmount ({exp}) ≤ 50,000 — First50k equals ExpenditureAmount and Excess50k is 0",
                })
            else:
                reasons = []
                if abs(f50 - exp) >= 0.01:
                    reasons.append(f"First50k ({f50}) should equal ExpenditureAmount ({exp})")
                if abs(ex50) >= 0.01:
                    reasons.append(f"Excess50k ({ex50}) should be 0")
                results.append({
                    "Record #": rec_num,
                    "Rule": "ExpenditureAmount ≤ 50k → First50k=Expenditure, Excess50k=0",
                    "Fields Involved": "ExpenditureAmount, First50k, Excess50k",
                    "Values": f"ExpenditureAmount={exp}, First50k={f50}, Excess50k={ex50}",
                    "Status": "❌ Fail",
                    "Reason": "✗ " + "; ".join(reasons),
                })
        else:
            expected_f50  = 50000.0
            expected_ex50 = round(exp - 50000.0, 4)
            if abs(f50 - expected_f50) < 0.01 and abs(ex50 - expected_ex50) < 0.01:
                results.append({
                    "Record #": rec_num,
                    "Rule": "ExpenditureAmount > 50k → First50k=50000, Excess50k=Expenditure−50000",
                    "Fields Involved": "ExpenditureAmount, First50k, Excess50k",
                    "Values": f"ExpenditureAmount={exp}, First50k={f50}, Excess50k={ex50}",
                    "Status": "✅ Pass",
                    "Reason": f"✓ ExpenditureAmount ({exp}) > 50,000 — First50k=50,000 and Excess50k={expected_ex50} are correct",
                })
            else:
                reasons = []
                if abs(f50 - expected_f50) >= 0.01:
                    reasons.append(f"First50k ({f50}) should be 50,000")
                if abs(ex50 - expected_ex50) >= 0.01:
                    reasons.append(f"Excess50k ({ex50}) should be {expected_ex50} (ExpenditureAmount−50,000)")
                results.append({
                    "Record #": rec_num,
                    "Rule": "ExpenditureAmount > 50k → First50k=50000, Excess50k=Expenditure−50000",
                    "Fields Involved": "ExpenditureAmount, First50k, Excess50k",
                    "Values": f"ExpenditureAmount={exp}, First50k={f50}, Excess50k={ex50}",
                    "Status": "❌ Fail",
                    "Reason": "✗ " + "; ".join(reasons),
                })

    if exp is not None and f50 is not None and ex50 is not None:
        expected_excess = round(exp - f50, 4)
        if abs(ex50 - expected_excess) < 0.01:
            results.append({
                "Record #": rec_num,
                "Rule": "Excess50k = ExpenditureAmount − First50k",
                "Fields Involved": "Excess50k, ExpenditureAmount, First50k",
                "Values": f"Excess50k={ex50}, ExpenditureAmount={exp}, First50k={f50}, Expected={expected_excess}",
                "Status": "✅ Pass",
                "Reason": f"✓ Excess50k ({ex50}) = ExpenditureAmount ({exp}) − First50k ({f50}) = {expected_excess}",
            })
        else:
            results.append({
                "Record #": rec_num,
                "Rule": "Excess50k = ExpenditureAmount − First50k",
                "Fields Involved": "Excess50k, ExpenditureAmount, First50k",
                "Values": f"Excess50k={ex50}, ExpenditureAmount={exp}, First50k={f50}, Expected={expected_excess}",
                "Status": "❌ Fail",
                "Reason": f"✗ Excess50k ({ex50}) ≠ ExpenditureAmount ({exp}) − First50k ({f50}) = {expected_excess}",
            })

    if sub is not None and exp is not None:
        if sub <= exp:
            results.append({
                "Record #": rec_num,
                "Rule": "SubawardAmount ≤ ExpenditureAmount",
                "Fields Involved": "SubawardAmount, ExpenditureAmount",
                "Values": f"SubawardAmount={sub}, ExpenditureAmount={exp}",
                "Status": "✅ Pass",
                "Reason": f"✓ SubawardAmount ({sub}) ≤ ExpenditureAmount ({exp})",
            })
        else:
            results.append({
                "Record #": rec_num,
                "Rule": "SubawardAmount ≤ ExpenditureAmount",
                "Fields Involved": "SubawardAmount, ExpenditureAmount",
                "Values": f"SubawardAmount={sub}, ExpenditureAmount={exp}",
                "Status": "❌ Fail",
                "Reason": f"✗ SubawardAmount ({sub}) exceeds ExpenditureAmount ({exp}) — subaward cannot exceed total expenditure",
            })
    else:
        results.append({
            "Record #": rec_num,
            "Rule": "SubawardAmount ≤ ExpenditureAmount",
            "Fields Involved": "SubawardAmount, ExpenditureAmount",
            "Values": f"SubawardAmount={row.get('SubawardAmount')}, ExpenditureAmount={row.get('ExpenditureAmount')}",
            "Status": "❌ Fail",
            "Reason": "✗ Cannot evaluate — one or both values are missing or non-numeric",
        })

    return results


def run_unused_leave_business_rules(row, rec_num):
    results = []
    direct   = _to_float(row.get("DirectUnusedLeavePaymentAmount"))
    indirect = _to_float(row.get("IndirectUnusedLeavePaymentAmount"))

    if direct is not None and indirect is not None:
        total = round(direct + indirect, 4)
        results.append({
            "Record #": rec_num,
            "Rule": "Direct + Indirect = Total Leave Payment",
            "Fields Involved": "DirectUnusedLeavePaymentAmount, IndirectUnusedLeavePaymentAmount",
            "Values": f"Direct={direct}, Indirect={indirect}, Total={total}",
            "Status": "✅ Pass",
            "Reason": f"✓ DirectUnusedLeavePayment ({direct}) + IndirectUnusedLeavePayment ({indirect}) = Total Payout {total}. Both values present and non-negative.",
        })
    else:
        results.append({
            "Record #": rec_num,
            "Rule": "Direct + Indirect = Total Leave Payment",
            "Fields Involved": "DirectUnusedLeavePaymentAmount, IndirectUnusedLeavePaymentAmount",
            "Values": f"Direct={row.get('DirectUnusedLeavePaymentAmount')}, Indirect={row.get('IndirectUnusedLeavePaymentAmount')}",
            "Status": "❌ Fail",
            "Reason": "✗ Cannot compute total leave payment — one or both of Direct/Indirect amounts are missing or non-numeric",
        })

    return results


# ════════════════════════════════════════════════════════════════════
# SECTION 3 — BUDGET & ALLOCATION VALIDATIONS
# ════════════════════════════════════════════════════════════════════
def run_budget_allocation_validations(target_dfs_by_res, approved_budget_map):
    results = []
    actual_df = target_dfs_by_res.get("LocalActual", pd.DataFrame())

    if actual_df.empty or "Amount" not in actual_df.columns:
        results.append({
            "Record #": "—",
            "AccountIdentifier": "—",
            "Rule": "Actual Amount ≤ Approved Budget",
            "Values": "LocalActual not available",
            "Status": "⏭ Skipped",
            "Reason": "LocalActual data not fetched — budget validation skipped",
        })
        return pd.DataFrame(results)

    for _, row in actual_df.iterrows():
        if row.get("_api_status", "FOUND") != "FOUND":
            continue
        acc   = str(row.get("AccountIdentifier", "")).strip()
        rn    = row.get("_record_num", 1)
        amt   = _to_float(row.get("Amount"))
        if amt is None:
            continue

        budget_key = f"{acc}_{rn}"
        approved = _to_float(approved_budget_map.get(budget_key) or approved_budget_map.get(acc))
        if approved is not None:
            if amt <= approved:
                results.append({
                    "Record #": rn,
                    "AccountIdentifier": acc,
                    "Rule": "Actual Amount ≤ Approved Budget",
                    "Values": f"ActualAmount={amt:,.2f}, ApprovedBudget={approved:,.2f}",
                    "Status": "✅ Pass",
                    "Reason": f"✓ Actual Amount ({amt:,.2f}) does not exceed Approved Budget ({approved:,.2f}). Remaining: {approved - amt:,.2f}",
                })
            else:
                results.append({
                    "Record #": rn,
                    "AccountIdentifier": acc,
                    "Rule": "Actual Amount ≤ Approved Budget",
                    "Values": f"ActualAmount={amt:,.2f}, ApprovedBudget={approved:,.2f}",
                    "Status": "❌ Fail",
                    "Reason": f"✗ Actual Amount ({amt:,.2f}) EXCEEDS Approved Budget ({approved:,.2f}) by {amt - approved:,.2f} — budget overrun detected",
                })
        else:
            results.append({
                "Record #": rn,
                "AccountIdentifier": acc,
                "Rule": "Actual Amount ≤ Approved Budget",
                "Values": f"ActualAmount={amt:,.2f}, ApprovedBudget=Not Provided",
                "Status": "⏭ Skipped",
                "Reason": "⚠️ Approved Budget not provided for this account — enter budget in Step 1 to enable this check",
            })

    actual_amounts = {}
    for _, row in actual_df.iterrows():
        if row.get("_api_status", "FOUND") != "FOUND":
            continue
        acc = str(row.get("AccountIdentifier", "")).strip()
        rn  = row.get("_record_num", 1)
        amt = _to_float(row.get("Amount"))
        if acc and amt is not None:
            key = (acc, rn)
            actual_amounts[key] = actual_amounts.get(key, 0) + amt

    allocation_order = [
        ("LocalCapitalizedEquipment", "Equipment", "PaymentAmount"),
        ("LocalSubaward", "Subaward", "ExpenditureAmount"),
        ("LocalUnusedLeavePayment", "Leave", None),
    ]

    for key, actual_amt in actual_amounts.items():
        acc, rn = key
        running_balance = actual_amt
        for res, label, field in allocation_order:
            df = target_dfs_by_res.get(res, pd.DataFrame())
            if df.empty:
                continue
            subset = df[(df.get("AccountIdentifier", pd.Series()).astype(str) == acc) &
                        (df.get("_record_num", pd.Series()) == rn)] if "_record_num" in df.columns else pd.DataFrame()
            if subset.empty:
                continue
            cat_total = 0
            for _, r2 in subset.iterrows():
                if r2.get("_api_status", "FOUND") != "FOUND":
                    continue
                if field:
                    v = _to_float(r2.get(field))
                else:
                    d = _to_float(r2.get("DirectUnusedLeavePaymentAmount"))
                    i = _to_float(r2.get("IndirectUnusedLeavePaymentAmount"))
                    v = (d or 0) + (i or 0) if (d is not None or i is not None) else None
                if v is not None:
                    cat_total += v
            if cat_total == 0:
                continue
            running_balance -= cat_total
            if running_balance >= 0:
                results.append({
                    "Record #": rn,
                    "AccountIdentifier": acc,
                    "Rule": f"Remaining Balance After {label} Allocation ≥ 0",
                    "Values": f"Actual={actual_amt:,.2f}, {label}={cat_total:,.2f}, RunningBalance={running_balance:,.2f}",
                    "Status": "✅ Pass",
                    "Reason": f"✓ After allocating {label} ({cat_total:,.2f}), remaining balance is {running_balance:,.2f} — non-negative balance maintained",
                })
            else:
                results.append({
                    "Record #": rn,
                    "AccountIdentifier": acc,
                    "Rule": f"Remaining Balance After {label} Allocation ≥ 0",
                    "Values": f"Actual={actual_amt:,.2f}, {label}={cat_total:,.2f}, RunningBalance={running_balance:,.2f}",
                    "Status": "❌ Fail",
                    "Reason": f"✗ After allocating {label} ({cat_total:,.2f}), running balance is NEGATIVE ({running_balance:,.2f}) — allocation exceeds available funds",
                })

    return pd.DataFrame(results) if results else pd.DataFrame()


# ════════════════════════════════════════════════════════════════════
# SECTION 4 — DUPLICATE TRANSACTION DETECTION
# ════════════════════════════════════════════════════════════════════
def run_duplicate_detection(target_dfs_by_res):
    results = []

    all_transactions = []
    for res in FINANCE_RESOURCES:
        df = target_dfs_by_res.get(res, pd.DataFrame())
        if df.empty:
            continue
        for _, row in df.iterrows():
            if row.get("_api_status", "FOUND") != "FOUND":
                continue
            acc  = str(row.get("AccountIdentifier", "")).strip()
            fy   = str(row.get("FiscalYear", "")).strip()
            aod  = str(row.get("AsOfDate", "")).strip()
            rn   = row.get("_record_num", 1)

            amt = None
            if res == "LocalActual":
                amt = _to_float(row.get("Amount"))
            elif res == "LocalCapitalizedEquipment":
                amt = _to_float(row.get("PaymentAmount"))
            elif res == "LocalSubaward":
                amt = _to_float(row.get("ExpenditureAmount"))
            elif res == "LocalUnusedLeavePayment":
                d = _to_float(row.get("DirectUnusedLeavePaymentAmount"))
                i = _to_float(row.get("IndirectUnusedLeavePaymentAmount"))
                amt = round((d or 0) + (i or 0), 4) if (d is not None or i is not None) else None

            if acc and fy and aod and amt is not None:
                all_transactions.append({
                    "resource": res,
                    "AccountIdentifier": acc,
                    "FiscalYear": fy,
                    "AsOfDate": aod,
                    "Amount": amt,
                    "RecordNum": rn,
                })

    within_table_keys = {}
    for txn in all_transactions:
        key = (txn["resource"], txn["AccountIdentifier"], txn["FiscalYear"], txn["AsOfDate"], txn["Amount"])
        if key not in within_table_keys:
            within_table_keys[key] = []
        within_table_keys[key].append(txn["RecordNum"])

    for key, rec_nums in within_table_keys.items():
        res, acc, fy, aod, amt = key
        if len(rec_nums) > 1:
            results.append({
                "Record #": ", ".join(str(r) for r in rec_nums),
                "Resource": res,
                "Rule": "No Duplicate Transactions Within Table",
                "Key Fields": f"AccountIdentifier={acc}, FiscalYear={fy}, AsOfDate={aod}, Amount={amt}",
                "Status": "❌ Fail",
                "Reason": f"✗ DUPLICATE DETECTED in {res} — same AccountIdentifier+FiscalYear+AsOfDate+Amount appears {len(rec_nums)} times. Records: {rec_nums}. Duplicate financial impact detected.",
            })

    cross_table_keys = {}
    for txn in all_transactions:
        key = (txn["AccountIdentifier"], txn["FiscalYear"], txn["AsOfDate"], txn["Amount"])
        if key not in cross_table_keys:
            cross_table_keys[key] = []
        cross_table_keys[key].append(txn["resource"])

    for key, resources in cross_table_keys.items():
        acc, fy, aod, amt = key
        if len(resources) > 1:
            results.append({
                "Record #": "Cross-Table",
                "Resource": ", ".join(resources),
                "Rule": "No Cross-Table Double-Counting",
                "Key Fields": f"AccountIdentifier={acc}, FiscalYear={fy}, AsOfDate={aod}, Amount={amt}",
                "Status": "⚠️ Flag",
                "Reason": f"⚠️ Same amount ({amt}) on {aod} appears in multiple tables: {resources}. Review for potential double-counting of financial impact.",
            })

    if not results:
        results.append({
            "Record #": "All",
            "Resource": "All Tables",
            "Rule": "No Duplicate Transactions",
            "Key Fields": "AccountIdentifier, FiscalYear, AsOfDate, Amount",
            "Status": "✅ Pass",
            "Reason": "✓ No duplicate transactions detected across all tables — no double-counting of financial impact",
        })

    return pd.DataFrame(results)


# ════════════════════════════════════════════════════════════════════
# SECTION 5 — TIME-BASED VALIDATIONS
# ════════════════════════════════════════════════════════════════════
def _parse_date(val):
    try:
        return datetime.strptime(str(val).strip(), "%Y-%m-%d").date()
    except Exception:
        return None


def _fiscal_year_date_range(fiscal_year_val):
    try:
        fy = int(float(str(fiscal_year_val).strip()))
        return datetime(fy - 1, 7, 1).date(), datetime(fy, 6, 30).date()
    except Exception:
        return None, None


def run_time_based_validations(row, rec_num, res_name):
    results = []
    fy_val     = row.get("FiscalYear")
    as_of      = _parse_date(row.get("AsOfDate"))
    acq_date   = _parse_date(row.get("AcquisitionDate"))
    pay_date   = _parse_date(row.get("PaymentDate"))
    fy_start, fy_end = _fiscal_year_date_range(fy_val)

    def _date_in_fy(label, d):
        if d is None or fy_start is None:
            return
        if fy_start <= d <= fy_end:
            results.append({
                "Record #": rec_num,
                "Rule": f"{label} Within FiscalYear",
                "Fields Involved": f"{label}, FiscalYear",
                "Values": f"{label}={d}, FY={fy_val} ({fy_start}→{fy_end})",
                "Status": "✅ Pass",
                "Reason": f"✓ {label} ({d}) falls within FiscalYear {fy_val} window ({fy_start} to {fy_end})",
            })
        else:
            results.append({
                "Record #": rec_num,
                "Rule": f"{label} Within FiscalYear",
                "Fields Involved": f"{label}, FiscalYear",
                "Values": f"{label}={d}, FY={fy_val} ({fy_start}→{fy_end})",
                "Status": "❌ Fail",
                "Reason": f"✗ {label} ({d}) is OUTSIDE FiscalYear {fy_val} window ({fy_start} to {fy_end}) — transaction recorded in incorrect fiscal period",
            })

    if row.get("AsOfDate"):
        _date_in_fy("AsOfDate", as_of)

    if res_name == "LocalCapitalizedEquipment" and row.get("AcquisitionDate"):
        _date_in_fy("AcquisitionDate", acq_date)
        if acq_date is not None and as_of is not None:
            if acq_date <= as_of:
                results.append({
                    "Record #": rec_num,
                    "Rule": "AcquisitionDate ≤ AsOfDate",
                    "Fields Involved": "AcquisitionDate, AsOfDate",
                    "Values": f"AcquisitionDate={acq_date}, AsOfDate={as_of}",
                    "Status": "✅ Pass",
                    "Reason": f"✓ AcquisitionDate ({acq_date}) is on or before AsOfDate ({as_of}) — correct sequence",
                })
            else:
                results.append({
                    "Record #": rec_num,
                    "Rule": "AcquisitionDate ≤ AsOfDate",
                    "Fields Involved": "AcquisitionDate, AsOfDate",
                    "Values": f"AcquisitionDate={acq_date}, AsOfDate={as_of}",
                    "Status": "❌ Fail",
                    "Reason": f"✗ AcquisitionDate ({acq_date}) is AFTER AsOfDate ({as_of}) — asset cannot be acquired after the reporting date",
                })

    if res_name == "LocalUnusedLeavePayment" and row.get("PaymentDate"):
        _date_in_fy("PaymentDate", pay_date)
        if pay_date is not None and as_of is not None:
            if pay_date <= as_of:
                results.append({
                    "Record #": rec_num,
                    "Rule": "PaymentDate ≤ AsOfDate",
                    "Fields Involved": "PaymentDate, AsOfDate",
                    "Values": f"PaymentDate={pay_date}, AsOfDate={as_of}",
                    "Status": "✅ Pass",
                    "Reason": f"✓ PaymentDate ({pay_date}) is on or before AsOfDate ({as_of}) — correct financial sequence",
                })
            else:
                results.append({
                    "Record #": rec_num,
                    "Rule": "PaymentDate ≤ AsOfDate",
                    "Fields Involved": "PaymentDate, AsOfDate",
                    "Values": f"PaymentDate={pay_date}, AsOfDate={as_of}",
                    "Status": "❌ Fail",
                    "Reason": f"✗ PaymentDate ({pay_date}) is AFTER AsOfDate ({as_of}) — payment cannot be recorded after the reporting date",
                })

    return results


# ════════════════════════════════════════════════════════════════════
# SECTION 6 — FUND & CLASSIFICATION RULES
# ════════════════════════════════════════════════════════════════════
def run_fund_classification_validations(target_dfs_by_res):
    results = []

    account_df = target_dfs_by_res.get("LocalAccount", pd.DataFrame())
    leave_df   = target_dfs_by_res.get("LocalUnusedLeavePayment", pd.DataFrame())
    equip_df   = target_dfs_by_res.get("LocalCapitalizedEquipment", pd.DataFrame())

    if account_df.empty:
        results.append({
            "Record #": "—",
            "AccountIdentifier": "—",
            "Rule": "Fund Code Purpose Alignment",
            "Values": "LocalAccount not available",
            "Status": "⏭ Skipped",
            "Reason": "LocalAccount data not fetched — fund classification checks skipped",
        })
        return pd.DataFrame(results)

    for _, acct_row in account_df.iterrows():
        if acct_row.get("_api_status", "FOUND") != "FOUND":
            continue
        acc      = str(acct_row.get("AccountIdentifier", "")).strip()
        rn       = acct_row.get("_record_num", 1)
        fund_c   = str(acct_row.get("FundCode", "")).strip()
        func_c   = str(acct_row.get("FunctionCode", "")).strip()
        obj_c    = str(acct_row.get("ObjectCode", "")).strip()

        is_capital_fund = fund_c in CAPITAL_FUND_CODES or fund_c.startswith("4")
        has_leave = not leave_df.empty and any(
            str(r.get("AccountIdentifier", "")).strip() == acc
            for _, r in leave_df.iterrows()
            if r.get("_api_status", "FOUND") == "FOUND"
        )

        if is_capital_fund and has_leave:
            results.append({
                "Record #": rn,
                "AccountIdentifier": acc,
                "Rule": "Capital Fund Not Used for Leave Payments",
                "Values": f"FundCode={fund_c}, HasLeavePayments=True",
                "Status": "❌ Fail",
                "Reason": f"✗ FundCode '{fund_c}' appears to be a capital fund but is associated with unused leave payments — capital funds must not be used for payroll/leave expenditures",
            })
        elif is_capital_fund:
            results.append({
                "Record #": rn,
                "AccountIdentifier": acc,
                "Rule": "Capital Fund Not Used for Leave Payments",
                "Values": f"FundCode={fund_c}, HasLeavePayments=False",
                "Status": "✅ Pass",
                "Reason": f"✓ Capital FundCode '{fund_c}' is not associated with leave payment transactions",
            })
        else:
            results.append({
                "Record #": rn,
                "AccountIdentifier": acc,
                "Rule": "Capital Fund Not Used for Leave Payments",
                "Values": f"FundCode={fund_c}",
                "Status": "✅ Pass",
                "Reason": f"✓ FundCode '{fund_c}' is not a capital fund — no fund misuse concern",
            })

        is_capital_func = func_c in CAPITAL_FUNCTION_CODES or func_c.startswith("4")
        if is_capital_func and has_leave:
            results.append({
                "Record #": rn,
                "AccountIdentifier": acc,
                "Rule": "Capital FunctionCode Not Used for Leave Payments",
                "Values": f"FunctionCode={func_c}, HasLeavePayments=True",
                "Status": "❌ Fail",
                "Reason": f"✗ FunctionCode '{func_c}' appears capital in nature but account has leave payment transactions — function code does not align with leave payout purpose",
            })
        elif is_capital_func:
            results.append({
                "Record #": rn,
                "AccountIdentifier": acc,
                "Rule": "Capital FunctionCode Not Used for Leave Payments",
                "Values": f"FunctionCode={func_c}",
                "Status": "✅ Pass",
                "Reason": f"✓ Capital FunctionCode '{func_c}' is not associated with leave payments",
            })

        is_payroll_obj = obj_c in PAYROLL_OBJECT_CODES or (obj_c.isdigit() and 100 <= int(obj_c) <= 290)
        has_equipment = not equip_df.empty and any(
            str(r.get("AccountIdentifier", "")).strip() == acc
            for _, r in equip_df.iterrows()
            if r.get("_api_status", "FOUND") == "FOUND"
        )
        if is_payroll_obj and has_equipment:
            results.append({
                "Record #": rn,
                "AccountIdentifier": acc,
                "Rule": "ObjectCode Alignment with Transaction Type",
                "Values": f"ObjectCode={obj_c} (payroll-range), HasEquipment=True",
                "Status": "⚠️ Flag",
                "Reason": f"⚠️ ObjectCode '{obj_c}' falls in payroll/salary range but account has capitalized equipment transactions — review for potential misclassification",
            })
        else:
            results.append({
                "Record #": rn,
                "AccountIdentifier": acc,
                "Rule": "ObjectCode Alignment with Transaction Type",
                "Values": f"ObjectCode={obj_c}",
                "Status": "✅ Pass",
                "Reason": f"✓ ObjectCode '{obj_c}' does not indicate a classification conflict with transaction types for this account",
            })

        parts = acc.split("-")
        if len(parts) >= 3:
            results.append({
                "Record #": rn,
                "AccountIdentifier": acc,
                "Rule": "AccountIdentifier Structure Maps to Financial Dimensions",
                "Values": f"AccountIdentifier={acc}, Segments={len(parts)}",
                "Status": "✅ Pass",
                "Reason": f"✓ AccountIdentifier '{acc}' has {len(parts)} segments — structure is consistent with multi-dimension financial classification",
            })
        else:
            results.append({
                "Record #": rn,
                "AccountIdentifier": acc,
                "Rule": "AccountIdentifier Structure Maps to Financial Dimensions",
                "Values": f"AccountIdentifier={acc}, Segments={len(parts)}",
                "Status": "⚠️ Flag",
                "Reason": f"⚠️ AccountIdentifier '{acc}' has only {len(parts)} segment(s) — expected multi-segment format (e.g., S-FUND-FUNCTION-OBJECT-OPUNIT-SECTION) for proper dimension mapping",
            })

    return pd.DataFrame(results) if results else pd.DataFrame()


# ════════════════════════════════════════════════════════════════════
# SECTION 7 — MULTI-YEAR & CONTRACT-BASED VALIDATIONS
# ════════════════════════════════════════════════════════════════════
def run_multi_year_validations(target_dfs_by_res):
    results = []
    subaward_df = target_dfs_by_res.get("LocalSubaward", pd.DataFrame())

    if subaward_df.empty:
        results.append({
            "Record #": "—",
            "AccountIdentifier": "—",
            "Rule": "Contract Amount Distribution Check",
            "Values": "LocalSubaward not available",
            "Status": "⏭ Skipped",
            "Reason": "LocalSubaward data not fetched — multi-year validation skipped",
        })
        return pd.DataFrame(results)

    for _, row in subaward_df.iterrows():
        if row.get("_api_status", "FOUND") != "FOUND":
            continue
        acc  = str(row.get("AccountIdentifier", "")).strip()
        rn   = row.get("_record_num", 1)
        exp  = _to_float(row.get("ExpenditureAmount"))
        cny  = _to_float(row.get("ContractNumberOfYears"))

        if exp is None or cny is None:
            results.append({
                "Record #": rn,
                "AccountIdentifier": acc,
                "Rule": "Contract Amount Reasonable Distribution",
                "Values": f"ExpenditureAmount={row.get('ExpenditureAmount')}, ContractNumberOfYears={row.get('ContractNumberOfYears')}",
                "Status": "⏭ Skipped",
                "Reason": "Cannot evaluate — ExpenditureAmount or ContractNumberOfYears is missing or non-numeric",
            })
            continue

        if cny <= 0:
            results.append({
                "Record #": rn,
                "AccountIdentifier": acc,
                "Rule": "ContractNumberOfYears > 0",
                "Values": f"ContractNumberOfYears={cny}",
                "Status": "❌ Fail",
                "Reason": f"✗ ContractNumberOfYears ({cny}) must be greater than 0 — a valid contract must have at least 1 year",
            })
            continue

        annual_avg = round(exp / cny, 2)

        if cny > 1 and exp > 500_000:
            results.append({
                "Record #": rn,
                "AccountIdentifier": acc,
                "Rule": "Multi-Year Contract: No Excessive Single-Year Concentration",
                "Values": f"ExpenditureAmount={exp:,.2f}, ContractYears={int(cny)}, AnnualAvg={annual_avg:,.2f}",
                "Status": "⚠️ Flag",
                "Reason": f"⚠️ ExpenditureAmount ({exp:,.2f}) is large for a {int(cny)}-year contract (avg {annual_avg:,.2f}/year). Verify this single-period amount is correctly distributed and not a full contract total posted in one year.",
            })
        else:
            results.append({
                "Record #": rn,
                "AccountIdentifier": acc,
                "Rule": "Multi-Year Contract: No Excessive Single-Year Concentration",
                "Values": f"ExpenditureAmount={exp:,.2f}, ContractYears={int(cny)}, AnnualAvg={annual_avg:,.2f}",
                "Status": "✅ Pass",
                "Reason": f"✓ ExpenditureAmount ({exp:,.2f}) is reasonable for a {int(cny)}-year contract (implied avg {annual_avg:,.2f}/year) — no abnormal concentration detected",
            })

        if annual_avg > 0:
            results.append({
                "Record #": rn,
                "AccountIdentifier": acc,
                "Rule": "ExpenditureAmount Aligned with ContractNumberOfYears",
                "Values": f"ExpenditureAmount={exp:,.2f}, ContractYears={int(cny)}, AnnualAvg={annual_avg:,.2f}",
                "Status": "✅ Pass",
                "Reason": f"✓ ExpenditureAmount ({exp:,.2f}) divided by ContractNumberOfYears ({int(cny)}) = annual avg {annual_avg:,.2f} — financially plausible distribution",
            })
        else:
            results.append({
                "Record #": rn,
                "AccountIdentifier": acc,
                "Rule": "ExpenditureAmount Aligned with ContractNumberOfYears",
                "Values": f"ExpenditureAmount={exp:,.2f}, ContractYears={int(cny)}, AnnualAvg={annual_avg:,.2f}",
                "Status": "❌ Fail",
                "Reason": f"✗ Annual average ({annual_avg:,.2f}) is zero or negative — ExpenditureAmount does not align with ContractNumberOfYears",
            })

    return pd.DataFrame(results) if results else pd.DataFrame()


# ════════════════════════════════════════════════════════════════════
# SECTION 8 — REASONABILITY CHECKS
# ════════════════════════════════════════════════════════════════════
def run_reasonability_checks(row, rec_num, res_name):
    results = []

    if res_name == "LocalCapitalizedEquipment":
        pay   = _to_float(row.get("PaymentAmount"))
        unit  = _to_float(row.get("PerUnitCost"))
        if pay is not None and unit is not None and unit > 0:
            ratio = round(pay / unit, 4)
            if ratio >= 1:
                results.append({
                    "Record #": rec_num,
                    "Rule": "PaymentAmount / PerUnitCost = Realistic Quantity",
                    "Fields Involved": "PaymentAmount, PerUnitCost",
                    "Values": f"PaymentAmount={pay}, PerUnitCost={unit}, Implied Qty={ratio}",
                    "Status": "✅ Pass",
                    "Reason": f"✓ Implied quantity ({ratio}) is ≥ 1 — realistic unit count",
                })
            else:
                results.append({
                    "Record #": rec_num,
                    "Rule": "PaymentAmount / PerUnitCost = Realistic Quantity",
                    "Fields Involved": "PaymentAmount, PerUnitCost",
                    "Values": f"PaymentAmount={pay}, PerUnitCost={unit}, Implied Qty={ratio}",
                    "Status": "❌ Fail",
                    "Reason": f"✗ Implied quantity ({ratio}) < 1 — PaymentAmount is less than a single unit cost, which is unrealistic",
                })
        if pay is not None and pay > 1_000_000:
            results.append({
                "Record #": rec_num,
                "Rule": "PaymentAmount Reasonability",
                "Fields Involved": "PaymentAmount",
                "Values": f"PaymentAmount={pay}",
                "Status": "⚠️ Flag",
                "Reason": f"⚠️ PaymentAmount ({pay:,.2f}) exceeds $1,000,000 — flagged for review. Verify this is not a data entry error.",
            })

    if res_name == "LocalSubaward":
        sub = _to_float(row.get("SubawardAmount"))
        exp = _to_float(row.get("ExpenditureAmount"))
        cny = _to_float(row.get("ContractNumberOfYears"))

        if cny is not None:
            if 1 <= cny <= 30:
                results.append({
                    "Record #": rec_num,
                    "Rule": "ContractNumberOfYears Reasonability",
                    "Fields Involved": "ContractNumberOfYears",
                    "Values": f"ContractNumberOfYears={int(cny)}",
                    "Status": "✅ Pass",
                    "Reason": f"✓ ContractNumberOfYears ({int(cny)}) is within reasonable range (1–30 years)",
                })
            else:
                results.append({
                    "Record #": rec_num,
                    "Rule": "ContractNumberOfYears Reasonability",
                    "Fields Involved": "ContractNumberOfYears",
                    "Values": f"ContractNumberOfYears={cny}",
                    "Status": "❌ Fail",
                    "Reason": f"✗ ContractNumberOfYears ({cny}) is outside the expected range (1–30) — review for data entry errors",
                })

        if sub is not None:
            if sub > 0:
                results.append({
                    "Record #": rec_num,
                    "Rule": "SubawardAmount > 0",
                    "Fields Involved": "SubawardAmount",
                    "Values": f"SubawardAmount={sub}",
                    "Status": "✅ Pass",
                    "Reason": f"✓ SubawardAmount ({sub}) is positive — valid subaward entry",
                })
            else:
                results.append({
                    "Record #": rec_num,
                    "Rule": "SubawardAmount > 0",
                    "Fields Involved": "SubawardAmount",
                    "Values": f"SubawardAmount={sub}",
                    "Status": "❌ Fail",
                    "Reason": f"✗ SubawardAmount ({sub}) is zero or negative — a subaward entry must have a positive value",
                })

        if exp is not None and exp > 1_000_000:
            results.append({
                "Record #": rec_num,
                "Rule": "ExpenditureAmount Reasonability",
                "Fields Involved": "ExpenditureAmount",
                "Values": f"ExpenditureAmount={exp}",
                "Status": "⚠️ Flag",
                "Reason": f"⚠️ ExpenditureAmount ({exp:,.2f}) exceeds $1,000,000 — flagged for review",
            })

    if res_name == "LocalUnusedLeavePayment":
        direct   = _to_float(row.get("DirectUnusedLeavePaymentAmount"))
        indirect = _to_float(row.get("IndirectUnusedLeavePaymentAmount"))
        if direct is not None and indirect is not None:
            total = direct + indirect
            if total > 500_000:
                results.append({
                    "Record #": rec_num,
                    "Rule": "Total Leave Payment Reasonability",
                    "Fields Involved": "DirectUnusedLeavePaymentAmount, IndirectUnusedLeavePaymentAmount",
                    "Values": f"Direct={direct}, Indirect={indirect}, Total={total}",
                    "Status": "⚠️ Flag",
                    "Reason": f"⚠️ Total leave payment ({total:,.2f}) exceeds $500,000 — flagged for review",
                })

    return results


# ════════════════════════════════════════════════════════════════════
# SECTION 9 — LIFECYCLE & PROCESS VALIDATIONS
# ════════════════════════════════════════════════════════════════════
def run_lifecycle_validations(target_dfs_by_res):
    results = []

    account_df = target_dfs_by_res.get("LocalAccount", pd.DataFrame())
    actual_df  = target_dfs_by_res.get("LocalActual", pd.DataFrame())
    equip_df   = target_dfs_by_res.get("LocalCapitalizedEquipment", pd.DataFrame())
    sub_df     = target_dfs_by_res.get("LocalSubaward", pd.DataFrame())
    leave_df   = target_dfs_by_res.get("LocalUnusedLeavePayment", pd.DataFrame())

    def get_active_accounts(df):
        if df.empty:
            return set()
        result = set()
        for _, row in df.iterrows():
            if row.get("_api_status", "FOUND") == "FOUND":
                acc = str(row.get("AccountIdentifier", "")).strip()
                if acc:
                    result.add(acc)
        return result

    acct_with_account = get_active_accounts(account_df)
    acct_with_actual  = get_active_accounts(actual_df)
    acct_with_equip   = get_active_accounts(equip_df)
    acct_with_sub     = get_active_accounts(sub_df)
    acct_with_leave   = get_active_accounts(leave_df)

    all_accts = acct_with_account | acct_with_actual | acct_with_equip | acct_with_sub | acct_with_leave

    if not all_accts:
        results.append({
            "Record #": "—",
            "AccountIdentifier": "—",
            "Rule": "Transaction Lifecycle Check",
            "Layer": "All",
            "Status": "⏭ Skipped",
            "Reason": "No active records found — lifecycle validation skipped",
        })
        return pd.DataFrame(results)

    acc_to_recnum = {}
    for _df in [account_df, actual_df, equip_df, sub_df, leave_df]:
        if _df.empty:
            continue
        for _, _row in _df.iterrows():
            _acc = str(_row.get("AccountIdentifier", "")).strip()
            _rn  = _row.get("_record_num", 1)
            if _acc and _acc not in acc_to_recnum:
                acc_to_recnum[_acc] = _rn

    for acc in sorted(all_accts):
        rn = acc_to_recnum.get(acc, 1)
        if acc in acct_with_account:
            results.append({
                "Record #": rn,
                "AccountIdentifier": acc,
                "Rule": "LocalAccount Exists (Foundation Layer)",
                "Layer": "LocalAccount",
                "Status": "✅ Pass",
                "Reason": f"✓ LocalAccount record found for '{acc}' — foundation layer present for all subsequent transactions",
            })
        else:
            results.append({
                "Record #": rn,
                "AccountIdentifier": acc,
                "Rule": "LocalAccount Exists (Foundation Layer)",
                "Layer": "LocalAccount",
                "Status": "❌ Fail",
                "Reason": f"✗ LocalAccount NOT found for '{acc}' — financial transactions cannot be valid without a corresponding account definition",
            })

        has_any_payment = (acc in acct_with_equip or acc in acct_with_sub or acc in acct_with_leave)
        if has_any_payment:
            if acc in acct_with_actual:
                results.append({
                    "Record #": rn,
                    "AccountIdentifier": acc,
                    "Rule": "LocalActual Exists Before Payment Transactions",
                    "Layer": "LocalActual",
                    "Status": "✅ Pass",
                    "Reason": f"✓ LocalActual found for '{acc}' — expenditure context exists before payment transactions (correct lifecycle: Account → Actual → Payments)",
                })
            else:
                results.append({
                    "Record #": rn,
                    "AccountIdentifier": acc,
                    "Rule": "LocalActual Exists Before Payment Transactions",
                    "Layer": "LocalActual",
                    "Status": "❌ Fail",
                    "Reason": f"✗ Payment transactions found for '{acc}' but NO LocalActual record exists — payments must not be recorded without corresponding expenditure or approval context (lifecycle violation)",
                })

        if acc in acct_with_equip:
            if acc in acct_with_actual:
                results.append({
                    "Record #": rn,
                    "AccountIdentifier": acc,
                    "Rule": "Equipment Payment Has Expenditure Context",
                    "Layer": "LocalCapitalizedEquipment",
                    "Status": "✅ Pass",
                    "Reason": f"✓ CapitalizedEquipment payment for '{acc}' has corresponding LocalActual — expenditure context satisfied",
                })
            else:
                results.append({
                    "Record #": rn,
                    "AccountIdentifier": acc,
                    "Rule": "Equipment Payment Has Expenditure Context",
                    "Layer": "LocalCapitalizedEquipment",
                    "Status": "❌ Fail",
                    "Reason": f"✗ CapitalizedEquipment payment for '{acc}' has NO LocalActual expenditure context — payment recorded without approval/expenditure foundation",
                })

        if acc in acct_with_sub:
            if acc in acct_with_actual:
                results.append({
                    "Record #": rn,
                    "AccountIdentifier": acc,
                    "Rule": "Subaward Payment Has Expenditure Context",
                    "Layer": "LocalSubaward",
                    "Status": "✅ Pass",
                    "Reason": f"✓ Subaward payment for '{acc}' has corresponding LocalActual — expenditure context satisfied",
                })
            else:
                results.append({
                    "Record #": rn,
                    "AccountIdentifier": acc,
                    "Rule": "Subaward Payment Has Expenditure Context",
                    "Layer": "LocalSubaward",
                    "Status": "❌ Fail",
                    "Reason": f"✗ Subaward payment for '{acc}' has NO LocalActual expenditure context — payment recorded without approval/expenditure foundation",
                })

        if acc in acct_with_leave:
            if acc in acct_with_actual:
                results.append({
                    "Record #": rn,
                    "AccountIdentifier": acc,
                    "Rule": "Leave Payment Has Expenditure Context",
                    "Layer": "LocalUnusedLeavePayment",
                    "Status": "✅ Pass",
                    "Reason": f"✓ Leave payment for '{acc}' has corresponding LocalActual — expenditure context satisfied",
                })
            else:
                results.append({
                    "Record #": rn,
                    "AccountIdentifier": acc,
                    "Rule": "Leave Payment Has Expenditure Context",
                    "Layer": "LocalUnusedLeavePayment",
                    "Status": "❌ Fail",
                    "Reason": f"✗ Leave payment for '{acc}' has NO LocalActual expenditure context — payment recorded without approval/expenditure foundation",
                })

    return pd.DataFrame(results) if results else pd.DataFrame()


# ════════════════════════════════════════════════════════════════════
# SECTION 10 — DESCRIPTOR CONSISTENCY
# ════════════════════════════════════════════════════════════════════
def run_descriptor_consistency_check(all_target_dfs):
    results = []
    descriptor_by_account = {}

    for res, df in all_target_dfs.items():
        if df.empty or "FinancialCollectionDescriptor" not in df.columns:
            continue
        for _, row in df.iterrows():
            api_status = row.get("_api_status", "FOUND")
            if api_status in ("NOT_FOUND", "SKIPPED", "EMPTY_RESPONSE"):
                continue
            acc_id = str(row.get("AccountIdentifier", "")).strip()
            rec_num = row.get("_record_num", 1)
            desc_val = strip_descriptor_code(str(row.get("FinancialCollectionDescriptor", "")).strip())
            if not acc_id or not desc_val or desc_val.lower() in ("nan", "none", ""):
                continue
            if acc_id not in descriptor_by_account:
                descriptor_by_account[acc_id] = {}
            if rec_num not in descriptor_by_account[acc_id]:
                descriptor_by_account[acc_id][rec_num] = {}
            descriptor_by_account[acc_id][rec_num][res] = desc_val

    for acc_id, rec_map in descriptor_by_account.items():
        for rec_num, res_descs in rec_map.items():
            unique_descs = set(res_descs.values())
            tables_str = ", ".join([f"{r}={v}" for r, v in res_descs.items()])
            if len(unique_descs) == 1:
                results.append({
                    "Record #": rec_num,
                    "AccountIdentifier": acc_id,
                    "Rule": "FinancialCollectionDescriptor Consistency",
                    "Tables Checked": ", ".join(res_descs.keys()),
                    "Values": tables_str,
                    "Status": "✅ Pass",
                    "Reason": f"✓ FinancialCollectionDescriptor is consistent ('{list(unique_descs)[0]}') across all related records",
                })
            else:
                results.append({
                    "Record #": rec_num,
                    "AccountIdentifier": acc_id,
                    "Rule": "FinancialCollectionDescriptor Consistency",
                    "Tables Checked": ", ".join(res_descs.keys()),
                    "Values": tables_str,
                    "Status": "❌ Fail",
                    "Reason": f"✗ FinancialCollectionDescriptor is INCONSISTENT across related records: {tables_str} — all records for same account must use the same descriptor",
                })

    return pd.DataFrame(results) if results else pd.DataFrame()


# ════════════════════════════════════════════════════════════════════
# SECTION 2 — CROSS-TABLE FINANCIAL CONSISTENCY
# ════════════════════════════════════════════════════════════════════
def run_cross_table_consistency(target_dfs_by_res):
    results = []

    actual_df = target_dfs_by_res.get("LocalActual", pd.DataFrame())
    if actual_df.empty or "Amount" not in actual_df.columns:
        results.append({
            "Record #": "—", "AccountIdentifier": "—",
            "Rule": "Cross-Table: Total Spending vs Actual Amount",
            "Category": "All",
            "Values": "LocalActual not available",
            "Status": "⏭ Skipped",
            "Reason": "LocalActual data not fetched or Amount field missing — cross-table check skipped",
        })
        return pd.DataFrame(results)

    actual_amounts = {}
    for _, row in actual_df.iterrows():
        if row.get("_api_status", "FOUND") not in ("FOUND",):
            continue
        acc = str(row.get("AccountIdentifier", "")).strip()
        rn  = row.get("_record_num", 1)
        amt = _to_float(row.get("Amount"))
        if acc and amt is not None:
            key = (acc, rn)
            actual_amounts[key] = actual_amounts.get(key, 0) + amt

    if not actual_amounts:
        results.append({
            "Record #": "—", "AccountIdentifier": "—",
            "Rule": "Cross-Table: Total Spending vs Actual Amount",
            "Category": "All",
            "Values": "No valid Actual records",
            "Status": "⏭ Skipped",
            "Reason": "No valid LocalActual Amount records found — cross-table check skipped",
        })
        return pd.DataFrame(results)

    spending_fields = {
        "LocalCapitalizedEquipment": "PaymentAmount",
        "LocalSubaward":             "ExpenditureAmount",
        "LocalUnusedLeavePayment":   None,
    }
    category_labels = {
        "LocalCapitalizedEquipment": "Equipment (PaymentAmount)",
        "LocalSubaward":             "Subaward (ExpenditureAmount)",
        "LocalUnusedLeavePayment":   "Leave (Direct+Indirect)",
    }

    spending_totals = {}
    for res, field in spending_fields.items():
        df = target_dfs_by_res.get(res, pd.DataFrame())
        if df.empty:
            continue
        for _, row in df.iterrows():
            if row.get("_api_status", "FOUND") not in ("FOUND",):
                continue
            acc = str(row.get("AccountIdentifier", "")).strip()
            rn  = row.get("_record_num", 1)
            key = (acc, rn)
            if key not in spending_totals:
                spending_totals[key] = {}
            if field:
                val = _to_float(row.get(field))
            else:
                d = _to_float(row.get("DirectUnusedLeavePaymentAmount"))
                i = _to_float(row.get("IndirectUnusedLeavePaymentAmount"))
                val = (d or 0) + (i or 0) if (d is not None or i is not None) else None
            if val is not None:
                cat = category_labels[res]
                spending_totals[key][cat] = spending_totals[key].get(cat, 0) + val

    all_keys = set(actual_amounts.keys()) | set(spending_totals.keys())
    for key in sorted(all_keys):
        acc, rn = key
        actual_amt  = actual_amounts.get(key)
        cats        = spending_totals.get(key, {})
        total_spent = sum(cats.values()) if cats else 0
        balance     = (actual_amt - total_spent) if actual_amt is not None else None

        if actual_amt is None:
            results.append({
                "Record #": rn, "AccountIdentifier": acc,
                "Rule": "Cross-Table: Total Spending vs Actual Amount",
                "Category": "All Categories",
                "Values": f"Actual=N/A, TotalSpending={total_spent}",
                "Status": "⏭ Skipped",
                "Reason": "No LocalActual Amount found for this account — cannot evaluate cross-table balance",
            })
            continue

        cats_str = " + ".join([f"{c}={v:,.2f}" for c, v in cats.items()]) if cats else "No spending records"
        bal_str  = f"{balance:,.2f}" if balance is not None else "N/A"

        if balance is not None and balance >= 0:
            results.append({
                "Record #": rn, "AccountIdentifier": acc,
                "Rule": "Cross-Table: Total Spending ≤ Actual Amount",
                "Category": "All Categories",
                "Values": f"Actual={actual_amt:,.2f}, TotalSpending={total_spent:,.2f}, Balance={bal_str}",
                "Status": "✅ Pass",
                "Reason": f"✓ Total spending ({total_spent:,.2f}) does not exceed Actual Amount ({actual_amt:,.2f}). Remaining balance: {bal_str}. Breakdown: {cats_str}",
            })
        elif balance is not None:
            results.append({
                "Record #": rn, "AccountIdentifier": acc,
                "Rule": "Cross-Table: Total Spending ≤ Actual Amount",
                "Category": "All Categories",
                "Values": f"Actual={actual_amt:,.2f}, TotalSpending={total_spent:,.2f}, Balance={bal_str}",
                "Status": "❌ Fail",
                "Reason": f"✗ Total spending ({total_spent:,.2f}) EXCEEDS Actual Amount ({actual_amt:,.2f}) by {abs(balance):,.2f}. Balance is NEGATIVE. Breakdown: {cats_str}",
            })

        for cat, cat_amt in cats.items():
            if actual_amt is not None:
                if cat_amt <= actual_amt:
                    results.append({
                        "Record #": rn, "AccountIdentifier": acc,
                        "Rule": f"Cross-Table: {cat} ≤ Actual Amount",
                        "Category": cat,
                        "Values": f"Actual={actual_amt:,.2f}, {cat}={cat_amt:,.2f}",
                        "Status": "✅ Pass",
                        "Reason": f"✓ {cat} ({cat_amt:,.2f}) does not exceed Actual Amount ({actual_amt:,.2f})",
                    })
                else:
                    results.append({
                        "Record #": rn, "AccountIdentifier": acc,
                        "Rule": f"Cross-Table: {cat} ≤ Actual Amount",
                        "Category": cat,
                        "Values": f"Actual={actual_amt:,.2f}, {cat}={cat_amt:,.2f}",
                        "Status": "❌ Fail",
                        "Reason": f"✗ {cat} ({cat_amt:,.2f}) EXCEEDS Actual Amount ({actual_amt:,.2f}) — spending category exceeds available actual",
                    })

    return pd.DataFrame(results) if results else pd.DataFrame()


# ════════════════════════════════════════════════════════════════════
# BUSINESS RULES RUNNER
# ════════════════════════════════════════════════════════════════════
def run_business_rules_for_resource(res_name, df):
    all_rows = []
    if df.empty:
        return pd.DataFrame()

    for _, row in df.iterrows():
        api_status = row.get("_api_status", "FOUND")
        rec_num    = row.get("_record_num", 1)

        if api_status in ("NOT_FOUND", "SKIPPED", "EMPTY_RESPONSE"):
            all_rows.append({
                "Record #": rec_num,
                "Rule": "N/A — Record unavailable",
                "Fields Involved": "—",
                "Values": "—",
                "Status": "⏭ Skipped",
                "Reason": f"Business rules not evaluated — record status is {api_status}",
            })
            continue

        if res_name == "LocalCapitalizedEquipment":
            all_rows.extend(run_capitalized_equipment_business_rules(row, rec_num))
        elif res_name == "LocalSubaward":
            all_rows.extend(run_subaward_business_rules(row, rec_num))
        elif res_name == "LocalUnusedLeavePayment":
            all_rows.extend(run_unused_leave_business_rules(row, rec_num))

        if res_name in ("LocalCapitalizedEquipment", "LocalSubaward", "LocalUnusedLeavePayment", "LocalActual"):
            all_rows.extend(run_time_based_validations(row, rec_num, res_name))

        if res_name in ("LocalCapitalizedEquipment", "LocalSubaward", "LocalUnusedLeavePayment"):
            all_rows.extend(run_reasonability_checks(row, rec_num, res_name))

    return pd.DataFrame(all_rows) if all_rows else pd.DataFrame()


# ════════════════════════════════════════════════════════════════════
# FIELD-LEVEL VALIDATION RUNNER
# ════════════════════════════════════════════════════════════════════
def run_finance_validation(target_df, query_params_map=None):
    rows = []
    qpm = query_params_map or {}

    for rec_idx, row in target_df.iterrows():
        api_status = row.get("_api_status", "FOUND") if "_api_status" in target_df.columns else "FOUND"
        rec_num    = row.get("_record_num", rec_idx + 1) if "_record_num" in target_df.columns else rec_idx + 1
        qp         = qpm.get(rec_num, {})
        coa_checked = False

        for col in target_df.columns:
            if col.startswith("_"):
                continue
            val = row[col]

            if api_status == "NOT_FOUND":
                rows.append({
                    "Record #": rec_num, "Field": col, "Value": "—",
                    "Status": "❌ Invalid",
                    "Reason": "🔴 Record NOT FOUND — vendor did not post this record to the API",
                })
                continue

            if api_status == "EMPTY_RESPONSE":
                rows.append({
                    "Record #": rec_num, "Field": col, "Value": str(qp.get("AccountIdentifier", "—")),
                    "Status": "❌ Invalid",
                    "Reason": (
                        "🔴 Empty API Response — API returned HTTP 200 but 0 records. "
                        "The AccountIdentifier provided does not exist in the system or no data has been posted for it."
                    ),
                })
                continue

            if api_status == "SKIPPED":
                rows.append({
                    "Record #": rec_num, "Field": col, "Value": "—",
                    "Status": "⏭ Skipped",
                    "Reason": "Record ID not provided — entity was not fetched",
                })
                continue

            if col == "ChartOfAccountIdentifier" and not coa_checked:
                coa_id    = str(row.get("ChartOfAccountIdentifier", "")).strip()
                coa_edorg = str(row.get("ChartOfAccountEducationOrganizationId", "")).strip()
                if coa_id and coa_edorg:
                    coa_valid, coa_reason = check_chart_of_accounts_via_api(coa_id, coa_edorg)
                    coa_checked = True
                    rows.append({
                        "Record #": rec_num, "Field": "ChartOfAccountIdentifier", "Value": coa_id,
                        "Status": "✅ Valid" if coa_valid else "❌ Invalid",
                        "Reason": coa_reason,
                    })
                    rows.append({
                        "Record #": rec_num, "Field": "ChartOfAccountEducationOrganizationId", "Value": coa_edorg,
                        "Status": "✅ Valid" if coa_valid else "❌ Invalid",
                        "Reason": coa_reason,
                    })
                    continue

            if col == "ChartOfAccountEducationOrganizationId" and coa_checked:
                continue

            display_val = (
                strip_descriptor_code(str(val))
                if col == "FinancialCollectionDescriptor" and val is not None
                else (str(val) if val is not None else "")
            )
            is_valid, reason = validate_finance_field(col, val, qp)
            rows.append({
                "Record #": rec_num,
                "Field": col,
                "Value": display_val,
                "Status": "✅ Valid" if is_valid else "❌ Invalid",
                "Reason": reason,
            })

    return pd.DataFrame(rows)


def style_validation_df(df):
    def color_row(row):
        s = row.get("Status", "")
        if s in ("✅ Valid", "✅ Pass"):
            return ["background-color:#f0fdf4"] * len(row)
        if s.startswith("⏭") or s == "⚠️ Flag":
            return ["background-color:#fffbeb"] * len(row)
        return ["background-color:#fef2f2"] * len(row)
    return df.style.apply(color_row, axis=1)


def prep_display_df(df: pd.DataFrame) -> pd.DataFrame:
    """Drop internal cols (Section, _*) and return clean display-ready df."""
    drop_cols = [c for c in df.columns if c.startswith("_") or c == "Section"]
    return df.drop(columns=drop_cols, errors="ignore")


# ════════════════════════════════════════════════════════════════════
# FIX 3: HELPER — Render the top ribbon with dynamic page title
# ════════════════════════════════════════════════════════════════════
def render_top_ribbon(page_title: str = "School Finance Vendor Certification", page_subtitle: str = "Ed-Fi ODS 2026 · Indiana DOE"):
    """Renders the top header ribbon with a dynamic page title."""
    st.markdown(
        f"<div style='background:#ffffff;border:1.5px solid #cbd5e1;border-radius:10px;"
        f"padding:11px 18px;margin-bottom:16px;display:flex;align-items:center;"
        f"justify-content:space-between;gap:14px;box-shadow:0 1px 4px rgba(0,0,0,0.06);box-sizing:border-box;'>"
        f"<div style='display:flex;align-items:center;gap:9px;flex-shrink:0;'>"
        f"<div style='width:34px;height:34px;flex-shrink:0;background:#dae1f2;border-radius:7px;"
        f"display:flex;align-items:center;justify-content:center;font-size:17px;'>🎓</div>"
        f"<div><div style='font-size:14px;font-weight:800;color:#0d2d5e;white-space:nowrap;'>EdWise Group</div>"
        f"<div style='font-size:9px;color:#94a3b8;letter-spacing:1.4px;text-transform:uppercase;white-space:nowrap;'>Vendor Certification Portal</div></div></div>"
        f"<div style='text-align:center;flex:1;min-width:0;'>"
        f"<div style='font-size:13px;font-weight:700;color:#0d2d5e;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;'>🎓 {page_title}</div>"
        f"<div style='font-size:9px;color:#94a3b8;letter-spacing:1px;text-transform:uppercase;margin-top:1px;white-space:nowrap;'>{page_subtitle}</div></div>"
        f"<div style='text-align:right;flex-shrink:0;'>"
        f"<div style='font-size:12px;font-weight:600;color:#1e293b;white-space:nowrap;'>{get_vendor_name()}&nbsp;"
        f"<span style='background:#dbeafe;color:#1a6fd4;font-size:10px;font-weight:700;padding:2px 8px;border-radius:50px;'>LOGGED IN</span></div>"
        f"<div style='font-size:10px;color:#94a3b8;margin-top:2px;white-space:nowrap;'>🔒 Secure session</div></div>"
        f"</div>",
        unsafe_allow_html=True,
    )


# ════════════════════════════════════════════════════════════════════
# SIDEBAR — Navigation
# ════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown(
        "<div style='padding:14px 12px 10px;border-bottom:1px solid #e2e8f0;margin-bottom:4px;'>"
        "<div style='font-size:15px;font-weight:800;color:#0d2d5e;'>🎓&nbsp; EdWise Group</div>"
        "<div style='font-size:10px;font-weight:600;color:#94a3b8;letter-spacing:1.5px;text-transform:uppercase;margin-top:2px;'>School Finance Portal</div>"
        "</div>", unsafe_allow_html=True)

    st.markdown("<div style='padding:7px 12px 3px;margin-top:8px;font-size:10px;font-weight:700;color:#94a3b8;letter-spacing:2px;text-transform:uppercase;'>Navigation</div>", unsafe_allow_html=True)

    is_verif = st.session_state.get("fin_active_tab") == "verification"
    if is_verif:
        st.markdown("<div style='background:#eff6ff;border-left:3px solid #1a6fd4;margin:0;padding:0;'>", unsafe_allow_html=True)
    if st.button("📊  Finance Data Verification", key="nav_verification", width="stretch"):
        st.session_state.fin_active_tab = "verification"
        st.rerun()
    if is_verif:
        st.markdown("</div>", unsafe_allow_html=True)

    is_reset = st.session_state.get("fin_active_tab") == "reset"
    if is_reset:
        st.markdown("<div style='background:#eff6ff;border-left:3px solid #1a6fd4;margin:0;padding:0;'>", unsafe_allow_html=True)
    if st.button("🔄  Financial Data Reset", key="nav_reset", width="stretch"):
        st.session_state.fin_active_tab = "reset"
        st.rerun()
    if is_reset:
        st.markdown("</div>", unsafe_allow_html=True)

    # ── Single logout button — only here in sidebar nav ──────────────
    render_logout_button(sidebar=True)
    st.markdown(
        f"<div style='padding:4px 12px 8px;font-size:11px;color:#94a3b8;'>"
        f"v3.0.0 · Ed-Fi ODS 2026 · Indiana DOE</div>",
        unsafe_allow_html=True,
    )


# ════════════════════════════════════════════════════════════════════
# FINANCIAL DATA RESET TAB
# ════════════════════════════════════════════════════════════════════
if st.session_state.get("fin_active_tab") == "reset":

    # ── FIX 3: Dynamic ribbon for Financial Data Reset page ──
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

    st.stop()


# ════════════════════════════════════════════════════════════════════
# MAIN UI — Finance Data Verification page
# ════════════════════════════════════════════════════════════════════

# ── FIX 3: Dynamic ribbon for Finance Data Verification page ──
render_top_ribbon(
    page_title="School Finance Vendor Certification",
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
        "Provide Account ID, Education Organization ID, Fiscal Year, and optionally the Approved Budget for budget validation."
        "</div>"
        "</div>",
        unsafe_allow_html=True,
    )
with hdr_r:
    st.markdown("<div style='padding-top:18px;'>", unsafe_allow_html=True)
    if st.button("+ Add New Record", key="fin_add_record", type="primary"):
        st.session_state.finance_num_records += 1
        st.session_state.finance_record_data.append({"account_id": "", "edorg_id": "", "fiscal_year": "", "approved_budget": ""})
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

fin_pairs = []
n = st.session_state.finance_num_records
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
            dv     = st.session_state.finance_record_data[i] if i < len(st.session_state.finance_record_data) else {"account_id": "", "edorg_id": "", "fiscal_year": "", "approved_budget": ""}
            acc_id = st.text_input(f"Account ID {i+1}",       value=dv.get("account_id", ""),       key=f"fin_acc_{i}")
            edorg  = st.text_input(f"Edorg ID {i+1}",         value=dv.get("edorg_id", ""),         key=f"fin_edorg_{i}")
            fy     = st.text_input(f"Fiscal Year {i+1}",      value=dv.get("fiscal_year", ""),      key=f"fin_fy_{i}")
            budget = st.text_input(f"Approved Budget {i+1} (optional)",
                                   value=dv.get("approved_budget", ""), key=f"fin_budget_{i}",
                                   placeholder="e.g. 150000")

            prev    = st.session_state.finance_record_data[i] if i < len(st.session_state.finance_record_data) else {}
            changed = (
                acc_id != prev.get("account_id", "")
                or edorg != prev.get("edorg_id", "")
                or fy != prev.get("fiscal_year", "")
                or budget != prev.get("approved_budget", "")
            )
            if i < len(st.session_state.finance_record_data):
                st.session_state.finance_record_data[i] = {"account_id": acc_id, "edorg_id": edorg, "fiscal_year": fy, "approved_budget": budget}
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
    "Review expected values across all five finance entities. Account ID fields sync automatically from Step 1."
    "</div>"
    "</div>",
    unsafe_allow_html=True,
)


def render_editable_sample(entity_key, rows_key):
    rows   = st.session_state[rows_key]
    edited = st.data_editor(
        pd.DataFrame(rows),
        key=f"fin_editor_{entity_key}",
        width="stretch",
        num_rows="dynamic",
        hide_index=True,
    )
    st.session_state[rows_key] = edited.to_dict(orient="records")
    return edited


fin_sample_tabs = st.tabs([
    "📋 LocalAccount", "📊 LocalActual",
    "🖥️ LocalCapitalizedEquipment", "🤝 LocalSubaward", "🏖️ LocalUnusedLeavePayment",
])
finance_sample_dfs = {}
for tab_widget, res in zip(fin_sample_tabs, FINANCE_RESOURCES):
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
        if st.button("+ Add", key="fin_ep_add", type="primary", use_container_width=True):
            new_id = f"fep_{len(st.session_state.finance_api_endpoints)+10}"
            st.session_state.finance_api_endpoints.append({
                "id": new_id, "resource": "Custom",
                "template": f"{FINANCE_BASE_IDOE}/",
                "url":      f"{FINANCE_BASE_IDOE}/",
                "active": True,
            })
            st.rerun()

    st.markdown("<div style='margin:6px 0;'></div>", unsafe_allow_html=True)
    to_delete   = []
    fetch_ep_id = None

    for idx, ep in enumerate(st.session_state.finance_api_endpoints):
        col1, col2, col3 = st.columns([0.85, 0.08, 0.07], gap="small")
        ep_obj = next((e for e in st.session_state.finance_api_endpoints if e.get("id") == ep.get("id")), None)
        with col1:
            if ep_obj:
                new_url = st.text_input(
                    label=f"fin_ep_url_{idx}",
                    value=ep_obj["url"],
                    key=f"fin_ep_url_{ep.get('id', idx)}",
                    label_visibility="collapsed",
                    placeholder="https://...",
                )
                if new_url != ep_obj["url"]:
                    ep_obj["url"] = new_url
        with col2:
            if st.button("📊", key=f"fin_ep_fetch_{ep.get('id', idx)}", use_container_width=True, help="Fetch Data"):
                fetch_ep_id = ep.get("id", idx)
        with col3:
            if st.button("🗑️", key=f"fin_ep_del_{ep.get('id', idx)}", use_container_width=True):
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
                        r     = requests.get(fetch_url, headers={"Authorization": f"Bearer {token}"}, timeout=15)
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
        "Pull live data from the Ed-Fi ODS and run all validations."
        "</div>"
        "</div>",
        unsafe_allow_html=True,
    )
    run = st.button("▶  Run Certification Validation", type="primary", width="stretch")

if run:
    if not fin_pairs:
        st.error("❌ Please enter at least one Account Identifier.")
    else:
        st.session_state.finance_api_debug_info = []
        finance_target_dfs = {res: [] for res in FINANCE_RESOURCES}

        def make_fin_null(res_name, rec_num, status="SKIPPED"):
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
                for res in FINANCE_RESOURCES:
                    ep_obj = next(
                        (e for e in st.session_state.finance_api_endpoints
                         if e.get("resource") == res and e.get("active", True)),
                        None,
                    )
                    if not ep_obj or not acc_id:
                        finance_target_dfs[res].append(make_fin_null(res, rec_num, "SKIPPED"))
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
                        df_r = make_fin_null(res, rec_num, fetch_status)
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
        st.session_state["fin_query_params_map"] = qpm

        for res in FINANCE_RESOURCES:
            parts = finance_target_dfs[res]
            all_cols = FINANCE_COLS[res] + ["_api_status", "_record_num"]
            aligned = []
            for p in parts:
                p_clean = p.dropna(axis=1, how="all") if not p.empty else p
                for col in all_cols:
                    if col not in p_clean.columns:
                        p_clean[col] = ""
                aligned.append(p_clean[all_cols])
            st.session_state[f"fin_target_{res}"] = pd.concat(aligned, ignore_index=True)
        st.success(f"✅ Data fetched for {len(fin_pairs)} record(s).")

# ════════════════════════════════════════════════════════════════════
# RESULTS
# ════════════════════════════════════════════════════════════════════
def _result_heading(badge: str, title: str, subtitle: str):
    st.markdown(
        f"<div style='margin-bottom:10px;margin-top:6px;'>"
        f"<span style='font-size:10px;font-weight:700;letter-spacing:2px;text-transform:uppercase;"
        f"color:#1a6fd4;background:#eff6ff;padding:3px 10px;border-radius:20px;'>{badge}</span>"
        f"<div style='font-size:18px;font-weight:800;color:#0d2d5e;margin-top:8px;'>{title}</div>"
        f"<div style='width:36px;height:3px;background:#1a6fd4;border-radius:2px;margin-top:5px;'></div>"
        f"<div style='font-size:12px;color:#64748b;margin-top:6px;font-weight:400;'>{subtitle}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )


def _stat_card(col, label: str, value, color: str):
    with col:
        st.markdown(
            f"<div style='background:#f8fafc;border:1px solid #e2e8f0;border-top:3px solid {color};"
            f"border-radius:10px;padding:14px;text-align:center;'>"
            f"<div style='font-size:11px;font-weight:700;color:#64748b;margin-bottom:6px;text-transform:uppercase;letter-spacing:.5px;'>{label}</div>"
            f"<div style='font-size:26px;font-weight:800;color:{color};'>{value}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

if all(f"fin_target_{res}" in st.session_state for res in FINANCE_RESOURCES):

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
    for res in FINANCE_RESOURCES:
        df_t = st.session_state[f"fin_target_{res}"]
        if "_api_status" in df_t.columns:
            for status_val, label in [("NOT_FOUND", "🔴 NOT FOUND"), ("EMPTY_RESPONSE", "🟡 EMPTY RESPONSE")]:
                nf = df_t[df_t["_api_status"] == status_val]
                if not nf.empty and "_record_num" in nf.columns:
                    for rn in sorted(nf["_record_num"].unique()):
                        problem_recs.append(f"Record {rn} — {res} [{label}]")
    if problem_recs:
        st.error("Issues detected: " + "  |  ".join(problem_recs))

    target_tabs = st.tabs([
        "📋 LocalAccount", "📊 LocalActual",
        "🖥️ LocalCapitalizedEquipment", "🤝 LocalSubaward", "🏖️ LocalUnusedLeavePayment",
    ])
    for tab_widget, res in zip(target_tabs, FINANCE_RESOURCES):
        with tab_widget:
            df_t         = st.session_state[f"fin_target_{res}"]
            display_cols = [c for c in df_t.columns if not c.startswith("_")]
            show_df      = df_t[display_cols + ["_api_status"]].copy() if "_api_status" in df_t.columns else df_t[display_cols].copy()
            show_df      = safe_df_for_display(show_df)
            st.dataframe(highlight_api_status(show_df), width="stretch", hide_index=True)

    st.divider()

    # ── Result 2: Field Validation ────────────────────────────────────
    _result_heading(
        "Result 2 · Data Quality",
        "Field-Level Validation",
        "Each field verified against query parameters, format rules, and Ed-Fi dimension code APIs.",
    )

    qpm = st.session_state.get("fin_query_params_map", {})
    finance_val_dfs = {}
    for res in FINANCE_RESOURCES:
        df_t = st.session_state[f"fin_target_{res}"]
        finance_val_dfs[res] = run_finance_validation(df_t, qpm)

    def entity_status_fin(vdf):
        if vdf.empty:
            return "❌ FAIL"
        n = int((vdf["Status"] == "❌ Invalid").sum())
        return "✅ PASS" if n == 0 else f"❌ FAIL ({n})"

    fin_stat_cols = st.columns(5)
    for ui_col, res in zip(fin_stat_cols, FINANCE_RESOURCES):
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
            short_name = res.replace("Local", "")
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

    val_tabs = st.tabs([
        "📋 LocalAccount", "📊 LocalActual",
        "🖥️ LocalCapitalizedEquipment", "🤝 LocalSubaward", "🏖️ LocalUnusedLeavePayment",
    ])
    for tab_widget, res in zip(val_tabs, FINANCE_RESOURCES):
        with tab_widget:
            vdf = finance_val_dfs[res]
            if vdf.empty:
                st.warning(f"No data for {res}")
            else:
                st.dataframe(style_validation_df(prep_display_df(vdf)), width="stretch", hide_index=True)

    st.divider()

    # Collect all target dfs for cross-validations
    all_target_dfs_for_cross = {res: st.session_state[f"fin_target_{res}"] for res in FINANCE_RESOURCES}

    # ── Result 3: Business Rules ──────────────────────────────────────
    _result_heading(
        "Result 3 · Financial Integrity",
        "Business Rule Validation",
        "Core calculations &nbsp;·&nbsp; Date/time sequence &nbsp;·&nbsp; Reasonability & anomaly checks",
    )

    BUSINESS_RULE_RESOURCES = ["LocalCapitalizedEquipment", "LocalSubaward", "LocalUnusedLeavePayment"]
    biz_rule_dfs = {}
    for res in BUSINESS_RULE_RESOURCES:
        df_t = st.session_state[f"fin_target_{res}"]
        biz_rule_dfs[res] = run_business_rules_for_resource(res, df_t)

    def biz_status(bdf):
        if bdf.empty:
            return "⏭ N/A"
        fails = int((bdf["Status"] == "❌ Fail").sum())
        return "✅ PASS" if fails == 0 else f"❌ FAIL ({fails})"

    biz_stat_cols = st.columns(3)
    biz_res_labels = {
        "LocalCapitalizedEquipment": ("🖥️", "CapEquipment"),
        "LocalSubaward": ("🤝", "Subaward"),
        "LocalUnusedLeavePayment": ("🏖️", "UnusedLeave"),
    }
    for ui_col, res in zip(biz_stat_cols, BUSINESS_RULE_RESOURCES):
        bdf     = biz_rule_dfs[res]
        status  = biz_status(bdf)
        is_pass = status.startswith("✅")
        top_c   = "#16a34a" if is_pass else ("#94a3b8" if status.startswith("⏭") else "#dc2626")
        bg_c    = "#f0fdf4" if is_pass else ("#f8fafc" if status.startswith("⏭") else "#fef2f2")
        pill_bg = "#dcfce7" if is_pass else ("#f1f5f9" if status.startswith("⏭") else "#fee2e2")
        pill_fg = "#16a34a" if is_pass else ("#64748b" if status.startswith("⏭") else "#dc2626")
        total   = len(bdf)
        passes  = int((bdf["Status"] == "✅ Pass").sum()) if not bdf.empty else 0
        fails   = int((bdf["Status"] == "❌ Fail").sum()) if not bdf.empty else 0
        flags   = int((bdf["Status"] == "⚠️ Flag").sum()) if not bdf.empty else 0
        icon, short = biz_res_labels[res]
        with ui_col:
            st.markdown(
                f"<div style='background:{bg_c};border:1px solid #e2e8f0;border-top:3px solid {top_c};"
                f"border-radius:10px;padding:18px;'>"
                f"<div style='font-size:12px;font-weight:700;color:#64748b;margin-bottom:12px;'>{icon} {short}</div>"
                f"<div style='display:flex;justify-content:space-between;margin-bottom:5px;'>"
                f"<span style='font-size:12px;color:#94a3b8;'>Rules Checked</span>"
                f"<span style='font-size:20px;font-weight:800;color:#0d2d5e;'>{total}</span></div>"
                f"<div style='display:flex;justify-content:space-between;margin-bottom:5px;'>"
                f"<span style='font-size:12px;color:#16a34a;'>✅ Pass</span>"
                f"<span style='font-size:16px;font-weight:700;color:#16a34a;'>{passes}</span></div>"
                f"<div style='display:flex;justify-content:space-between;margin-bottom:5px;'>"
                f"<span style='font-size:12px;color:#dc2626;'>❌ Fail</span>"
                f"<span style='font-size:16px;font-weight:700;color:#dc2626;'>{fails}</span></div>"
                f"<div style='display:flex;justify-content:space-between;margin-bottom:14px;'>"
                f"<span style='font-size:12px;color:#d97706;'>⚠️ Flag</span>"
                f"<span style='font-size:16px;font-weight:700;color:#d97706;'>{flags}</span></div>"
                f"<span style='background:{pill_bg};color:{pill_fg};font-size:12px;font-weight:700;"
                f"padding:4px 14px;border-radius:50px;'>{status}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )

    st.markdown("<br>", unsafe_allow_html=True)
    biz_tabs = st.tabs(["🖥️ CapitalizedEquipment Rules", "🤝 Subaward Rules", "🏖️ UnusedLeave Rules"])
    for tab_widget, res in zip(biz_tabs, BUSINESS_RULE_RESOURCES):
        with tab_widget:
            bdf = biz_rule_dfs[res]
            if bdf.empty:
                st.info(f"No business rules evaluated for {res} — records may not have been fetched.")
            else:
                st.dataframe(style_validation_df(prep_display_df(bdf)), width="stretch", hide_index=True)

    st.divider()

    # ── Result 4: Cross-Table ─────────────────────────────────────────
    _result_heading(
        "Result 4 · Cross-Table Consistency",
        "Cross-Table Spending vs Actual Amount",
        "Total spending (equipment + subaward + leave) must not exceed LocalActual Amount. Per-category balance checks included.",
    )

    cross_table_df = run_cross_table_consistency(all_target_dfs_for_cross)

    if cross_table_df.empty:
        st.info("No cross-table data available to evaluate.")
    else:
        cross_pass  = int((cross_table_df["Status"] == "✅ Pass").sum())
        cross_fail  = int((cross_table_df["Status"] == "❌ Fail").sum())
        cross_flag  = int((cross_table_df["Status"] == "⚠️ Flag").sum())
        cross_skip  = int((cross_table_df["Status"] == "⏭ Skipped").sum())
        cross_total = len(cross_table_df)
        c1, c2, c3, c4 = st.columns(4)
        for col, label, val, color in [
            (c1, "Total Checks", cross_total, "#0d2d5e"),
            (c2, "✅ Pass", cross_pass, "#16a34a"),
            (c3, "❌ Fail", cross_fail, "#dc2626"),
            (c4, "⚠️ Flag", cross_flag, "#d97706"),
        ]:
            _stat_card(col, label, val, color)
        st.markdown("<br>", unsafe_allow_html=True)

        def style_cross_df(df):
            def color_row(row):
                if row["Status"] == "✅ Pass":   return ["background-color:#f0fdf4"] * len(row)
                if row["Status"] == "⚠️ Flag":   return ["background-color:#fffbeb"] * len(row)
                if row["Status"].startswith("⏭"): return ["background-color:#f8fafc"] * len(row)
                return ["background-color:#fef2f2"] * len(row)
            return df.style.apply(color_row, axis=1)

        st.dataframe(style_cross_df(prep_display_df(cross_table_df)), width="stretch", hide_index=True)

    st.divider()

    # ── Result 5: Budget ──────────────────────────────────────────────
    _result_heading(
        "Result 5 · Budget & Allocation",
        "Actual Amount vs Approved Budget & Allocation Balance",
        "Actual Amount must not exceed approved budget. Running balance after each allocation must remain non-negative.",
    )

    budget_df = run_budget_allocation_validations(all_target_dfs_for_cross, st.session_state.approved_budget_map)

    if budget_df.empty:
        st.info("No budget validation data available.")
    else:
        bud_pass  = int((budget_df["Status"] == "✅ Pass").sum())
        bud_fail  = int((budget_df["Status"] == "❌ Fail").sum())
        bud_skip  = int((budget_df["Status"] == "⏭ Skipped").sum())
        bud_total = len(budget_df)
        b1, b2, b3, b4 = st.columns(4)
        for col, label, val, color in [
            (b1, "Total Checks", bud_total, "#0d2d5e"),
            (b2, "✅ Pass", bud_pass, "#16a34a"),
            (b3, "❌ Fail", bud_fail, "#dc2626"),
            (b4, "⏭ Skipped", bud_skip, "#94a3b8"),
        ]:
            _stat_card(col, label, val, color)
        st.markdown("<br>", unsafe_allow_html=True)
        st.dataframe(style_validation_df(prep_display_df(budget_df)), width="stretch", hide_index=True)

    st.divider()

    # ── Result 6: Duplicate Detection ─────────────────────────────────
    _result_heading(
        "Result 6 · Duplicate Detection",
        "Duplicate Transaction & Double-Count Check",
        "Same transaction must not appear multiple times. Financial values must not be double-counted across equipment, subaward, and leave tables.",
    )

    dup_df = run_duplicate_detection(all_target_dfs_for_cross)

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

    # ── Result 7: Fund & Classification ──────────────────────────────
    _result_heading(
        "Result 7 · Fund & Classification",
        "Fund Code Purpose Alignment & ObjectCode Classification",
        "Capital funds must not be used for payroll/leave. ObjectCode must align with transaction type. AccountIdentifier must map to all financial dimensions.",
    )

    fund_class_df = run_fund_classification_validations(all_target_dfs_for_cross)

    if fund_class_df.empty:
        st.info("No fund classification data available.")
    else:
        fc_pass  = int((fund_class_df["Status"] == "✅ Pass").sum())
        fc_fail  = int((fund_class_df["Status"] == "❌ Fail").sum())
        fc_flag  = int((fund_class_df["Status"] == "⚠️ Flag").sum())
        fc_skip  = int((fund_class_df["Status"] == "⏭ Skipped").sum())
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

    # ── Result 8: Multi-Year ──────────────────────────────────────────
    _result_heading(
        "Result 8 · Multi-Year & Contract",
        "Contract Amount Distribution & Multi-Year Alignment",
        "Financial amounts must align with ContractNumberOfYears. Large expenditures concentrated in a single year are flagged for review.",
    )

    multi_year_df = run_multi_year_validations(all_target_dfs_for_cross)

    if multi_year_df.empty:
        st.info("No multi-year contract data available.")
    else:
        my_pass  = int((multi_year_df["Status"] == "✅ Pass").sum())
        my_fail  = int((multi_year_df["Status"] == "❌ Fail").sum())
        my_flag  = int((multi_year_df["Status"] == "⚠️ Flag").sum())
        my_skip  = int((multi_year_df["Status"] == "⏭ Skipped").sum())
        my_total = len(multi_year_df)
        m1, m2, m3, m4 = st.columns(4)
        for col, label, val, color in [
            (m1, "Total Checks", my_total, "#0d2d5e"),
            (m2, "✅ Pass", my_pass, "#16a34a"),
            (m3, "❌ Fail", my_fail, "#dc2626"),
            (m4, "⚠️ Flag", my_flag, "#d97706"),
        ]:
            _stat_card(col, label, val, color)
        st.markdown("<br>", unsafe_allow_html=True)
        st.dataframe(style_validation_df(prep_display_df(multi_year_df)), width="stretch", hide_index=True)

    st.divider()

    # ── Result 9: Lifecycle ───────────────────────────────────────────
    _result_heading(
        "Result 9 · Lifecycle & Process",
        "Transaction Lifecycle: Account → Actual → Payments",
        "Payments must have corresponding expenditure context. LocalAccount must exist. No payments without LocalActual foundation.",
    )

    lifecycle_df = run_lifecycle_validations(all_target_dfs_for_cross)

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

    # ── Result 10: Descriptor Consistency ────────────────────────────
    _result_heading(
        "Result 10 · Reporting Consistency",
        "FinancialCollectionDescriptor Consistency",
        "FinancialCollectionDescriptor must be consistent across all related records for the same account and reporting period.",
    )

    desc_consistency_df = run_descriptor_consistency_check(all_target_dfs_for_cross)

    if desc_consistency_df.empty:
        st.info("No descriptor consistency data available — records may not have been fetched.")
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
            "Dimension code and descriptor lookups performed during validation — inspect raw API responses"
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

    # ── Download ──────────────────────────────────────────────────────
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        summary_rows = []
        for res in FINANCE_RESOURCES:
            vdf = finance_val_dfs[res]
            summary_rows.append({
                "Resource": res,
                "Total Fields": len(vdf),
                "Valid": int((vdf["Status"] == "✅ Valid").sum()) if not vdf.empty else 0,
                "Invalid": int((vdf["Status"] == "❌ Invalid").sum()) if not vdf.empty else 0,
                "Field Validation Status": entity_status_fin(vdf),
            })
        for res in BUSINESS_RULE_RESOURCES:
            bdf = biz_rule_dfs.get(res, pd.DataFrame())
            for sr in summary_rows:
                if sr["Resource"] == res:
                    sr["Business Rules Checked"] = len(bdf)
                    sr["Business Rules Pass"]    = int((bdf["Status"] == "✅ Pass").sum()) if not bdf.empty else 0
                    sr["Business Rules Fail"]    = int((bdf["Status"] == "❌ Fail").sum()) if not bdf.empty else 0
                    sr["Business Rule Status"]   = biz_status(bdf)

        pd.DataFrame(summary_rows).to_excel(writer, sheet_name="Summary", index=False)

        for res in FINANCE_RESOURCES:
            st.session_state[f"fin_target_{res}"].to_excel(writer, sheet_name=f"Target_{res[:15]}", index=False)
            if not finance_val_dfs[res].empty:
                finance_val_dfs[res].to_excel(writer, sheet_name=f"FieldVal_{res[:13]}", index=False)

        for res in BUSINESS_RULE_RESOURCES:
            bdf = biz_rule_dfs.get(res, pd.DataFrame())
            if not bdf.empty:
                bdf.to_excel(writer, sheet_name=f"BizRules_{res[:12]}", index=False)

        all_parts = [df.assign(Resource=res) for res, df in finance_val_dfs.items() if not df.empty]
        if all_parts:
            combined = pd.concat(all_parts, ignore_index=True)
            inv = combined[combined["Status"] == "❌ Invalid"]
            if not inv.empty:
                inv.to_excel(writer, sheet_name="All_Invalid_Fields", index=False)

        biz_parts = [bdf.assign(Resource=res) for res, bdf in biz_rule_dfs.items() if not bdf.empty]
        if biz_parts:
            biz_combined = pd.concat(biz_parts, ignore_index=True)
            biz_fails = biz_combined[biz_combined["Status"] == "❌ Fail"]
            if not biz_fails.empty:
                biz_fails.to_excel(writer, sheet_name="Failed_BizRules", index=False)

        if not cross_table_df.empty:
            cross_table_df.to_excel(writer, sheet_name="S2_CrossTable", index=False)
            cross_fails = cross_table_df[cross_table_df["Status"] == "❌ Fail"]
            if not cross_fails.empty:
                cross_fails.to_excel(writer, sheet_name="S2_CrossTable_Fails", index=False)

        if not budget_df.empty:
            budget_df.to_excel(writer, sheet_name="S3_Budget_Allocation", index=False)
            bud_fails = budget_df[budget_df["Status"] == "❌ Fail"]
            if not bud_fails.empty:
                bud_fails.to_excel(writer, sheet_name="S3_Budget_Fails", index=False)

        if not dup_df.empty:
            dup_df.to_excel(writer, sheet_name="S4_Duplicate_Detection", index=False)
            dup_fails = dup_df[dup_df["Status"].isin(["❌ Fail", "⚠️ Flag"])]
            if not dup_fails.empty:
                dup_fails.to_excel(writer, sheet_name="S4_Duplicate_Issues", index=False)

        if not fund_class_df.empty:
            fund_class_df.to_excel(writer, sheet_name="S6_Fund_Classification", index=False)
            fc_fails = fund_class_df[fund_class_df["Status"].isin(["❌ Fail", "⚠️ Flag"])]
            if not fc_fails.empty:
                fc_fails.to_excel(writer, sheet_name="S6_Fund_Issues", index=False)

        if not multi_year_df.empty:
            multi_year_df.to_excel(writer, sheet_name="S7_MultiYear_Contract", index=False)
            my_fails = multi_year_df[multi_year_df["Status"].isin(["❌ Fail", "⚠️ Flag"])]
            if not my_fails.empty:
                my_fails.to_excel(writer, sheet_name="S7_MultiYear_Issues", index=False)

        if not lifecycle_df.empty:
            lifecycle_df.to_excel(writer, sheet_name="S9_Lifecycle_Process", index=False)
            lc_fails = lifecycle_df[lifecycle_df["Status"] == "❌ Fail"]
            if not lc_fails.empty:
                lc_fails.to_excel(writer, sheet_name="S9_Lifecycle_Fails", index=False)

        if not desc_consistency_df.empty:
            desc_consistency_df.to_excel(writer, sheet_name="S10_Descriptor_Consistency", index=False)

    dl_c, _sp3 = st.columns([2, 3])
    with dl_c:
        st.download_button(
            label="📥 Export Full Certification Report",
            data=output.getvalue(),
            file_name=f"EdWise_Finance_CertReport_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            width="stretch",
        )