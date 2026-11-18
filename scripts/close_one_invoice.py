#!/usr/bin/env python
"""Minimal test: close ONE e-book order line's invoice in Alma SANDBOX, step by step.

Dry run by default (reads only). --live sends at most two writes, each once:
process_invoice, then paid. Prints every step and stops at the first problem.

Every run writes output/invoice_closer/single/<time>_<pol>_<dry|live>/:
  log.jsonl     every read (full record), every write (request + full reply), each
                decision, and any error with its traceback. Redacted: credentials,
                e-mail addresses, free-text notes. Written line by line, so a crash
                keeps everything up to that point.
  snapshot_before.json / snapshot_after.json
                order line, invoice and invoice lines in full, for comparing.

  poetry run python scripts/close_one_invoice.py --pol POL-4912 --invoice-number 2412851
  poetry run python scripts/close_one_invoice.py --pol POL-4912 --invoice-number 2412851 --live
"""
import argparse
import json
import logging
import sys
import time
import traceback
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from invoice_closer.gateway import Gateway, WriteOutcomeUnknown, WriteRejected  # noqa: E402
from invoice_closer.redact import redact  # noqa: E402
from invoice_closer.reporting import RunLog, run_context  # noqa: E402

VENDOR, OWNER, CUTOFF = "RIALTO", "AC1", "2026-10-01"
SETTLE_SECONDS, POLL = 30, 5


class Stop(Exception):
    """A check failed: stop without writing anything further."""


def v(obj, key):
    val = (obj or {}).get(key)
    return val.get("value") if isinstance(val, dict) else val


def state(inv):
    return {"status": v(inv, "invoice_status"), "workflow": v(inv, "invoice_workflow_status"),
            "approval": v(inv, "invoice_approval_status"), "payment": v(inv.get("payment"), "payment_status")}


def alerts(inv):
    raw = inv.get("alert") or []
    return [a.get("value") if isinstance(a, dict) else str(a) for a in (raw if isinstance(raw, list) else [raw])]


class Run:
    def __init__(self, gw, log, run_dir):
        self.gw, self.log, self.dir = gw, log, run_dir

    def say(self, msg, **data):
        print(msg)
        self.log("step", msg=msg, **data)

    # every read is logged with the full (redacted) record
    def read(self, what, fn, *args):
        t0 = time.monotonic()
        try:
            rec = fn(*args)
        except Exception as ex:
            self.log("read_error", what=what, args=args, error=f"{type(ex).__name__}: {ex}"[:2000],
                     tracking_id=getattr(ex, "tracking_id", None), traceback=traceback.format_exc())
            raise
        self.log("read", what=what, args=args, seconds=round(time.monotonic() - t0, 2), record=rec)
        return rec

    def snapshot(self, name, pol_no, iid):
        snap = {"taken": datetime.now().isoformat(timespec="seconds"),
                "order_line": self.read("order line", self.gw.get_pol, pol_no)}
        if iid:
            snap["invoice"] = self.read("invoice", self.gw.get_invoice, iid)
            snap["invoice_lines"] = self.read("invoice lines", self.gw.get_invoice_lines, iid)
        (self.dir / f"snapshot_{name}.json").write_text(
            json.dumps(redact(snap), ensure_ascii=False, indent=2), encoding="utf-8")
        return snap

    # a write is sent once; its outcome is always established by reading back
    def write(self, iid, op, body):
        self.log("write_request", method="POST", path=f"/almaws/v1/acq/invoices/{iid}",
                 params={"op": op}, body=body)
        try:
            http, reply, secs = self.gw.invoice_service(iid, op, body)
        except WriteRejected as ex:
            self.log("write_rejected", op=op, http=ex.status, alma_code=ex.alma_code,
                     tracking_id=ex.tracking_id, message=ex.message)
            raise Stop(f"Alma refused {op}: {ex} (nothing changed)")
        except WriteOutcomeUnknown as ex:
            self.log("write_unknown", op=op, error=str(ex), traceback=traceback.format_exc())
            after = state(self.read("invoice after unknown write", self.gw.get_invoice, iid))
            self.log("write_unknown_readback", op=op, state=after)
            raise Stop(f"no reply to {op} ({ex}); invoice now {after}. Check Alma before any re-run; "
                       "do not resend")
        self.log("write_response", op=op, http=http, seconds=secs, reply=reply)
        print(f"   HTTP {http} in {secs}s")
        return reply

    def settle(self, iid, done):
        waited = 0
        while True:
            inv = self.read("invoice (settle)", self.gw.get_invoice, iid)
            st = state(inv)
            self.log("settle", waited=waited, state=st, alerts=alerts(inv))
            if done(st) or waited >= SETTLE_SECONDS:
                return inv, st
            time.sleep(POLL)
            waited += POLL


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--pol", required=True)
    p.add_argument("--invoice-number", required=True, help="the invoice known to hold this order line")
    p.add_argument("--live", action="store_true")
    a = p.parse_args()
    logging.disable(logging.INFO)

    run_dir = ROOT / "output" / "invoice_closer" / "single" / \
        f"{datetime.now():%Y%m%d_%H%M%S}_{a.pol}_{'live' if a.live else 'dry'}"
    log = RunLog(run_dir)
    log("run_context", **run_context(sys.argv))
    log("run_start", env="SANDBOX", live=a.live, pol=a.pol, invoice_number=a.invoice_number,
        vendor=VENDOR, owner=OWNER, cutoff=CUTOFF)
    print(f"Log: {run_dir}")
    r = Run(Gateway("SANDBOX"), log, run_dir)   # Sandbox only, by design
    outcome, code = "error", 2
    try:
        outcome = steps(r, a)
        code = 0
    except Stop as ex:
        outcome = f"stopped: {ex}"
        print(f"STOP: {ex}")
        code = 1
    except KeyboardInterrupt:
        outcome = "interrupted by the user"
        log("interrupted", traceback=traceback.format_exc())
        print("Interrupted. Check the log before re-running.")
        code = 130
    except Exception as ex:
        outcome = f"error: {type(ex).__name__}: {ex}"[:2000]
        log("error", error=outcome, traceback=traceback.format_exc())
        print(f"ERROR: {outcome}\nSee {run_dir / 'log.jsonl'}")
    finally:
        log("run_end", outcome=outcome, exit_code=code)
        log.close()
    return code


def steps(r, a) -> str:
    r.say(f"1. Read order line {a.pol}")
    pol = r.read("order line", r.gw.get_pol, a.pol)
    ptype, pstatus = v(pol, "type") or "", v(pol, "status")
    r.say(f"   type={ptype} status={pstatus} vendor={v(pol, 'vendor')} owner={v(pol, 'owner')} "
          f"price={(pol.get('price') or {}).get('sum')}")
    if not (ptype.startswith("E_") and ptype.endswith("_OT")):
        raise Stop("not a one-time electronic order")
    if pstatus in ("CLOSED", "CANCELLED"):
        raise Stop(f"order line is {pstatus}")
    if v(pol, "vendor") != VENDOR or v(pol, "owner") != OWNER:
        raise Stop("vendor or library outside scope")

    r.say(f"2. Read invoice {a.invoice_number} (known from the input)")
    invs = [i for i in r.read("invoice search by number", r.gw.find_invoices_by_number, a.invoice_number)
            if v(i, "vendor") == VENDOR]
    if len(invs) != 1:
        raise Stop(f"{len(invs)} {VENDOR} invoices have number {a.invoice_number}")
    iid = str(invs[0]["id"])
    r.say(f"   invoice ID {iid}", invoice_id=iid)

    r.say("3. Check the invoice")
    before = r.snapshot("before", a.pol, iid)
    inv, lines = before["invoice"], before["invoice_lines"]
    st = state(inv)
    line_pols = [v(l, "po_line") for l in lines]
    idate = (inv.get("invoice_date") or "")[:10]
    r.say(f"   number={inv.get('number')} vendor={v(inv, 'vendor')} owner={v(inv, 'owner')} date={idate}")
    r.say(f"   state={st} lines={line_pols} total={inv.get('total_amount')} {v(inv, 'currency')}")
    r.say(f"   alerts={alerts(inv)}")
    for l in lines:
        r.say(f"   line {l.get('number')}: po_line={v(l, 'po_line')} status={v(l, 'status')} "
              f"price={l.get('price')} total={l.get('total_price')} fully_invoiced={l.get('fully_invoiced')}")
    if v(inv, "vendor") != VENDOR or v(inv, "owner") != OWNER:
        raise Stop("invoice vendor or library outside scope")
    if not idate or idate >= CUTOFF:
        raise Stop(f"invoice date {idate or 'missing'} not before {CUTOFF}")
    if line_pols != [a.pol]:
        raise Stop(f"invoice lines are {line_pols}, expected only {a.pol}")
    if st["status"] != "ACTIVE" or st["payment"] != "NOT_PAID":
        raise Stop("invoice is not open and unpaid")
    if st["workflow"] not in ("InReview", "Ready to be Paid"):
        raise Stop(f"workflow {st['workflow']} is not handled")

    voucher = {"payment": {"voucher_date": date.today().isoformat(),
                           "voucher_number": f"AUTO-PAY-{inv.get('number')}",
                           "voucher_amount": str(inv.get("total_amount")),
                           "voucher_currency": {"value": v(inv, "currency")}}}
    if not a.live:
        r.say("DRY RUN: all checks passed. With --live it would:")
        if st["workflow"] == "InReview":
            r.say(f"   4. POST /acq/invoices/{iid}?op=process_invoice  body {{}}")
        r.say(f"   5. POST /acq/invoices/{iid}?op=paid  body {voucher}")
        return "dry run: checks passed"

    try:
        if st["workflow"] == "InReview":
            r.say("4. Process the invoice (op=process_invoice)")
            r.write(iid, "process_invoice", {})
            inv, st = r.settle(iid, lambda s: s["workflow"] != "InReview")
            r.say(f"   now {st}; alerts={alerts(inv)}")
            if not (st["workflow"] == "Ready to be Paid" and st["approval"] in ("APPROVED", "NOT_REQUIRED")):
                raise Stop(f"not ready to pay after processing ({st}); nothing paid")

        fresh = state(r.read("invoice (before pay)", r.gw.get_invoice, iid))   # double-payment guard
        if fresh["payment"] != "NOT_PAID" or fresh["status"] == "CLOSED":
            raise Stop(f"state changed before paying: {fresh}")
        r.say(f"5. Pay (op=paid) {voucher['payment']}")
        r.write(iid, "paid", voucher)
        inv, st = r.settle(iid, lambda s: s["status"] == "CLOSED")
    finally:
        # Whatever happened after the first write, record the end state. A failure here
        # is logged but must not hide the original error.
        try:
            after = r.snapshot("after", a.pol, iid)
            r.log("end_state", invoice=state(after["invoice"]), alerts=alerts(after["invoice"]),
                  order_line_status=v(after["order_line"], "status"))
        except Exception:
            r.log("end_state_failed", traceback=traceback.format_exc())

    r.say("6. Verify")
    r.say(f"   invoice {state(after['invoice'])}")
    r.say(f"   order line status {v(after['order_line'], 'status')}")
    return f"invoice {state(after['invoice'])}, order line {v(after['order_line'], 'status')}"


if __name__ == "__main__":
    sys.exit(main())
