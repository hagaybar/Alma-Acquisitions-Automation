# Open tasks

Last updated: 2026-11-18

## PRs
- #21 (bulk invoice processor: read nested payment status, stops paying already-paid invoices again) — review and merge; check whether masedet runs the bulk processor

## Work in progress
- `training/invoice-closing-review` branch (acquisitions history dashboard for invoice review) — pushed, no PR; decide: open a PR or drop

## Issues
- #11 (almaapitk upgrade protocol) — 0.7.0 is on `main`; after one clean DevSandbox run on masedet, owner merges `main` → `prod`
- #10 (research: failure-mode audit of the run context) — not started

## Other
- Production run of the invoice closer — input format and voucher values to settle
- Skill: physical-closure findings (pay-only, PUT-close ignored, API receive) pushed to dotfiles — run `cd ~/dotfiles && git pull && ./install-skills.sh` in WSL
- Sandbox item AC1-800063808 (POL-6400) left in transit with an acquisitions work order after the receive test — user chose to leave it
