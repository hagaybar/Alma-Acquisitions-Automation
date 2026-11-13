# almaapitk 0.4.5 → 0.7.0 audit

Issue #11 asked for 0.6.0; 0.7.0 (2026-11-11) is now the current release, so the bump
goes there directly. Audit date: 2026-11-13.

## (a) Usage surface

| Where | almaapitk use |
|---|---|
| `workflows/rialto/workflow.py:41,72-74` | `AlmaAPIClient(env)`, `Acquisitions`, `BibliographicRecords`, `AlmaAPIError` |
| `workflows/rialto/workflow.py:102` | `Acquisitions.search_invoices(query=..., limit=100)`; reads `result['invoice']`, uses `len()` |
| `workflows/rialto/workflow.py` | `get_pol`, `get_invoice`, `get_invoice_lines`, `extract_items_from_pol_data`, `receive_and_keep_in_department`, `approve_invoice`, `mark_invoice_paid` |
| `workflows/rialto/pipeline.py:46` | `AlmaAPIClient` |
| `workflows/invoices/erp_integration.py:16,33-34` | `AlmaAPIClient`, `Acquisitions`, `AlmaAPIError` (caught at 227, 317, 373); `get_pol`, `update_pol`, `create_invoice(dict)`, `create_invoice_line(id, dict)`, `approve_invoice`, `mark_invoice_paid`, `test_connection` |
| `workflows/invoices/bulk_processor.py:16,143-144` | `AlmaAPIClient`, `Acquisitions`; `get_invoice`, `mark_invoice_paid`, `test_connection` |
| `invoice_closer/gateway.py:34-38` | `AlmaAPIClient(env)`, `AlmaAPIClient(env, max_retries=0, timeout=...)`, `.get(path, params=)`, `.post(path, data=, params=)`; catches `requests.Timeout` / `ConnectionError`, reads `status_code` / `alma_code` from raised errors |
| `scripts/smoke_project.py:21-23` | imports `AlmaAPIClient`, `Acquisitions`, `BibliographicRecords` |
| `tests/logging/test_no_credential_leak.py` | `AlmaAPIClient`, `AlmaAPIError`, the `almapi.api_client` logger |

Environment: `ALMA_SB_API_KEY`, `ALMA_PROD_API_KEY`. No `RetryError`, `build_alma_bib_xml`,
`DEFAULT_LEADER`, `total_record_count` from the toolkit, or `AlmaInvalidPolModeError` in use.

## (b) Upstream changes 0.4.6 → 0.7.0 that touch this surface

From `CHANGELOG.md`, plus a diff of the two wheels (signatures and bodies of every method above):

- 0.4.6: default log level INFO for every domain (was DEBUG for acquisitions/api_client), gated on
  the `almapi` parent logger; full bodies no longer logged by default; PII redaction; **POST is no
  longer retried automatically**; `AlmaAPIClient(api_key=...)` added; `CredentialError`.
- 0.5.0: `40166411` outside acq URLs raised as plain `AlmaAPIError`; MARC builder changes.
- 0.6.0: `AlmaTimeoutError` (subclass of `requests.Timeout`); per-call `timeout=`; 5xx after retries
  raised as `AlmaServerError` (not `RetryError`); `Retry-After` capped at 120 s;
  `search_invoices` returns Alma's grand total in `total_record_count` and one page per call;
  invoice *builders* send schema-correct field names (#172).
- 0.7.0: Alma Lab; `raw_request`; 401/429/5xx outrank mapped Alma codes.

Wheel diff of the used methods: only additive signature changes (`api_key=`, `timeout=` on
`get`/`post`) and the `search_invoices` paging change. All other used method bodies are identical
apart from unused exception variables.

## (c) Classification

| Symbol | Verdict |
|---|---|
| `AlmaAPIClient(...)`, `.get`, `.post` | changed, compatible (new optional kwargs) |
| `search_invoices` | changed, compatible: Rialto code uses `len(result['invoice'])`, never `total_record_count`, and passes no offset |
| `create_invoice`, `create_invoice_line` | unchanged; this repo passes raw dicts, not the builders fixed in #172 |
| `get_pol`, `update_pol`, `get_invoice`, `get_invoice_lines`, `approve_invoice`, `mark_invoice_paid`, `receive_and_keep_in_department`, `extract_items_from_pol_data`, `test_connection` | unchanged |
| `AlmaAPIError` catches | compatible: `AlmaServerError` / `AlmaTimeoutError` paths still land in existing handlers |
| invoice closer error handling | compatible: timeouts are still `requests.Timeout`; 5xx errors still carry `status_code` |
| `almapi.api_client` DEBUG output | **changed**: not emitted at the default INFO level. Breaks `test_debug_logging_redacts_authorization_header`; fixed by enabling DEBUG inside the test |

## (d) Repo-specific risks

- The Rialto pipeline runs in production on masedet from `prod`. Nothing here changes its code;
  the behaviour differences it will see are: POSTs (receive, pay) are no longer auto-retried on
  5xx (safer: no duplicate payment), and less console/file logging by default.
- `search_invoices(limit=100)` keeps returning at most 100 invoices per call, as before.

## (e) Verdict

**SAFE WITH CHANGES**: one test adjusted to the 0.4.6 logging default. No production code change.

## Validation

- Pin `^0.7.0`; `poetry update almaapitk` moved only almaapitk (0.4.5 → 0.7.0); `poetry check --lock` passes.
- L2: `poetry run pytest`: 34 passed (the logging test failed before its fix, passes after). Smoke test passes.
- L3 (SANDBOX, reads only): invoice closer dry runs on set 43266180120004146 (10 already closed) and
  on a print + closed invoice file (held / already closed) behave as on 0.4.5; Rialto workflow
  `--dry-run` on one print POL completed (verify: success).
- **Left for the owner:** the issue's full L3 (Rialto create → receive → invoice with writes) and the
  DevSandbox cycle on masedet after merge.
