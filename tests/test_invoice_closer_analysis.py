"""Offline tests for the read-only pre-analysis."""
import pytest

from invoice_closer import engine as E
from invoice_closer.analysis import ReadOnlyGateway, analyze, summary
from invoice_closer.inputs import Target
from tests.test_invoice_closer import FakeAlma, invoice, pol


class SearchableAlma(FakeAlma):
    def _get(self, path, params=None):
        q = (params or {}).get("q", "")
        if q.startswith("pol_number~"):
            p = q.split("~", 1)[1]
            return {"invoice": [i for iid, i in self.invoices.items()
                                if any(l["po_line"] == p for l in self.lines[iid])]}
        return {}


def cfg(**kw):
    base = dict(live=True, vendor="RIALTO", owner="AC1", voucher_number_template="T-{invoice_number}",
                include_physical=True, invoice_date_before="2026-10-01", sleep=lambda s: None)
    base.update(kw)
    return E.Config(**base)


def run(alma, pols, **kw):
    rows, results = analyze(alma, [Target("pol", p, "t") for p in pols], cfg(**kw), lambda *a, **k: None)
    return {r["pol"]: r for r in rows}, results


def test_never_writes_even_with_live_config():
    a = SearchableAlma()
    a.add(invoice("I1", "100"), [pol("POL-1", "100", "9911")])
    rows, _ = run(a, ["POL-1"])
    assert a.writes == [] and rows["POL-1"]["predicted_outcome"] == E.WOULD_PROCESS


def test_flags_lines_outside_input_and_date_and_physical():
    a = SearchableAlma()
    a.add(invoice("I1", "100", invoice_date="2026-10-02Z"),
          [pol("POL-1", "100", "9911", ptype="PRINTED_BOOK_OT", status="SENT"), pol("POL-2", "100", "9922")])
    rows, _ = run(a, ["POL-1"])
    issues = rows["POL-1"]["issues"].split()
    assert {"OTHER_LINES_NOT_IN_SET", "DATE_ON_OR_AFTER_CUTOFF", "PHYSICAL"} <= set(issues)
    assert rows["POL-1"]["lines_not_in_input"] == "POL-2"
    assert rows["POL-1"]["predicted_outcome"] == E.HELD


def test_invoice_found_through_lines_without_invoice_reference():
    a = SearchableAlma()
    a.add(invoice("I1", "100"), [pol("POL-1", None, "9911")])
    rows, _ = run(a, ["POL-1"])
    assert rows["POL-1"]["predicted_outcome"] == E.WOULD_PROCESS
    assert "NO_INVOICE" not in rows["POL-1"]["issues"]


def test_deleted_set_member_flagged():
    a = SearchableAlma()
    rows, results = analyze(a, [Target("not_pol", "PO line 123 was deleted", "t")], cfg(),
                            lambda *a, **k: None)
    assert rows[0]["issues"] == "NOT_AN_ORDER_LINE" and results[0].outcome == E.HELD


def test_no_invoice():
    a = SearchableAlma()
    a.pols["POL-9"] = pol("POL-9", None, "9999")
    rows, results = run(a, ["POL-9"])
    assert "NO_INVOICE" in rows["POL-9"]["issues"] and rows["POL-9"]["predicted_outcome"] == E.HELD
    assert "Possible issues" in summary(list(rows.values()), results, env="SANDBOX", source="t",
                                        cfg=cfg(), out_dir=__import__("pathlib").Path("."))


def test_read_only_gateway_refuses_writes():
    with pytest.raises(RuntimeError):
        ReadOnlyGateway(SearchableAlma()).invoice_service("I1", "paid", {})


class PagedAlma(SearchableAlma):
    """List endpoints for BulkGateway: invoices with lines (view=full), brief order lines."""
    def _get(self, path, params=None):
        params = params or {}
        if path.endswith("/acq/invoices") and params.get("view") == "full":
            items = [dict(i, invoice_lines={"invoice_line": self.lines[iid]},
                          number_of_lines={"value": len(self.lines[iid])})
                     for iid, i in self.invoices.items()]
            key = "invoice"
        elif path.endswith("/acq/po-lines"):
            items = [{k: v for k, v in p.items() if k != "invoice_reference"} for p in self.pols.values()]
            key = "po_line"
        else:
            return super()._get(path, params)
        off = params.get("offset", 0)
        return {key: items[off:off + 100], "total_record_count": len(items)}


def test_bulk_gateway_matches_record_by_record():
    from invoice_closer.bulk import BulkGateway
    a = PagedAlma()
    a.add(invoice("I1", "100"), [pol("POL-1", "100", "9911")])
    a.add(invoice("I2", "200", invoice_date="2026-10-05Z"),
          [pol("POL-2", "200", "9922", ptype="PRINTED_BOOK_OT", status="SENT")])
    a.add(invoice("I3", "300", vendor="OTHER"), [pol("POL-3", "300", "9933", vendor="OTHER")])
    bulk = BulkGateway(a, "RIALTO").load()
    assert set(bulk.invoices) == {"I1", "I2"} and set(bulk.pols) == {"POL-1", "POL-2"}
    plain, _ = run(a, ["POL-1", "POL-2"])
    fast, _ = run(bulk, ["POL-1", "POL-2"])
    for p in ("POL-1", "POL-2"):
        assert plain[p]["predicted_outcome"] == fast[p]["predicted_outcome"]
        assert plain[p]["issues"] == fast[p]["issues"]
    assert a.writes == []
