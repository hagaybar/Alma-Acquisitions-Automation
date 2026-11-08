"""Regress the nested payment field seen in a real Sandbox invoice response."""
import importlib.util
import logging
from pathlib import Path
from unittest.mock import Mock


def processor(invoices):
    path = Path(__file__).resolve().parents[1] / 'workflows/invoices/bulk_processor.py'
    spec = importlib.util.spec_from_file_location('bulk_under_test', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    obj = module.AutomatedInvoiceProcessor.__new__(module.AutomatedInvoiceProcessor)
    obj.logger = logging.getLogger('synthetic-invoice-regression')
    obj.acq = Mock()
    obj.acq.get_invoice.side_effect = invoices
    return obj


def invoice(base, payment):
    return {'invoice_status': {'value': base}, 'payment': {'payment_status': {'value': payment}}}


def test_reads_nested_payment_before_and_after_processing():
    obj = processor([invoice('ACTIVE', 'NOT_PAID'), invoice('CLOSED', 'PAID')])
    result = obj.process_single_invoice('synthetic-invoice')
    assert result['initial_payment_status'] == 'NOT_PAID'
    assert result['final_payment_status'] == 'PAID'
    assert result['payment_status_changed'] is True
    obj.acq.mark_invoice_paid.assert_called_once_with('synthetic-invoice')


def test_already_paid_open_invoice_is_not_paid_again():
    obj = processor([invoice('ACTIVE', 'PAID')])
    result = obj.process_single_invoice('synthetic-invoice')
    assert result['skipped'] is True
    assert result['initial_payment_status'] == 'PAID'
    obj.acq.mark_invoice_paid.assert_not_called()


def test_closed_invoice_keeps_its_nested_payment_in_result():
    obj = processor([invoice('CLOSED', 'PAID')])
    result = obj.process_single_invoice('synthetic-invoice')
    assert result['skipped'] is True
    assert result['final_payment_status'] == 'PAID'
    obj.acq.mark_invoice_paid.assert_not_called()
