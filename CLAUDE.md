# Alma Acquisitions Automation

Tools and workflows that automate Ex Libris Alma acquisitions: Rialto PDF-to-POL processing,
bulk invoice and ERP integration, and the invoice closer. Python 3.12, Poetry.

## Commands

```bash
poetry install
poetry run python scripts/smoke_project.py                                       # imports clean
poetry run pytest tests/
poetry run python -m workflows.rialto.pipeline --input-folder ./input            # dry run
poetry run python -m workflows.rialto.pipeline --input-folder ./input --live     # live Alma
poetry run python -m workflows.invoices.bulk_processor config/invoice_processor.json
```

The invoice closer: `scripts/close_invoices.py`, dry run by default (see `docs/INVOICE_CLOSER.md`).

## Rules for every change

- **Dry run by default.** Live Alma operations only with an explicit `--live`.
- **SANDBOX before PRODUCTION.** Validate live behaviour with `ALMA_SB_API_KEY`; use `ALMA_PROD_API_KEY` only for approved production runs.
- **Payments are irreversible.** Before creating or paying an invoice, check what already exists for that POL: a duplicate payment happened once (`docs/INCIDENT_REPORT_DUPLICATE_PAYMENT_POL5994.md`).
- **Tests never need live Alma.** New tests go in `tests/test_*.py` and must run locally and in CI without Alma access.
- **Never commit keys or real configs.** Only `config/*.example.json` is tracked; copy it to a non-example name for local runs.

## Layout

`workflows/rialto/` (PDF to POL), `workflows/invoices/` (bulk invoices, ERP), `invoice_closer/` +
`scripts/close_invoices.py`, `config/` (templates), `batch/` (Windows entry points), `docs/`, `tests/`.
`input/`, `output/`, `processed/`, `failed/`, `logs/` are runtime folders, not source.

Style: follow the existing code (4 spaces, type hints where useful, `snake_case`, docstrings on
scripts, descriptive logging). Commits: a short imperative subject; context in the body.

## Where to look

- Alma acquisitions API (POs, POLs, invoices, receiving, funds): load the `alma-acquisitions-specialist` skill
- Invoice closer: `docs/INVOICE_CLOSER.md`; Rialto: `docs/RIALTO_README.md`
- Developer guide: `docs/DEVELOPER_GUIDE.md`; open work: `docs/OPEN-TASKS.md`
- Bumping `almaapitk`: follow `docs/almaapitk-bump-protocol.md` (binding)
- Deployment and operations notes for the production host are kept in the owner's private documentation; the user-level instructions say where.
- `AGENTS.md` is the reviewer's brief (Codex reviews, report only)
