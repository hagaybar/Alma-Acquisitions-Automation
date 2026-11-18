"""Unit tests for RialtoWorkflowProcessor._pay_invoice (issue #14)."""
from workflows.rialto.workflow import RialtoWorkflowProcessor


def inv(status="ACTIVE", wf="InReview", appr="PENDING", pay="NOT_PAID"):
    return {"invoice_status": {"value": status}, "invoice_workflow_status": {"value": wf},
            "invoice_approval_status": {"value": appr},
            "payment": {"payment_status": {"value": pay}}}


class FakeAcq:
    """Returns invoice states in order; records writes."""
    def __init__(self, *states):
        self.states = list(states)
        self.calls = []

    def get_invoice(self, invoice_id):
        return self.states[0] if len(self.states) == 1 else self.states.pop(0)

    def approve_invoice(self, invoice_id):
        self.calls.append("process")

    def mark_invoice_paid(self, invoice_id):
        self.calls.append("paid")


def run(*states):
    wf = RialtoWorkflowProcessor.__new__(RialtoWorkflowProcessor)
    wf.acq = FakeAcq(*states)
    return wf._pay_invoice("1"), wf.acq.calls


def test_in_review_processes_then_pays():
    res, calls = run(inv(), inv(wf="Ready to be Paid", appr="APPROVED"),
                     inv(status="CLOSED", wf="", appr="APPROVED", pay="PAID"))
    assert calls == ["process", "paid"] and res["status"] == "success"


def test_stays_in_review_after_processing_is_held():
    res, calls = run(inv(), inv())
    assert calls == ["process"] and res["status"] == "held"


def test_ready_and_approved_pays_without_processing():
    res, calls = run(inv(wf="Ready to be Paid", appr="APPROVED"), inv(status="CLOSED", pay="PAID"))
    assert calls == ["paid"] and res["status"] == "success"


def test_already_paid_never_writes():
    res, calls = run(inv(pay="PAID"))
    assert calls == [] and res["status"] == "skipped"


def test_erp_stage_and_manual_approval_are_held():
    for state in (inv(wf="Waiting to be Sent"), inv(wf="InApproval"),
                  inv(wf="Ready to be Paid", appr="PENDING"), inv(status="CLOSED")):
        res, calls = run(state)
        assert calls == [] and res["status"] == "held"
