# Open tasks

Last updated: 2026-11-22

## PRs
- #21 (bulk invoice processor: read nested payment status, stops paying already-paid invoices again) — review and merge; check whether the production workstation runs the bulk processor

## Work in progress
- `training/invoice-closing-review` branch (acquisitions history dashboard for invoice review) — pushed, no PR; decide: open a PR or drop

## Issues
- #11 (almaapitk upgrade protocol) — 0.7.0 is on `main`; after one clean DevSandbox run, owner merges `main` → `prod`
- #10 (research: failure-mode audit of the run context) — not started

## Other
- Invoice closer production run (22 Nov, done): 1,259 of 1,271 invoices paid/closed. Follow-ups: 12 invoices held because a line's fund share is not 100% — staff fix in Alma, then rerun the same command; 6 e-book order lines still SENT after payment (likely not activated) — check in Alma; add a pre-analysis check for fund share ≠ 100%; fix the plan's step 5 (`FIRST` does not skip rows)
- #29 (production workstation: poetry cache permission error) — investigate
- DevSandbox clone has the tracked `.bat` edited — user runs `git checkout -- batch\close_invoices_before_2026-10-01.bat` so auto-deploy resumes
- Skills: physical-closure findings and large-sets lessons pushed to dotfiles — run `cd ~/dotfiles && git pull && ./install-skills.sh` in WSL
- AlmaAPITK#250 (logical PO_LINE set listed 5.3M members) — test other logical sets; guard in `get_set_members`
- Sandbox item AC1-800063808 (POL-6400) left in transit with an acquisitions work order after the receive test — user chose to leave it
