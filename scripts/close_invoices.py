#!/usr/bin/env python
"""Close Alma invoices (process, then pay) and their order lines.

Dry run by default: reads everything and reports what it would do.

Examples:
  poetry run python scripts/close_invoices.py --set-id 43266180120004146 --vendor RIALTO
  poetry run python scripts/close_invoices.py --file input/to_close.xlsx --vendor RIALTO \
      --voucher-number "PAY-{invoice_number}" --live

Input: exactly one of --set-id (title set) or --file (.xlsx, .csv, .tsv). See
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

from invoice_closer.engine import Closer, Config  # noqa: E402
from invoice_closer.gateway import Gateway  # noqa: E402
from invoice_closer.inputs import load_targets  # noqa: E402
from invoice_closer.reporting import RunLog, short_report, write_results_csv  # noqa: E402


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--set-id", help="Alma set of titles (BIB_MMS)")
    src.add_argument("--file", type=Path, help=".xlsx, .csv or .tsv file")
    p.add_argument("--env", choices=["SANDBOX", "PRODUCTION"], default="SANDBOX")
    p.add_argument("--live", action="store_true", help="send the writes (default: dry run)")
    p.add_argument("--production-approved", action="store_true",
                   help="required with --env PRODUCTION --live, after a reviewed dry run")
    p.add_argument("--vendor", help="only touch invoices of this vendor code, e.g. RIALTO")
    p.add_argument("--owner", help="only touch invoices of this owner code, e.g. AC1")
    p.add_argument("--voucher-number", dest="voucher_template",
                   help='voucher number template, e.g. "PAY-{invoice_number}"')
    p.add_argument("--payment-date", help="YYYY-MM-DD (default: today)")
    p.add_argument("--settle-seconds", type=int, default=30,
                   help="how long to watch for a delayed state change after a write")
    p.add_argument("--out", type=Path, default=ROOT / "output" / "invoice_closer")
    return p.parse_args(argv)


def main(argv=None) -> int:
    a = parse_args(argv)
    # AlmaAPITK logs full record bodies at DEBUG/INFO to the console and logs/.
    # This program keeps its own redacted log, so silence those levels.
    logging.disable(logging.INFO)
    if a.env == "PRODUCTION" and a.live and not a.production_approved:
        print("Refusing: production writes need --production-approved after a reviewed dry run.")
        return 2
    run_dir = a.out / f"{datetime.now():%Y%m%d_%H%M%S}_{a.env.lower()}_{'live' if a.live else 'dry'}"
    log = RunLog(run_dir)
    cfg = Config(live=a.live, vendor=a.vendor, owner=a.owner, voucher_number_template=a.voucher_template,
                 settle_seconds=a.settle_seconds)
    if a.payment_date:
        cfg.payment_date = a.payment_date
    source = f"set {a.set_id}" if a.set_id else f"file {a.file.name}"
    log("run_start", env=a.env, live=a.live, source=source, vendor=a.vendor, owner=a.owner,
        voucher_template=a.voucher_template, payment_date=cfg.payment_date)
    try:
        gw = Gateway(a.env)
        targets = load_targets(gw, a.set_id, a.file)
        log("targets", count=len(targets), sample=[f"{t.kind}:{t.value}" for t in targets[:20]])
        closer = Closer(gw, cfg, log)
        work, results = closer.resolve(targets)
        for w in work:
            results.append(closer.run_one(w))
    except Exception as ex:
        log("run_failed", error=f"{type(ex).__name__}: {str(ex)[:300]}")
        print(f"Run failed: {type(ex).__name__}: {ex}\nLog: {log.path}")
        log.close()
        return 2
    write_results_csv(run_dir / "results.csv", results)
    report = short_report(results, env=a.env, live=a.live, source=source, out_dir=run_dir)
    (run_dir / "report.txt").write_text(report + "\n", encoding="utf-8")
    log("run_end", outcomes={r.invoice_number or "?": r.outcome for r in results})
    log.close()
    print(report)
    bad = {"ERROR", "WRITE_OUTCOME_UNKNOWN", "WRITE_REJECTED"}
    return 1 if any(r.outcome in bad for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
