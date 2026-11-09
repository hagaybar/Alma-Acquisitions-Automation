# Maturity, coverage and continuing evaluation

**Status: initial draft with bounded reads and one operator-run Sandbox payment/closure case.** The skill has not
been established as a reliable full-domain specialist. Coverage below is separate
from script correctness, structural format validation and agent behavior evaluation.

## Coverage by domain

| Area | Current evidence | Remaining scope |
|---|---|---|
| Invoice/vendor/library reads | Bounded GETs with installed almaapitk 0.4.5, Python 3.12, 8 Nov 2026 | Other tenants/configurations/filters and complete populations |
| Invoice payment field | One detailed Sandbox invoice showed payment.payment_status; root field absent | Other response variants; mutation postconditions |
| Invoice-line/PO linkage | One invoice line had a plain-string PO reference; linked PO GET succeeded | Other line types, mixed invoices, multi-page/link edge cases |
| Physical-book example | One linked PO-line had BOOK/PRINTED_BOOK_OT | Classification coverage, receiving and closure transitions |
| Electronic-book workflows | One E_BOOK_OT invoice: reconciled processing progression and HTTP 200 PAY with GET CLOSED/PAID, 8 Nov 2026 | Other records, activation and paid-open continuation |
| Processing, approval, payment, ERP | One operator-run payment case; prior processing response unknown with later APPROVED/Waiting for Payment observed; no active ERP | Other transitions and institutional rules; ERP untested |
| Invoice creation, updating and duplicate workflows | Existing skill/toolkit/project references; no new live write validation | Relevant schema/payload combinations and state transitions |
| Vendors, funds, fiscal management, licenses, purchase requests | Dated official acquisition-contract catalog | Substantive workflow and live behavior coverage |
| Cross-vendor skill format | Shared standard SKILL.md structure validated | Actual discovery and end-to-end use in both installed clients |
| Agent usefulness | Four-task independent model scenario exercise met predefined criteria, 8 Nov 2026; see report below | Broader unseen tasks and actual vendor-client invocation |

The 59-operation/163-parameter catalog is complete relative to its dated projection,
not a claim that all operations, parameter combinations or actions were tested.

## Claim-level evidence

Use the owning project's versioned evidence ledger for exact claims and test results.
The current worked example is docs/ACQUISITIONS_API_EVIDENCE.md in the canonical
Acquisitions repository. Read the matching revision; that project-specific report
is not a required local path in every installation.

Use four verdicts: documented/untested, Sandbox-confirmed within tested scope,
contradicted, unresolved. Include official source/date, SDK/source revision, test
inputs described without private IDs, expected/actual results and remaining scope.
Keep source observations distinct from actual API observations.

## Re-evaluation during normal use

Check the relevant evidence, not every reference. Trigger a focused review when:
- a response or task contradicts the recorded claim;
- a new transition or important parameter combination has no adequate evidence;
- a relevant API, SDK or institutional configuration change affects the claim;
- the user explicitly asks for an accuracy or behavioral evaluation.

For deliberate reviews, the separate alma-api-knowledge-evaluator supplies the
cross-domain method. It can evaluate this specialist or another Alma domain skill;
its conclusions need supporting evidence too. Its presence is optional for ordinary
domain assistance. Never upgrade an untested statement simply because an evaluator
repeated it. Preserve earlier observations and explain superseding evidence.

## Initial behavioral exercise

An isolated independent Codex subagent used snapshots of the specialist/evaluator
to answer four realistic synthetic tasks without external actions. The reviewer
found the predefined criteria met for state distinctions, electronic/physical workflow
branching, Letters domain boundary and evaluation of an unsupported verification claim.
Inputs, reviewer rubric, responses, hashes and limitations are versioned in
hagaybar/agent-sandbox at docs/debug-sbx/skill-evaluations/2026-11-08/REVIEW.md.
This is limited model scenario evidence, not a full-domain or cross-vendor validation.

## Dated API reference validity

[validation-status.md](validation-status.md) separates the official snapshot check
date from each operation's actual last-tested timestamp. The current read run on
8 November 2026 at 09:46 Israel time passed six bounded GET assertions. Five belong
to the Acquisitions catalog and are marked sandbox_tested_partial; 54 remain
not_live_tested with null dates. The supporting Configuration libraries GET is
recorded in [validation-evidence.json](validation-evidence.json), not inserted into
the Acquisitions contract catalog. No write transition was tested.

The live report preserves operation templates, request parameter names, client
timestamps, SDK version, HTTP status, assertion outcomes and partial population
counts. Raw responses, headers, server request IDs/timestamps and durations were
not retained. HTTP-only, failed and untested results remain distinguishable.

See [scoped operator-run transition evidence](invoice-transition-evidence.json) for the payment case, unknown processing response and retained-alert/empty-workflow observations. No generic approval or closure guarantee is established.
