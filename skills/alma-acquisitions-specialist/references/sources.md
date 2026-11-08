# Sources and portability

## Existing knowledge reviewed

- General alma-api-expert skill: SKILL.md and references/acquisitions_api.md in
  the operator's existing skill library. Its claims are inputs to reconciliation,
  not automatically validated facts; do not copy private sample assets.
- Alma-Acquisitions-Automation: docs/DEVELOPER_GUIDE.md,
  docs/rialto_project_flow_findings.md, docs/SANDBOX_TEST_PLAN.md,
  docs/ACQUISITIONS_DOMAIN_STATUS.md and workflows/invoices/bulk_processor.py.
  Project review baseline: 50de1a2; earlier dashboard branch: 91d5a1f.
- AlmaAPITK: docs/domains/acquisitions.md, docs/alma-swagger/acq.json,
  src/almaapitk/domains/acquisition.py at de2013db. The other original checkout
  is on a different revision; do not assume its source equals the installed SDK.
- Debug project installed SDK: almaapitk 0.4.5, Python 3.12. Treat source-main
  implementation observations and installed-SDK observations as separate evidence.

## Official reference, checked 8 November 2026

- [Acquisitions endpoint index](https://developers.exlibrisgroup.com/alma/apis/acq/)
- [Current official Acquisitions OpenAPI](https://developers.exlibrisgroup.com/wp-content/uploads/alma/openapi/acq.json)
- [Get invoices](https://developers.exlibrisgroup.com/alma/apis/docs/acq/R0VUIC9hbG1hd3MvdjEvYWNxL2ludm9pY2VzLw==)
- [Invoice service](https://developers.exlibrisgroup.com/alma/apis/docs/acq/UE9TVCAvYWxtYXdzL3YxL2FjcS9pbnZvaWNlcy97aW52b2ljZV9pZH0=)
- [Invoice schema](https://developers.exlibrisgroup.com/alma/apis/xsd/rest_invoice.xsd/)
- [Invoice payment schema](https://developers.exlibrisgroup.com/alma/apis/xsd/invoice_payment.xsd/)

The generated catalog records source date/hash and 59 operations with 163 parameter
declarations. It preserves machine-readable names/constraints and schema references,
not the entire human manual. Check official descriptions for conditional rules.
The general skill's examples include legacy search fields and broad workflow rules;
the official catalog and targeted Sandbox probes are needed to reconcile them.

## Shared skill format

Compatibility review: 8 November 2026, using the official
[Codex skill guide](https://learn.chatgpt.com/docs/build-skills) and
[Claude Code skill guide](https://code.claude.com/docs/en/skills).

The canonical directory has SKILL.md with only name/description YAML frontmatter,
relative Markdown references and ordinary Python scripts. It has no Claude-specific
argument substitution, dynamic command injection, hook, context/fork, tool grant,
model pin or mandatory Codex-only metadata. Neither vendor's permissions are changed.

Install the same directory bytes into one discovery location per vendor/scope:

| Client | Current documented project location | Current documented user location |
|---|---|---|
| Codex | .agents/skills/alma-acquisitions-specialist | ~/.agents/skills/alma-acquisitions-specialist |
| Claude Code | .claude/skills/alma-acquisitions-specialist | ~/.claude/skills/alma-acquisitions-specialist |

Codex desktop deployments may additionally supply CODEX_HOME/skills. Use that
environment's existing supported root when appropriate; do not assume the current
web documentation proves discovery behavior of a pinned older CLI. Keep one
canonical versioned source and check installed copies against it rather than
maintaining two independently edited skills. Avoid installing same-name duplicates
within one client's discovery scope.

The domain content uses no vendor-specific invocation syntax. The user can invoke
the installed skill through that client's own skill selector/command. Loading it
explicitly by file path is a fallback for a running session, not evidence of automatic
registration. Verify discovery and useful behavior separately for each installed
runtime. Claude live selection remains untested while the subscription is paused.
Format compatibility does not prove all optional host tools or live APIs are available.
