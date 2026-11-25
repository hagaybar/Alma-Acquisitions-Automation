# almaapitk bump protocol (binding)

Every change to this repo's `almaapitk` pin follows this document, step by step. It is binding:
a bump that skips a step is not done. `CLAUDE.md` points here.

**Why it exists.** This repo is a production consumer of `almaapitk`. It runs on masedet, and
`main` and `prod` auto-deploy on a schedule with no second checkpoint. A bad bump on a
scheduled repo can fail silently in production. A bump is therefore a small, audited change
made inside this repo, never a one-line pin edit pushed from somewhere else.

## Ground rules

- **One repo at a time, from this repo.** The bump is done by a session working in this repo,
  using this repo's tests. Never as part of a batch across consumer repos, and never driven
  from the AlmaAPITK repo. An AlmaAPITK release ends by opening this repo's bump issue.
- **Trigger:** the issue "Bump almaapitk to `<version>` (pin → validate → main → prod)" in this
  repo. Bump to the current release directly; skip intermediate versions.
- **Agents never merge to `prod` or push to it.** The owner merges the PR into `main` and
  promotes `main` → `prod`.
- **No production writes during validation.** Live checks against PRODUCTION are read-only.
  Anything that writes to Alma, sends email or uploads files runs only against the SANDBOX,
  with `ALMA_PROD_API_KEY` unset, or not at all.
- **No real identifiers** (user IDs, MMS IDs, report paths with names, emails) in commits, PRs,
  issues or the audit. Use placeholders.

## Steps

### 1. Branch

`git checkout main && git pull && git checkout -b chore/almaapitk-<version>`.

### 2. Audit first: `docs/almaapitk-<version>-audit.md`

Write it before changing the pin. Earlier audits in `docs/` are the model. Sections:

- **(a) Usage surface.** Every `almaapitk` import and call in this repo, with `file:line`:
  classes, methods and arguments, exceptions caught, environment variables relied on.
- **(b) Upstream changes** from the version in `poetry.lock` to `<version>`: the AlmaAPITK
  `CHANGELOG.md` sections in between, plus anything the bump issue calls out. When the
  CHANGELOG is unclear, diff the wheels (`pip download almaapitk==<v> --no-deps` for both,
  then `diff -ru`).
- **(c) Per-symbol classification** of the usage surface: unchanged / changed but compatible
  / breaking. Every breaking entry names its fix.
- **(d) Repo-specific risks** listed under "This repo" below.
- **(e) Verdict:** SAFE, SAFE WITH CHANGES (list them), or BLOCKED (stop and report upstream).

### 3. Pin and lock

- Set `almaapitk = ">=<version>"`, keeping the pin's style and its comment.
- Run `poetry update almaapitk`, never a bare `poetry lock` that refreshes everything. Then run
  `poetry check --lock` and confirm `poetry.lock` resolves `almaapitk <version>`.
- No other package may move. If one must, list it in the audit with the reason.
- In the TAU sandbox, prefix Poetry commands with `POETRY_VIRTUALENVS_IN_PROJECT=false`. A
  `.venv` in the folder belongs to the WSL host.

### 4. Code changes (only if the audit requires them)

Keep them minimal, and give each one a test that fails without it. Don't add unrelated work
to the bump branch.

### 5. L2: this repo's tests

Run the commands under "This repo". All green, with no new skips.

### 6. L3: live check

Run the commands under "This repo" and record what ran and the result in the audit. If a
required L3 step can't run where you are (for example missing config), the PR says so and the
owner runs it before merging.

### 7. Pull request into `main`

- Commit the audit, pin, lock and any code changes:
  `chore(deps): bump almaapitk to >=<version> (#<issue>)`.
- The PR body links the audit and gives the L2 result and the L3 result (or what is left for
  the owner). It says `Refs #<issue>`, not `Closes`.
- Tick the issue's boxes that are actually done.
- The owner merges.

### 8. DevSandbox (masedet)

After the next auto-deploy of `main`, run the repo's DevSandbox check on masedet (see "This
repo"). If L3 in step 6 already ran there, on the deployed `main`, it counts. Note the result in
the issue.

### 9. Prod

The owner merges `main` → `prod`; the next auto-deploy pulls the new version into Prod. After
the next Prod run, check its logs and output, then close the issue.

### Rollback

Pin `almaapitk==<previous>` on `prod`, run `poetry update almaapitk`, and push. The next
auto-deploy restores the previous version. Report the regression in AlmaAPITK with a failing
test (AlmaAPITK rule R10).

## This repo: Alma-Acquisitions-Automation

This repo **writes money**: it receives items, approves invoices and marks them paid. Payments
are irreversible, and a duplicate payment has happened once
(`docs/INCIDENT_REPORT_DUPLICATE_PAYMENT_POL5994.md`). Treat every bump as high-risk.

Earlier bumps followed the checklist in issue #11 (almaapitk upgrade, 0.4.5 → 0.7.0). This
document replaces that checklist for every future bump; #11 stays open only to finish the 0.7.0
rollout (DevSandbox, then `prod`). The pin style here is caret (`almaapitk = "^<version>"`):
keep it, as step 3 says, instead of switching to `>=`.

- **Usage surface:** `docs/almaapitk-0.7.0-audit.md` (a) is the latest full list. In short:
  - `workflows/rialto/workflow.py`, `workflows/rialto/pipeline.py`: `AlmaAPIClient(env)`,
    `Acquisitions` (`search_invoices`, `get_pol`, `get_invoice`, `get_invoice_lines`,
    `extract_items_from_pol_data`, `receive_and_keep_in_department`, `approve_invoice`,
    `mark_invoice_paid`), `BibliographicRecords`, `AlmaAPIError`.
  - `workflows/invoices/erp_integration.py`, `workflows/invoices/bulk_processor.py`:
    `get_pol`, `update_pol`, `create_invoice(dict)`, `create_invoice_line`, `approve_invoice`,
    `mark_invoice_paid`, `test_connection`; `AlmaAPIError` caught.
  - `invoice_closer/gateway.py`: the client's raw `.get` / `.post`, with a separate writer
    `AlmaAPIClient(env, max_retries=0, timeout=)`; reads `status_code` and `alma_code` from
    raised errors and catches `requests` timeouts and connection errors.
  - `tests/logging/`: `AlmaAPIClient`, `AlmaAPIError`, the `almapi.api_client` logger.

  Check it with
  `grep -rn "from almaapitk\|AlmaAPIError\|status_code\|alma_code\|max_retries" workflows invoice_closer scripts tests --include=*.py`
  (ignore `tests/integration/` and `tests/case_studies/`, which are hand-run scripts).
- **Repo-specific risks for (d):**
  - Anything that could pay or receive twice: automatic retries of POST, timeouts after Alma
    saved the write, and the invoice closer's writer (`max_retries=0`), which must stay
    single-shot.
  - `search_invoices` paging and `total_record_count`: the Rialto invoice lookup by POL
    reads the returned page (at most 100), never `total_record_count`, and picks which invoice
    to pay from it.
  - Error classification: which exception class, `status_code` and `alma_code` the invoice
    closer and the Rialto/ERP handlers see for 400/401/429/5xx and timeouts.
  - Invoice and invoice-line field names: this repo sends raw dicts, not the toolkit's builders.
  - Logging defaults and redaction (`tests/logging/test_no_credential_leak.py`).
- **L2:** `poetry run pytest -q` and `poetry run python scripts/smoke_project.py`. Neither needs
  Alma or keys. `pytest` deliberately skips `tests/integration/` and `tests/case_studies/`
  (they call Alma at import time, some pay invoices); never run those during a bump.
- **L3 (SANDBOX only, `ALMA_PROD_API_KEY` unset):**
  1. Invoice closer pre-analysis, read-only by design:
     `poetry run python scripts/analyze_set.py --env SANDBOX --file <sandbox export> --include-physical`.
  2. Invoice closer dry run on the same input (no `--live`, so no writes):
     `poetry run python scripts/close_invoices.py --env SANDBOX --file <sandbox export> --include-physical`.
     Both must give the same per-invoice decisions as on the previous version.
  3. Rialto dry run on one test PDF:
     `poetry run python -m workflows.rialto.pipeline --input-folder <folder with one test PDF> --environment SANDBOX`.
     Use `--input-folder`, not `--config`: a config with `"live": true` turns the run live
     without `--live`. A dry run moves the PDF to `processed`.
  4. Only when audit (b) touches POST, retries, timeouts or error mapping: one SANDBOX write
     through the invoice closer, on one sandbox invoice waiting for payment, with `--live`
     (the 0.7.0 audit is the worked example). Never `--live` or `--production-approved`
     against PRODUCTION during a bump.

  Not determined: whether a SANDBOX fixture exists for a full Rialto run with writes (receive
  and pay). The 0.7.0 bump found none; if there is still none, the PR says so.
- **DevSandbox check (masedet):** no scheduled task is known to run from the DevSandbox clone,
  so there is no clean cycle to wait for. Instead, in
  `D:\Scripts\DevSandbox\Alma-Acquisitions-Automation`:
  1. `git status --porcelain` prints nothing (an edited tracked file makes auto-deploy skip
     the clone); `git log -1 --oneline` shows the merged `main`;
     `poetry run python -c "import importlib.metadata as m; print(m.version('almaapitk'))"`
     prints the new version.
  2. `poetry run python scripts/smoke_project.py` passes.
  3. Copy `batch\close_invoices_before_2026-10-01.bat` to its git-ignored `.local.bat` and run
     the copy with `ENV=SANDBOX`, `MODE=ANALYZE`, then `MODE=DRY`. Never edit the tracked
     `.bat`. Don't use the `rialto_pipeline_*.bat` files for this check: they `cd` into the
     Prod clone.
- **Not determined:** which jobs, if any, run on a schedule from the Prod clone (the Rialto
  daemon `.bat` exists, but its Task Scheduler status is not recorded here), and whether
  masedet runs the bulk invoice processor (`docs/OPEN-TASKS.md`). The "Prod" step's log check
  covers whatever does run; if nothing runs, the owner names the first Prod run to check.
- **More:** `docs/INVOICE_CLOSER.md`, `docs/RIALTO_README.md`, `docs/DEVELOPER_GUIDE.md`.
