# Hands on Alma Sandbox request tests

For saved hypotheses, step-by-step execution and automatic GET verification, use
the [workflow wizard](WORKFLOW_WIZARD.md), available as app option 3 or command
workflow-wizard. Standalone request-composer and invoice-desk operations below
are not automatically added to a wizard run.

This is an Acquisitions-project prototype, not yet a general AlmaAPITK CLI.
Run one request, inspect its actual input/output and interpret the result before
continuing. Starting scripts/sandbox_get_review.py without arguments opens the
app dashboard: request composer or invoice desk. Existing named GET commands still work.

The prototype supports GET, POST, PUT and DELETE for operations in the dated
Acquisitions catalog, plus the existing libraries GET lookup. It always selects
Alma Sandbox on the EU API host. Requests use a 15-second timeout, no retries and
no redirect following. Method dispatch and confirmation were verified with mocks;
live write operations have not been validated by this development work.

Each sent request prints the prepared URL/headers/body, actual response headers/body,
timestamps and result. Named GET tests retain their specific assertions; generic
request mode records HTTP success without certifying a business outcome. Authentication is masked, while useful
record IDs and business values remain visible. Local JSON files are saved under
ignored output/sandbox-review. Do not commit or paste authentication values.
HTTP errors retain their response content when the HTTP response was captured;
connection failures can have no response body. A pass is limited to the assertion.

## Debug terminal setup

Keep preview and Codex panes running. Create a new Zellij pane using the displayed
New pane action. It starts on WSL; run sbxtest there to enter the existing debug SBX.
Then, at the agent@dbg-tau-complete-1104 prompt:

```bash
cd /home/hagaybar/codex-rollout/2026-11-04-debug/workspace/acquisitions-api-review
acq_python=/home/agent/.cache/pypoetry/virtualenvs/alma-acquisitions-automation-Ef2DPWLU-py3.12/bin/python
```

This uses the prepared Python 3.12 project environment without changing the active
Codex pane's project branch. The variable belongs to this shell; set it again in a
new pane. No key is supplied on the command line.

## Interactive request composer

From the prepared guest shell:

```bash
"$acq_python" scripts/sandbox_get_review.py
```

1. Choose Request composer, then GET, POST, PUT or DELETE.
2. Choose an object such as Invoices, Invoice lines, Vendors or PO lines.
3. Choose the exact operation, such as list invoices or retrieve one invoice.
4. Supply the requested path IDs. Required service actions use a documented menu.
5. Add optional query parameters if needed. List requests start with limit=1;
   change it through the parameter menu. Continue with the displayed parameters.
6. For documented bodies, choose a JSON/XML file or enter a one-line JSON object.
   The prototype does not invent an empty body for a service action.
7. Review the method, full path/query, body, reference validity and last-tested date.
   Choose Send or return to selection. Data-changing requests additionally require
   typing the exact displayed confirmation, including a service action when present.
8. Inspect the actual input/output and result. Captures are saved as JSON and HTML
   under ignored output/sandbox-review. Choose another request or finish.

Enter 0 at a selection menu to cancel/back out. Ctrl+C at a prompt exits. If a write
was already sent and is interrupted or times out, its effect may be unknown: inspect
the result and read back state before retrying. HTTP 2xx is reported as transport
success with the business outcome unverified; the tool does not automatically replay
or verify a mutation. Processing, payment, receiving and deletion have real Sandbox
effects and are not discovery steps.

## Invoice desk: inspect, prepare PAY, compare

Open the dashboard and choose Invoice desk, or open it directly:

```bash
"$acq_python" scripts/sandbox_get_review.py invoice-desk
```

The terminal redraws one panel with the selected invoice ID, number/vendor,
base/workflow/approval/payment states, payment details, PAY readiness and last result.
Both API code and description are shown. Redirected output uses plain text; NO_COLOR
disables colour. The request composer also shows a panel with your selections and
the complete preview. No extra terminal library is required.

First hands-on test: choose **1 Select ID**, enter one Alma Sandbox internal invoice
ID (not its vendor invoice number), then **2 GET / Refresh / compare**. Inspect the
dashboard and **6 Actual input/output**. Stop there and interpret the current states.
Opening the desk, selecting an ID or editing payment details sends nothing.

Only after deciding that the invoice is the intended payment test:

1. Choose **8 Workflow help**. PAY means recording payment in Alma, not sending money.
   Processing, approval and ERP handoff are distinct stages. The generic composer
   exposes their documented service actions separately; the desk never chains them.
2. Choose **3 Payment details**: explicitly enter date, identifier, final amount and
   currency. No invoice total is silently substituted. Four required fields are a
   prototype policy; no institution-specific currency/exchange/tax rules are validated.
3. Choose **4 Preview PAY**. Expect exactly one POST to the selected invoice with
   op=paid and a minimal JSON payment object. It sends nothing. The local eligibility
   policy requires ACTIVE, API workflow code Ready to be Paid (UI Waiting for Payment),
   APPROVED or NOT_REQUIRED, and NOT_PAID. Paid/unknown/PENDING states require review.
4. **5 Send reviewed PAY** first performs one GET preflight. Any changed invoice or
   failed read cancels the proposal. If unchanged, the exact request is displayed
   again and the operator must type its full confirmation phrase. Cancelling here
   sends only the preflight GET. Confirming dispatches exactly one POST, without retry.
5. Inspect **6 Actual input/output**, including any HTTP error body. Then choose
   **2 GET / Refresh / compare**, followed by **7 Compare before/after**. The comparison
   is also saved in local JSON/HTML with the actual GET. Payment, invoice closure and
   PO-line closure are separate assertions. Use named lines/pol GETs for linked orders;
   the desk does not validate linked-order closure or population eligibility.

The API workflow code Waiting to be Sent means UI Ready to be paid (ERP handoff);
Ready to be Paid means UI Waiting for Payment. Neither ACTIVE nor PENDING alone
establishes payment eligibility. Rialto can mark payment status/date without changing
invoice status; do not replay PAY on a paid-but-open invoice as a closure shortcut.
Read the specialist invoice reference for dated official sources and unresolved rules.

Each invoice is limited to one PAY attempt per CLI process, including revisiting the
desk. A timeout, interrupt, failed capture or unchanged immediate read-back is not a
reason to resend: processing may be asynchronous. The lock is not durable across
relaunches, other terminals or other tools; reconcile state and saved evidence first.
The tool cannot remove the race between preflight GET and POST and cannot certify
that a submitted payment was accepted. No automatic polling, rollback or write chain
is performed. A later GET is an observation, not proof of causation for every change.

Development validation: mocked tests only, with synthetic records and fake executors.
No live Alma GET or write was issued while implementing the invoice desk. All payment
transitions and institution-specific effects remain untested until the operator runs
and reviews a bounded Sandbox experiment. Production remains unsupported by this tool.

## Help and command mode

```bash
"$acq_python" scripts/sandbox_get_review.py --help
"$acq_python" scripts/sandbox_get_review.py --list-operations --method GET --object invoice
```

Preview a vendor GET with exact named path parameters:

```bash
"$acq_python" scripts/sandbox_get_review.py request --method GET --object vendor --id vendorCode=RIALTO
```

Add --send to execute that GET. Command mode previews by default. For nested objects,
repeat --id NAME=VALUE with each path ID, and repeat --param NAME=VALUE for queries.
Use --list-operations to see exact parameter names in the path templates.

For an operation with several possible meanings, select its exact catalog key.
This example is a preview only; replace the quoted placeholder before any live use:

```bash
"$acq_python" scripts/sandbox_get_review.py request \
  --operation 'POST /almaws/v1/acq/invoices/{invoice_id}' \
  --id 'invoice_id=<sandbox-invoice-id>' --param op=process_invoice --json '{}'
```

Writes require --send plus the exact interactive confirmation; there is no --yes
or production mode. JSON objects and XML text/files are supported when their media
type is documented. Names, primitive parameter types and required inputs are checked,
but complete body schemas and business eligibility are not validated. Binary/multipart
body composition, lossless binary downloads, pagination automation, reusable profiles
and other Alma domains are deferred to the broader AlmaAPITK design.

## Existing named GET tests

These commands retain their earlier assertions. Interactive/generic requests instead
require interpretation of the actual response and separate business verification.

| Test | Purpose | Inspect before continuing |
|---|---|---|
| vendor | Resolve the known vendor code | HTTP 200, code/name/account information; assertion compares requested and returned code |
| invoices | One active invoice for the selected owner/vendor | Filters, response total, returned invoice ID and states; this is discovery, not eligibility |
| invoice | Read that invoice in detail | Base/workflow/approval and nested payment states separately |
| lines | Read its invoice lines | Linked PO references, line types and pagination completeness |
| pol | Read one linked PO line | Type/material, owner and current state; identify physical/electronic and book/non-book evidence |
| libraries | Supporting configuration lookup if ownership is unclear | Actual library labels/codes, distinct from invoice or PO ownership assumptions |

Later tests build the two electronic/physical discovery sets, establish eligibility
and choose a bounded Sandbox mutation sample. Processing and payment are separate
tests with known starting states and explicit read-back expectations; no universal
process-then-pay chain is assumed. Production acquisition writes remain out of scope.

## First test

Preview the request if useful:

```bash
"$acq_python" scripts/sandbox_get_review.py vendor --vendor-code RIALTO
```

Run this one GET:

```bash
"$acq_python" scripts/sandbox_get_review.py vendor --vendor-code RIALTO --live-readonly
```

Expected: HTTP 200, returned code RIALTO, vendor name ProQuest LLC, and
assertion_passed true. These are expected observations based on earlier reads;
interpret the actual result rather than assuming it passed. Stop after this test.

## Subsequent command forms

Invoice query, after vendor result interpretation:

```bash
"$acq_python" scripts/sandbox_get_review.py invoices --library-code AC1 --vendor-code RIALTO --limit 1 --live-readonly
```

For the next steps copy an actual ID from the preceding response, replacing the
placeholder in quotes; placeholders are not runnable fixture IDs:

```bash
"$acq_python" scripts/sandbox_get_review.py invoice --invoice-id "<invoice ID>" --live-readonly
"$acq_python" scripts/sandbox_get_review.py lines --invoice-id "<invoice ID>" --live-readonly
"$acq_python" scripts/sandbox_get_review.py pol --po-line-id "<PO line reference>" --live-readonly
```

Run these individually after reviewing the preceding result. No script chains them
or silently selects a payment sample. Codes above are pilot inputs, not defaults
embedded in the reusable specialist.

## Broader AlmaAPITK follow up

The generic cross-domain CLI is tracked in [AlmaAPITK issue 230](https://github.com/hagaybar/AlmaAPITK/issues/230). This project remains the Acquisitions prototype.
