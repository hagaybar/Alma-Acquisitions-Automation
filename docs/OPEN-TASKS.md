# Open tasks

Last updated: 2026-11-22

## PRs
- #21 (bulk invoice processor: read nested payment status, stops paying already-paid invoices again) — review and merge; check whether masedet runs the bulk processor

## Work in progress
- `training/invoice-closing-review` branch (acquisitions history dashboard for invoice review) — pushed, no PR; decide: open a PR or drop

## Issues
- #11 (almaapitk upgrade protocol) — 0.7.0 is on `main`; after one clean DevSandbox run on masedet, owner merges `main` → `prod`
- #10 (research: failure-mode audit of the run context) — not started

## Other
- Invoice closer production run (invoices before 2026-10-01, Analytics report input) — Stage 1 done (PR #26 merged 22 Nov; Sandbox live run of 5 verified). Next: masedet DevSandbox (.bat with INPUT_FILE: ANALYZE, DRY, LIVE LIMIT=5), then prod (window, reviewed dry run, `--production-approved`)
- Skills: physical-closure findings and large-sets lessons pushed to dotfiles — run `cd ~/dotfiles && git pull && ./install-skills.sh` in WSL
- AlmaAPITK#250 (logical PO_LINE set listed 5.3M members) — test other logical sets; guard in `get_set_members`
- Sandbox item AC1-800063808 (POL-6400) left in transit with an acquisitions work order after the receive test — user chose to leave it
