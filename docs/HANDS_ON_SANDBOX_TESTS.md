# Hands on Alma Sandbox tests

Run one test, inspect its input/output and interpret the result before continuing.
scripts/sandbox_get_review.py executes one named GET only. It previews by default;
--live-readonly explicitly runs it. SDK selection is SANDBOX, timeout 15 seconds,
retries disabled and redirects refused. It does not process or pay invoices.

Each live test prints the prepared URL/headers/body, actual response headers/body,
timestamps, expected assertion and result. Authentication is masked, while useful
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

## Planned sequence

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
