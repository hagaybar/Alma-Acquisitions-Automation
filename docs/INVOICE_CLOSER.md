# Invoice closer

`scripts/close_invoices.py` closes Alma invoices and their order lines by following the
flow validated in Alma Sandbox in November 2026. It is a dry run unless you pass `--live`.

## The flow it applies

| Invoice state now | What it does | What it expects next |
|---|---|---|
| Closed | Nothing. Reports `ALREADY_CLOSED` and any order line still open | — |
| In Review, not paid | `POST /acq/invoices/{id}?op=process_invoice` with body `{}` | Waiting for Payment (API code `Ready to be Paid`), approved. Electronic order lines with an active title close here |
| Waiting for Payment, approved, not paid | `POST ...?op=paid` with the four voucher fields | Invoice `CLOSED` / `PAID` |

Anything else is **held** with a reason, never forced:

- invoice already marked paid but still open (continuing it is not validated; it is never paid twice)
- waiting for manual approval, or at the ERP stage (`Waiting to be Sent`)
- processing left it In Review (Alma's review rules flagged something; the alerts are reported)
- any line that is not an electronic order (`E_…` type), a charge line with no order line,
  a cancelled order line, or a title with no available portfolio
- invoice outside `--vendor` / `--owner`
- no voucher number available (nothing is written for that invoice)

## Safety rules built in

- **Dry run by default.** `--live` sends writes. Production also needs `--production-approved`,
  given only after a reviewed dry run.
- **One attempt per write.** Writes are sent with automatic retries switched off. If Alma does not
  answer, the program reads the invoice back and reports `WRITE_OUTCOME_UNKNOWN` if it did not
  change. It never resends.
- **Double-payment guard.** The invoice is read again right before paying; it is paid only if it is
  still open and `NOT_PAID`.
- **Re-runnable.** Closed invoices are skipped; an invoice left at Waiting for Payment is paid on the
  next run.
- **One invoice's failure never stops the batch.**

## Input

Exactly one of:

- `--set-id <id>`: an Alma set of titles (`BIB_MMS`).
- `--file <path>`: `.xlsx` (first sheet), `.csv` or `.tsv`.

A file may have a header row. The first recognised identifier column is used:
`mms_id`, `pol` / `po_line`, `invoice_number`, `invoice_id` (case and spacing ignored).
Without a recognised header, the first column is read and each value's kind is detected from
its shape (`POL-…` order line, `99…` MMS ID, 15+ digits invoice ID, anything else invoice number).

Optional columns per row override the payment values for that invoice:
`voucher_number`, `voucher_amount`, `voucher_currency`, `voucher_date`.

Payment defaults: amount = invoice total, currency = invoice currency, date = today
(`--payment-date`), number from `--voucher-number "PAY-{invoice_number}"`. Check these against
the real payment before a production run: `op=paid` records a payment in Alma; it does not send money.

## Output

Each run writes a folder under `output/invoice_closer/<time>_<env>_<live|dry>/` (gitignored):

- `report.txt`: the short report (also printed).
- `results.csv`: one row per invoice: outcome, reason, before/after states, order lines.
- `log.jsonl`: every read decision, request and reply. Credentials, e-mail addresses and free-text
  notes are redacted; record IDs and states are kept.

Exit code: 0 when every invoice ended cleanly (closed, already closed, held or dry run), 1 when any
write was refused or its outcome is unknown, or an error occurred; 2 when the run could not start.

## Examples

```bash
# Dry run on a set
poetry run python scripts/close_invoices.py --set-id 43266180120004146 --vendor RIALTO --owner AC1 \
    --voucher-number "SBX-TEST-{invoice_number}"

# Live, from a spreadsheet
poetry run python scripts/close_invoices.py --file input/to_close.xlsx --vendor RIALTO --owner AC1 \
    --voucher-number "PAY-{invoice_number}" --live
```

## Evidence

- 8 Nov 2026: one e-book invoice processed and paid by hand (`docs/INVOICE_CLOSURE_RESULTS.md` on the
  `training/acquisitions-api-expert` branch).
- 12 Nov 2026: invoice 2410609 (e-book): `process_invoice` returned HTTP 200 in 21 s with the new
  state; the order line was already CLOSED on the first read; `paid` closed the invoice.
- 12 Nov 2026: invoice 2409757 (print, item not received, invoice price 35.29 vs order 39.95):
  `process_invoice` returned HTTP 200 in 0.9 s and the invoice stayed In Review. No error is returned
  in that case, which is why the program reads back and holds.
- 13 Nov 2026: live run on set 43266180120004146 (10 Rialto e-book titles, one-line invoices):
  10 of 10 closed. `process_invoice` answered in 2.3–3.4 s (one took 39.7 s), each reply already
  showing Waiting for Payment; every order line was CLOSED on the read right after processing;
  `paid` answered in under 1 s and closed each invoice. One of the ten carried the
  `DIFF_PRICE_THAN_POLINE` alert and still advanced, so a price difference alone does not stop
  processing. A second run reported all ten as already closed. CSV, TSV and Excel inputs were
  checked in dry runs.

Not validated: print orders, charge lines, multi-currency payments, invoices already paid but open,
manual approval, ERP-stage invoices, and whether the order (PO) itself closes (the API cannot read it).
