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

## Payment flow: documentation checked 8 November 2026

**Evidence: official documentation, not a live mutation test.** Invoice processing,
approval, ERP handoff, payment confirmation and closure are separate stages.
Institutional configuration can skip ERP or payment tracking. With
handle_invoice_payment=true, the ERP handoff can lead to Waiting for Payment;
false can close the invoice without waiting for payment confirmation. Do not change
that configuration merely to make a test work.

Preserve the API/UI naming distinction documented in the invoice schema:

| API workflow code | User-facing stage |
|---|---|
| Waiting to be Sent | Ready to be paid; ERP handoff stage |
| Ready to be Paid | Waiting for Payment; payment stage |

The invoice service POST with op=paid records a payment confirmation in Alma. It is
not an instruction to transfer money. The official ERP integration example supplies
a minimal invoice object containing payment.voucher_date, voucher_amount,
voucher_currency and voucher_number. The invoice schema also documents optional
explicit_ratios and notes; create_rt_invoice controls a reporting-tax invoice.
Do not replay all GET fields or infer final paid amount/currency from invoice totals
when exchange rates may apply. Inspect the relevant financial requirements.

The API schema describes a default current payment date; the UI payment guide
requires a payment identifier for Accounting Department. Do not assume UI field
requirements completely specify the service API's conditional validation. The
project's guided PAY desk requires all four voucher fields as a conservative local
prototype policy, not a universal Alma requirement. It uses ACTIVE, APPROVED or
NOT_REQUIRED, the waiting-for-payment workflow code and NOT_PAID as local entry
conditions. These checks are not proof that Alma will accept the action.

The schema warns that processing is asynchronous. Read back payment, base and
workflow state after an action; a POST body or HTTP 2xx alone is insufficient.
Inspect linked PO lines separately: closure depends on invoicing/payment and
receiving or activation. An older official ERP blog comment also reports a PO-line
closure defect; neither that historical report nor current workflow prose proves
this institution's current behavior. Do not automatically close PO lines to hide a
discrepancy.

Rialto's optional "Mark Invoices as Paid in Alma" feature updates payment status/date
without itself changing invoice status. This makes paid-but-open a meaningful
investigation case; it does not establish that this institution enabled the option
or that repeating op=paid is an appropriate remedy.

Official references checked on that date:

- [Invoice service](https://developers.exlibrisgroup.com/alma/apis/docs/acq/UE9TVCAvYWxtYXdzL3YxL2FjcS9pbnZvaWNlcy97aW52b2ljZV9pZH0=/)
- [Invoice schema and payment fields](https://developers.exlibrisgroup.com/alma/apis/docs/xsd/rest_invoice.xsd/?tags=POST)
- [ERP invoice API integration and minimal payment example](https://developers.exlibrisgroup.com/blog/alma-erp-invoices-integration-using-apis/)
- [Invoicing workflow and configuration](https://knowledge.exlibrisgroup.com/Alma/Product_Documentation/010Alma_Online_Help_%28English%29/020Acquisitions/020Invoicing/010Invoicing_Workflow)
- [Working with invoices waiting for payment](https://knowledge.exlibrisgroup.com/Alma/Product_Documentation/010Alma_Online_Help_%28English%29/020Acquisitions/020Invoicing/060Working_with_Invoices_Waiting_for_Payment)
- [Rialto invoicing option](https://knowledge.exlibrisgroup.com/Rialto/Product_Documentation/040Rialto_Administrator_Guide/API_Invoicing_Workflow_and_Options)

**Last live PAY test: none.** Payload construction, local policy, confirmation,
preflight-change detection and read-back comparison have offline mocked coverage in
the project. This is implementation evidence, not validation of an Alma transition.

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

## Validation status of invoice claims

| Claim | Validity indication | Last live test |
|---|---|---|
| Owner/vendor/ACTIVE search predicate | Confirmed on the three returned records only | 8 Nov 2026 09:46 Israel time |
| Nested payment status field | Confirmed in one invoice detail; root field absent | 8 Nov 2026 09:46 Israel time |
| Invoice-line collection and linked PO read | Confirmed for one invoice and one linked PO line | 8 Nov 2026 09:46 Israel time |
| approve_invoice maps to process_invoice | Source-reviewed implementation fact; resulting approval not established | Not transition-tested |
| PENDING makes an invoice eligible for payment | Unresolved business/API claim; wrapper logic is insufficient | Not tested |
| paid produces the desired closure | Documented service action; before/after business result untested | Not tested |
| ERP and PO-line closure effects | Configuration-dependent and not established by current reads | Not tested |

See [validation-status.md](validation-status.md) and the dated evidence for exact
operation scope. A test date does not establish every parameter combination.
