"""Detailed JSONL log (redacted) and the short end-of-run report."""
import csv
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import List

from .redact import redact

PLAIN = {
    "CLOSED": "closed (invoice paid and closed, order lines closed)",
    "CLOSED_ORDER_LINE_OPEN": "invoice closed, but an order line is still open",
    "ALREADY_CLOSED": "already closed before this run",
    "DRY_RUN_WOULD_PROCESS_AND_PAY": "dry run: would process, then pay",
    "DRY_RUN_WOULD_PAY": "dry run: would pay",
    "HELD": "held for a person (see reason)",
    "WRITE_OUTCOME_UNKNOWN": "no reply from Alma; check before re-running",
    "WRITE_REJECTED": "Alma refused the request",
    "ERROR": "error",
}


class RunLog:
    def __init__(self, out_dir: Path):
        self.dir = out_dir
        self.dir.mkdir(parents=True, exist_ok=True)
        self.path = self.dir / "log.jsonl"
        self._fh = self.path.open("a", encoding="utf-8")

    def __call__(self, event: str, **data):
        rec = {"t": datetime.now().isoformat(timespec="seconds"), "event": event, **data}
        self._fh.write(json.dumps(redact(rec), ensure_ascii=False, default=str) + "\n")
        self._fh.flush()

    def close(self):
        self._fh.close()


def write_results_csv(path: Path, results) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["invoice_number", "invoice_id", "outcome", "reason", "order_lines",
                    "invoice_before", "invoice_after", "order_lines_after", "actions", "sources"])
        for r in results:
            fmt = lambda s: "/".join(str(s.get(k)) for k in ("status", "workflow", "approval", "payment")) if s else ""
            w.writerow([r.invoice_number or "", r.invoice_id or "", r.outcome, r.reason,
                        " ".join(r.order_lines), fmt(r.before), fmt(r.after),
                        " ".join(f"{k}={v}" for k, v in r.order_lines_after.items()),
                        "+".join(r.actions), " | ".join(r.sources)])


def short_report(results, *, env: str, live: bool, source: str, out_dir: Path) -> str:
    counts = Counter(r.outcome for r in results)
    lines = [f"Invoice closer · {env} · {'LIVE' if live else 'DRY RUN'} · input: {source}",
             f"{len(results)} invoices: " + ", ".join(f"{n} {k}" for k, n in counts.most_common())]
    for r in results:
        if r.outcome in ("CLOSED", "ALREADY_CLOSED") and not r.reason:
            continue
        who = r.invoice_number or (r.sources[0] if r.sources else "?")
        lines.append(f"- {who}: {PLAIN.get(r.outcome, r.outcome)}" + (f" — {r.reason}" if r.reason else ""))
    lines.append(f"Details: {out_dir}")
    return "\n".join(lines)
