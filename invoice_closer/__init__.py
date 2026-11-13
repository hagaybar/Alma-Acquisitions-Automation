"""Close Alma invoices and their order lines by following the validated flow.

Flow (validated in Alma Sandbox, Nov 2026, electronic one-time orders):

    In Review / NOT_PAID --op=process_invoice--> Waiting for Payment / APPROVED
        (the order line closes here when the e-resource is already active)
    Waiting for Payment / NOT_PAID --op=paid + voucher--> CLOSED / PAID

Everything outside that flow is held and reported, never forced.
See docs/INVOICE_CLOSER.md.
"""

__version__ = "0.1.0"
