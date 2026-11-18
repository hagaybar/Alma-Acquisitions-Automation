"""Unit tests for RialtoWorkflowProcessor._find_invoice_for_pol (issue #12)."""
from workflows.rialto.workflow import RialtoWorkflowProcessor


class FakeAcq:
    def __init__(self, invoices, lines):
        self.invoices = invoices
        self.lines = lines
        self.queries = []

    def search_invoices(self, query, limit=10, offset=0):
        self.queries.append(query)
        return {"invoice": self.invoices, "total_record_count": len(self.invoices)}

    def get_invoice_lines(self, invoice_id):
        return self.lines[invoice_id]


def make(invoices, lines):
    wf = RialtoWorkflowProcessor.__new__(RialtoWorkflowProcessor)
    wf.acq = FakeAcq(invoices, lines)
    return wf


def test_searches_by_pol_number():
    wf = make([{"id": "1"}], {"1": [{"po_line": "POL-1"}]})
    assert wf._find_invoice_for_pol("POL-1") == "1"
    assert wf.acq.queries == ["pol_number~POL-1"]


def test_no_results_returns_none():
    assert make([], {})._find_invoice_for_pol("POL-1") is None


def test_lines_must_confirm_match():
    wf = make([{"id": "1"}], {"1": [{"po_line": "POL-10"}]})
    assert wf._find_invoice_for_pol("POL-1") is None


def test_prefers_open_invoice():
    invoices = [
        {"id": "closed", "invoice_status": {"value": "CLOSED"}},
        {"id": "open", "invoice_status": {"value": "ACTIVE"}},
    ]
    lines = {"closed": [{"po_line": "POL-1"}], "open": [{"po_line": "POL-1"}]}
    assert make(invoices, lines)._find_invoice_for_pol("POL-1") == "open"


def test_only_closed_match_still_returned():
    invoices = [{"id": "c", "invoice_status": {"value": "CLOSED"}}]
    assert make(invoices, {"c": [{"po_line": "POL-1"}]})._find_invoice_for_pol("POL-1") == "c"
