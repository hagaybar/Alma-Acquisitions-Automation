"""Read-only pre-analysis of an input set before a closer run.

For every input record it reports the order line, its invoice, the invoice's date,
state and alerts, other order lines on that invoice, and what the closer would do
(the closer's own dry-run decision, so the two cannot disagree). A summary counts
the possible issues.

Nothing is written to Alma: the gateway wrapper refuses every write, and the closer
runs with live=False.
"""
import csv
import re
from collections import Counter, defaultdict
from dataclasses import replace
from pathlib import Path
from typing import Dict, List, Optional

from .engine import (Closer, Config, HELD, WOULD_PAY, WOULD_PROCESS,
                     _v, alerts_of, state_of)
from .inputs import Target

ISSUES = {
    "NO_INVOICE": "order line has no invoice the closer can find",
    "NOT_AN_ORDER_LINE": "set member is not an order line (e.g. deleted)",
    "SEVERAL_INVOICES": "order line is on more than one invoice (held)",
    "DATE_ON_OR_AFTER_CUTOFF": "invoice dated on or after the cutoff (held)",
    "NO_INVOICE_DATE": "invoice has no invoice date (held)",
    "PHYSICAL": "print/physical order: paid only, order line stays open until received",
    "CONTINUOUS_ORDER": "not a one-time order (held)",
    "POL_CANCELLED": "order line cancelled",
    "POL_CLOSED": "order line already closed",
    "INVOICE_CLOSED": "invoice already closed",
    "PAID_BUT_OPEN": "invoice marked paid but still open (held)",
    "MANUAL_APPROVAL": "invoice waiting for manual approval (held)",
    "ERP_STAGE": "invoice at ERP stage, Waiting to be Sent (held)",
    "OTHER_LINES_NOT_IN_SET": "invoice also covers order lines not in the input (held)",
    "NO_FUND": "an invoice line has no fund (held: add a fund in Alma)",
    "PRICE_ALERT": "invoice price differs from the order line (DIFF_PRICE_THAN_POLINE)",
    "SCOPE": "vendor or owner outside the requested scope (held)",
}

COLUMNS = ["input", "pol", "pol_type", "pol_status", "pol_created", "invoice_reference",
           "invoice_number", "invoice_id", "invoice_date", "vendor", "owner", "invoice_status",
           "workflow", "approval", "payment", "total", "currency", "alerts", "invoice_lines",
           "lines_not_in_input", "predicted_outcome", "reason", "issues"]

_SOURCE_RE = re.compile(r"^(\w+):(\S+)")


class ReadOnlyGateway:
    """Caches reads; any write raises before reaching Alma."""

    def __init__(self, gw):
        self._gw = gw
        self._cache: Dict = {}

    def __getattr__(self, name):
        target = getattr(self._gw, name)
        if name == "invoice_service" or not callable(target):
            if name == "invoice_service":
                def refuse(*a, **k):
                    raise RuntimeError("pre-analysis is read-only: write refused")
                return refuse
            return target

        def cached(*args):
            key = (name, args)
            try:
                hash(key)
            except TypeError:
                return target(*args)
            if key not in self._cache:
                self._cache[key] = target(*args)
            return self._cache[key]
        return cached

    def find_invoices_by_pol(self, pol_no: str) -> List[Dict]:
        """Invoices whose lines reference this order line."""
        key = ("find_invoices_by_pol", pol_no)
        if key not in self._cache:
            inner = getattr(self._gw, "find_invoices_by_pol", None)
            if inner is not None:
                self._cache[key] = inner(pol_no)
            else:
                data = self._gw._get("almaws/v1/acq/invoices", {"q": f"pol_number~{pol_no}", "limit": 100})
                self._cache[key] = [inv for inv in data.get("invoice") or []
                                    if any(_line_pol(l) == pol_no for l in self.get_invoice_lines(str(inv["id"])))]
        return self._cache[key]


def _line_pol(line) -> Optional[str]:
    ref = line.get("po_line")
    return ref.get("value") if isinstance(ref, dict) else (ref or None)


def analyze(gw, targets: List[Target], cfg: Config, log):
    """Returns (rows, results). rows: one dict per input record."""
    ro = gw if isinstance(gw, ReadOnlyGateway) else ReadOnlyGateway(gw)
    dry = replace(cfg, live=False)
    closer = Closer(ro, dry, log)
    work, unresolved = closer.resolve(targets)
    results = []
    for n, w in enumerate(work, 1):
        if n % 100 == 0:
            log("progress", stage="check invoices", done=n, total=len(work))
        results.append(closer.run_one(w))

    by_pol: Dict[str, object] = {}
    by_invoice: Dict[str, object] = {}
    input_pols = set()
    for w, r in zip(work, results):
        by_invoice[w.invoice_id] = (w, r)
        for p in w.selected_pols:
            by_pol[p] = (w, r)
    unresolved_by_value = {}
    for r in unresolved:
        m = _SOURCE_RE.match(r.sources[0] if r.sources else "")
        if m:
            unresolved_by_value[m.group(2)] = r
    for t in targets:
        if t.kind == "pol":
            input_pols.add(t.value)

    rows = []
    for n, t in enumerate(targets, 1):
        if n % 100 == 0:
            log("progress", stage="order line details", done=n, total=len(targets))
        row = {c: "" for c in COLUMNS}
        row["input"] = f"{t.kind}:{t.value}"
        issues: List[str] = []
        pair = None
        if t.kind == "pol":
            row["pol"] = t.value
            try:
                pol = ro.get_pol(t.value)
                ptype, pstatus = _v(pol, "type") or "", _v(pol, "status") or ""
                row.update(pol_type=ptype, pol_status=pstatus,
                           pol_created=(pol.get("created_date") or "")[:10],
                           invoice_reference=pol.get("invoice_reference") or "")
                if not ptype.startswith("E_"):
                    issues.append("PHYSICAL")
                    if not ptype.endswith("_OT"):
                        issues.append("CONTINUOUS_ORDER")
                elif not ptype.endswith("_OT"):
                    issues.append("CONTINUOUS_ORDER")
                if pstatus == "CANCELLED":
                    issues.append("POL_CANCELLED")
                if pstatus == "CLOSED":
                    issues.append("POL_CLOSED")
            except Exception as ex:
                row["reason"] = f"order line read failed: {type(ex).__name__}"
            pair = by_pol.get(t.value)
            if pair is None and pstatus_ok(row):
                found = ro.find_invoices_by_pol(t.value)
                issues.append("SEVERAL_INVOICES" if len(found) > 1 else "NO_INVOICE")
                if found:
                    row["invoice_number"] = " ".join(str(i.get("number")) for i in found)
        elif t.kind == "not_pol":
            issues.append("NOT_AN_ORDER_LINE")
        elif t.kind in ("invoice_id", "invoice_number"):
            pair = next(((w, r) for w, r in zip(work, results)
                         if any(s.startswith(f"{t.kind}:{t.value} ") for s in w.sources)), None)

        if pair:
            w, r = pair
            inv = ro.get_invoice(w.invoice_id)
            st = state_of(inv)
            alerts = alerts_of(inv)
            pols = [p for p in (_line_pol(l) for l in ro.get_invoice_lines(w.invoice_id)) if p]
            outside = sorted(set(pols) - input_pols) if t.kind == "pol" else []
            row.update(invoice_number=str(inv.get("number")), invoice_id=w.invoice_id,
                       invoice_date=(inv.get("invoice_date") or "")[:10],
                       vendor=_v(inv, "vendor") or "", owner=_v(inv, "owner") or "",
                       invoice_status=st["status"] or "", workflow=st["workflow"] or "",
                       approval=st["approval"] or "", payment=st["payment"] or "",
                       total=inv.get("total_amount") or "", currency=_v(inv, "currency") or "",
                       alerts=" ".join(alerts), invoice_lines=len(pols),
                       lines_not_in_input=" ".join(outside),
                       predicted_outcome=r.outcome, reason=r.reason)
            if t.kind != "pol" and pols:
                # Invoice input: describe the order lines from the invoice's lines.
                types, statuses = [], []
                for p in pols:
                    try:
                        pol = ro.get_pol(p)
                        types.append(_v(pol, "type") or "?")
                        statuses.append(_v(pol, "status") or "?")
                    except Exception as ex:
                        types.append(f"read failed: {type(ex).__name__}")
                row.update(pol=" ".join(pols), pol_type=" ".join(dict.fromkeys(types)),
                           pol_status=" ".join(dict.fromkeys(statuses)))
            if cfg.invoice_date_before:
                if not row["invoice_date"]:
                    issues.append("NO_INVOICE_DATE")
                elif row["invoice_date"] >= cfg.invoice_date_before:
                    issues.append("DATE_ON_OR_AFTER_CUTOFF")
            if st["status"] == "CLOSED":
                issues.append("INVOICE_CLOSED")
            elif st["payment"] and st["payment"] != "NOT_PAID":
                issues.append("PAID_BUT_OPEN")
            if st["workflow"] == "InApproval":
                issues.append("MANUAL_APPROVAL")
            if st["workflow"] == "Waiting to be Sent":
                issues.append("ERP_STAGE")
            if outside:
                issues.append("OTHER_LINES_NOT_IN_SET")
            if any(not l.get("fund_distribution") for l in ro.get_invoice_lines(w.invoice_id)):
                issues.append("NO_FUND")
            if "DIFF_PRICE_THAN_POLINE" in alerts:
                issues.append("PRICE_ALERT")
            if (cfg.vendor and row["vendor"] != cfg.vendor) or (cfg.owner and row["owner"] != cfg.owner):
                issues.append("SCOPE")
        elif t.value in unresolved_by_value:
            r = unresolved_by_value[t.value]
            row.update(predicted_outcome=r.outcome, reason=row["reason"] or r.reason)
        row["issues"] = " ".join(dict.fromkeys(issues))
        rows.append(row)
    return rows, unresolved + results


def pstatus_ok(row) -> bool:
    return row.get("pol_status") != "CANCELLED"


def write_csv(path: Path, rows: List[Dict]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as fh:   # BOM: Excel opens it as UTF-8
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)


def summary(rows: List[Dict], results, *, env: str, source: str, cfg: Config, out_dir: Path) -> str:
    out = [f"Pre-analysis · {env} · read only · input: {source}",
           f"Filters: vendor={cfg.vendor or 'any'} owner={cfg.owner or 'any'} "
           f"invoice date before={cfg.invoice_date_before or 'none'} "
           f"physical={'included' if cfg.include_physical else 'excluded'}",
           f"{len(rows)} input records, {len(results)} invoices/unresolved"]

    def block(title, counter):
        if counter:
            out.append(f"\n{title}")
            out.extend(f"  {n:5d}  {k}" for k, n in counter.most_common())

    block("Order line types", Counter(r["pol_type"] or "(not an order line)" for r in rows))
    block("Order line status", Counter(r["pol_status"] for r in rows if r["pol_status"]))
    block("Predicted outcome per invoice", Counter(r.outcome for r in results))
    held = Counter(_reason_kind(r.reason) for r in results if r.outcome == HELD)
    block("Held, by reason", held)
    issue_counts = Counter(i for r in rows for i in r["issues"].split())
    if issue_counts:
        out.append("\nPossible issues (order lines)")
        out.extend(f"  {n:5d}  {k}: {ISSUES.get(k, '')}" for k, n in issue_counts.most_common())
    block("Invoice alerts", Counter(a for r in _unique_invoices(rows) for a in r["alerts"].split()))
    dates = sorted(r["invoice_date"] for r in _unique_invoices(rows) if r["invoice_date"])
    if dates:
        out.append(f"\nInvoice dates: {dates[0]} to {dates[-1]}")
    to_pay = defaultdict(float)
    for r in _unique_invoices(rows):
        if r["predicted_outcome"] in (WOULD_PROCESS, WOULD_PAY) and r["total"] != "":
            try:
                to_pay[r["currency"]] += float(r["total"])
            except ValueError:
                pass
    if to_pay:
        out.append("Would record as paid: " + ", ".join(f"{v:,.2f} {k}" for k, v in to_pay.items()))
    out.append(f"\nPer order line: {out_dir / 'analysis.csv'}")
    return "\n".join(out)


def _unique_invoices(rows):
    seen = set()
    for r in rows:
        if r["invoice_id"] and r["invoice_id"] not in seen:
            seen.add(r["invoice_id"])
            yield r


def _reason_kind(reason: str) -> str:
    """Group held reasons: strip record numbers and dates so like counts with like."""
    s = re.sub(r"POL-\d+", "POL-…", reason or "")
    s = re.sub(r"\d{4}-\d{2}-\d{2}", "<date>", s)
    s = re.sub(r"alerts: .*", "alerts: …", s)
    return s[:120]
