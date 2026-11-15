# Open tasks

Last updated: 2026-11-15

## PRs
- #17 (bump almaapitk 0.4.5 → 0.7.0) — run the full Rialto Sandbox L3 with writes, then review and merge
- #16 (housekeeping: document the invoice closer, drop empty `common/`) — review and merge
- #8 (draft: Acquisitions specialist + journaled Sandbox workflow wizard) — owner to decide: finish or close

## Work in progress
- `training/invoice-closing-review` branch (acquisitions history dashboard for invoice review) — pushed, no PR; decide: open a PR or drop

## Issues
- #14 (Rialto approve-before-pay branch never runs: impossible status check) — fix, no outside input needed
- #13 (Rialto uses POL `invoice_reference` as an Alma invoice ID) — fix, no outside input needed
- #12 (Rialto `_find_invoice_for_pol` filters on `invoice_status~`, which Alma ignores) — fix, no outside input needed
- #11 (almaapitk upgrade protocol: pin → validate → main → prod) — continues via PR #17; after merge, DevSandbox cycle on masedet, then owner merges to `prod`
- #10 (research: failure-mode audit of the run context) — not started

## Other
- Physical test, Sandbox set 43266192370004146: 5 invoices CLOSED/PAID, order lines still SENT — close them by receiving in the Alma UI (API receiving is deferred)
- alma skills receiving warning pushed to dotfiles — run `~/dotfiles/install-skills.sh` in WSL again (sandbox skills folder is read-only)
