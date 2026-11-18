#!/usr/bin/env python
"""Close Alma invoices (process, then pay) and their order lines.

Dry run by default: reads everything and reports what it would do.

Examples:
  poetry run python scripts/close_invoices.py --set-id <PO_LINE set id> --vendor RIALTO
  poetry run python scripts/close_invoices.py --file input/to_close.xlsx --vendor RIALTO \
      --voucher-number "PAY-{invoice_number}" --live

Input: exactly one of --set-id (Order lines / PO_LINE set) or --file (.xlsx, .csv, .tsv). See
docs/INVOICE_CLOSER.md for file columns. Production requires --production-approved,
given only after a reviewed dry run.
"""
import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from invoice_closer.engine import WOULD_PAY, WOULD_PROCESS, Closer, Config, _v  # noqa: E402
from invoice_closer.bulk import BulkGateway  # noqa: E402
from invoice_closer.gateway import Gateway  # noqa: E402
from invoice_closer.inputs import load_targets  # noqa: E402
from invoice_closer.reporting import RunLog, run_context, short_report, staff_summary, write_results_csv  # noqa: E402


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--set-id", help="Alma Order lines (PO_LINE) set; title sets are refused")
    src.add_argument("--file", type=Path, help=".xlsx, .csv or .tsv file")
    p.add_argument("--env", choices=["SANDBOX", "PRODUCTION"], default="SANDBOX")
    p.add_argument("--live", action="store_true", help="send the writes (default: dry run)")
    p.add_argument("--production-approved", action="store_true",
                   help="required with --env PRODUCTION --live, after a reviewed dry run")
    p.add_argument("--vendor", help="only touch invoices of this vendor code, e.g. RIALTO")
    p.add_argument("--owner", help="only touch invoices of this owner code, e.g. AC1")
    p.add_argument("--invoice-date-before", metavar="YYYY-MM-DD",
                   help="only touch invoices whose invoice date is before this date; "
                        "later or undated invoices are held")
    p.add_argument("--voucher-number", dest="voucher_template",
                   help='voucher number template, e.g. "PAY-{invoice_number}"')
    p.add_argument("--include-physical", action="store_true",
                   help="also close one-time physical orders (pays only; never receives items). "
                        "Not yet validated: Sandbox only until reviewed")
    p.add_argument("--payment-date", help="YYYY-MM-DD (default: today)")
    p.add_argument("--settle-seconds", type=int, default=30,
                   help="how long to watch for a delayed state change after a write")
    p.add_argument("--limit", type=int, metavar="N",
                   help="handle only the first N invoices (e.g. a small first live run); "
                        "the rest are listed as not attempted")
    p.add_argument("--out", type=Path, default=ROOT / "output" / "invoice_closer")
    p.add_argument("--cache-minutes", type=float, default=60,
                   help="reuse the vendor download saved under OUT/cache if younger than this "
                        "(0 = always download)")
    return p.parse_args(argv)


def main(argv=None) -> int:
    a = parse_args(argv)
    # AlmaAPITK logs full record bodies at DEBUG/INFO to the console and logs/.
    # This program keeps its own redacted log, so silence those levels.
    logging.disable(logging.INFO)
    if a.env == "PRODUCTION" and a.live and not a.production_approved:
        print("Refusing: production writes need --production-approved after a reviewed dry run.")
        return 2
    if a.invoice_date_before:
        try:
            # Normalise (e.g. 2026-1-1 -> 2026-01-01): the cutoff is compared as text.
            a.invoice_date_before = datetime.strptime(a.invoice_date_before, "%Y-%m-%d").date().isoformat()
        except ValueError:
            print("Refusing: --invoice-date-before must be YYYY-MM-DD.")
            return 2
    run_dir = a.out / f"{datetime.now():%Y%m%d_%H%M%S}_{a.env.lower()}_{'live' if a.live else 'dry'}"
    log = RunLog(run_dir)
    log("run_context", **run_context(sys.argv if argv is None else argv))
    cfg = Config(live=a.live, vendor=a.vendor, owner=a.owner,
                 invoice_date_before=a.invoice_date_before, voucher_number_template=a.voucher_template,
                 settle_seconds=a.settle_seconds, include_physical=a.include_physical)
    if a.payment_date:
        cfg.payment_date = a.payment_date
    source = f"set {a.set_id}" if a.set_id else f"file {a.file.name}"
    log("run_start", env=a.env, live=a.live, source=source, vendor=a.vendor, owner=a.owner,
        invoice_date_before=a.invoice_date_before, voucher_template=a.voucher_template, payment_date=cfg.payment_date,
        include_physical=a.include_physical, limit=a.limit)
    try:
        gw = Gateway(a.env)
        # Resolve the input against a bulk download of the vendor's invoices and order
        # lines (a few dozen calls). Each invoice is then handled with fresh reads from Alma.
        # The download only maps the input to invoices. A live run still reads every open
        # invoice fresh before writing, so a recent saved download is safe to reuse.
        cache = a.out / "cache" / f"bulk_{a.env.lower()}_{a.vendor}.json"
        lookup = BulkGateway(gw, a.vendor, log).load(cache, a.cache_minutes) if a.vendor else gw
        targets = load_targets(lookup, a.set_id, a.file)
        log("targets", count=len(targets), targets=[f"{t.kind}:{t.value} ({t.source})" for t in targets])
        work, results = Closer(lookup, cfg, log).resolve(targets)
        # Live: fresh reads around every write. Dry: the bulk view is enough.
        closer = Closer(gw if a.live else lookup, cfg, log)
        # --limit counts invoices that need action; already-closed ones don't use it up.
        # In a live run, invoices the download shows as closed are reported from it
        # (nothing is ever written to a closed invoice); open ones are read fresh.
        reporter = Closer(lookup, cfg, log)
        acted, not_attempted = 0, []
        for n, w in enumerate(work, 1):
            if n % 100 == 0:
                log("progress", stage="close invoices", done=n, total=len(work))
            if a.limit is not None and acted >= a.limit:
                not_attempted.append(w.invoice_number)
                continue
            known_closed = lookup is not gw and _v(lookup.get_invoice(w.invoice_id), "invoice_status") == "CLOSED"
            r = (reporter if known_closed else closer).run_one(w)
            results.append(r)
            if r.actions or r.outcome in (WOULD_PROCESS, WOULD_PAY):
                acted += 1
        if not_attempted:
            log("limit", limit=a.limit, not_attempted=not_attempted)
            source += f"; limited to {a.limit} invoices needing action ({len(not_attempted)} not attempted)"
    except Exception as ex:
        import traceback
        log("run_failed", error=f"{type(ex).__name__}: {str(ex)[:2000]}", traceback=traceback.format_exc())
        print(f"Run failed: {type(ex).__name__}: {ex}\nLog: {log.path}")
        log.close()
        return 2
    write_results_csv(run_dir / "results.csv", results)
    report = short_report(results, env=a.env, live=a.live, source=source, out_dir=run_dir)
    (run_dir / "report.txt").write_text(report + "\n", encoding="utf-8")
    staff = staff_summary(results, env=a.env, mode="LIVE" if a.live else "DRY", source=source,
                          cutoff=a.invoice_date_before, out_dir=run_dir)
    (run_dir / "summary_for_staff.txt").write_text(staff + "\n", encoding="utf-8-sig")
    bad = {"ERROR", "WRITE_OUTCOME_UNKNOWN", "WRITE_REJECTED"}
    code = 1 if any(r.outcome in bad for r in results) else 0
    log("run_end", exit_code=code, outcomes={r.invoice_number or "?": r.outcome for r in results})
    log.close()
    print(report)
    return code


if __name__ == "__main__":
    sys.exit(main())
