import streamlit as st
import pandas as pd
import requests
import re
import io
import base64
from datetime import datetime, timedelta, timezone
from auth import render_logout_button, render_login_page, is_logged_in, get_vendor_creds, get_vendor_name
import urllib.parse

# ════════════════════════════════════════════════════════════════════
# CREDENTIAL-DEPENDENT CONFIG (initialized via init_credentials())
# ════════════════════════════════════════════════════════════════════
FINANCE_TOKEN_URL  = ""
FINANCE_API_KEY    = ""
FINANCE_API_SECRET = ""
FINANCE_BASE_EDFI  = ""
FINANCE_BASE_IDOE  = ""

FINANCE_CODE_APIS = {}
CHART_OF_ACCOUNTS_URL               = ""
FINANCIAL_COLLECTION_DESCRIPTOR_URL = ""
RESET_ENDPOINTS = {}
FINANCE_API_ENDPOINT_TEMPLATES = {}


def init_credentials():
    """Call after login to populate credential-dependent constants."""
    global FINANCE_TOKEN_URL, FINANCE_API_KEY, FINANCE_API_SECRET
    global FINANCE_BASE_EDFI, FINANCE_BASE_IDOE
    global FINANCE_CODE_APIS, CHART_OF_ACCOUNTS_URL, FINANCIAL_COLLECTION_DESCRIPTOR_URL
    global RESET_ENDPOINTS, FINANCE_API_ENDPOINT_TEMPLATES

    _creds             = get_vendor_creds()
    FINANCE_TOKEN_URL  = _creds.get("token_url", "")
    FINANCE_API_KEY    = _creds.get("api_key", "")
    FINANCE_API_SECRET = _creds.get("api_secret", "")
    FINANCE_BASE_EDFI  = _creds.get("finance_base_edfi", "")
    FINANCE_BASE_IDOE  = _creds.get("finance_base_idoe", "")

    FINANCE_CODE_APIS.update({
        "FunctionCode":        f"{FINANCE_BASE_EDFI}/functionDimensions?fiscalYear=2025&code={{code}}",
        "FundCode":            f"{FINANCE_BASE_EDFI}/fundDimensions?fiscalYear=2025&code={{code}}",
        "ObjectCode":          f"{FINANCE_BASE_EDFI}/objectDimensions?fiscalYear=2025&code={{code}}",
        "OperationalUnitCode": f"{FINANCE_BASE_EDFI}/operationalUnitDimensions?fiscalYear=2025&code={{code}}",
        "SectionCode":         f"{FINANCE_BASE_IDOE}/sectionDimensions?fiscalYear=2025&code={{code}}",
        "SubCategoryCode":     f"{FINANCE_BASE_IDOE}/subCategoryDimensions?fiscalYear=2025&code={{code}}",
    })

    CHART_OF_ACCOUNTS_URL               = f"{FINANCE_BASE_EDFI}/chartOfAccounts?fiscalYear=2025"
    FINANCIAL_COLLECTION_DESCRIPTOR_URL = f"{FINANCE_BASE_EDFI}/financialCollectionDescriptors"

    RESET_ENDPOINTS.update({
        "LocalActual":                f"{FINANCE_BASE_EDFI}/localActuals",
        "LocalCapitalizedEquipment": f"{FINANCE_BASE_IDOE}/localCapitalizedEquipment",
        "LocalSubaward":              f"{FINANCE_BASE_IDOE}/localSubawards",
        "LocalUnusedLeavePayment":    f"{FINANCE_BASE_IDOE}/localUnusedLeavePayments",
    })

    FINANCE_API_ENDPOINT_TEMPLATES.update({
        "LocalAccount":              f"{FINANCE_BASE_EDFI}/LocalAccounts?accountIdentifier={{AccountIdentifier}}",
        "LocalActual":                f"{FINANCE_BASE_EDFI}/localActuals?accountIdentifier={{AccountIdentifier}}",
        "LocalCapitalizedEquipment": f"{FINANCE_BASE_IDOE}/LocalCapitalizedEquipment?accountIdentifier={{AccountIdentifier}}",
        "LocalSubaward":              f"{FINANCE_BASE_IDOE}/LocalSubawards?accountIdentifier={{AccountIdentifier}}",
        "LocalUnusedLeavePayment":    f"{FINANCE_BASE_IDOE}/LocalUnusedLeavePayments?accountIdentifier={{AccountIdentifier}}",
    })


# ── Code digit length rules ────────────────────────
CODE_LENGTH_RULES = {
    "FundCode":            4,
    "ObjectCode":          3,
    "OperationalUnitCode": 4,
    "SubCategoryCode":     2,
    "SectionCode":         1,
    "FunctionCode":         5,
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
# MANDATORY FIELDS PER RESOURCE (used for Step 2 UI star markers)
# ════════════════════════════════════════════════════════════════════
MANDATORY_FIELDS = {
    "LocalAccount": {
        "AccountIdentifier", "EducationOrganizationId", "FiscalYear",
        "ChartOfAccountIdentifier", "ChartOfAccountEducationOrganizationId", "SectionCode",
    },
    "LocalActual": {
        "AccountIdentifier", "EducationOrganizationId", "FiscalYear",
        "AsOfDate", "Amount", "FinancialCollectionDescriptor",
    },
    "LocalCapitalizedEquipment": {
        "RecordIdentifier", "AccountIdentifier", "EducationOrganizationId", "FiscalYear",
        "AsOfDate", "EquipmentType", "AcquisitionDate",
        "PaymentAmount", "PerUnitCost", "CapitalizedThreshold", "FinancialCollectionDescriptor",
    },
    "LocalSubaward": {
        "RecordIdentifier", "AccountIdentifier", "EducationOrganizationId", "FiscalYear",
        "AsOfDate", "ContractNumberOfYears", "DepartmentName", "Excess50k",
        "ExpenditureAmount", "First50k", "SubawardAmount", "VendorOrganizationName",
        "FinancialCollectionDescriptor",
    },
    "LocalUnusedLeavePayment": {
        "RecordIdentifier", "AccountIdentifier", "EducationOrganizationId", "FiscalYear",
        "AsOfDate", "DirectUnusedLeavePaymentAmount", "EmployeeName",
        "IndirectUnusedLeavePaymentAmount", "FinancialCollectionDescriptor",
    },
}


def get_mandatory_column_config(res_name, df_cols):
    """
    Build a Streamlit column_config dict that marks mandatory fields with a ★ red-star
    prefix in the column header label (for use in st.data_editor Step 2 tables).
    Non-mandatory fields are left with their default label.
    """
    mandatory = MANDATORY_FIELDS.get(res_name, set())
    config = {}
    for col in df_cols:
        if col in mandatory:
            # Use Column base class so we only override label, not data-type behaviour
            config[col] = st.column_config.Column(label=f"★ {col}")
    return config


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
# SESSION STATE INITIALIZATION
# ════════════════════════════════════════════════════════════════════
def init_session_state():
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
    code_val = strip_descriptor_code(str(raw_value).strip())
    full_url = f"{FINANCIAL_COLLECTION_DESCRIPTOR_URL}?codeValue={code_val}"
    label = f"FinancialCollectionDescriptor Validation (codeValue={code_val})"
    found, status, count = _api_lookup(full_url, label)
    if found:
        return code_val, True, f"✓ Descriptor code '{code_val}' found in FinancialCollectionDescriptor API"
    if status == 0:
        return code_val, False, "Connection error — FinancialCollectionDescriptor API unreachable"
    return code_val, False, f"✗ Descriptor code '{code_val}' NOT found in FinancialCollectionDescriptor API"

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
        # ── AccountIdentifier structured format validation ────────────────
        # Expected format: Section-Fund-Function-Object-OperationalUnit-SubCategory
        # This validation checks if the AccountIdentifier matches the format built
        # from the dimension code fields returned by LocalAccount API.
        acct_row = qp.get("_local_account_row")
        if acct_row is not None:
            section  = str(acct_row.get("SectionCode", "")).strip()
            fund     = str(acct_row.get("FundCode", "")).strip()
            function = str(acct_row.get("FunctionCode", "")).strip()
            obj      = str(acct_row.get("ObjectCode", "")).strip()
            opunit   = str(acct_row.get("OperationalUnitCode", "")).strip()
            subcat   = str(acct_row.get("SubCategoryCode", "")).strip()
            if all([section, fund, function, obj, opunit, subcat]):
                combined = f"{section}-{fund}-{function}-{obj}-{opunit}-{subcat}"
                if val_str == combined:
                    return True, (
                        f"✓ AccountIdentifier '{val_str}' matches query param, format is valid, "
                        f"and structure matches combined dimension codes: "
                        f"Section={section} | Fund={fund} | Function={function} | "
                        f"Object={obj} | OperationalUnit={opunit} | SubCategory={subcat}"
                    )
                else:
                    return False, (
                        f"✗ AccountIdentifier structure mismatch — "
                        f"API returned '{val_str}' but expected combined format is '{combined}' "
                        f"(Section-Fund-Function-Object-OperationalUnit-SubCategory). "
                        f"Extracted codes: Section={section}, Fund={fund}, Function={function}, "
                        f"Object={obj}, OperationalUnit={opunit}, SubCategory={subcat}"
                    )
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

    # ── Resolve FinancialCollectionDescriptor code for window checks ──────
    raw_desc = row.get("FinancialCollectionDescriptor", "")
    descriptor_code = strip_descriptor_code(str(raw_desc).strip()) if raw_desc else ""
    descriptor_code = descriptor_code if descriptor_code.lower() not in ("", "nan", "none") else ""

    # ── Helper: date within fiscal year ───────────────────────────────────
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

    # ── Helper: date within FinancialCollectionDescriptor window ─────────
    # Descriptor code "1" → January 1 – June 30  (first half of calendar year)
    # Descriptor code "2" → July 1   – December 31 (second half of calendar year)
    # The calendar year is derived from the date being checked.
    def _date_in_descriptor_window(label, d):
        if d is None or not descriptor_code:
            return
        year = d.year
        if descriptor_code == "1":
            win_start   = datetime(year, 1, 1).date()
            win_end     = datetime(year, 6, 30).date()
            window_desc = f"January 1 – June 30, {year}"
        elif descriptor_code == "2":
            win_start   = datetime(year, 7, 1).date()
            win_end     = datetime(year, 12, 31).date()
            window_desc = f"July 1 – December 31, {year}"
        else:
            # Unknown descriptor code — skip window check
            return

        if win_start <= d <= win_end:
            results.append({
                "Record #": rec_num,
                "Rule": f"{label} Within FinancialCollectionDescriptor Window",
                "Fields Involved": f"{label}, FinancialCollectionDescriptor",
                "Values": f"{label}={d}, Descriptor='{descriptor_code}' ({window_desc})",
                "Status": "✅ Pass",
                "Reason": (
                    f"✓ {label} ({d}) falls within FinancialCollectionDescriptor '{descriptor_code}' "
                    f"reporting window ({window_desc})"
                ),
            })
        else:
            results.append({
                "Record #": rec_num,
                "Rule": f"{label} Within FinancialCollectionDescriptor Window",
                "Fields Involved": f"{label}, FinancialCollectionDescriptor",
                "Values": f"{label}={d}, Descriptor='{descriptor_code}' ({window_desc})",
                "Status": "❌ Fail",
                "Reason": (
                    f"✗ {label} ({d}) is OUTSIDE FinancialCollectionDescriptor '{descriptor_code}' "
                    f"reporting window ({window_desc}) — date must fall within the descriptor's "
                    f"defined reporting period (Code 1 = Jan 1–Jun 30, Code 2 = Jul 1–Dec 31)"
                ),
            })

    # ── AsOfDate: FiscalYear check + Descriptor window check (all resources) ──
    if row.get("AsOfDate"):
        _date_in_fy("AsOfDate", as_of)
        _date_in_descriptor_window("AsOfDate", as_of)

    # ── LocalCapitalizedEquipment: AcquisitionDate checks ─────────────────
    if res_name == "LocalCapitalizedEquipment" and row.get("AcquisitionDate"):
        _date_in_fy("AcquisitionDate", acq_date)
        _date_in_descriptor_window("AcquisitionDate", acq_date)
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

    # ── LocalUnusedLeavePayment: PaymentDate checks ────────────────────────
    if res_name == "LocalUnusedLeavePayment" and row.get("PaymentDate"):
        _date_in_fy("PaymentDate", pay_date)
        _date_in_descriptor_window("PaymentDate", pay_date)
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

    return pd.DataFrame(results)


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
# MANDATORY FIELD DETERMINATION (from vendor sample data)
# ════════════════════════════════════════════════════════════════════
def _build_mandatory_sets(sample_df):
    """
    Given a sample-data DataFrame (from the vendor's Step 2 editable table),
    return two sets:
      mandatory_fields    — fields that had at least one non-empty value in sample
      non_mandatory_fields — fields where every sample row was blank/empty

    Fields absent from sample_df entirely are treated as mandatory (safe default).
    """
    mandatory = set()
    non_mandatory = set()
    if sample_df is None or sample_df.empty:
        return mandatory, non_mandatory
    for col in sample_df.columns:
        if col.startswith("_"):
            continue
        has_value = sample_df[col].apply(lambda v: not _is_empty(v)).any()
        if has_value:
            mandatory.add(col)
        else:
            non_mandatory.add(col)
    return mandatory, non_mandatory


def _build_mandatory_sets_for_row(sample_row_dict):
    """
    Given a SINGLE sample-data row dict (one record's row from Step 2),
    return mandatory_fields and non_mandatory_fields sets for that specific record.

    A field is mandatory for this record if it has a non-empty value in the sample row.
    A field is non-mandatory for this record if it is blank/empty in the sample row.
    This enables per-record independent mandatory/non-mandatory control.
    """
    mandatory = set()
    non_mandatory = set()
    if not sample_row_dict:
        return mandatory, non_mandatory
    for col, val in sample_row_dict.items():
        if col.startswith("_"):
            continue
        if not _is_empty(val):
            mandatory.add(col)
        else:
            non_mandatory.add(col)
    return mandatory, non_mandatory


def _mandate_tag(col, mandatory_fields, non_mandatory_fields):
    """Return a short mandate label for appending to a Reason string."""
    if col in non_mandatory_fields:
        return "Field is non-mandatory"
    return "Field is mandatory"          # mandatory set OR unknown → mandatory


# ════════════════════════════════════════════════════════════════════
# FIELD-LEVEL VALIDATION RUNNER
# ════════════════════════════════════════════════════════════════════
def run_finance_validation(target_df, query_params_map=None, sample_df=None, sample_rows=None):
    """
    Validate every field in target_df.

    sample_rows (optional, list of dicts):
        Per-record sample data — index 0 = Record 1, index 1 = Record 2, etc.
        For each target record, the matching sample row (by rec_num - 1) is used to
        independently determine which fields are mandatory vs non-mandatory.
        This allows Record 1 to have a field as mandatory while Record 2 has it
        as non-mandatory, based on what the vendor filled in per row in Step 2.
        TAKES PRIORITY over sample_df when provided.

    sample_df (optional, pd.DataFrame):
        Legacy parameter — whole-DataFrame mandate determination (all records share
        the same mandatory/non-mandatory sets). Used only when sample_rows is None.
        Fields with a value in sample_df → mandatory.
        Fields left blank in sample_df   → non-mandatory.
        When both sample_df and sample_rows are None, all fields are mandatory.
    """
    rows = []
    qpm  = query_params_map or {}

    # ── Build global mandatory / non-mandatory sets (legacy fallback) ────
    global_mandatory_fields, global_non_mandatory_fields = _build_mandatory_sets(sample_df)

    for rec_idx, row in target_df.iterrows():
        api_status  = row.get("_api_status", "FOUND") if "_api_status" in target_df.columns else "FOUND"
        rec_num     = row.get("_record_num", rec_idx + 1) if "_record_num" in target_df.columns else rec_idx + 1
        qp          = qpm.get(rec_num, {})
        coa_checked = False

        # ── Per-record mandatory/non-mandatory determination ──────────────
        # When sample_rows is provided, use the row at index (rec_num - 1) so
        # each record independently controls which fields are mandatory.
        if sample_rows is not None:
            rec_zero_idx = int(rec_num) - 1
            sample_row_dict = (
                sample_rows[rec_zero_idx]
                if 0 <= rec_zero_idx < len(sample_rows)
                else {}
            )
            mandatory_fields, non_mandatory_fields = _build_mandatory_sets_for_row(sample_row_dict)
        else:
            mandatory_fields, non_mandatory_fields = global_mandatory_fields, global_non_mandatory_fields

        for col in target_df.columns:
            if col.startswith("_"):
                continue
            val = row[col]

            # ── Hard-status short-circuits (API-level failures) ────────────
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

            # ── Determine mandate status for this field ────────────────────
            is_mandatory = col not in non_mandatory_fields   # mandatory unless explicitly blank in sample
            tag          = _mandate_tag(col, mandatory_fields, non_mandatory_fields)

            # ── Handle empty target value ──────────────────────────────────
            if _is_empty(val):
                if not is_mandatory:
                    rows.append({
                        "Record #": rec_num, "Field": col, "Value": "",
                        "Status": "✅ Valid",
                        "Reason": (
                            "ℹ️ Non-mandatory field – value not required "
                            "(field was left blank in vendor sample data, so absence in API response is acceptable)"
                        ),
                    })
                else:
                    # mandatory field is missing in target data
                    rows.append({
                        "Record #": rec_num, "Field": col, "Value": "",
                        "Status": "❌ Invalid",
                        "Reason": (
                            f"❗ Mandatory field missing — '{col}' is required "
                            "(field has a value in vendor sample data) but was not populated in the API response"
                        ),
                    })
                continue

            # ── ChartOfAccount special joint-validation ────────────────────
            if col == "ChartOfAccountIdentifier" and not coa_checked:
                coa_id    = str(row.get("ChartOfAccountIdentifier", "")).strip()
                coa_edorg = str(row.get("ChartOfAccountEducationOrganizationId", "")).strip()
                if coa_id and coa_edorg:
                    coa_valid, coa_reason = check_chart_of_accounts_via_api(coa_id, coa_edorg)
                    coa_checked = True
                    coa_tag_id    = _mandate_tag("ChartOfAccountIdentifier",    mandatory_fields, non_mandatory_fields)
                    coa_tag_edorg = _mandate_tag("ChartOfAccountEducationOrganizationId", mandatory_fields, non_mandatory_fields)
                    rows.append({
                        "Record #": rec_num, "Field": "ChartOfAccountIdentifier", "Value": coa_id,
                        "Status": "✅ Valid" if coa_valid else "❌ Invalid",
                        "Reason": f"{coa_reason} | {coa_tag_id}",
                    })
                    rows.append({
                        "Record #": rec_num, "Field": "ChartOfAccountEducationOrganizationId", "Value": coa_edorg,
                        "Status": "✅ Valid" if coa_valid else "❌ Invalid",
                        "Reason": f"{coa_reason} | {coa_tag_edorg}",
                    })
                    continue

            if col == "ChartOfAccountEducationOrganizationId" and coa_checked:
                continue

            # ── Normal field validation ────────────────────────────────────
            display_val = (
                strip_descriptor_code(str(val))
                if col == "FinancialCollectionDescriptor" and val is not None
                else (str(val) if val is not None else "")
            )
            is_valid, reason = validate_finance_field(col, val, qp)
            rows.append({
                "Record #": rec_num,
                "Field":    col,
                "Value":    display_val,
                "Status":   "✅ Valid" if is_valid else "❌ Invalid",
                "Reason":   f"{reason} | {tag}",
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
# HELPER — Render the top ribbon with dynamic page title
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
# RESULT HEADING & STAT CARD HELPERS
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