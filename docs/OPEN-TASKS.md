# Open tasks

Last updated: 2026-11-15

## PRs
- #22 (closer docs: unreceived print items do not block pay-only closure, Sandbox evidence) — review and merge
- #17 (bump almaapitk 0.4.5 → 0.7.0) — run the full Rialto Sandbox L3 with writes, then review and merge
- #16 (housekeeping: document the invoice closer, drop empty `common/`) — review and merge
- #21 (bulk invoice processor: read nested payment status, stops paying already-paid invoices again) — review and merge; check whether masedet runs the bulk processor

## Work in progress
- `training/invoice-closing-review` branch (acquisitions history dashboard for invoice review) — pushed, no PR; decide: open a PR or drop

## Issues
- #14 (Rialto approve-before-pay branch never runs: impossible status check) — fix, no outside input needed
- #13 (Rialto uses POL `invoice_reference` as an Alma invoice ID) — fix, no outside input needed
- #12 (Rialto `_find_invoice_for_pol` filters on `invoice_status~`, which Alma ignores) — fix, no outside input needed
- #11 (almaapitk upgrade protocol: pin → validate → main → prod) — continues via PR #17; after merge, DevSandbox cycle on masedet, then owner merges to `prod`
- #10 (research: failure-mode audit of the run context) — not started

## Other
- Skill: physical-closure findings (pay-only, PUT-close ignored, API receive) pushed to dotfiles — run `cd ~/dotfiles && git pull && ./install-skills.sh` in WSL
- Sandbox item AC1-800063808 (POL-6400) left in transit with an acquisitions work order after the receive test — user chose to leave it
