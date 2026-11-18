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
- an invoice line with no fund distribution (checked when selecting and again right before paying)
- a physical order line, unless `--include-physical` is given; even then only one-time orders
  (`…_OT`). Physical lines are paid, never received: receiving stays a person's job in Alma
- any other line that is not an electronic order (`E_…` type), a charge line with no order line,
  a cancelled order line, or a title with no available portfolio
- invoice outside `--vendor` / `--owner`
- with `--invoice-date-before YYYY-MM-DD`: an invoice whose invoice date is on or after the cutoff,
  or that has no invoice date. Enforced per invoice in code, whatever the set or file contains
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

## Operator instructions: preparing the selection

Build the selection (Alma set or Analytics report) with these filters, then run the
pre-analysis (`scripts/analyze_set.py`, or MODE=ANALYZE in the batch file) before any run:

1. **Every invoice line has a fund.** Exclude invoice lines with no fund distribution, for
   print and electronic alike. Without a fund Alma will not process the invoice, and an invoice
   paid without processing closes with **no fund expenditure** and can no longer be given a fund
   (Alma refuses: "Fund distribution can't be edited in an invoice line of a closed invoice").
   The closer also checks this itself and holds such invoices, but they should not be selected.
2. Vendor RIALTO, owner AC1 (Sourasky Central Library), one-time orders only.
3. Invoice date before the job's cutoff (this job: 2026-10-01). Also enforced in code.
4. Use an itemized set, or check that the set's member count matches (the closer refuses a
   mismatch; see AlmaAPITK#250).

Invoices held for "no fund" are listed in `summary_for_staff.txt`: add the fund in Alma and
they close on the next run.

## Input

Exactly one of:

- `--set-id <id>`: an Alma **Order lines** (`PO_LINE`) set. Members are POL numbers.
  Title (`BIB_MMS`) sets are refused: a title can have several order lines, each with its own
  invoice, so a title set reaches invoices nobody selected. Alma has no invoice set type.
- `--file <path>`: `.xlsx` (first sheet), `.csv` or `.tsv`.

**Selection rules.** Closing an invoice processes every line on it, so when the input names
order lines (a set, or `pol` / `mms_id` rows), an invoice that also covers an order line *not* in
the input is held. Naming the invoice itself (`invoice_number` / `invoice_id`) covers all its
lines. A title row (`mms_id`) is accepted only if the title has exactly one order line; otherwise
it is held and you name the order line.

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
# Dry run on an order-line set
poetry run python scripts/close_invoices.py --set-id <PO_LINE set id> --vendor RIALTO --owner AC1 \
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
- 13 Nov 2026: live run on title set 43266180120004146 (10 Rialto e-book titles, one order line
  and one-line invoice each; title sets have since been replaced by order-line sets):
  10 of 10 closed. `process_invoice` answered in 2.3–3.4 s (one took 39.7 s), each reply already
  showing Waiting for Payment; every order line was CLOSED on the read right after processing;
  `paid` answered in under 1 s and closed each invoice. One of the ten carried the
  `DIFF_PRICE_THAN_POLINE` alert and still advanced, so a price difference alone does not stop
  processing. A second run reported all ten as already closed. CSV, TSV and Excel inputs were
  checked in dry runs.

- 15 Nov 2026: live run with `--include-physical` on order-line set 43266192370004146 (5 Rialto
  PRINTED_BOOK_OT lines, one-line invoices, each with one item that has an arrival date, is in place
  and has no process type; order lines SENT). `process_invoice` answered in 0.7–5.6 s with Waiting
  for Payment / APPROVED; `paid` closed every invoice (CLOSED/PAID). **Every order line stayed SENT**
  after processing and after payment: an item's arrival date does not make the order line received,
  and paying does not close a physical order line. Outcome `CLOSED_ORDER_LINE_OPEN` for all five.
  Closing those lines needs receiving in Alma (by a person).

- 15 Nov 2026, **items not received**: live run with `--include-physical` on order-line set
  43266194870004146. It held 5 Rialto PRINTED_BOOK_OT lines with one-line invoices; invoice, order
  line, location and items were all AC1. No item had an arrival date and no copy had a receive date;
  3 items were in acquisition (ACQ), 2 were in place without receiving. `process_invoice` returned
  Waiting for Payment / APPROVED in 0.7–1.2 s, despite NOT_READY_LINES and the other three usual
  alerts. `paid` then closed every invoice (CLOSED/PAID). Order lines stayed SENT, and the items
  were unchanged (no arrival date, same process type). In Sandbox, unreceived items do not block
  processing or payment of a one-time print invoice.

Not validated: charge lines, multi-currency payments, invoices already paid but open,
manual approval, ERP-stage invoices, and whether the order (PO) itself closes (the API cannot read it).
