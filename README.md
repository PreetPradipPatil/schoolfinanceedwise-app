# EdWise School Finance Vendor Certification Portal

> **v3.0.0 · Ed-Fi ODS 2026 · Indiana DOE**

A multi-page Streamlit application for Indiana school finance vendor certification. Validates financial data posted to the Ed-Fi ODS 2026 API against 50+ field-level and business rules, and verifies delete/reset operations.

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Architecture](#architecture)
3. [File Structure](#file-structure)
4. [Setup Instructions](#setup-instructions)
5. [Configuration — secrets.toml](#configuration--secretstoml)
6. [Running the App](#running-the-app)
7. [Navigation and Modules](#navigation-and-modules)
8. [Key Features](#key-features)
9. [Supported Financial Resources](#supported-financial-resources)
10. [Business Rule Sections](#business-rule-sections)
11. [API Integration](#api-integration)
12. [Export and Reporting](#export-and-reporting)
13. [Testing Checklist](#testing-checklist)

---

## Project Overview

The **EdWise School Finance Vendor Certification Portal** enables Indiana DOE-registered vendors to:

- **Verify** that financial data posted to the Ed-Fi ODS 2026 API is complete, correctly formatted, and passes all business rules.
- **Validate** five financial resource types (`LocalAccount`, `LocalActual`, `LocalCapitalizedEquipment`, `LocalSubaward`, `LocalUnusedLeavePayment`) across 10 validation sections and 50+ rules.
- **Confirm** that deleted records are no longer retrievable from the ODS.
- **Confirm** that reset operations have successfully zeroed all records for a given org/year/descriptor combination.
- **Export** timestamped Excel reports for audit trail and certification submissions.

---

## Architecture

```
User Browser
     │
     ▼
Streamlit App (app.py)
     │
     ├── auth.py           ← Login / logout / token management
     ├── shared.py         ← Constants, API helpers, business rule functions
     │
     ├── page_cap_equipment.py    ← Capitalized Equipment verification
     ├── page_subawards.py        ← Subawards verification
     ├── page_unused_leave.py     ← Unused Leave Payment verification
     ├── page_update.py           ← Financial Data Update verification
     ├── page_delete.py           ← Financial Data Delete verification
     └── page_reset.py            ← Financial Data Reset verification
          │
          ▼
     Ed-Fi ODS 2026 API
     (Azure Container Apps — Indiana DOE)
```

**Authentication Flow:**
1. User selects vendor and enters credentials → SHA-256 hash compared to `secrets.toml`
2. Vendor-specific `api_key` + `api_secret` loaded
3. OAuth 2.0 `client_credentials` POST to `token_url` → Bearer token cached in `st.session_state`
4. All API calls use `Authorization: Bearer <token>` header

---

## File Structure

```
your_project/
├── app.py                    # Main entry point: auth gate, CSS, sidebar nav, routing
├── auth.py                   # Authentication, vendor registry, login/logout UI
├── shared.py                 # All constants, helpers, validation functions, business rules
├── page_cap_equipment.py     # Local Capitalized Equipment verification page
├── page_subawards.py         # Local Subawards verification page
├── page_unused_leave.py      # Local Unused Leave Payment verification page
├── page_update.py            # Financial Data Update verification page
├── page_delete.py            # Financial Data Delete verification page
├── page_reset.py             # Financial Data Reset verification page
└── .streamlit/
    └── secrets.toml          # Vendor credentials and API config (NOT committed to git)
```

---

## Setup Instructions

### 1. Clone / copy the project

```bash
mkdir edwise-finance
cd edwise-finance
# Copy all .py files into this directory
```

### 2. Install Python dependencies

```bash
pip install streamlit pandas requests openpyxl
```

### 3. Create `.streamlit/secrets.toml`

```bash
mkdir -p .streamlit
touch .streamlit/secrets.toml
```

See [Configuration — secrets.toml](#configuration--secretstoml) below for the required structure.

### 4. Verify the file tree

```
edwise-finance/
├── app.py
├── auth.py
├── shared.py
├── page_cap_equipment.py
├── page_subawards.py
├── page_unused_leave.py
├── page_update.py
├── page_delete.py
├── page_reset.py
└── .streamlit/
    └── secrets.toml
```

---

## Configuration — secrets.toml

All vendor credentials and API base URLs live in `.streamlit/secrets.toml`. **Never commit this file to source control.**

```toml
[vendors.vendor_joshua_academy]
username          = "your_username"
password_hash     = "sha256_hex_of_password"   # sha256("your_password")
token_url         = "https://<ods-host>/oauth/token"
api_key           = "your_api_key"
api_secret        = "your_api_secret"
finance_base_edfi = "https://<ods-host>/2026/data/v3/ed-fi"
finance_base_idoe = "https://<ods-host>/2026/data/v3/idoe"

[vendors.vendor_bremen_public_schools]
username          = "another_username"
password_hash     = "sha256_hex_of_another_password"
token_url         = "https://<ods-host>/oauth/token"
api_key           = "another_api_key"
api_secret        = "another_api_secret"
finance_base_edfi = "https://<ods-host>/2026/data/v3/ed-fi"
finance_base_idoe = "https://<ods-host>/2026/data/v3/idoe"
```

**Generating a password hash (Python):**

```python
import hashlib
print(hashlib.sha256("your_password".encode()).hexdigest())
```

**Adding a new vendor:**

1. Add a new `[vendors.vendor_<name>]` block to `secrets.toml`
2. Add the vendor key and display name to `VENDOR_DISPLAY_NAMES` in `auth.py`

---

## Running the App

```bash
streamlit run app.py
```

The app will open at `http://localhost:8501`.

**For production / cloud deployment**, set the `STREAMLIT_SERVER_PORT` environment variable and ensure `secrets.toml` is available via your deployment platform's secrets management.

---

## Navigation and Modules

After login, the sidebar provides access to all six modules:

### Data Verification

| Module | Description | Resources |
|--------|-------------|-----------|
| 🖥️ **Local Capitalized Equipment** | End-to-end validation for equipment purchase records | LocalAccount, LocalActual, LocalCapitalizedEquipment |
| 🤝 **Local Subawards** | Validates subcontract expenditure records including $50K split logic | LocalAccount, LocalActual, LocalSubaward |
| 🏖️ **Local Unused Leave Payment** | Validates employee unused-leave payout records | LocalAccount, LocalActual, LocalUnusedLeavePayment |

### Data Management

| Module | Description |
|--------|-------------|
| ✏️ **Financial Data Update** | Verifies that vendor field updates are reflected in the live ODS API |
| 🗑️ **Financial Data Delete** | Confirms specific records have been deleted (HTTP 404/410 or blank 200) |
| 🔄 **Financial Data Reset** | Confirms all records return zero count after a vendor reset operation |

---

## Key Features

### 3-Step Verification Workflow (Verification Modules)

**Step 1 — Query Parameters**
- Input AccountIdentifier, EducationOrganizationId, FiscalYear (and optional Approved Budget)
- Supports multiple records via "+ Add New Record" button
- Parameters propagate automatically to all sample data grids

**Step 2 — Vendor Sample Data**
- Editable data grids pre-populated with realistic sample values
- Tabs for each resource: LocalAccount | LocalActual | target resource
- Supports `num_rows="dynamic"` for flexible multi-record testing

**Step 3 — Fetch and Validate**
- Fires authenticated GET requests to all ODS API endpoints
- Displays results in tabbed per-resource views
- Shows summary stat cards (Total / Pass / Fail / Flag / Skipped)
- Provides API Debug expanders (collapsible raw JSON responses)

### Validation Status Model

| Status | Meaning |
|--------|---------|
| ✅ Pass | All conditions met |
| ❌ Fail | Condition not met — vendor must correct and repost |
| ⚠️ Flag | Within tolerance but requires manual DOE review |
| ⏭ Skipped | Prerequisite unavailable; rule not evaluated |

### Excel Export
Every module generates a downloadable timestamped `.xlsx` report. Filename format: `EdWise_Finance_[Module]Report_YYYYMMDD_HHMM.xlsx`

---

## Supported Financial Resources

| Resource | Namespace | Fields | Notes |
|----------|-----------|--------|-------|
| `LocalAccount` | ed-fi | 12 | Foundation layer; must exist before all transactions |
| `LocalActual` | ed-fi | 6 | Expenditure context; must exist before payment resources |
| `LocalCapitalizedEquipment` | idoe | 12 | Requires `RecordIdentifier` (UUID-style) |
| `LocalSubaward` | idoe | 13 | Requires `RecordIdentifier`; enforces $50K split rules |
| `LocalUnusedLeavePayment` | idoe | 11 | Requires `RecordIdentifier`; validates Direct + Indirect amounts |

---

## Business Rule Sections

All 10 validation sections are implemented in `shared.py` and applied across all three verification modules.

| Section | Rules |
|---------|-------|
| **§1 Core Calculations** | Equipment: PerUnitCost ≤ PaymentAmount; PaymentAmount ≥ CapitalizedThreshold. Subaward: First50k + Excess50k = ExpenditureAmount; $50K cap logic; SubawardAmount ≤ ExpenditureAmount. Leave: Direct + Indirect present and non-negative. |
| **§2 Cross-Table Consistency** | Total spending (Equipment + Subaward + Leave) ≤ LocalActual Amount. Each category individually ≤ Actual. |
| **§3 Budget & Allocation** | Optional: Actual Amount ≤ Approved Budget. Running balance after sequential allocation must stay ≥ 0. |
| **§4 Duplicate Detection** | Within-table: same AccountID + FiscalYear + AsOfDate + Amount = Fail. Cross-table: same combo in multiple resources = Flag. |
| **§5 Time-Based** | All dates within FiscalYear window (July 1 – June 30). AcquisitionDate ≤ AsOfDate. PaymentDate ≤ AsOfDate. |
| **§6 Fund Classification** | Capital fund codes (4xxx) must not fund leave/payroll. Payroll ObjectCodes (100–290) with equipment transactions = Flag. |
| **§7 Multi-Year Contracts** | ContractNumberOfYears > 0 and 1–30 range. Expenditures > $500K on multi-year contracts flagged. |
| **§8 Reasonability** | PaymentAmount / PerUnitCost must imply quantity ≥ 1. Amounts > $1M (equipment, subaward) or > $500K (leave) flagged. |
| **§9 Lifecycle** | Required sequence: LocalAccount → LocalActual → payments. Missing foundation layers = Fail. |
| **§10 Descriptor Consistency** | FinancialCollectionDescriptor must be identical across all resources for the same account + fiscal year. |

---

## API Integration

### Token Endpoint
```
POST {token_url}
Headers: Authorization: Basic base64(api_key:api_secret)
         Content-Type: application/x-www-form-urlencoded
Body:    grant_type=client_credentials
```

### Data Query Endpoints (GET)
```
{finance_base_edfi}/LocalAccounts?accountIdentifier={id}
{finance_base_edfi}/localActuals?accountIdentifier={id}
{finance_base_idoe}/LocalCapitalizedEquipment?accountIdentifier={id}
{finance_base_idoe}/LocalSubawards?accountIdentifier={id}
{finance_base_idoe}/LocalUnusedLeavePayments?accountIdentifier={id}
```

### Code Dimension Validation Endpoints (GET)
```
{finance_base_edfi}/fundDimensions?fiscalYear=2025&code={code}
{finance_base_edfi}/functionDimensions?fiscalYear=2025&code={code}
{finance_base_edfi}/objectDimensions?fiscalYear=2025&code={code}
{finance_base_edfi}/operationalUnitDimensions?fiscalYear=2025&code={code}
{finance_base_idoe}/sectionDimensions?fiscalYear=2025&code={code}
{finance_base_idoe}/subCategoryDimensions?fiscalYear=2025&code={code}
```

### Code Length Requirements

| Field | Required Length |
|-------|----------------|
| FundCode | 4 digits (zero-padded) |
| FunctionCode | 5 digits (zero-padded) |
| ObjectCode | 3 digits (zero-padded) |
| OperationalUnitCode | 4 digits (zero-padded) |
| SectionCode | 1 character |
| SubCategoryCode | 2 digits (zero-padded) |

---

## Export and Reporting

### Verification Modules
Exports a multi-sheet `.xlsx` with:
- `Summary` — Resource-level pass/fail counts
- `{Resource}` — Raw API response data per resource
- `{Resource}_FieldValidation` — Field-level results
- `{Resource}_BusinessRules` — Rule evaluation results
- `CrossTable` / `BudgetAllocation` / `DuplicateCheck` — Cross-cutting results
- `Issues` — All failing items (filtered, for remediation reference)

### Delete/Reset/Update Modules
Exports a 2-sheet `.xlsx` with:
- Main results sheet (all resources)
- Issues sheet (non-pass items only)

---

## Testing Checklist

- [ ] Login with each registered vendor
- [ ] Logout clears all session keys
- [ ] Each verification module loads without errors
- [ ] "+ Add New Record" adds rows correctly
- [ ] Query parameters propagate to sample data grids
- [ ] Fetch & Validate fires API calls and shows results
- [ ] API Debug expanders show raw JSON
- [ ] Stat cards show correct Pass/Fail/Flag/Skip counts
- [ ] All 10 business rule sections produce results
- [ ] Download button generates valid `.xlsx` on all modules
- [ ] Delete verification correctly identifies 404/410/200-empty vs 200-with-data
- [ ] Reset verification correctly reads `Total-Count` header
- [ ] Update verification compares expected vs live values field-by-field
- [ ] Sidebar active state highlights current module
- [ ] Top ribbon shows correct vendor name and page title

---

## Support

- **Platform:** Ed-Fi ODS 2026 · Indiana DOE
- **Version:** v3.0.0
- **Website:** [www.edwisegroup.com](https://www.edwisegroup.com)

> © Edwise Group — Confidential
