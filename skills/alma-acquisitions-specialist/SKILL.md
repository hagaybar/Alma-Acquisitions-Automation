---
name: alma-acquisitions-specialist
description: Investigate Alma acquisitions workflows and API contracts, reconcile existing toolkit knowledge with official documentation and Sandbox tests, and prepare invoice, PO-line, receiving and ERP pilots.
---

# Alma Acquisitions Specialist

Use existing project knowledge and AlmaAPITK before designing a new workflow.
This skill supplies domain reasoning, not permission to change financial records.
It is shared by Codex and Claude Code; use the tools available in the current client.

## Establish the evidence

Read the owning repository's instructions and relevant existing workflow first.
Inspect local and remote branches/worktrees before assuming the default branch
contains earlier work. Preserve uncommitted data and earlier experiments.

For each material API claim record:
- the exact claim and its scope: field path, request parameter, action, transition,
  search filter, error diagnosis or configuration-dependent effect;
- official endpoint/schema source and retrieval date;
- installed AlmaAPITK version and implementation actually used;
- Sandbox test, expected result, actual result and verdict.

Use these verdicts: **documented, untested**; **Sandbox-confirmed within tested
scope**; **contradicted**; **unresolved**. Existing prose, a wrapper method name,
a mock passing or HTTP 200 alone does not establish a workflow fact. Do not promote
a documented contract to Sandbox-confirmed without a corresponding live test.

Treat official documentation as the contract reference. If actual Sandbox behavior
differs, preserve both sources and the smallest reproduction; do not silently
rewrite either into a universal rule. Revalidate vague or conflicting terms before
using them to select or mutate records. Read [evidence-and-workflows.md](references/evidence-and-workflows.md).

## Look up the contract precisely

Use [api-contracts.json](references/api-contracts.json) for the documented operation
and parameter inventory. It is a dated projection of the official Acquisitions
OpenAPI, **not a list of tested capabilities**. Query a specific contract with:

```bash
python scripts/describe_contract.py --method GET --path /almaws/v1/acq/invoices/
```

The catalog includes every documented operation and parameter from its snapshot,
body/response schema links and declared schema constraints. Explanatory prose,
conditional requirements and action semantics still require the linked official
endpoint page/schema. Do not infer unsupported actions from UI labels or old notes.
Check live official documentation before a previously unused mutation or relying
on a changed contract. Read [sources.md](references/sources.md) for provenance.

## Distinguish workflow state and actions

Record invoice base status, workflow status, approval status, nested payment status,
ERP/export state and linked PO-line status separately. `approve_invoice` is a toolkit
name for `op=process_invoice`; processing is not proof of final approval. `paid`
changes payment information and must not be treated as an innocuous generic close.
Validate the intended transition and prerequisites on a bounded Sandbox sample.
Read-back must prove the expected business postcondition, not merely method return.

Errors do not identify a unique cause without current state and request evidence.
Do not create a second invoice, force payment or replay a timed-out mutation as a
generic recovery. Read back first and preserve duplicate prevention. Do not bypass
an input guard; record the exact blocked scope for separate review.

## Discover populations before selecting a mutation sample

Resolve actual library/vendor codes from configuration and vendor reads. Treat
invoice ownership and PO-line ownership as different facts. Use only officially
supported search fields and separate filters; post-check returned records rather
than assuming a filter worked. Preserve raw API totals separately from returned
page counts and wrapper-produced counts. Page explicitly with a bound and report
when coverage is partial.

Classify electronic books and physical books through linked order/line metadata,
not a vendor or title substring. Mixed formats, unresolved/missing PO-lines and
ambiguous non-book/ongoing types go to review. Account for invoice-level side
effects: selecting one book line does not authorize paying a mixed invoice.
Use [candidate-sets.md](references/candidate-sets.md) for the current two-set pilot.

## Validate in Sandbox and preserve the result

Start with read-only probes. The bundled `scripts/probe_read_contracts.py` uses only
GET and explicit SANDBOX selection, finite timeouts and no retries. It reports
structural observations without keys, record IDs or raw bodies; it does not prove
write permissions or payment transitions. Run it with the project's Python/Poetry
environment and reviewed library/vendor codes. Never pass an API key as an argument.

Test writes only on an explicitly scoped, bounded Sandbox sample after discovery
and current-state review. A skill load is not new authorization. Preserve before/
after state locally, stop on unexpected results, and wait for the user's stated
review/librarian-feedback gate before widening the run. No production write is
authorized by this skill or by a successful Sandbox test.

Keep private manifests/reports ignored; commit code, synthetic regression fixtures,
redacted findings and the claim ledger in the owning repository. Push meaningful
changes to a review branch and open the appropriate PR. Keep toolkit fixes in
AlmaAPITK and consumer-specific fixes in the consumer project. Record actual tested
versions; do not upgrade dependencies to resolve a documentation disagreement.
