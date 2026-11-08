# Guided invoice workflow experiments

An operator-driven prototype for existing Central Library (AC1) / RIALTO invoices
in Alma Sandbox EU. It records hypotheses and evidence; it is not a validated
universal closer. There is no active ERP integration. Each run requires operator
confirmation of invoice_skip_erp=true and handle_invoice_payment=true.

## Start in the existing debug guest terminal

```bash
cd /home/hagaybar/codex-rollout/2026-11-04-debug/workspace/acquisitions-api-review
acq_python=/home/agent/.cache/pypoetry/virtualenvs/alma-acquisitions-automation-Ef2DPWLU-py3.12/bin/python
"$acq_python" scripts/sandbox_get_review.py workflow-wizard
```

The home screen also offers Workflow wizard as option 3. Local-only commands:

```bash
"$acq_python" scripts/sandbox_get_review.py workflow-wizard --help
"$acq_python" scripts/sandbox_get_review.py workflow-wizard --list-runs
"$acq_python" scripts/sandbox_get_review.py workflow-wizard --resume RUN_ID
"$acq_python" scripts/sandbox_get_review.py workflow-wizard --report RUN_ID
```

Opening, creating or resuming a run sends nothing. No key appears on the command
line. Writes require the exact typed request confirmation, including the service op.

## One guided experiment

1. Choose New experiment run, enter the internal invoice ID (not its vendor invoice
   number) and confirm the displayed Sandbox configuration. Its provenance is saved
   as operator confirmation, not an API configuration observation.
2. **1 Inspect / refresh** automatically GETs the invoice, paged lines and linked
   PO lines. Inspect the states and suggested route. API Ready to be Paid means
   UI Waiting for Payment. The classification does not establish real settlement.
3. **2 Build one experiment** offers PROCESS, PAY, invoice PUT or invoice-line PUT.
   Unsupported states show a hold explanation. Enter/accept a hypothesis and choose
   expected results. The proposal and complete request are saved without sending.
4. **3 Run saved step** refreshes the invoice, lines and orders. Any difference from
   the planned baseline prevents a write; inspect and create a new experiment.
   Otherwise review the request again and type its confirmation. Cancellation sends
   only the preflight GETs. One write is followed by automatic bounded GET verification.
5. Inspect expected versus actual values, observed differences, closure verification
   and the verdict. No next write runs automatically. **5 Full evidence / report**
   shows actual masked request/response content, timestamps, errors and history.
6. **6 Add interpretation** appends an explanation without changing the original
   expectations/verdict. **7 Propose a revised workflow version** saves a lesson and
   optionally revises an action hypothesis in a new local definition. A future new
   run can select it; existing runs retain their original definition.

PROCESS is restricted to an In Review experiment and preserves payment information
as an invariant; it is not an approval API. Choose an expected workflow stage,
CLOSED, remaining In Review, or your own field checks. Paid-in-review records can
therefore be investigated without paying again.

PAY uses the conservative existing state checks. Enter date, reference, final amount
and currency, and classify the inputs as a Sandbox simulation or confirmed existing
payment. Expected results include PAID, CLOSED and supplied voucher fields. Date and
decimal comparisons tolerate date-Z and numeric representation differences.

PUT corrections require an explicit JSON/XML file and expected fields such as
invoice.number or lines.<line-id>.price. Expected values accept JSON or unquoted
text. PUT is not a merge-patch; lists can replace existing lists. Full body-schema
validation is not implemented. Corrections are restricted to In Review and must
preserve payment. Unexpected changes are recorded, not automatically undone.

## Source of truth

```text
workflow-tests/workflows/invoice-closure-v1.json  Tracked initial definition
output/workflow-tests/                          Private, ignored evidence
  workflows/<version>-<hash>.json               Proposed local revisions
  runs/<run-id>/
    manifest.json                              Frozen definition, config, commit, SDK
    events/000001.json ...                      Plans, confirmations, I/O, comparisons
    report.json / report.html                  Regenerated evidence views
```

Events have sequence numbers, Israel-time timestamps and linked hashes. Files are
flushed before replacement; the dispatch marker is saved durably before a write.
Manifest/events are authoritative. Reports can be regenerated. Hash checks detect
accidental edits/gaps, not malicious rewriting; this is not a backup service.
Do not edit/delete evidence. Preserve the private folder separately if it must
survive loss of this debug workspace. Do not commit raw evidence, correction
payloads or private local revisions. Promote only reviewed, sanitized findings.
Saving a lesson does not certify it or automatically update skills or Git.

## Recovery and limits

- Resume the SAME run after a timeout/crash and choose **4 Reconcile attempted step**.
  It uses GETs only, against the original expectations. It never replays the write.
- An unresolved attempt blocks further wizard writes for that invoice in the same
  evidence folder, including new runs. Successful read-back plus an explicit note
  and RESOLVE confirmation can lift a hold; original verdicts remain unchanged.
- An attempted step cannot run again. The same request against the same complete
  state is not dispatched twice in this store. Build another reviewed experiment
  only after interpreting the previous evidence.
- A process lock serializes cooperating wizard operations. It does not control the
  Alma UI, generic composer, older invoice desk, other tools/folders or machines.
  A race remains after the preflight reads.
- Inspection bounds are 10 pages of 100 lines and 20 linked PO lines. Incomplete
  inspection blocks writes. Reads do not automatically classify the electronic/
  physical-book population or certify every linked-order closure requirement.
- Verification defaults to three read rounds, two seconds apart, with a 30-second
  scheduling deadline checked before each request. A request in progress can extend
  beyond it, subject to the SDK's 15-second timeout. Unmet expectations are inconclusive;
  invariant violations are contradicted; captured HTTP/API rejection is request_failed.
  Matching state after an unknown request outcome is not certified request success.
- There is no automatic approval, ERP action, creation/deletion, rollback, retry or
  write chain. Paid-but-waiting, manual approval, historical ERP and unfamiliar
  states remain holds until a supported experiment is defined.

Validation: 107 offline tests passed, including 29 workflow tests. Actual help,
direct launch/cancel and app entry passed in the guest interpreter without API
calls. No Alma GET or write was issued while implementing the wizard. Actual
transitions remain operator-run Sandbox tests.
