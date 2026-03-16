# Sandbox Test Plan

## Purpose
This repository has passed import validation (`scripts/smoke_project.py`) and a Rialto pipeline mock run. The functionality of the components in this repository was already tested and verified before the extraction from the original codebase. The remaining work is therefore focused on confirming that nothing was broken during the creation of this new standalone repository, especially around imports, packaging, CLI entrypoints, file handling, and live Alma API integration. This document defines what still needs testing and what must exist in Alma `SANDBOX` before those tests can be run safely.

## What Has Already Been Verified
- Project imports resolve correctly.
- The Rialto pipeline CLI runs locally.
- PDF discovery, text extraction, POL extraction, CSV report creation, and file movement work in mock mode.

## What Is Still Not Verified
- Alma API connectivity using `ALMA_SB_API_KEY`
- POL lookup and identifier extraction from Alma
- Invoice discovery by POL
- Item receiving in Alma
- Item scan-in to department/work order
- Invoice approval, payment, and resulting POL closure
- Bulk invoice processing against real Sandbox invoice records
- ERP-to-Alma invoice creation and line linking

## Required Sandbox Fixtures
Prepare dedicated, disposable test records in Alma `SANDBOX`:

1. One bibliographic record with one holding and one item.
2. One open POL linked to that item.
3. One invoice linked to that POL, not yet paid.
4. Valid configuration values for:
   - library
   - department
   - work order type
   - work order status
5. A sandbox API key available as `ALMA_SB_API_KEY`.

Recommended additional negative-case fixtures:
- A POL that is already closed.
- A POL with an already received item.
- An invoice that is already paid.
- A POL with no linked invoice.

## Remaining Tests

### 1. API Connectivity Check
Goal: confirm the extracted repo can authenticate and read Alma Sandbox data.

Needed in Sandbox:
- Valid `ALMA_SB_API_KEY`

Suggested command:
```bash
poetry run python -m workflows.rialto.workflow --tsv pols.tsv --environment SANDBOX
```

Pass criteria:
- The script connects successfully and retrieves POL data without import or authentication errors.

### 2. Rialto Workflow Dry Run
Goal: validate lookup logic without changing Alma data.

Needed in Sandbox:
- Known test POL in open state
- Linked invoice discoverable from invoice lines
- Item data present (`mms_id`, `holding_id`, `item_pid`)

Pass criteria:
- The workflow finds the POL, item, and invoice and reports the expected next actions.

### 3. Rialto Workflow Live Sandbox Run
Goal: validate the real receive -> scan -> approve invoice -> pay -> verify close sequence.

Needed in Sandbox:
- All fixtures from the dry run
- Records approved for modification

Pass criteria:
- Item is received
- Scan-in succeeds with the configured department/work order
- Invoice is approved before payment
- Invoice is marked paid
- POL ends in `CLOSED` state

### 4. Rialto Pipeline Live Sandbox Run
Goal: validate end-to-end processing from PDF input through Alma operations.

Needed in Sandbox:
- A test PDF containing the dedicated test POL
- Same fixtures as the live Rialto workflow test

Pass criteria:
- PDF is processed successfully
- Output report is generated
- PDF is moved to `processed/`

### 5. Bulk Invoice Processor Sandbox Test
Goal: validate payment processing for existing Sandbox invoice IDs.

Needed in Sandbox:
- One or more unpaid test invoices
- Excel input file with invoice IDs

Pass criteria:
- The processor reads the file, updates invoice payment state correctly, and writes the TSV results file.

### 6. ERP Integration Sandbox Test
Goal: validate ERP file loading, POL price updates, invoice creation, invoice line creation, approval, and optional payment.

Needed in Sandbox:
- ERP test file
- Mapping file from ERP Number to POL ID
- POLs safe to update
- Vendor behavior understood for the target test POLs

Pass criteria:
- ERP rows load correctly
- POL prices update
- Invoice and invoice lines are created
- Optional payment succeeds when enabled

## Execution Order
Run tests in this order:

1. API connectivity
2. Rialto workflow dry run
3. Rialto workflow live run in Sandbox
4. Rialto pipeline live run in Sandbox
5. Bulk invoice processor Sandbox test
6. ERP integration Sandbox test

## Notes
- Do not use production data for these tests.
- Keep all test POLs, invoices, and items dedicated to Sandbox validation.
- Record fixture IDs and expected starting states before running live tests.
- If a test fails, capture the exact Alma object state afterward before retrying.
