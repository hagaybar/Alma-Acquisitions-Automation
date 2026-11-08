# Invoice workflows and API interpretation

## Existing versus new invoices

For an existing invoice, inspect its header, lines, linked orders and current states.
Do not create another invoice to work around processing/payment failures. For new
invoice creation, reuse project duplicate/linkage checks, validate header/line payloads
and test the relevant transitions. The current skill has no live creation coverage.

## Distinct state dimensions

| Dimension | Evidence to inspect | Interpretation boundary |
|---|---|---|
| Invoice base state | invoice_status | ACTIVE is not a payment-eligibility decision |
| Invoice workflow | invoice_workflow_status, including value and description | Preserve both if they differ; do not silently replace one with a familiar label |
| Approval | invoice_approval_status | Toolkit readiness logic is not proof of institutional approval policy |
| Payment | payment.payment_status | This nested path was observed in a bounded Sandbox read; revalidate other response shapes/versions |
| ERP/export | Relevant invoice fields, configured integration and service effects | Recording an ERP state is distinct from processing and payment |
| PO-line state | Linked PO-line status and relevant receiving/activation/invoicing data | Closed invoice does not by itself prove closed PO-line |

## Service operations

The current official catalog documents invoice-service `op` values mark_in_erp,
paid, process_invoice and rejected, plus create_rt_invoice. These are documented
contracts, not live-tested transitions. Read the exact official parameter/body schema
and current state requirements before a previously unused operation.

In the reviewed toolkit source, approve_invoice delegates to process_invoice.
That implementation fact does not prove that processing always ends in approval.
The reviewed payment guard permits PENDING in its can_pay calculation; this is
wrapper logic requiring separate business/API validation, not a domain synonym.

The toolkit posts an empty object for service operations. Whether that is sufficient
for a particular action/configuration must be verified against the official body
contract and a scoped Sandbox test. Do not turn earlier successful examples into
an assertion that all operations need the same payload.

The paid operation must be investigated as a payment-recording action, not used as
a generic administrative close. Confirm the intended financial/ERP semantics and
read back the result. Current evidence does not establish any mutation transition.

## Implementation discrepancies and troubleshooting

The baseline bulk processor read payment_status at the root. The review branch
corrects its before/after reads to the observed nested field; three regressions
failed before correction and all 16 configured offline tests passed after it.
The underlying duplicate guard and already-paid skip behavior were retained.
This does not resolve the business treatment of an invoice that is paid but open,
or prove that the processor's success flag enforces every desired final state.

Legacy query examples use vendor/invoice_status in q. Use the current official
invoice search fields and separate owner/base_status/invoice_workflow_status filters
instead of treating those examples as authoritative. Validate the returned predicate.

For errors, collect the HTTP operation, relevant state, sanitized error code and
official error contract. A general retrieval/validation error does not uniquely
prove a missing approval step. Read back before retrying an uncertain mutation;
do not force payment, recreate an invoice or automatically process it as a diagnosis.
