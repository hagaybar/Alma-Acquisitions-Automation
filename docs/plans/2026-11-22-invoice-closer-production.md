# Invoice closer: production plan

Job: process and pay the Rialto / AC1 (Sourasky Central Library) invoices dated before
1 Oct 2026, listed by an Alma Analytics report. E-book order lines close with their invoice.
Print order lines stay open: this job never receives items. Payments are status changes only
(voucher `AUTO-PAY-<invoice number>`, dated the run day); no money moves.

**A payment cannot be undone through the API.** Every step below that writes needs the owner's
explicit OK after reviewing the step before it.

## Where we are (22 Nov 2026)

- Code: PR #26 merged to `main` (`2603a99`). almaapitk 0.7.0.
- Tested in the Alma Sandbox with the production report (1,513 invoice lines, 1,271 invoices):
  - pre-analysis and dry run agree, both from the sandbox (Linux) and from masedet DevSandbox
    (Windows `.bat`);
  - two live runs of 5 invoices each (one per host): 10 print invoices processed and paid. Alma
    read back CLOSED / APPROVED / PAID, voucher `AUTO-PAY-<number>`, AAC_FUND on every line, and
    print order lines still SENT, as designed.
  - earlier single tests: e-book invoices close their order lines (2 of 2).
- Not tested in production at all. Production differs from the Sandbox in data (3½ months newer)
  and possibly in configuration.

## Production facts checked (read-only, 22 Nov 2026)

- AC1's paid RIALTO invoices carry a manual voucher (e.g. `1`), not an ERP voucher. Another
  library (AS1) does use ERP vouchers, so ERP export exists in this institution. The closer
  holds an invoice that goes to the ERP stage instead of paying it; the first live run of 5
  will show which way AC1 goes.
- AAC_FUND: one fund per fiscal period, each with an allocation of 10⁹ or more and overexpenditure
  not in question. Paying about 80,000 USD will not hit a fund limit.
- **Open, for the acquisitions team:** the invoices date from 2023 to 2026. Alma charges each
  payment to the fund on the invoice line. Which fiscal period's AAC_FUND it lands in has not been
  checked. Confirm this is acceptable for reporting before the full run (step 6), or check it on
  the first 5 (step 5).

## Where to run it

On masedet, from the **Prod** clone `D:\Scripts\Prod\Alma-Acquisitions-Automation`, which tracks
`prod` and holds the production API key. (The sandbox here would need a production window and
is meant for development; it is used below only for read-only checks.)

**Never edit the tracked `.bat` in a clone.** An edited tracked file leaves the clone dirty and
the scheduled auto-deploy then skips it. Copy it to
`batch\close_invoices_before_2026-10-01.local.bat` (git-ignored) and edit and run the copy.

## Steps

### 0. Fix the DevSandbox clone (now)

The `.bat` was edited in place in `D:\Scripts\DevSandbox\Alma-Acquisitions-Automation` on 22 Nov,
so auto-deploy now skips that clone. Keep your settings, then restore the file:

1. `copy batch\close_invoices_before_2026-10-01.bat %TEMP%\closer_settings.bat` (your settings);
2. `git checkout -- batch\close_invoices_before_2026-10-01.bat`;
3. `git status --porcelain` prints nothing.

After the next pull brings the `.gitignore` change (this plan's PR), make the `.local.bat` copy.

### 1. Bring the code to Prod (owner)

1. Merge this plan's PR to `main`, then `main` into `prod` (owner only; agents never touch `prod`).
2. On masedet, after the scheduled pull, in the Prod clone:
   - `git log -1 --oneline` shows the merge;
   - `poetry run python -c "import importlib.metadata as m; print(m.version('almaapitk'))"`
     prints `0.7.0`;
   - `git status --porcelain` prints nothing.

### 2. Fresh export (owner, on the run day)

Run the same Analytics report on the day of the production run (Funds Expenditure; filter
Fund Type = Allocated fund; one row per invoice line). Copy it to the Prod clone's
`tests\invoice_closer\input\`. Note the row count and the number of distinct invoices.

Invoices paid by staff between the export and the run are read fresh and reported as already
closed. Invoices that become eligible after the export are not in this run.

### 3. Pre-analysis in production (read-only)

`batch\close_invoices_before_2026-10-01.local.bat` with `ENV=PRODUCTION`, `MODE=ANALYZE`,
`INPUT_FILE=tests\invoice_closer\input\<export>`, `FIRST` and `LIMIT` empty.

Expected, unlike the Sandbox: no "Invoice not found"; almost no "already closed". Any held
invoice is read together before going on. Share `summary_for_staff.txt` and `console.txt`.

### 4. Dry run in production (read-only); the owner's review

Same with `MODE=DRY`. Its `results.csv` is the dry run that the production rule asks for: every
invoice, its current state, and the planned calls:

- `POST /almaws/v1/acq/invoices/{id}?op=process_invoice` (body `{}`), only if In Review;
- `POST /almaws/v1/acq/invoices/{id}?op=paid` with voucher number `AUTO-PAY-<number>`, voucher
  date = run day, amount = invoice total, currency = invoice currency.

Expected after: invoice CLOSED / PAID; e-book order lines CLOSED; print order lines unchanged.

The numbers must match step 3. **The owner reviews and gives an explicit OK for step 5.**

### 5. Live, 5 invoices

Same with `MODE=LIVE`, `LIMIT=5`. The batch file adds `--production-approved` and asks for YES.

Then, read-only from the sandbox, Claude checks each of the 5 in production Alma against the log:
state, voucher, fund on each line, order line status, and which fiscal period the expenditure
went to. If any invoice ended at the ERP stage or held, stop and decide before step 6.

If the 5 include no e-book invoice, run `LIMIT=5` again with `FIRST` set past the first e-book row
so that at least one e-book closes in production before the full run.

**The owner gives an explicit OK for step 6.**

### 6. Live, all

Same with `LIMIT` empty. About 1,260 invoices at about 1–4 seconds each: plan for 1–1½ hours.
Leave the window open; the screen shows each invoice as it goes.

If it stops (network, Ctrl+C, a crash): read the end of `console.txt`. An invoice marked
"no answer from Alma" must be checked in Alma before anything else. Then run the same command
again: closed invoices are skipped, and the rest continue.

### 7. After the run

- Share `summary_for_staff.txt` with the acquisitions team (plain language).
- Claude reads the production results back from Alma (read-only bulk download) and lists any
  difference between `results.csv` and Alma.
- Print order lines stay open by design; receiving them is a separate, manual decision.
- Archive the run folder outside the clone if it must be kept (the clone's output folder is not
  backed up by git).

## Stop conditions

Stop and decide with the owner if any of these appear:

- a pre-analysis or dry-run number that differs from the report beyond a few invoices;
- any `WRITE_REJECTED`, `WRITE_OUTCOME_UNKNOWN` or `ERROR`;
- an invoice going to the ERP stage, or held after processing;
- an e-book order line that stays open after payment.
