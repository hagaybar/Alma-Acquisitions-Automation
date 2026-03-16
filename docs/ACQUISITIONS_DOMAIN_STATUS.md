# AlmaAPITK Acquisitions Domain Status

## Scope & Sources
- File reviewed: `src/domains/acquisition.py` (heads at `create_invoice_with_lines` ~L500, `receive_item` ~L1304, `check_pol_invoiced` ~L1753).
- Compared against Alma Acquisitions product workflows (purchasing → receiving → invoicing → payment/ERP) and public Alma Acquisitions REST API endpoints (`/almaws/v1/acq/*`) available as of 2024.
- Focus: feature coverage, workflow alignment, and notable gaps; not a formal QA verdict.

## Implementation Inventory

| Functional Area | Key Methods | API Endpoints Used | Workflow Notes |
|-----------------|-------------|--------------------|----------------|
| Invoice creation (header) | `_build_invoice_structure()`, `create_invoice_simple()`, `create_invoice()` | `POST /acq/invoices` | Supports SANDBOX/PROD toggle via `AlmaAPIClient`; header payload constructed via helper with optional VAT/charges. |
| Invoice lines | `_build_invoice_line_structure()`, `create_invoice_line_simple()`, `create_invoice_line()` | `POST /acq/invoices/{id}/lines` | Auto-fetches fund from POL when absent; hard-codes `percent=100` distribution. |
| End-to-end invoice flow | `create_invoice_with_lines()` | Sequence of calls to endpoints above plus service ops | Automates totals, duplicate checks, optional approve/pay toggles. |
| Invoice service ops | `process_invoice_service()`, `approve_invoice()`, `mark_invoice_paid()`, `mark_invoice_in_erp()`, `reject_invoice()` | `POST /acq/invoices/{id}?op={operation}` | Implements `paid`, `process_invoice`, `mark_in_erp`, `rejected`. No hooks for other documented ops (e.g., cancel, ready_to_pay). |
| Invoice retrieval | `get_invoice()`, `get_invoice_lines()`, `list_invoices()`, `search_invoices()`, `get_invoice_summary()` | `GET /acq/invoices`, `GET /acq/invoices/{id}`, `GET /acq/invoices/{id}/lines` | Coverage for basic read/list queries; summary helper reshapes payload. |
| Duplicate prevention | `check_pol_invoiced()` | `GET /acq/invoices?q=pol_number~{pol}` + `GET /acq/invoices/{id}/lines` | Flags existing invoice lines before creating new ones; warns on API search limits. |
| POL metadata | `get_pol()`, `update_pol()`, `get_vendor_from_pol()`, `get_fund_from_pol()`, `get_price_from_pol()` | `GET /acq/po-lines/{id}`, `PUT /acq/po-lines/{id}` | Reads vendor/fund/price to feed invoice helpers; update is pass-through (no schema guidance). |
| POL receiving | `get_pol_items()`, `extract_items_from_pol_data()` | `GET /acq/po-lines/{id}/items`, structure parsing | Provides flat item list for downstream workflows. |
| Receiving workflow | `receive_item()`, `receive_and_keep_in_department()` | `POST /acq/po-lines/{pol}/items/{item}?op=receive` + `bibs.scan_in_item()` | Allows optional receive date and department. Composite helper keeps item in department via work order scan. |
| Health checks | `test_connection()` | `GET /acq/invoices` | Simple ping that expects HTTP 200. |

## Alignment with Alma Workflows

### Invoice Lifecycle
- **Create → Review → Approve:** Helpers mirror the documented sequence (create header, add lines, process/approve). `create_invoice_with_lines()` orchestrates the canonical steps and surfaces partial failures.
- **Payments & ERP Posting:** `mark_invoice_paid()` and `mark_invoice_in_erp()` cover two key invoice-service operations. There is no explicit support for “Ready to be Paid”, “Cancel”, or “Delete” actions exposed in Alma UI/API.
- **Adjustments & Credits:** `_build_invoice_structure()` allows `additional_charges` and `invoice_vat` but there are no high-level helpers for credits, price adjustments, or multi-line fund splits that Alma supports. Fund distribution is limited to one fund at 100%.
- **Attachments / Notes:** No methods for `/invoices/{id}/attachments` or `/notes`, which Alma workflows use for documentation/audit trails.

### Purchase Order Line & Receiving
- **POL Context:** The domain reads vendor, fund, and price from existing POLs but does not create/encumber new POLs, nor does it manage POL statuses (e.g., move to Closed, reopen).
- **Receiving Scenarios:** `receive_item()` aligns with the “Receive New Material” workflow using `op=receive` and optional department parameters. `receive_and_keep_in_department()` extends this with a scan-in to prevent Transit, matching the documented “Keep in department” scenario validated in `docs/POL-5989_TEST_SUMMARY.md`.
- **Partial/Serial Receiving:** No logic for multi-copy partial receiving, claiming, or automatic work order completion; Alma supports those through additional parameters/operations.

### Fund & Fiscal Management
- **Fund Distribution:** The implementation assumes a single primary fund (percent=100). Alma allows multiple funds, prorated splits, and encumbrance/disencumbrance handling—none are modeled here.
- **Encumbrance/Disencumbrance:** No calls to budgets, ledgers, or fiscal periods (REST endpoints under `/acq/bibs`, `/acq/funds`). Invoices created here rely on Alma’s back office to adjust encumbrances automatically, but the domain does not expose controls or verifications.
- **Currency Handling:** Helpers accept a currency code but convert amounts to plain floats (`total_amount`, `price`). Alma’s API examples wrap amounts in `{ "sum": ..., "currency": { "value": ... } }`. `$client.post()` may coerce floats, but mismatch risk remains for locales or currency rounding rules.

### Vendor & ERP Integration
- **Vendor Data:** Only vendor code retrieval from POLs is available. There are no vendor lookups (`/acq/vendors`) or validation against vendor accounts, which Alma workflows use before invoice approval.
- **ERP Sync:** `mark_invoice_in_erp()` performs the API call, but there is no polling or status reconciliation with ERP integration tasks (e.g., verifying export files, batching).

### Monitoring & Error Handling
- The domain prints to stdout for progress/errors rather than leveraging `self.client.logger`, deviating from the logging infrastructure designed in `src/alma_logging`.
- `AlmaAPIError` rethrows preserve status codes, but there is limited structured context (e.g., invoice ID, POL ID) for downstream error analytics.
- Duplicate checks rely on invoice search; Alma documentation notes search limits and indexing delays, so high-volume sites might still experience race conditions.

## Observed Divergences vs REST Schema
- `create_invoice_simple()` sends `total_amount` as a float; Alma API examples use nested `{"sum": ...}` objects. Need confirmation that Alma’s JSON parser accepts raw numeric values (it often does, but not guaranteed).
- `_build_invoice_line_structure()` sets `"price": amount` instead of `"price": {"sum": amount, "currency": {...}}`. Works in some tenants but diverges from published schema; consider aligning to avoid future validation failures.
- `process_invoice_service()` allows `operation` outside the known set but only warns via `print`. Alma rejects unsupported ops with 400; could pre-validate against the official list (`approve`, `reject`, `delete`, `mark_in_erp`, `paid`, etc.).
- `receive_item()` submits `<item/>` body with `Content-Type: application/xml`. Alma expects a minimal XML structure, so this is compliant, but response handling falls back to manual XML parsing—might benefit from explicit schema parsing to extract process status.

## Capabilities Not Yet Covered
- Creating/closing invoices in batch, or querying task lists (e.g., “Invoices in review” queues).
- Managing invoice adjustments (shipping, overhead) via `/additional_charges` helper functions.
- Handling invoice line types beyond `REGULAR` (e.g., `DISCOUNT`, `VAT`, `OVERHEAD`).
- Deleting invoice lines or entire invoices (`DELETE /acq/invoices/{id}` and `/lines/{line_id}`).
- Support for advance shipping notices, receiving work queues, or claim notifications.
- Integration with Alma’s task lists (approval/review) which may require `/tasks` endpoints.
- Unit tests reference `INVOICE_CREATION_TODO.md` but there are no automated tests verifying live API behavior (dry-run only).

## Questions & Follow-Ups
1. Should we refactor payload builders to match Alma’s documented JSON structure (nested `sum/currency`) to guard against API schema changes?
2. Do we need wrappers for additional invoice service operations (`cancel`, `ready_to_be_paid`, `delete`), or are current workflows limited to approve/pay/ERP?
3. How should multi-fund splits be represented? Alma requires balancing `percent` or `amount` across funds; current helpers hard-code a single 100% entry.
4. Is there appetite for vendor validation (e.g., confirm vendor accounts or ERP references) before invoice creation?
5. Should receiving workflows include serial/partial receiving logic, claims, or automatic work order closure?
6. Logging: move from `print` to structured logger to align with `src/alma_logging` module for better observability?

This report can be expanded with scenario-specific test results once sandbox or production dry-runs are executed against representative Alma data.

