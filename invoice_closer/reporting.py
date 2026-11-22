"""Detailed JSONL log (redacted) and the short end-of-run report."""
import csv
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import List

from .redact import redact

PLAIN = {
    "CLOSED": "closed (invoice paid and closed, order lines closed)",
    "CLOSED_ORDER_LINE_OPEN": "invoice closed, but an e-book order line is still open",
    "ALREADY_CLOSED": "already closed before this run",
    "DRY_RUN_WOULD_PROCESS_AND_PAY": "dry run: would process, then pay",
    "DRY_RUN_WOULD_PAY": "dry run: would pay",
    "HELD": "held for a person (see reason)",
    "WRITE_OUTCOME_UNKNOWN": "no reply from Alma; check before re-running",
    "WRITE_REJECTED": "Alma refused the request",
    "ERROR": "error",
}


# Events too bulky for the screen (they stay in full in log.jsonl).
_SCREEN_SKIP = {"run_context", "targets"}
_SCREEN_DROP_KEYS = {"record", "reply", "traceback", "targets", "body", "outcomes"}


def screen_line(rec: dict) -> str:
    """One readable line per event: time, event, then key=value (long values cut)."""
    parts = []
    for k, v in rec.items():
        if k in ("t", "event") or k in _SCREEN_DROP_KEYS or v in (None, "", [], {}):
            continue
        if isinstance(v, dict):
            v = " ".join(f"{a}={b}" for a, b in v.items() if b not in (None, ""))
        elif isinstance(v, (list, tuple)):
            v = ",".join(str(x) for x in v)
        s = str(v)
        parts.append(f"{k}={s if len(s) <= 160 else s[:157] + '...'}")
    return f"{rec['t'].replace('T', ' ')}  {rec['event']:<18} " + "  ".join(parts)


class RunLog:
    """log.jsonl: every event in full (redacted). With stream=True (the default) each event
    is also shown on screen as one timestamped line; console.txt in the run folder keeps a
    copy of everything shown on screen."""

    def __init__(self, out_dir: Path, stream: bool = True):
        self.dir = out_dir
        self.dir.mkdir(parents=True, exist_ok=True)
        self.path = self.dir / "log.jsonl"
        self.stream = stream
        self._fh = self.path.open("a", encoding="utf-8")
        self._con = (self.dir / "console.txt").open("a", encoding="utf-8")

    def __call__(self, event: str, **data):
        rec = redact({"t": datetime.now().isoformat(timespec="milliseconds"), "event": event, **data})
        self._fh.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
        self._fh.flush()
        if event in _SCREEN_SKIP:
            return
        if self.stream or event in ("progress", "run_failed", "analysis_failed"):
            self.echo(screen_line(rec))

    def echo(self, text: str):
        """Print to screen and keep it in console.txt."""
        print(text, flush=True)
        self._con.write(text + "\n")
        self._con.flush()

    def close(self):
        self._fh.close()
        self._con.close()


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


# ---- run context (for debugging) -------------------------------------------
def run_context(argv) -> dict:
    """Versions and environment, logged once at the start of every run."""
    import platform
    import subprocess
    import sys
    root = Path(__file__).resolve().parents[1]
    ctx = {"argv": list(argv), "cwd": str(Path.cwd()), "repo": str(root),
           "python": sys.version.split()[0], "platform": platform.platform(), "host": platform.node()}
    try:
        from importlib.metadata import version
        ctx["almaapitk"] = version("almaapitk")
    except Exception as ex:   # never fail a run over context
        ctx["almaapitk"] = f"unknown ({type(ex).__name__})"
    for key, args in (("git_commit", ["rev-parse", "--short", "HEAD"]),
                      ("git_branch", ["rev-parse", "--abbrev-ref", "HEAD"]),
                      ("git_dirty", ["status", "--porcelain"])):
        try:
            out = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True,
                                 timeout=10).stdout.strip()
            ctx[key] = bool(out) if key == "git_dirty" else out
        except Exception:
            ctx[key] = "unknown"
    return ctx


# ---- summary for staff (plain language, shareable) -------------------------
# (pattern in the technical reason, plain explanation, what someone should do)
HELD_PLAIN = [
    (r"have no fund", "An invoice line has no fund",
     "Add the fund to the invoice line in Alma; the next run will close it."),
    (r"not an order line: .*deleted", "The order line was deleted in Alma", "Nothing: remove it from the set."),
    (r"on \d+ (open )?invoices", "The order line appears on more than one invoice",
     "Check which invoice should be closed."),
    (r"invoice date .* not before the cutoff|no invoice date",
     "Invoice dated on or after the cutoff date (or undated)", "Nothing: outside this job."),
    (r"outside the requested scope", "Different vendor or library", "Nothing: outside this job."),
    (r"kept it In Review", "Alma flagged the invoice for review (for example, a price difference)",
     "Review the invoice in Alma."),
    (r"manual approval", "Waiting for approval in Alma", "Approve or reject it in Alma."),
    (r"ERP stage", "At the finance (ERP) stage", "Nothing: the finance process continues."),
    (r"not in the input", "The invoice also covers order lines that were not in the set",
     "Add those order lines to the set, or close the invoice by hand."),
    (r"^0 invoices match number", "Invoice not found in Alma",
     "Sandbox: expected for invoices created after the last Sandbox refresh. "
     "Production: check the invoice number in the report."),
    (r"no invoice|has no invoice", "No invoice found for the order line", "Check the order line in Alma."),
    (r"cancelled", "The order line is cancelled", "Check the invoice in Alma."),
    (r"only one-time", "Standing or continuous order", "Nothing: these are not closed by this job."),
    (r"no available portfolio", "E-book without an active portfolio", "Check the e-book's activation."),
    (r"payment status|state changed before payment|paid, but",
     "Already marked as paid, or changed during the run", "Check the invoice in Alma."),
    (r"title has \d+ order lines|matches number", "The set entry matched more than one record",
     "Ask the technical team."),
]
DONE_PLAIN = {
    "CLOSED": "Closed and recorded as paid (e-book orders closed; print orders stay open until received)",
    "CLOSED_ORDER_LINE_OPEN": "Closed and recorded as paid, but an e-book order is still open (please check it)",
    "ALREADY_CLOSED": "Already closed before this run (nothing done)",
    "DRY_RUN_WOULD_PROCESS_AND_PAY": "Would be closed and recorded as paid",
    "DRY_RUN_WOULD_PAY": "Would be recorded as paid and closed",
    "HELD": "Left for a person",
    "WRITE_REJECTED": "Alma refused the change (technical team will check)",
    "WRITE_OUTCOME_UNKNOWN": "No answer from Alma (technical team will check before any re-run)",
    "ERROR": "Error (technical team will check)",
}


def _plain_hold(reason: str):
    for pattern, plain, todo in HELD_PLAIN:
        if re.search(pattern, reason or "", re.I):
            return plain, todo
    return "Other reason (see the technical report)", "Ask the technical team."


def staff_summary(results, *, env: str, mode: str, source: str, cutoff: str = None,
                  out_dir: Path = None) -> str:
    """Plain-language summary for people who do not read logs. mode: LIVE, DRY or ANALYSIS."""
    real = mode == "LIVE"
    title = {"LIVE": "Invoice closing: results",
             "DRY": "Invoice closing: test run (nothing was changed)",
             "ANALYSIS": "Invoice closing: check before the run (nothing was changed)"}[mode]
    where = "Production Alma" if env == "PRODUCTION" else "Alma Sandbox (test environment)"
    lines = [title, "=" * len(title),
             f"Date: {datetime.now():%d %B %Y, %H:%M}",
             f"Where: {where}",
             f"Which invoices: {source}" + (f"; only invoices dated before {cutoff}" if cutoff else ""),
             ""]
    counts = Counter(r.outcome for r in results)
    lines.append(f"In numbers ({len(results)} invoices):")
    for outcome, n in counts.most_common():
        lines.append(f"  {n:5d}  {DONE_PLAIN.get(outcome, outcome)}")

    held = defaultdict(list)
    for r in results:
        if r.outcome == "HELD":
            held[_plain_hold(r.reason)].append(r)
        elif r.outcome in ("WRITE_REJECTED", "WRITE_OUTCOME_UNKNOWN", "ERROR"):
            held[(DONE_PLAIN[r.outcome], "The technical team will check before any re-run.")].append(r)
    if held:
        lines += ["", "Left for a person, by reason:"]
        for (plain, todo), rs in sorted(held.items(), key=lambda kv: -len(kv[1])):
            lines.append(f"- {plain}: {len(rs)}. What to do: {todo}")
            lines.append("    Invoices: " + ", ".join(_who(r) for r in rs[:40])
                         + (f" and {len(rs) - 40} more" if len(rs) > 40 else ""))

    to_receive = [(r, p) for r in results if r.outcome in ("CLOSED", "ALREADY_CLOSED")
                  for p, s in r.order_lines_after.items() if s and s != "CLOSED"]
    if to_receive and real:
        lines += ["", f"Print orders still open ({len(to_receive)}), as expected: this job pays them but "
                      "does not receive items. They close when the items are received in Alma.",
                  "    " + ", ".join(f"{p} (invoice {_who(r)})" for r, p in to_receive[:60])
                  + (f" and {len(to_receive) - 60} more" if len(to_receive) > 60 else "")]
    if not real:
        lines += ["", "This was not the real run: no invoice or order line was changed."]
    lines += ["", "Payments recorded by this job are automatic status changes in Alma. "
                  "They are not real payments and no money was transferred."]
    if out_dir:
        lines += ["", f"Technical details for the support team: {out_dir}"]
    return "\n".join(lines)


def _who(r) -> str:
    if r.invoice_number:
        return str(r.invoice_number)
    src = r.sources[0] if r.sources else "?"
    return src.split(" (")[0].split(":", 1)[-1]
