# Evidence model and workflow reconciliation

## Sources are complementary

Existing acquisition project docs, the general alma-api-expert skill, toolkit source,
unit tests and earlier Sandbox evidence are the starting material. Official API
documentation decides what is documented; live Sandbox probes decide what was
observed for a specific record state, parameter combination and tenant configuration.
A previous observation is not proof of current configuration or all parameter values.

## Findings requiring careful wording

| Topic | What existing material says | Required treatment |
|---|---|---|
| Payment field | General skill/toolkit read payment.payment_status.value; bulk processor reads payment_status at the root | Verify current Sandbox response shape, then add a failing offline consumer regression before correcting code |
| Processing/approval | General skill describes approve/process as mandatory approval; wrapper sends process_invoice | Distinguish method name, requested service and resulting approval/workflow state; inspect rules and read back |
| Payment readiness | Toolkit implementation permits APPROVED or PENDING approval status in can_pay | This is wrapper logic, not a proven Alma business rule; PENDING is not a synonym for approved |
| Search filters | Older examples use vendor~ and invoice_status~ in q | Official invoice search fields and separate owner/base_status/invoice_workflow_status parameters must be checked; do not copy legacy examples as validated syntax |
| Totals | Current toolkit main returns len(collected_records) in total_record_count for offset=0 | Do not confuse a wrapper page-size count with the server's population total; inspect installed version before choosing pagination |
| Closure | Existing flow records paid/closed invoices and related PO-line closure | Invoice closure, payment and PO-line closure have separate prerequisites; electronic activation and physical receiving are not interchangeable |
| Error diagnosis | Earlier skill suggests a specific error means missing processing | Treat as a hypothesis; inspect endpoint, state and official errors rather than automatically approving or recreating an invoice |
| Payload shapes | Historical domain-status report proposes sum/currency wrappers and extra service actions | Historical review contains unresolved/conflicting claims; validate against current schema, implementation and Sandbox before applying changes |

## Workflow modes

For **existing invoices**, discover and read the existing invoice and its lines;
do not run an invoice-creation workflow merely to complete or close it.

For **new invoice creation**, verify duplicate linkage first, validate header and
line contracts, then test the relevant processing/approval/ERP/payment transitions
for the supplied configuration. Do not prescribe one universal transition chain.

For **receiving**, distinguish physical receipt from activation of electronic
resources and subsequent PO-line closure. Receiving or scan-in is a mutation even
if it appears inside a method called verification or dry run.

For **ERP integration**, distinguish recording payment in Alma from actually paying
through a financial system. Confirm whether the institutional ERP export/payment
workflow is intended. Never infer that calling paid transfers money or that no
downstream financial reporting effects exist.

## Minimal claim ledger

Use claim ID, source/version, official contract, Sandbox test ID, request shape,
expected/actual result, verdict and remaining scope. Exclude keys, key-bearing URLs,
private record identifiers and raw response bodies from committed evidence.

An operation catalog can be complete relative to a dated schema while its live
coverage remains partial. State both explicitly. Validate new claims incrementally
with relevant Sandbox tests; do not run unrelated writes just to increase coverage.
