# Invoice closer: plan for Sunday 22 Nov 2026

Goal of the day: drive the closer from an **Alma Analytics report**, test it in the Alma
Sandbox, then run it on masedet DevSandbox. Production comes after, in a separate session.

## Where we are (end of 18 Nov)

- The closer is in draft PR #26 (`feature/closer-batch-script`). It pays invoices and closes what
  Alma lets close: e-book order lines close with their invoice; print order lines stay open
  (no receiving, by design).
- Proven in the Sandbox, one invoice at a time, with full logs:
  - e-book with a fund: processed, paid, invoice and order line closed (2 cases);
  - print with a fund: processed, paid, invoice closed, order line stays open (1 case).
- **The rule that matters most: every invoice line must have a fund.**
  - Without one, Alma will not process the invoice (6 of 6 cases).
  - An invoice paid without processing closes with no expense on any fund, and Alma then refuses
    to add the fund ("can't be edited in an invoice line of a closed invoice").
  - The closer holds such invoices and never pays them. The report must leave them out as well.
- Alerts (price difference, vendor account, etc.) do not block and are ignored for now.
- The e-book portfolio check is off (decided 18 Nov): no per-title calls. Use `--check-portfolios` to turn it on.

## Step 1: build the Analytics report (you)

Subject area: **Funds Expenditure** (the only Analytics subject area with invoices). One row
per invoice line.

**Where the fields are (checked 19 Nov against the Ex Libris page "Funds Expenditure" and our
Analytics):** there is **no separate Invoice folder**. The invoice-level fields sit inside the
**Invoice Line** folder, below a dashed separator line, after all the "Invoice Line-…" fields
(UI spelling `Invoice-…`, documentation spelling `Invoice - …`). Don't confuse
`Invoice Line-Number` (the line's position: 1, 2, 3…) with `Invoice-Number`.

**Columns (in this order is easiest):**

1. `Invoice Line > Invoice-Number`. **Required:** the closer works by invoice.
2. `PO Line > PO Line Reference` (e.g. `POL-4875`).
3. `Invoice Line > Invoice-Date` (the date on the invoice, not `Invoice-Creation Date`).
4. `PO Line > Vendor Code`.
5. `Invoice Line > Invoice-Owner Code` (expect `AC1`); `PO Line > PO Line Owner Library Code`
   is the order line's owner.
6. `PO Line > Order Line Type`.
7. `Funds > Fund Code`.
8. `Invoice Line > Invoice-Status`, `Invoice-Payment Status` (NOT_PAID / PAID),
   `Invoice-Approval Status`.

**Filters:**

- Vendor Code = RIALTO
- Invoice-Owner Code = AC1
- Invoice-Date before 01/10/2026
- Invoice-Status is not Closed; Invoice-Payment Status = NOT_PAID
- Order Line Type is a one-time order (print or electronic)
- **Fund Code is not empty** (invoice line has a fund)

Field names checked from the documentation; not yet confirmed that a Funds Expenditure row
exists for an invoice line with no fund (it is built on fund transactions). If it doesn't, the
no-fund lines drop out of the report on their own; the closer still checks funds before paying.

**Export:** Excel (.xlsx) or tab-delimited. Both are read, including Analytics' UTF-16
tab-delimited files. The closer recognises the headers `Invoice-Number` and `PO Line Reference`
(`Invoice Line-Number` is ignored). When both are present it uses the invoice number.

### Important: the report comes from production, the test runs in the Sandbox

Analytics reports production data. The Sandbox is a copy of production taken at its last
refresh, plus everything we changed in tests. So in the Sandbox run expect:

- invoices missing from the Sandbox (created after the refresh): reported as not found;
- invoices already closed in the Sandbox (by our tests, or by the copy date): already closed;
- states and funds that differ from what the report shows.

None of this is an error in the closer. The Sandbox run tests the mechanics: reading the file,
checks, writes, logs, summaries. In production the report and Alma match, which is where this
design fits.

## Step 2: test here, in the Alma Sandbox (with Claude)

Put the export where Claude can read it, or send it in the chat. Then:

1. **Pre-analysis** (read-only):
   `poetry run python scripts/analyze_set.py --file <export> --vendor RIALTO --owner AC1 --include-physical --invoice-date-before 2026-10-01`
   Read `summary_for_staff.txt` together: how many found, already closed, held, and why.
2. **Dry run:** the same filters with `scripts/close_invoices.py --voucher-number "AUTO-PAY-{invoice_number}"`.
3. **Live, 5 invoices:** add `--limit 5 --live`. Check `log.jsonl`, `results.csv` and
   `summary_for_staff.txt` together. Expect `fund_check` before every `paid`.
4. Fix whatever the first three steps show. Then mark PR #26 ready; you review and merge it to
   `main`. The next scheduled pull brings it to masedet DevSandbox.

## Step 3: masedet DevSandbox (you, Claude guides)

1. In `D:\Scripts\DevSandbox\Alma-Acquisitions-Automation`:
   - `git log -1 --oneline` shows the merge commit;
   - `poetry run python -c "import importlib.metadata as m; print(m.version('almaapitk'))"` prints 0.7.0.
2. Copy the export to `tests\invoice_closer\input\`.
3. Edit the SETTINGS block of `batch\close_invoices_before_2026-10-01.bat`: set `INPUT_FILE`.
4. Run it three times:
   - `MODE=ANALYZE`;
   - then `MODE=DRY`;
   - then `MODE=LIVE` with `LIMIT=5` (you type YES).
5. Each run makes a folder in `tests\invoice_closer\output\`. Share `summary_for_staff.txt`,
   the console copy and, if needed, `log.jsonl`. We read them together.

## Afterwards: production (separate session)

Production needs:

- the production window (`tau-window`, opened by you);
- a production pre-analysis and dry run that you review;
- your explicit OK;
- the `--production-approved` flag;
- a merge of `main` into `prod`, done by you only.

First live run limited (e.g. 5), then the rest.

## Open questions to settle on Sunday

- Sandbox invoice 2412944 (paid without a fund in a test): left as is, decided 18 Nov; the February
  Sandbox refresh replaces it.
- The Analytics report's exact column names (Claude adjusts the reader if needed).

## Before Sunday (you, in WSL)

- `cd ~/dotfiles && git pull && ./install-skills.sh` (skill updates from 18 Nov).
