#!/usr/bin/env python
"""Pre-analysis of an invoice-closer input, before any run. Read only: never writes to Alma.

Takes the same input and filters as close_invoices.py and reports, per order line, its
invoice, the invoice date, state and alerts, and what the closer would do; then a summary
of possible issues.

Example:
  poetry run python scripts/analyze_set.py --set-id <PO_LINE set id> --vendor RIALTO --owner AC1 \
      --include-physical --invoice-date-before 2026-10-01
"""
import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from invoice_closer.analysis import ReadOnlyGateway, analyze, summary, write_csv  # noqa: E402
from invoice_closer.engine import Config  # noqa: E402
from invoice_closer.gateway import Gateway  # noqa: E402
from invoice_closer.inputs import load_targets  # noqa: E402
from invoice_closer.reporting import RunLog  # noqa: E402


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--set-id", help="Alma Order lines (PO_LINE) set")
    src.add_argument("--file", type=Path, help=".xlsx, .csv or .tsv file")
    p.add_argument("--env", choices=["SANDBOX", "PRODUCTION"], default="SANDBOX")
    p.add_argument("--vendor")
    p.add_argument("--owner")
    p.add_argument("--invoice-date-before", metavar="YYYY-MM-DD")
    p.add_argument("--include-physical", action="store_true")
    p.add_argument("--voucher-number", dest="voucher_template", default="ANALYSIS-{invoice_number}",
                   help="only used to mirror the closer's checks; nothing is paid")
    p.add_argument("--out", type=Path, default=ROOT / "output" / "invoice_closer")
    return p.parse_args(argv)


def main(argv=None) -> int:
    a = parse_args(argv)
    logging.disable(logging.INFO)
    if a.invoice_date_before:
        try:
            a.invoice_date_before = datetime.strptime(a.invoice_date_before, "%Y-%m-%d").date().isoformat()
        except ValueError:
            print("Refusing: --invoice-date-before must be YYYY-MM-DD.")
            return 2
    run_dir = a.out / f"{datetime.now():%Y%m%d_%H%M%S}_{a.env.lower()}_analysis"
    log = RunLog(run_dir)
    cfg = Config(live=False, vendor=a.vendor, owner=a.owner, invoice_date_before=a.invoice_date_before,
                 voucher_number_template=a.voucher_template, include_physical=a.include_physical)
    source = f"set {a.set_id}" if a.set_id else f"file {a.file.name}"
    log("analysis_start", env=a.env, source=source, vendor=a.vendor, owner=a.owner,
        invoice_date_before=a.invoice_date_before, include_physical=a.include_physical)
    try:
        gw = ReadOnlyGateway(Gateway(a.env))
        if a.set_id:
            meta = gw.get_set(a.set_id)
            source += f" ({meta.get('name')}, {meta.get('number_of_members', {}).get('value', '?')} members)"
        targets = load_targets(gw, a.set_id, a.file)
        rows, results = analyze(gw, targets, cfg, log)
    except Exception as ex:
        log("analysis_failed", error=f"{type(ex).__name__}: {str(ex)[:300]}")
        print(f"Analysis failed: {type(ex).__name__}: {ex}\nLog: {log.path}")
        log.close()
        return 2
    write_csv(run_dir / "analysis.csv", rows)
    text = summary(rows, results, env=a.env, source=source, cfg=cfg, out_dir=run_dir)
    (run_dir / "summary.txt").write_text(text + "\n", encoding="utf-8")
    log("analysis_end", records=len(rows))
    log.close()
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
