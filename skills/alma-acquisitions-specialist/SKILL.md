---
name: alma-acquisitions-specialist
description: Help Claude Code and Codex understand, implement, and troubleshoot Alma Acquisitions workflows and APIs using official documentation, AlmaAPITK, and project knowledge. Initial draft with partial Sandbox validation; consult coverage and evidence before relying on a workflow.
---

# Alma Acquisitions Specialist

Help the agent work with Alma's acquisitions domain: orders and PO-lines, vendors,
funding, physical receiving and electronic activation, invoices, approval, ERP/payment
integration, and closure. Connect the real institutional workflow to the relevant
API operations and existing implementation rather than treating endpoints in isolation.

**Maturity: initial domain draft, partially validated.** Read
[coverage and evidence](references/coverage-and-evidence.md) for the relevant area.
An official contract, a toolkit implementation and a Sandbox observation are different
kinds of evidence. Neither the domain catalog nor passing code tests establish that
this skill is a reliable expert across the whole domain.

## Find the relevant domain guidance

- For lifecycle, ownership, receiving/activation and cross-record effects, read
  [the workflow map](references/workflows.md).
- For invoice state, processing, approval, payment/ERP and closure, read
  [invoice workflows](references/invoice-workflows.md).
- For an exact method, path, parameter or schema, use
  [the documented API catalog](references/api-contracts.json). The offline helper
  `python scripts/describe_contract.py --method GET --path /almaws/v1/acq/invoices/`
  selects one contract with its validation status and last-tested date. The
  [validation overview](references/validation-status.md) lists every operation;
  [recorded evidence](references/validation-evidence.json) preserves the redacted live run.
  Documentation-check dates and actual Sandbox test dates are separate.
  Check the linked official documentation for conditional
  requirements and semantics omitted by this projection.
- For toolkit/project provenance and portable installation, read
  [sources](references/sources.md). Inspect the installed SDK version and actual
  method before assuming source-main or an older example describes runtime behavior.

## Apply the knowledge to the project

Read the owning project's instructions and existing workflow. Identify the business
goal and intended final state, then map the current state to the smallest relevant
read or action. Resolve library/vendor/type codes from configuration, not display-name
guesses. Separate record discovery, business eligibility and the selected action sample.

Use existing AlmaAPITK and project tools where they match the contract. Account for
missing parameters, wrapper-specific behavior and cross-record side effects. A method
named approve, close, verify or dry-run does not establish its actual HTTP effects.
Inspect those effects when they matter to the task. Explain unresolved institutional
rules rather than replacing them with a universal workflow.

Before a mutation, verify the current records, authorization and scope. Preserve
duplicate prevention, distinguish invoice payment from invoice/PO-line closure, and
read back the intended postcondition. A timeout or partial failure calls for state
reconciliation before replay. A successful Sandbox run does not authorize production.
Keep private data and secrets out of committed findings.

## Keep the specialist accurate

Consult the claim's evidence and tested scope during normal use. Re-evaluate when a
contradiction, unfamiliar transition/parameter combination, relevant API/SDK/configuration
change, or explicit review makes prior evidence insufficient. Do not rerun every probe
for every question or treat evidence age alone as proof of invalidity.

For a material claim, compare the official contract, implementation/version and a
bounded Sandbox test, then update its evidence record. Mark untested or conflicting
claims explicitly; do not infer validation from prose or HTTP 200 alone. The bundled
`scripts/probe_read_contracts.py` can inspect a small set of GET contracts using the
project's SDK environment; it does not test write transitions or classify a population.

For a deliberate accuracy or behavioral review, use `alma-api-knowledge-evaluator`
when available. If it is unavailable, these evidence rules still apply and uncertainty
must remain visible. Project-specific selection criteria and review gates belong in
the project, not in this reusable skill.

For a new reviewed read-probe report, `scripts/record_validation.py --report REPORT
--write` updates the dated references. It records only the tested assertion scope;
an HTTP response alone does not establish business semantics. Review the redacted
report before recording it. A last-tested date is an observation, not a guarantee
or automatic expiry rule.

## Hands on inspection

When the user wants to run tests hands on, present one named test, its exact inputs,
expected observations and stop point before execution. Show the actual prepared
request and returned response body when inspection is requested; metadata or a pass
assertion is not a substitute for input/output. Mask authentication, keep useful
record IDs in private local captures, and interpret each result before moving to
the next test. Keep read tests distinct from processing/payment/receiving mutations.
The Acquisitions project supplies scripts/sandbox_get_review.py for one GET per
command; it is a project helper, not a mandatory dependency of this generic skill.
