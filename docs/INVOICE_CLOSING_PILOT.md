# Central Library / Rialto invoice pilot

The user requested two **discovery populations**, both in Alma Sandbox:

1. Central Library invoices for Rialto electronic books.
2. Central Library invoices for Rialto physical books.

These criteria do not by themselves define eligibility to mark an invoice paid.
Keep the whole population, open-invoice candidates and the selected mutation sample
as distinct sets with separate counts.

Resolve codes through configuration/vendor APIs. A platform name can differ from
the vendor's display name. Prefer a documented exact code lookup after resolving
that identity; an empty vendor-name search is not proof that the vendor is absent.
Do not embed real institution codes or invoice IDs in generic skill instructions.

Invoice discovery uses documented owner and base/workflow filters plus the vendor
search field supported by that endpoint. Confirm returned owner/vendor. Fetch and
page invoice lines, then resolve linked PO-lines as necessary to verify book type
and electronic/physical format. Do not assume every invoice contains one format,
every charge line has a PO-line, or every electronic order is a book.

Mixed-format and unresolved invoices remain review items, not members of either
automatic-payment sample. If a report is bounded or truncated, state this beside
the counts. A zero result under an unverified filter is not an empty business set.

Before testing the current bulk processor, review payment status parsing, paid/open
handling, approval readiness, duplicate prevention and final-state verification.
Use synthetic unit fixtures for corrections and separate live Sandbox acceptance.

The user reviews a small sample's result before sending the set to the acquisitions
librarian. Wider testing/production work waits for her feedback and later direction.
Prepare a review artifact; do not send it to anyone without explicit authorization.

## State-based closure investigation: 8 November 2026

Status: proposed protocol, not a validated automatic closer. No new API calls are
needed to write this plan. The operator executes each selected Sandbox mutation;
agents may research, inspect code, run mocked tests and perform bounded GETs.
Production and automatic multi-step write execution are outside this protocol.

Operator-confirmed Sandbox configuration on this date:

- invoice_skip_erp=true: skip external ERP routing in the invoice workflow.
- handle_invoice_payment=true: track payment handling after approval.

These are operator observations, not API-read configuration or claims about
production. They do not explain every historical invoice state or establish whether
money was paid outside Alma. Preserve both settings during the experiment.

The working hypothesis is that a valid existing invoice can progress through review
and applicable approval into payment handling, then close when the appropriate
continuation is completed. Existing PAID records require a separate continuation
branch; they must not be paid again as a shortcut. No mark_in_erp step belongs in
the default hypothesis for this ERP-skipping configuration. A historical ERP-stage
record needs investigation rather than an invented corrective action.

### Completion and scope

Closure success means a subsequent GET confirms invoice_status.value=CLOSED.
Record workflow, approval, payment and voucher values independently. No HTTP-only
success, paid-only flag or skipped record counts as newly verified closure.
Already CLOSED is a no-op with any inconsistent fields flagged separately.
Unknown real-world settlement means a payment decision is unresolved, even if the
Alma field is NOT_PAID. A controlled Sandbox simulation must explicitly identify
its test payment values; do not represent them as historical financial evidence.

Invoice closure and linked PO-line closure are separate assertions. Record relevant
PO-line state and receiving/activation evidence without silently changing either.
Electronic-book and physical-book populations stay separate, with mixed/unresolved
invoices held for review. Group each population by the complete state tuple, not
just its visible workflow label. Include already-closed controls when discovering
state groups; an ACTIVE-only query cannot establish whole-population coverage.

### Initial routing matrix

All write entries below are hypotheses for individually reviewed operator tests,
not an executable state machine. API code Ready to be Paid means UI Waiting for
Payment; API Waiting to be Sent means UI Ready to be paid.

| Current condition | Candidate next step | Expected result / stop condition |
|---|---|---|
| Base CLOSED, any payment state | GET only; no mutation | Confirm closure; flag inconsistencies separately |
| InReview, NOT_PAID | Inspect header, all lines/links and approval context; if suitable, operator POST op=process_invoice with explicit empty invoice object | Processing may stay in review, require manual approval or advance; GET determines which. Do not assume approval or pay next automatically |
| InReview, PAID | Same read inspection; investigate a single operator process_invoice test while preserving existing payment data | Hypothesis: advance the existing workflow without recording payment again. Whether it closes or waits remains untested |
| InApproval | Inspect approval status/rules; stop at a manual-approval boundary | No independently verified API approval transition is established. The wrapper name approve_invoice is insufficient |
| Waiting for Payment, NOT_PAID | Resolve payment intent/evidence; operator may test POST op=paid with explicit voucher fields | Expected payment confirmation and eventual closure; verify each separately by GET |
| Waiting for Payment, PAID | Investigate API equivalent of payment-stage continuation | UI Save & Continue is documented; its exact API equivalent for this starting state is not established. Do not invent op=close or repeat paid |
| Ready to be paid / API Waiting to be Sent | Inspect historical state versus current ERP-skip configuration | Hold; mark_in_erp is not an assumed repair |
| Missing, conflicting or unrecognized states; other payment values | Capture and classify as unresolved | No write until a documented/testable branch is defined |

Processing can change linked financial/order state, even without sending a new
payment confirmation. Review those effects before an operator test. "No alerts
returned" does not establish that review rules, line problems or approval holds
are absent. A full list of safe branches is the goal; forced closure from every
possible state is not promised.

### Existing code to reconcile and reuse

- workflows/invoices/bulk_processor.py supplies invoice-list input, iteration,
  before/after GETs and tabular reporting. Its current paid-or-closed skip conflates
  states, and operation_success does not enforce CLOSED. Reuse useful reporting,
  but correct those semantics before any batch closure use.
- AlmaAPITK acquisition methods supply GET and service dispatch. The reviewed source
  accepts PENDING in can_pay, always uses an empty service body and names a
  process_invoice wrapper approve_invoice. Compare installed SDK 0.4.5 with source
  before reuse; none of those choices proves business readiness or approval.
- workflows/invoices/erp_integration.py creates invoices/lines, updates PO prices
  and can chain processing/payment. It is a source of implementation lessons, not
  the runner for closing existing invoices; avoid invoking its creation path.
- scripts/sandbox_get_review.py, sandbox_request_cli.py and sandbox_invoice_desk.py
  provide explicit previews, masked actual I/O and a separate read-back comparison.
  Extend them only for the next reviewed experiment; retain operator write control.
- Reconcile older ACQUISITIONS_DOMAIN_STATUS.md operation examples against the
  official catalog: suggested approve/cancel/ready_to_pay names are not evidence of
  supported invoice-service operations.

### Test sequence and evidence record

1. Establish the read-only baseline and state groups, including one CLOSED control.
   Use bounded pages first; clearly label incomplete coverage. Check invoice owner,
   vendor, all relevant lines and linked PO-line type/material/ownership. Select
   one representative per distinct branch before broader discovery or batch work.
2. Prepare one case card: run ID, invoice ID, scope, starting state, configuration
   source/date, source commit, SDK version, hypothesis, one exact request, payload,
   expected allowed outcomes and fields that must remain unchanged. Identify whether
   financial data represents an existing fact or an explicit Sandbox simulation.
3. Immediately before the operator action, GET the invoice and stop if it changed.
   Operator reviews/confirms one write. Preserve masked actual request/response,
   HTTP status, Alma error/tracking identifiers, timestamp and elapsed time.
4. Perform explicit read-back GETs. Initially inspect one result at a time; if
   pending, use at most five reads over at most 30 seconds. No repeated write.
   If still unresolved, label pending/unknown and stop. An uncertain write outcome
   requires reconciliation before any later attempt, including another CLI run.
5. Compare expected versus actual workflow/approval/payment/base/voucher values,
   and relevant linked-order effects. Classify the hypothesis as supported for this
   tested case, contradicted, inconclusive or untested. Record unexpected differences;
   do not silently change the expected outcome after seeing the result.
6. Update this project's routing matrix and case record with evidence IDs/dates.
   Keep private IDs/bodies in ignored output/sandbox-review; commit only reviewed,
   sanitized findings and regression tests with synthetic fixtures. Add generic
   documented/observed facts to the specialist separately, preserving test scope.
   Re-test a revised hypothesis under a new run ID. Expand only after interpretation.

A per-step record needs: expected result, actual result, verdict, next action and
evidence location, alongside the exact I/O and execution metadata. Distinguish
request submitted, HTTP accepted, workflow progressed, payment recorded and closure
verified. The [workflow wizard](WORKFLOW_WIZARD.md) now supplies saved case plans,
explicit expected checks, automatic bounded GET verification and durable run history.
Its initial routing restrictions expose unresolved cases as holds; this is not a
validated automatic closer or completed transition matrix. No active ERP integration
is present: all changes are manual or operator-controlled API actions.

First experiment priority: read/classify an existing paid-in-review example and an
unpaid-in-review example. Prepare a single process_invoice hypothesis for one
suitable record before another PAY test. Whether that operation is valid and useful
from its exact starting state remains a question to test, not an assumed solution.

### Reference contract

- [Configuration meanings](https://knowledge.exlibrisgroup.com/Alma/Product_Documentation/010Alma_Online_Help_%28English%29/020Acquisitions/040Configuring_Acquisitions/200Configuring_Other_Settings)
- [Processing and Save & Continue](https://developers.exlibrisgroup.com/blog/creating-an-invoice-using-apis/)
- [Invoice service operations](https://developers.exlibrisgroup.com/alma/apis/docs/acq/UE9TVCAvYWxtYXdzL3YxL2FjcS9pbnZvaWNlcy97aW52b2ljZV9pZH0=/)
- [Payment-stage continuation](https://knowledge.exlibrisgroup.com/Alma/Product_Documentation/010Alma_Online_Help_%28English%29/020Acquisitions/020Invoicing/060Working_with_Invoices_Waiting_for_Payment)

Documentation checked 8 November 2026. No mutation was performed to prepare this
protocol. Historical read examples do not validate any of its proposed transitions.
