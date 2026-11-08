# Acquisition API evidence and invoice discovery — 8 November 2026

Purpose: refine existing knowledge rather than restart the investigation. The
canonical portable specialist skill is skills/alma-acquisitions-specialist. It
separates official contracts, source observations and actual Sandbox observations.
See its references/sources.md for exact source provenance and client compatibility.

## Live Sandbox evidence

All calls were GET-only, selected SANDBOX and ALMA_SB_API_KEY through the installed
SDK, used 15-second timeouts and disabled retries. No keys, record IDs, full invoice
objects or key-bearing URLs are committed here. Counts are observations at retrieval
time; no claim is made that they remain current.

| ID | Claim / test | Observation and scope |
|---|---|---|
| SB-01 | Bounded invoice list connection | GET invoices with limit=1 returned HTTP 200 |
| SB-02 | Central Library code lookup | GET libraries resolved the requested Central Library label; actual code remains operator configuration |
| SB-03 | Vendor identity | Vendor-name search for the platform label returned no results; documented exact vendor-code GET resolved the expected ProQuest vendor. An empty name search does not prove absence |
| SB-04 | Initial library/vendor population | Vendor-code search plus invoice-owner filter reported 3,215 invoices; only first 10 read, all CLOSED/PAID. No electronic/physical classification of the full population |
| SB-05 | Active population and distinct states | Adding base_status=ACTIVE reported 1,341 invoices; first 3 read: one APPROVED, two PENDING; all NOT_PAID. These are not equally ready for a payment operation |
| SB-06 | Payment field path | One active invoice detail has payment.payment_status and no root payment_status. This corroborates the general skill/toolkit and contradicts the bulk processor's root-level lookup for this response |
| SB-07 | Invoice-line/POL linkage | First inspected active invoice had one REGULAR line; po_line was a plain string, not a value wrapper. Linked POL retrieval succeeded |
| SB-08 | Physical-book classification example | That linked POL had material_type=BOOK and type=PRINTED_BOOK_OT, with the expected library owner. This validates one example, not the entire physical population or any electronic-book type |

No invoice was created, processed, paid, rejected, updated or closed. No receiving,
activation, ERP mutation or production API operation was performed.

## Contradictions and open claims

- Baseline bulk code reads payment_status from the root, unlike observed response
  and existing skill/toolkit. Three synthetic regressions failed before correction;
  this branch now reads the nested field before/after processing. All 16 configured
  offline tests pass. Already-paid handling is preserved; no payment-readiness or
  final-success policy was broadened.
- The helper named approve_invoice sends process_invoice. It does not establish
  that the invoice will always become approved regardless of configured review rules.
- Toolkit can_pay accepts PENDING in its implementation. That does not prove API
  readiness or the librarian's business eligibility rule. No mutation tested this.
- Legacy query examples use invoice_status/vendor in q; the official invoice
  contract lists vendor_code and separate owner/base_status/workflow filters.
- Invoice workflow value and description can differ: one observed workflow value
  was Ready to be Paid while its description was Waiting for Payment. Preserve both
  and resolve semantics against official docs/current configuration, not synonyms.
- The historical domain-status report includes proposed payload wrappers and extra
  actions that conflict with other references. Treat it as historical hypotheses,
  not a current endpoint contract or an instruction to change payloads.

## Two candidate sets and next acceptance

Discover Central Library / Rialto electronic books and physical books separately.
The user has not asked for all active invoices to be paid. Verify book/format using
invoice lines and linked PO-lines; handle mixed/unresolved invoices separately.
Active is a discovery filter, not sufficient eligibility. Electronic activation,
physical receiving, workflow/approval and payment require separate state evidence.

The observed population counts above precede format classification. They must not
be presented as completed electronic/physical sets. The next stage is bounded
classification discovery and review of the intended transition, followed by a small
Sandbox sample. User review comes before librarian feedback and wider testing.

Keep record-level manifests and reports in ignored output paths. Preserve source,
synthetic tests and redacted claims in Git and pushed review branches. No production
acquisition write is authorized; no message to the librarian is authorized.

The portable read-probe script was run against the same reviewed Sandbox codes: library lookup, vendor lookup, filters on the three returned active invoices, nested payment shape and linked POL retrieval all passed. Coverage remained explicitly partial (3 of the reported 1,341 active invoices). The shared skill passed the skill-creator structural validator; the offline descriptor returned the official invoice-service parameters and four documented actions. These checks do not validate mutation transitions or automatic skill discovery in either client.

## Skill restructuring — 8 November 2026

The specialist is now organized around domain assistance rather than the current
pilot or an evaluation procedure. It remains an initial draft with partial Sandbox
read coverage. Workflow, invoice interpretation and coverage references separate
business knowledge from API contracts and historical evidence. Campaign-specific
selection/review rules moved to INVOICE_CLOSING_PILOT.md.

The shared evaluation method is canonical in hagaybar/agent-sandbox under
skills/alma-api-knowledge-evaluator. The specialist retains lightweight evidence
checks and focused re-evaluation triggers; it does not require that evaluator for
ordinary domain assistance. No new API call or mutation is part of this restructuring.

The revised specialist and separate evaluator passed structural checks and relative
link validation. An independent four-task read-only model scenario exercise met its
predefined reviewer criteria; its full evidence is in agent-sandbox at
docs/debug-sbx/skill-evaluations/2026-11-08/. This does not add live API validation,
automatic skill discovery evidence or actual Claude Code use. Both remain initial drafts.
