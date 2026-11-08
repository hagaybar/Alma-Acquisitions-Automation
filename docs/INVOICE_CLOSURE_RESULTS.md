# Invoice closure experiment results

## Case 001: one electronic-book invoice

Operator-run Alma Sandbox experiment, 8 November 2026, almaapitk 0.4.5. One EDI
invoice, one electronic-book one-time PO line (E_BOOK_OT, material BOOK). Operator
confirmed ERP skip=true, payment handling=true and no active ERP integration.
Private identifiers, payloads, screenshots and complete I/O remain local; the
append-only workflow run is the source of truth. Generic findings are also recorded
in the specialist's invoice-transition-evidence.json.

| Step | Expected | Actual | Verdict |
|---|---|---|---|
| PROCESS | Reach Waiting for Payment, preserve payment/owner/vendor | Response unknown after approximately 15 seconds; initial GET rounds unchanged; later GET observed APPROVED / Waiting for Payment with invariants preserved | Expected state observed; request outcome unknown |
| Linked order observation | Record any side effects | PO line changed from WAITING_FOR_INVOICE to CLOSED before PAY, while invoice remained ACTIVE/NOT_PAID | Observed effect in this case; not a universal closure rule |
| PAY simulation | CLOSED / PAID, four supplied voucher fields, same owner/vendor | HTTP 200; automatic GET confirmed all eight checks | Supported for this case |
| UI corroboration | Confirm closure and inspect alerts | Operator screenshots show Closed and all four alerts still present | Closure corroborated; alerts retained |

The payment was explicitly a Sandbox simulation, not evidence of real-world
settlement. No fiscal-year error was returned for this date/record; this does not
establish that all fiscal periods or payment-date combinations are valid.

Important response details:

- Invoice base status CLOSED; invoice_workflow_status empty object.
- Four alert codes remained: DIFFERENT_VENDOR_ACCOUNT, DIFF_PRICE_THAN_POLINE,
  EDI_INVOICE_OF_EXTERNAL_SYSTEM and NOT_READY_LINES.
- The JSON used flat alert, singular. Earlier extraction of alerts alone missed
  these entries. The invoice desk and wizard now display normalized recorded alerts;
  raw responses and original test events are unchanged.

Alerts did not prevent processing progression/payment closure in this case. This
does not authorize ignoring them in every invoice. HTTP timing and asynchronous
workflow progression also require separate evidence; the processing timeout was
not cured by replaying the write.

## Deferred branch: physical book PAID but still In Review

A bounded read-only discovery found a Central Library/RIALTO invoice with one
physical-book one-time PO line (PRINTED_BOOK_OT, material BOOK): ACTIVE, InReview,
approval PENDING, payment PAID, linked order SENT. It has the same four alert codes.
Its voucher amount is zero and identifier blank; do not infer actual settlement.
Private candidate details and three GET captures are in ignored output folders.

Proposed experiment: determine whether PROCESS alone advances the existing
paid-in-review invoice while preserving every payment field. Choose an explicit
expected outcome before the operator confirms the action. A diagnostic expectation
such as Waiting for Payment tests only that stage; a CLOSED expectation directly
tests the closure hypothesis but may prove unmet. Do not PAY it again, force a
closure or alter voucher data to make a result pass. Record linked-order changes
independently; its physical receiving situation differs from Case 001.

This candidate changes both starting payment state and format. It is useful branch
coverage, not a controlled experiment isolating which variable explains an outcome.
If it remains open, a separate paid-stage continuation investigation is required.

**Operator update: physical receiving branch on hold.** Staff may have shelved items
without completing Alma receiving. The candidate's actual receipt/item/loan state
has not been checked, and a SENT PO line alone does not establish the item's state.
The operator reports that a receiving action could affect item processing,
availability or active loans. Do not receive, change item processes, or try to
complete physical orders as a closure shortcut. No automatic remediation is agreed.
Physical RIALTO purchasing has ceased; priority is electronic-resource invoices.

The hypothesis that non-receipt prevents invoice closure itself is not established
by this case. Invoice closure and linked PO-line closure remain separate assertions.
No write was performed on this candidate during discovery. Future receiving work
requires a separately designed investigation of actual item and loan conditions.

## Current next branch: electronic resources

Seek an electronic-book invoice with a different starting state, preferably PAID
but still In Review, so the continuation experiment does not introduce physical
receiving. Inspect actual linked types/material and all lines; hold mixed or
unresolved records. A suitable candidate has not yet been selected after this
operator update. Do not proceed with the earlier physical candidate.

## Deferred CLI improvements

- DONE (feature/short-write-confirmation): writes now require typing a short action
  word instead of the full request line.
- Offer invoice amount/currency as editable proposed payment defaults; do not silently
  assert that they equal an actual historical payment.
- Review configurable verification timing after the observed delayed processing.

Alert handling regression validation: all 111 offline tests passed. No write was
issued by the desktop agent while recording findings or discovering the candidate.
