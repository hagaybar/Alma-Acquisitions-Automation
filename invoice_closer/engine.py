"""Decide and apply the next step for each invoice, following the validated flow.

The engine never forces a state. Each invoice ends in exactly one outcome; anything
outside the validated path is HELD with a reason a person can act on.
"""
import time
import traceback
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Callable, Dict, List, Optional, Set

from .gateway import WriteOutcomeUnknown, WriteRejected
from .inputs import Target

# ---- outcomes --------------------------------------------------------------
CLOSED = "CLOSED"                        # this run closed invoice and all its order lines
CLOSED_POL_OPEN = "CLOSED_ORDER_LINE_OPEN"  # invoice closed, an order line is still open
ALREADY_CLOSED = "ALREADY_CLOSED"
WOULD_PROCESS = "DRY_RUN_WOULD_PROCESS_AND_PAY"
WOULD_PAY = "DRY_RUN_WOULD_PAY"
HELD = "HELD"
WRITE_UNKNOWN = "WRITE_OUTCOME_UNKNOWN"
WRITE_REJECTED = "WRITE_REJECTED"
ERROR = "ERROR"

# API workflow code "Ready to be Paid" is the UI's "Waiting for Payment".
WF_REVIEW, WF_PAYMENT, WF_APPROVAL, WF_ERP = "InReview", "Ready to be Paid", "InApproval", "Waiting to be Sent"
APPROVED_STATES = {"APPROVED", "NOT_REQUIRED"}
AVAILABLE = {"11", "AVAILABLE", "ACTIVE"}


def _v(obj, key) -> Optional[str]:
    val = (obj or {}).get(key)
    if isinstance(val, dict):
        return val.get("value")
    return val


def state_of(inv: Dict) -> Dict[str, Optional[str]]:
    pay = (inv.get("payment") or {})
    return {
        "status": _v(inv, "invoice_status"),
        "workflow": _v(inv, "invoice_workflow_status"),
        "approval": _v(inv, "invoice_approval_status"),
        "payment": _v(pay, "payment_status"),
    }


def lines_without_fund(lines: List[Dict]) -> List[str]:
    """Invoice line numbers with no fund distribution.

    Sandbox, 18 Nov 2026: invoices whose line had no fund stayed In Review after
    process_invoice (6 of 6). Paying one without processing closed it with no fund
    expenditure, and Alma then refuses to add a fund to a closed invoice's line
    (HTTP 400, 403877). So such an invoice is never processed or paid.
    """
    return [str(l.get("number", "?")) for l in lines if not l.get("fund_distribution")]


def alerts_of(inv: Dict) -> List[str]:
    raw = inv.get("alert") or (inv.get("alerts") or {}).get("alert") or []
    if isinstance(raw, dict):
        raw = [raw]
    return [a.get("value") if isinstance(a, dict) else str(a) for a in raw]


@dataclass
class Config:
    live: bool = False
    vendor: Optional[str] = None          # e.g. RIALTO; None = any
    owner: Optional[str] = None           # e.g. AC1; None = any
    invoice_date_before: Optional[str] = None  # YYYY-MM-DD; only invoices dated earlier; None = any
    voucher_number_template: Optional[str] = None   # e.g. "PAY-{invoice_number}"
    payment_date: str = field(default_factory=lambda: date.today().isoformat())
    include_physical: bool = False        # one-time physical orders: pay only, never receive
    check_portfolios: bool = True         # e-book lines: title must have an available portfolio
    check_items: bool = True              # physical lines: log how many items were received
    settle_seconds: int = 30              # how long to watch for a delayed state change
    poll_interval: float = 5.0
    sleep: Callable[[float], None] = time.sleep


@dataclass
class Result:
    invoice_id: Optional[str]
    invoice_number: Optional[str]
    outcome: str
    reason: str = ""
    sources: List[str] = field(default_factory=list)
    order_lines: List[str] = field(default_factory=list)
    before: Dict = field(default_factory=dict)
    after: Dict = field(default_factory=dict)
    order_lines_after: Dict[str, str] = field(default_factory=dict)
    actions: List[str] = field(default_factory=list)


@dataclass
class Work:
    invoice_id: str
    invoice_number: str
    sources: List[str] = field(default_factory=list)
    voucher: Dict[str, str] = field(default_factory=dict)
    selected_pols: Set[str] = field(default_factory=set)   # order lines the input named
    whole_invoice: bool = False                              # the input named the invoice itself


class Closer:
    def __init__(self, gateway, config: Config, log: Callable[..., None]):
        self.gw, self.cfg, self.log = gateway, config, log
        self._pol_types: Dict[str, str] = {}

    # ---- stage 1: resolve inputs to invoices ------------------------------
    def resolve(self, targets: List[Target]):
        work: Dict[str, Work] = {}
        unresolved: List[Result] = []

        def add(inv_id, inv_no, t: Target, pol_no: Optional[str] = None):
            w = work.setdefault(inv_id, Work(inv_id, inv_no))
            w.sources.append(f"{t.kind}:{t.value} ({t.source})")
            if pol_no:
                w.selected_pols.add(pol_no)
            else:
                w.whole_invoice = True
            if t.voucher and not w.voucher:
                w.voucher = dict(t.voucher)

        failed: Dict[tuple, Result] = {}

        def fail(t: Target, reason: str):
            # Several rows naming the same record (one per invoice line in an Analytics
            # export) make one held entry with all their sources, not one per row.
            src = f"{t.kind}:{t.value} ({t.source})"
            key = (t.kind, t.value, reason)
            if key in failed:
                failed[key].sources.append(src)
            else:
                failed[key] = Result(None, None, HELD, reason, [src])
                unresolved.append(failed[key])
            self.log("resolve_failed", target=t.value, kind=t.kind, source=t.source, reason=reason)

        for n, t in enumerate(targets, 1):
            if n % 100 == 0:
                self.log("progress", stage="find invoices", done=n, total=len(targets))
            try:
                if t.kind == "not_pol":
                    fail(t, f"set member is not an order line: {t.value}")
                    continue
                if t.kind == "invoice_id":
                    inv = self.gw.get_invoice(t.value)
                    add(t.value, str(inv.get("number")), t)
                    continue
                if t.kind == "invoice_number":
                    found = self.gw.find_invoices_by_number(t.value)
                    if self.cfg.vendor:
                        found = [i for i in found if _v(i, "vendor") == self.cfg.vendor]
                    if len(found) != 1:
                        fail(t, f"{len(found)} invoices match number {t.value}")
                        continue
                    add(str(found[0]["id"]), t.value, t)
                    continue
                if t.kind == "pol":
                    pols = [self.gw.get_pol(t.value)]
                else:
                    # Search results are brief (no invoice_reference): read each line in full.
                    pols = [self.gw.get_pol(p["number"]) for p in self.gw.find_pols_by_mms(t.value)]
                pols = [p for p in pols if _v(p, "status") != "CANCELLED"]
                if not pols:
                    fail(t, "no order line found" if t.kind == "mms" else "order line cancelled")
                    continue
                if t.kind == "mms" and len(pols) > 1:
                    # A title is not a unit of work: don't guess which order line was meant.
                    fail(t, f"title has {len(pols)} order lines "
                            f"({', '.join(p.get('number') or '?' for p in pols)}); name the order line")
                    continue
                linked = 0
                for p in pols:
                    inv = self._invoice_for_pol(p)
                    if inv is None:
                        self.log("pol_without_invoice", target=t.value, pol=p.get("number"),
                                 pol_status=_v(p, "status"))
                        continue
                    add(str(inv["id"]), str(inv.get("number")), t, p.get("number"))
                    linked += 1
                if not linked:
                    fail(t, getattr(self, "_no_invoice_reason", "order line has no invoice"))
            except Exception as ex:   # one bad row never stops the batch
                self.log("lookup_error", target=t.value, kind=t.kind, traceback=traceback.format_exc())
                fail(t, f"lookup error: {type(ex).__name__}: {str(ex)[:200]}")
        self.log("resolved", invoices=len(work), unresolved=len(unresolved))
        return list(work.values()), unresolved

    def _invoice_for_pol(self, pol: Dict) -> Optional[Dict]:
        """The order line's invoice, found through invoice lines; the POL's invoice_reference
        (a vendor invoice number) is only a fallback. Sets self._no_invoice_reason on None."""
        number = pol.get("number")
        self._no_invoice_reason = "order line has no invoice"
        finder = getattr(self.gw, "find_invoices_by_pol", None)
        candidates = finder(number) if finder else []
        if candidates:
            open_ = [i for i in candidates if _v(i, "invoice_status") != "CLOSED"]
            if len(open_) == 1:
                return open_[0]
            if not open_:
                # Every invoice for this line is closed: report the latest as already closed.
                latest = max(candidates, key=lambda i: (i.get("invoice_date") or "", str(i.get("number"))))
                if len(candidates) > 1:
                    self.log("pol_several_closed_invoices", pol=number,
                             invoices=[str(i.get("number")) for i in candidates], using=str(latest.get("number")))
                return latest
            self._no_invoice_reason = (f"order line is on {len(open_) or len(candidates)} "
                                       f"{'open ' if open_ else ''}invoices "
                                       f"({', '.join(str(i.get('number')) for i in (open_ or candidates))}); "
                                       "name the invoice")
            self.log("pol_ambiguous_invoices", pol=number,
                     invoices=[str(i.get("number")) for i in candidates])
            return None
        ref = pol.get("invoice_reference")
        if not ref:
            return None
        candidates = self.gw.find_invoices_by_number(str(ref))
        vendor = _v(pol, "vendor")
        if vendor:
            candidates = [i for i in candidates if _v(i, "vendor") == vendor] or candidates
        if len(candidates) == 1:
            return candidates[0]
        linked = [i for i in candidates if number in self._line_pols(str(i["id"]))]
        return linked[0] if len(linked) == 1 else None

    def _line_pols(self, invoice_id: str) -> List[Optional[str]]:
        out = []
        for line in self.gw.get_invoice_lines(invoice_id):
            ref = line.get("po_line")
            out.append(ref.get("value") if isinstance(ref, dict) else (ref or None))
        return out

    # ---- stage 2: per-invoice decision ------------------------------------
    def run_one(self, w: Work) -> Result:
        r = Result(w.invoice_id, w.invoice_number, ERROR, sources=list(w.sources))
        t0 = time.monotonic()
        try:
            self._run(w, r)
        except Exception as ex:
            r.outcome, r.reason = ERROR, f"{type(ex).__name__}: {str(ex)[:300]}"
            self.log("invoice_error", invoice=w.invoice_number, invoice_id=w.invoice_id,
                     error=str(ex)[:2000], traceback=traceback.format_exc())
        self.log("outcome", invoice=w.invoice_number, invoice_id=w.invoice_id, outcome=r.outcome,
                 reason=r.reason, before=r.before, after=r.after, order_lines=r.order_lines,
                 order_lines_after=r.order_lines_after, actions=r.actions, sources=r.sources,
                 seconds=round(time.monotonic() - t0, 1))
        return r

    def _hold(self, r: Result, reason: str):
        r.outcome, r.reason = HELD, reason

    def _run(self, w: Work, r: Result):
        inv = self.gw.get_invoice(w.invoice_id)
        st = state_of(inv)
        r.before = dict(st, alerts=alerts_of(inv))
        r.invoice_number = str(inv.get("number"))
        self.log("invoice_read", invoice=r.invoice_number, invoice_id=w.invoice_id, state=r.before,
                 owner=_v(inv, "owner"), vendor=_v(inv, "vendor"), invoice_date=inv.get("invoice_date"),
                 total=inv.get("total_amount"), currency=_v(inv, "currency"))

        if self.cfg.vendor and _v(inv, "vendor") != self.cfg.vendor:
            return self._hold(r, f"vendor {_v(inv, 'vendor')} is outside the requested scope")
        if self.cfg.owner and _v(inv, "owner") != self.cfg.owner:
            return self._hold(r, f"owner {_v(inv, 'owner')} is outside the requested scope")
        if self.cfg.invoice_date_before:
            # Alma returns dates as "YYYY-MM-DDZ".
            inv_date = (inv.get("invoice_date") or "")[:10]
            if not inv_date:
                return self._hold(r, "invoice has no invoice date; cannot apply the date cutoff")
            if inv_date >= self.cfg.invoice_date_before:
                return self._hold(r, f"invoice date {inv_date} is not before the cutoff "
                                     f"{self.cfg.invoice_date_before}")

        r.order_lines = [p for p in self._line_pols(w.invoice_id) if p]

        if st["status"] == "CLOSED":
            r.after = r.before
            r.order_lines_after = self._pol_states(r.order_lines)
            r.outcome = ALREADY_CLOSED
            r.reason = self._open_lines(r.order_lines_after)[1]
            return

        if not w.whole_invoice:
            # Closing an invoice processes every line on it. When the input named order
            # lines, don't touch lines it didn't name.
            extra = sorted(set(r.order_lines) - w.selected_pols)
            if extra:
                return self._hold(r, f"invoice also covers order lines not in the input: "
                                     f"{', '.join(extra)}; add them or name the invoice itself")

        problem = self._eligibility(w.invoice_id)
        if problem:
            return self._hold(r, problem)

        wf, pay, appr = st["workflow"], st["payment"], st["approval"]
        if pay != "NOT_PAID":
            return self._hold(r, f"payment status {pay} on an open invoice; "
                                 "continuing a paid-but-open invoice is not validated")
        if wf == WF_APPROVAL:
            return self._hold(r, "waiting for manual approval in Alma")
        if wf == WF_ERP:
            return self._hold(r, "at ERP stage (Waiting to be Sent); not part of the validated flow")
        if wf not in (WF_REVIEW, WF_PAYMENT):
            return self._hold(r, f"unrecognised workflow state {wf!r}")

        voucher, vproblem = self._voucher(inv, w)
        if vproblem and self.cfg.live:
            # Don't start a close we can't finish.
            return self._hold(r, f"cannot pay: {vproblem}")

        if wf == WF_REVIEW:
            if not self.cfg.live:
                r.outcome = WOULD_PROCESS
                r.reason = vproblem or f"would pay {voucher['payment']['voucher_amount']} " \
                                       f"{voucher['payment']['voucher_currency']['value']}"
                return
            st = self._process(w, r, st)
            if st is None:
                return
            if st["workflow"] == WF_APPROVAL:
                return self._hold(r, "processed; now waiting for manual approval in Alma")
            if st["workflow"] == WF_REVIEW:
                alerts = ", ".join(r.after.get("alerts") or []) or "none"
                return self._hold(r, f"processed but Alma kept it In Review; alerts: {alerts}")
            if not (st["workflow"] == WF_PAYMENT and st["approval"] in APPROVED_STATES
                    and st["payment"] == "NOT_PAID"):
                return self._hold(r, f"processed; unexpected state {st}")
        elif appr not in APPROVED_STATES:
            return self._hold(r, f"waiting for payment but approval is {appr}")

        if vproblem:
            return self._hold(r, f"ready to pay; {vproblem}")
        if not self.cfg.live:
            r.outcome, r.reason = WOULD_PAY, (f"would pay {voucher['payment']['voucher_amount']} "
                                              f"{voucher['payment']['voucher_currency']['value']}")
            return
        self._pay(w, r, voucher)

    # ---- checks -------------------------------------------------------------
    def _eligibility(self, invoice_id: str) -> Optional[str]:
        """Only electronic order lines with an available portfolio are validated."""
        lines = self.gw.get_invoice_lines(invoice_id)
        if not lines:
            return "invoice has no lines"
        no_fund = lines_without_fund(lines)
        if no_fund:
            return (f"invoice line(s) {', '.join(no_fund)} have no fund; add a fund in Alma "
                    "(an invoice paid without a fund cannot be corrected afterwards)")
        for line in lines:
            ref = line.get("po_line")
            pol_no = ref.get("value") if isinstance(ref, dict) else ref
            if not pol_no:
                return f"line {line.get('number', '?')} has no order line (charge line); not validated"
            pol = self.gw.get_pol(pol_no)
            ptype, pstatus = _v(pol, "type") or "", _v(pol, "status")
            self.log("line_check", invoice_id=invoice_id, line=line.get("number"), pol=pol_no,
                     type=ptype, pol_status=pstatus)
            if pstatus == "CANCELLED":
                return f"{pol_no} is cancelled"
            if not ptype.startswith("E_"):
                problem = self._physical_check(pol_no, pol, ptype, pstatus)
                if problem:
                    return problem
                continue
            if pstatus == "CLOSED" or not self.cfg.check_portfolios:
                continue
            mms = ((pol.get("resource_metadata") or {}).get("mms_id") or {}).get("value")
            ports = self.gw.get_bib_portfolios(mms) if mms else []
            avail = [p for p in ports if str(_v(p, "availability")).upper() in AVAILABLE
                     or str(((p.get("availability") or {}).get("desc") or "")).upper() == "AVAILABLE"]
            self.log("portfolio_check", pol=pol_no, mms_id=mms, portfolios=len(ports), available=len(avail))
            if not avail:
                return f"{pol_no}: title has no available portfolio"
        return None

    def _physical_check(self, pol_no: str, pol: Dict, ptype: str, pstatus: Optional[str]) -> Optional[str]:
        """Physical lines are paid, never received: receiving stays a person's job in Alma.
        Only one-time orders (`..._OT`); continuous and standing orders must not close."""
        if not self.cfg.include_physical:
            return f"{pol_no} is {ptype or 'unknown type'}; physical orders need --include-physical"
        if not ptype.endswith("_OT"):
            return f"{pol_no} is {ptype or 'unknown type'}; only one-time physical orders are handled"
        if not self.cfg.check_items:
            return None
        mms = ((pol.get("resource_metadata") or {}).get("mms_id") or {}).get("value")
        items = self.gw.get_items_for_pol(mms, pol_no) if mms else []
        received = [i for i in items if (i.get("item_data") or {}).get("arrival_date")]
        self.log("physical_line", pol=pol_no, type=ptype, pol_status=pstatus,
                 items=len(items), received=len(received))
        return None

    def _voucher(self, inv: Dict, w: Work):
        over = w.voucher or {}
        number = over.get("voucher_number")
        if not number and self.cfg.voucher_number_template:
            number = self.cfg.voucher_number_template.format(invoice_number=inv.get("number"),
                                                             invoice_id=inv.get("id"))
        amount = over.get("voucher_amount") or inv.get("total_amount")
        currency = (over.get("voucher_currency") or _v(inv, "currency") or "").upper()
        pdate = over.get("voucher_date") or self.cfg.payment_date
        problem = None
        try:
            amount = f"{Decimal(str(amount)):.2f}"
        except (InvalidOperation, TypeError):
            problem, amount = f"payment amount {amount!r} is not a number", str(amount)
        if not number:
            problem = problem or "no voucher number (give --voucher-number or a voucher_number column)"
        if not currency:
            problem = problem or "no currency on the invoice"
        body = {"payment": {"voucher_date": pdate, "voucher_number": number or "",
                            "voucher_amount": amount, "voucher_currency": {"value": currency}}}
        return body, problem

    def _pol_states(self, pols: List[str]) -> Dict[str, str]:
        out = {}
        for p in pols:
            pol = self.gw.get_pol(p)
            self._pol_types[p] = _v(pol, "type") or ""
            out[p] = _v(pol, "status")
        return out

    def _open_lines(self, states: Dict[str, str]):
        """(e-book lines still open, note). Print order lines stay open by design: they
        close only when items are received, and this job never receives."""
        is_ebook = lambda p: self._pol_types.get(p, "").startswith("E_")
        closed = [p for p, s in states.items() if s == "CLOSED"]
        open_ = [p for p, s in states.items() if s != "CLOSED"]
        printed = [p for p in open_ if not is_ebook(p)]
        ebook = [p for p in open_ if p not in printed]
        notes = []
        if closed:
            kind = "e-book order line" if all(is_ebook(p) for p in closed) else "order line"
            notes.append(f"{kind} closed: {', '.join(closed)}")
        if ebook:
            notes.append(f"e-book order line still open: {', '.join(ebook)}")
        if printed:
            notes.append(f"print order line stays open as expected (not received): {', '.join(printed)}")
        return ebook, "; ".join(notes)

    # ---- writes ---------------------------------------------------------------
    def _settle(self, w: Work, before_wf: Optional[str], want) -> Dict:
        """Read the invoice until `want(state)` or settle time runs out."""
        deadline = self.cfg.settle_seconds
        waited = 0.0
        while True:
            inv = self.gw.get_invoice(w.invoice_id)
            st = state_of(inv)
            if want(st) or waited >= deadline:
                return dict(st, alerts=alerts_of(inv))
            self.cfg.sleep(self.cfg.poll_interval)
            waited += self.cfg.poll_interval

    def _process(self, w: Work, r: Result, st: Dict) -> Optional[Dict]:
        self.log("write_request", invoice=r.invoice_number, method="POST",
                 path=f"/almaws/v1/acq/invoices/{w.invoice_id}", params={"op": "process_invoice"}, body={})
        r.actions.append("process_invoice")
        moved = lambda s: s["workflow"] != WF_REVIEW
        try:
            http, body, secs = self.gw.invoice_service(w.invoice_id, "process_invoice", {})
            self.log("write_response", invoice=r.invoice_number, op="process_invoice", http=http,
                     seconds=secs, reply_state=state_of(body), reply_alerts=alerts_of(body))
        except WriteRejected as ex:
            r.outcome, r.reason = WRITE_REJECTED, f"process_invoice refused: {ex}"
            self.log("write_rejected", invoice=r.invoice_number, op="process_invoice", error=str(ex),
                     http=ex.status, alma_code=ex.alma_code, tracking_id=ex.tracking_id)
            return None
        except WriteOutcomeUnknown as ex:
            self.log("write_unknown", invoice=r.invoice_number, op="process_invoice", error=str(ex))
            after = self._settle(w, st["workflow"], moved)
            r.after = after
            if not moved(after):
                r.outcome, r.reason = WRITE_UNKNOWN, f"process_invoice got no reply ({ex}); invoice unchanged"
                return None
        after = self._settle(w, st["workflow"], moved)
        r.after = after
        r.order_lines_after = self._pol_states(r.order_lines)
        self.log("after_process", invoice=r.invoice_number, state=after, order_lines=r.order_lines_after)
        return {k: after[k] for k in ("status", "workflow", "approval", "payment")}

    def _pay(self, w: Work, r: Result, voucher: Dict):
        # Double-payment guard: re-read immediately before paying.
        fresh = state_of(self.gw.get_invoice(w.invoice_id))
        if fresh["payment"] != "NOT_PAID" or fresh["status"] == "CLOSED":
            return self._hold(r, f"state changed before payment: {fresh}")
        # Fund guard: re-read the lines; never pay an invoice with a line that has no fund.
        no_fund = lines_without_fund(self.gw.get_invoice_lines(w.invoice_id))
        self.log("fund_check", invoice=r.invoice_number, lines_without_fund=no_fund)
        if no_fund:
            return self._hold(r, f"invoice line(s) {', '.join(no_fund)} have no fund; not paid")
        self.log("write_request", invoice=r.invoice_number, method="POST",
                 path=f"/almaws/v1/acq/invoices/{w.invoice_id}", params={"op": "paid"}, body=voucher)
        r.actions.append("paid")
        closed = lambda s: s["status"] == "CLOSED"
        try:
            http, body, secs = self.gw.invoice_service(w.invoice_id, "paid", voucher)
            self.log("write_response", invoice=r.invoice_number, op="paid", http=http, seconds=secs,
                     reply_state=state_of(body))
        except WriteRejected as ex:
            r.outcome, r.reason = WRITE_REJECTED, f"paid refused: {ex}"
            self.log("write_rejected", invoice=r.invoice_number, op="paid", error=str(ex),
                     http=ex.status, alma_code=ex.alma_code, tracking_id=ex.tracking_id)
            return
        except WriteOutcomeUnknown as ex:
            self.log("write_unknown", invoice=r.invoice_number, op="paid", error=str(ex))
            after = self._settle(w, None, lambda s: s["payment"] == "PAID")
            r.after = after
            if after["payment"] != "PAID":
                r.outcome = WRITE_UNKNOWN
                r.reason = f"paid got no reply ({ex}); invoice still NOT_PAID. Do not resend before checking Alma"
                return
        after = self._settle(w, None, closed)
        r.after = after
        r.order_lines_after = self._pol_states(r.order_lines)
        self.log("after_pay", invoice=r.invoice_number, state=after, order_lines=r.order_lines_after)
        if after["status"] != "CLOSED" or after["payment"] != "PAID":
            return self._hold(r, f"paid, but invoice is {after['status']}/{after['payment']}")
        ebook_open, note = self._open_lines(r.order_lines_after)
        r.outcome = CLOSED_POL_OPEN if ebook_open else CLOSED
        r.reason = note
