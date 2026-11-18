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


def test_invoice_found_only_by_search():
    a = SearchableAlma()
    p = pol("POL-1", None, "9911")
    a.add(invoice("I1", "100"), [p])
    rows, _ = run(a, ["POL-1"])
    assert "INVOICE_ONLY_BY_SEARCH" in rows["POL-1"]["issues"]


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
