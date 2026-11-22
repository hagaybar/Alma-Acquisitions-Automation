"""Offline tests for invoice_closer. A fake gateway models the Alma behaviour
observed in Sandbox (Nov 2026); no network access."""
import copy
import json
from pathlib import Path

import pytest

from invoice_closer import engine as E
from invoice_closer.gateway import WriteOutcomeUnknown, WriteRejected
from invoice_closer.inputs import Target, detect_kind, targets_from_file
from invoice_closer.redact import redact


def invoice(iid, number, wf="InReview", appr="PENDING", pay="NOT_PAID", status="ACTIVE",
            vendor="RIALTO", owner="AC1", total=29.99, alerts=(), invoice_date="2026-09-15Z"):
    return {"id": iid, "invoice_date": invoice_date, "number": number, "invoice_status": {"value": status},
            "invoice_workflow_status": {"value": wf} if wf else {},
            "invoice_approval_status": {"value": appr}, "payment": {"payment_status": {"value": pay}},
            "vendor": {"value": vendor}, "owner": {"value": owner}, "total_amount": total,
            "currency": {"value": "USD"}, "alert": [{"value": a} for a in alerts]}


def pol(number, inv_no, mms, ptype="E_BOOK_OT", status="WAITING_FOR_INVOICE", vendor="RIALTO"):
    return {"number": number, "invoice_reference": inv_no, "type": {"value": ptype},
            "status": {"value": status}, "vendor": {"value": vendor},
            "resource_metadata": {"mms_id": {"value": mms}}}


class FakeAlma:
    """Models: process moves e-book invoices to payment and closes active e-book lines;
    `stuck` invoices stay In Review; paid closes the invoice."""

    def __init__(self):
        self.invoices, self.lines, self.pols, self.portfolios = {}, {}, {}, {}
        self.writes, self.stuck, self.fail_next = [], set(), None

    def add(self, inv, pols, available=True, fund=True):
        self.invoices[inv["id"]] = inv
        fd = [{"percent": 100.0, "fund_code": {"value": "AAC_FUND"}}] if fund else []
        self.lines[inv["id"]] = [{"number": str(n + 1), "po_line": p["number"], "fund_distribution": list(fd)}
                                 for n, p in enumerate(pols)]
        for p in pols:
            self.pols[p["number"]] = p
            mms = p["resource_metadata"]["mms_id"]["value"]
            self.portfolios[mms] = [{"availability": {"value": "11" if available else "10",
                                                      "desc": "Available" if available else "Not Available"}}]

    # reads
    def get_invoice(self, iid): return copy.deepcopy(self.invoices[iid])
    def find_invoices_by_number(self, n): return [copy.deepcopy(i) for i in self.invoices.values() if i["number"] == n]
    def get_invoice_lines(self, iid): return copy.deepcopy(self.lines[iid])
    def get_pol(self, p): return copy.deepcopy(self.pols[p])
    def find_pols_by_mms(self, mms):
        return [copy.deepcopy(p) for p in self.pols.values() if p["resource_metadata"]["mms_id"]["value"] == mms]
    def get_bib_portfolios(self, mms): return copy.deepcopy(self.portfolios.get(mms, []))
    def get_items_for_pol(self, mms, pol_no):
        return [{"item_data": {"po_line": pol_no, "arrival_date": "2026-11-01Z"}}]

    # writes
    def invoice_service(self, iid, op, body):
        self.writes.append((iid, op, body))
        inv = self.invoices[iid]
        fail, self.fail_next = self.fail_next, None
        if fail == "reject":
            raise WriteRejected(400, "40166411", "bad request")
        if fail != "lost_not_applied":
            if op == "process_invoice" and iid not in self.stuck:
                inv["invoice_workflow_status"] = {"value": "Ready to be Paid"}
                inv["invoice_approval_status"] = {"value": "APPROVED"}
                for line in self.lines[iid]:
                    p = self.pols[line["po_line"]]
                    if p["type"]["value"].startswith("E_"):
                        p["status"] = {"value": "CLOSED"}
            if op == "paid":
                inv["invoice_status"] = {"value": "CLOSED"}
                inv["invoice_workflow_status"] = {}
                inv["payment"]["payment_status"] = {"value": "PAID"}
        if fail in ("lost_applied", "lost_not_applied"):
            raise WriteOutcomeUnknown("ReadTimeout after 180s")
        return 200, copy.deepcopy(inv), 0.5


def closer(alma, live=True, template="TEST-{invoice_number}", physical=False, date_before=None):
    events = []
    cfg = E.Config(live=live, include_physical=physical, invoice_date_before=date_before, vendor="RIALTO", voucher_number_template=template, payment_date="2026-11-13",
                   settle_seconds=10, poll_interval=5, sleep=lambda s: None)
    return E.Closer(alma, cfg, lambda ev, **d: events.append((ev, d))), events


def run(alma, targets, **kw):
    c, events = closer(alma, **kw)
    work, results = c.resolve(targets)
    results += [c.run_one(w) for w in work]
    return results, events


@pytest.fixture
def alma():
    a = FakeAlma()
    a.add(invoice("I1", "100"), [pol("POL-1", "100", "9911")])
    return a


def test_ebook_full_close(alma):
    (r,), _ = run(alma, [Target("mms", "9911", "t")])
    assert r.outcome == E.CLOSED
    assert [w[1] for w in alma.writes] == ["process_invoice", "paid"]
    assert alma.writes[1][2] == {"payment": {"voucher_date": "2026-11-13", "voucher_number": "TEST-100",
                                             "voucher_amount": "29.99", "voucher_currency": {"value": "USD"}}}
    assert r.order_lines_after == {"POL-1": "CLOSED"}
    assert r.reason == "e-book order line closed: POL-1"


def test_dry_run_sends_nothing(alma):
    (r,), _ = run(alma, [Target("mms", "9911", "t")], live=False)
    assert r.outcome == E.WOULD_PROCESS and alma.writes == []


def test_rerun_after_close_is_noop(alma):
    run(alma, [Target("mms", "9911", "t")])
    (r,), _ = run(alma, [Target("mms", "9911", "t")])
    assert r.outcome == E.ALREADY_CLOSED and len(alma.writes) == 2


def test_waiting_for_payment_only_pays(alma):
    alma.invoices["I1"].update(invoice("I1", "100", wf="Ready to be Paid", appr="APPROVED"))
    alma.pols["POL-1"]["status"] = {"value": "CLOSED"}
    (r,), _ = run(alma, [Target("pol", "POL-1", "t")])
    assert r.outcome == E.CLOSED and [w[1] for w in alma.writes] == ["paid"]


def test_stays_in_review_is_held_with_alerts(alma):
    alma.stuck.add("I1")
    alma.invoices["I1"]["alert"] = [{"value": "DIFF_PRICE_THAN_POLINE"}]
    (r,), _ = run(alma, [Target("mms", "9911", "t")])
    assert r.outcome == E.HELD and "DIFF_PRICE_THAN_POLINE" in r.reason
    assert [w[1] for w in alma.writes] == ["process_invoice"]


def test_physical_is_held_without_writes():
    a = FakeAlma()
    a.add(invoice("I2", "200"), [pol("POL-2", "200", "9922", ptype="PRINTED_BOOK_OT", status="SENT")])
    (r,), _ = run(a, [Target("invoice_number", "200", "t")])
    assert r.outcome == E.HELD and "PRINTED_BOOK_OT" in r.reason and a.writes == []


def test_no_available_portfolio_is_held():
    a = FakeAlma()
    a.add(invoice("I3", "300"), [pol("POL-3", "300", "9933")], available=False)
    (r,), _ = run(a, [Target("mms", "9933", "t")])
    assert r.outcome == E.HELD and "portfolio" in r.reason and a.writes == []


def test_paid_but_open_is_never_paid_again(alma):
    alma.invoices["I1"]["payment"]["payment_status"] = {"value": "PAID"}
    (r,), _ = run(alma, [Target("mms", "9911", "t")])
    assert r.outcome == E.HELD and alma.writes == []


def test_manual_approval_held(alma):
    alma.invoices["I1"]["invoice_workflow_status"] = {"value": "InApproval"}
    (r,), _ = run(alma, [Target("mms", "9911", "t")])
    assert r.outcome == E.HELD and "approval" in r.reason and alma.writes == []


def test_missing_voucher_number_blocks_before_any_write(alma):
    (r,), _ = run(alma, [Target("mms", "9911", "t")], template=None)
    assert r.outcome == E.HELD and "voucher" in r.reason and alma.writes == []


def test_lost_pay_reply_but_applied_is_reconciled_not_resent(alma):
    alma.invoices["I1"].update(invoice("I1", "100", wf="Ready to be Paid", appr="APPROVED"))
    alma.fail_next = "lost_applied"
    (r,), _ = run(alma, [Target("invoice_id", "I1", "t")])
    assert r.outcome == E.CLOSED_POL_OPEN or r.outcome == E.CLOSED
    assert [w[1] for w in alma.writes] == ["paid"]


def test_lost_pay_reply_not_applied_is_not_resent(alma):
    alma.invoices["I1"].update(invoice("I1", "100", wf="Ready to be Paid", appr="APPROVED"))
    alma.fail_next = "lost_not_applied"
    (r,), _ = run(alma, [Target("invoice_id", "I1", "t")])
    assert r.outcome == E.WRITE_UNKNOWN and len(alma.writes) == 1


def test_rejected_write(alma):
    alma.fail_next = "reject"
    (r,), _ = run(alma, [Target("mms", "9911", "t")])
    assert r.outcome == E.WRITE_REJECTED and "40166411" in r.reason


def test_two_titles_one_invoice_processed_once():
    a = FakeAlma()
    a.add(invoice("I4", "400"), [pol("POL-4", "400", "9944"), pol("POL-5", "400", "9955")])
    results, _ = run(a, [Target("mms", "9944", "a"), Target("mms", "9955", "b")])
    assert len(results) == 1 and results[0].outcome == E.CLOSED
    assert [w[1] for w in a.writes] == ["process_invoice", "paid"]


def test_other_vendor_out_of_scope():
    a = FakeAlma()
    a.add(invoice("I5", "500", vendor="OTHER"), [pol("POL-6", "500", "9966", vendor="OTHER")])
    (r,), _ = run(a, [Target("invoice_id", "I5", "t")])
    assert r.outcome == E.HELD and "vendor" in r.reason and a.writes == []


def test_unresolved_target_reported(alma):
    results, _ = run(alma, [Target("mms", "9999999999", "t")])
    assert results[0].outcome == E.HELD and "no order line" in results[0].reason


# ---- inputs ---------------------------------------------------------------
def test_detect_kind():
    assert detect_kind("POL-4913") == "pol"
    assert detect_kind("9933722419004146") == "mms"
    assert detect_kind("32141615270004146") == "invoice_id"
    assert detect_kind("2412476") == "invoice_number"


def test_csv_with_header_and_voucher(tmp_path):
    f = tmp_path / "x.csv"
    f.write_text("Invoice Number,voucher_number\n2412476,V-1\n\n2412477,\n", encoding="utf-8")
    t = targets_from_file(f)
    assert [(x.kind, x.value, x.voucher) for x in t] == [
        ("invoice_number", "2412476", {"voucher_number": "V-1"}), ("invoice_number", "2412477", {})]


def test_tsv_without_header(tmp_path):
    f = tmp_path / "x.tsv"
    f.write_text("POL-4913\textra\n9933722419004146\n", encoding="utf-8")
    assert [(x.kind, x.value) for x in targets_from_file(f)] == [("pol", "POL-4913"), ("mms", "9933722419004146")]


def test_xlsx_numeric_ids(tmp_path):
    from openpyxl import Workbook
    wb = Workbook(); ws = wb.active
    ws.append(["MMS ID"]); ws.append([9933722419004146]); ws.append([None])
    f = tmp_path / "x.xlsx"; wb.save(f)
    assert [(x.kind, x.value) for x in targets_from_file(f)] == [("mms", "9933722419004146")]


# ---- redaction ------------------------------------------------------------
def test_redaction():
    rec = {"url": "https://x/almaws?apikey=l7xxabcdef0123456789abcdef&q=1", "note": "call Dana",
           "who": "dana@example.org", "authorization": "apikey l7xx", "invoice": "100"}
    out = json.dumps(redact(rec))
    assert "l7xxabcdef" not in out and "Dana" not in out and "example.org" not in out and '"100"' in out


# ---- selection by order line (15 Nov 2026) ---------------------------------
class FakeSets:
    def __init__(self, content, ids, stype="ITEMIZED", count=None):
        self.content, self.ids, self.stype = content, ids, stype
        self.count = len(ids) if count is None else count
    def get_set(self, sid):
        return {"content": {"value": self.content}, "type": {"value": self.stype},
                "number_of_members": {"value": self.count}}
    def get_set_member_ids(self, sid, expected=None): return list(self.ids)


def test_logical_set_with_correct_members_accepted():
    from invoice_closer.inputs import targets_from_set
    ts = targets_from_set(FakeSets("PO_LINE", ["POL-1"], stype="LOGICAL"), "S1")
    assert [t.value for t in ts] == ["POL-1"]


def test_member_count_mismatch_refused():
    from invoice_closer.inputs import targets_from_set
    with pytest.raises(ValueError, match="says it has 5 members"):
        targets_from_set(FakeSets("PO_LINE", ["POL-1"], count=5), "S1")


def test_pol_set_gives_pol_targets():
    from invoice_closer.inputs import targets_from_set
    ts = targets_from_set(FakeSets("PO_LINE", ["POL-1", "POL-2"]), "S1")
    assert [(t.kind, t.value) for t in ts] == [("pol", "POL-1"), ("pol", "POL-2")]


@pytest.mark.parametrize("content", ["BIB_MMS", "ITEM", ""])
def test_non_pol_sets_refused(content):
    from invoice_closer.inputs import targets_from_set
    with pytest.raises(ValueError, match="PO_LINE"):
        targets_from_set(FakeSets(content, ["9911"]), "S1")


def test_invoice_with_unselected_order_line_is_held():
    a = FakeAlma()
    a.add(invoice("I6", "600"), [pol("POL-61", "600", "9961"), pol("POL-62", "600", "9962")])
    (r,), _ = run(a, [Target("pol", "POL-61", "set member 1")])
    assert r.outcome == E.HELD and "POL-62" in r.reason and a.writes == []


def test_invoice_named_directly_covers_all_its_lines():
    a = FakeAlma()
    a.add(invoice("I6", "600"), [pol("POL-61", "600", "9961"), pol("POL-62", "600", "9962")])
    (r,), _ = run(a, [Target("invoice_number", "600", "row 1")])
    assert r.outcome == E.CLOSED


def test_title_with_two_order_lines_is_not_expanded():
    a = FakeAlma()
    a.add(invoice("I7", "700"), [pol("POL-71", "700", "9977")])
    a.add(invoice("I8", "800"), [pol("POL-81", "800", "9977")])
    (r,), _ = run(a, [Target("mms", "9977", "row 1")])
    assert r.outcome == E.HELD and "2 order lines" in r.reason and a.writes == []


# ---- physical one-time orders: pay only, never receive (15 Nov 2026) --------
def test_physical_paid_with_flag_order_line_left_open():
    a = FakeAlma()
    a.add(invoice("I9", "900"), [pol("POL-9", "900", "9999", ptype="PRINTED_BOOK_OT", status="SENT")])
    (r,), events = run(a, [Target("pol", "POL-9", "t")], physical=True)
    assert [w[1] for w in a.writes] == ["process_invoice", "paid"]
    # A print order line stays open by design (never received): that is a clean close.
    assert r.outcome == E.CLOSED and "POL-9" in r.reason and "as expected" in r.reason
    assert "closed:" not in r.reason
    assert any(ev == "physical_line" and d["received"] == 1 for ev, d in events)


def test_physical_continuous_order_held_even_with_flag():
    a = FakeAlma()
    a.add(invoice("I10", "1000"), [pol("POL-10", "1000", "9910", ptype="PRINTED_JOURNAL_CO", status="SENT")])
    (r,), _ = run(a, [Target("pol", "POL-10", "t")], physical=True)
    assert r.outcome == E.HELD and "one-time" in r.reason and a.writes == []


def test_date_cutoff_closes_earlier_invoice(alma):
    (r,), _ = run(alma, [Target("invoice_id", "I1", "t")], date_before="2026-10-01")
    assert r.outcome == E.CLOSED


@pytest.mark.parametrize("inv_date", ["2026-10-01Z", "2026-11-02Z", None])
def test_date_cutoff_holds_on_or_after_or_undated(inv_date):
    a = FakeAlma()
    a.add(invoice("I1", "100", invoice_date=inv_date), [pol("POL-1", "100", "9911")])
    (r,), _ = run(a, [Target("invoice_id", "I1", "t")], date_before="2026-10-01")
    assert r.outcome == E.HELD and "date" in r.reason and a.writes == []


def test_line_without_fund_is_held_before_any_write():
    a = FakeAlma()
    a.add(invoice("I1", "100"), [pol("POL-1", "100", "9911")], fund=False)
    (r,), _ = run(a, [Target("invoice_id", "I1", "t")])
    assert r.outcome == E.HELD and "no fund" in r.reason and a.writes == []


def test_fund_removed_after_processing_blocks_payment():
    a = FakeAlma()
    a.add(invoice("I1", "100"), [pol("POL-1", "100", "9911")])
    real = a.invoice_service
    def process_then_drop_fund(iid, op, body):
        out = real(iid, op, body)
        if op == "process_invoice":
            a.lines[iid][0]["fund_distribution"] = []
        return out
    a.invoice_service = process_then_drop_fund
    (r,), _ = run(a, [Target("invoice_id", "I1", "t")])
    assert [w[1] for w in a.writes] == ["process_invoice"] and r.outcome == E.HELD and "no fund" in r.reason


def test_analytics_export_prefers_invoice_number_and_reads_utf16(tmp_path):
    f = tmp_path / "report.tsv"
    f.write_text("PO Line Reference\tInvoice Number\tFund Code\nPOL-1\t100\tAAC_FUND\nPOL-2\t200\tAAC_FUND\n",
                 encoding="utf-16")
    ts = targets_from_file(f)
    assert [(t.kind, t.value) for t in ts] == [("invoice_number", "100"), ("invoice_number", "200")]


def test_analytics_export_pol_only(tmp_path):
    f = tmp_path / "report.csv"
    f.write_text("PO Line Reference,Title\nPOL-7,x\n", encoding="utf-8")
    assert [(t.kind, t.value) for t in targets_from_file(f)] == [("pol", "POL-7")]
