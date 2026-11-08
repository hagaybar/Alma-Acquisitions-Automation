"""Operator-run invoice PAY experiment. Development tests must use fake executors.

PAY records payment in Alma; it does not transfer money. There is no automatic
approval, ERP handoff, invoice creation, retry, or chain of write operations here.
"""
from copy import deepcopy
from datetime import date
from decimal import Decimal, InvalidOperation
import json
import re

from sandbox_request_cli import authorize, compose, execute, now, preview, save_report
from sandbox_terminal import display


PATH = '/almaws/v1/acq/invoices/{invoice_id}'
STATE_FIELDS = ('invoice_status', 'invoice_workflow_status', 'invoice_approval_status')
SESSION_PAY_ATTEMPTS = set()
GUIDE = '''Invoice payment experiment | documentation checked 2026-11-08; one operator-run PAY case validated

Review -> processing/approval -> ERP handoff or configured ERP skip -> payment -> closure.
These are separate stages, not a sequence this app runs automatically.
process_invoice starts processing; it does not guarantee approval.
mark_in_erp records ERP handling; handle_invoice_payment determines the next state.
paid records payment confirmation in Alma; it does not send money to a vendor.
handle_invoice_payment=false can close an invoice without tracking payment confirmation.

API code "Waiting to be Sent" = UI "Ready to be paid" (ERP handoff stage).
API code "Ready to be Paid" = UI "Waiting for Payment" (payment stage).
The desk displays both code and description, without guessing from the label.

This guided PAY prototype requires ACTIVE, waiting-for-payment code, APPROVED or
NOT_REQUIRED, and NOT_PAID. This is a conservative local policy, not a complete
Alma eligibility rule. PENDING, paid-but-open and unknown states need investigation.
Payment date, identifier, final amount and currency must be entered explicitly.
Requiring all four is a prototype policy; the API describes a default current date,
and UI documentation makes the identifier mandatory for Accounting Department.
ERP settings, institutional currency rules, tax and exchange ratios remain unverified.
For explicit_ratios/notes/create_rt_invoice, review the contract and use the generic
composer; this desk never invents those values or replays the whole GET invoice.

After the one confirmed POST, use Refresh/compare (GET). Check payment AND invoice
workflow/base status separately. Processing can be asynchronous; an unchanged GET is
not permission to replay PAY. The desk allows only one PAY attempt per invoice per
app run. Reconcile an uncertain outcome before any later attempt, including relaunch.
Linked PO-line closure also depends on invoicing/payment and receipt or activation;
this desk does not certify it. Use the existing lines / pol GET tests for that evidence.
Rialto's optional payment-status/date update does not itself change invoice status.
Paid-but-open is therefore a separate case, not a reason to send PAY again.

Sources:
https://developers.exlibrisgroup.com/blog/alma-erp-invoices-integration-using-apis/
https://developers.exlibrisgroup.com/alma/apis/docs/xsd/rest_invoice.xsd/?tags=POST
https://knowledge.exlibrisgroup.com/Alma/Product_Documentation/010Alma_Online_Help_(English)/020Acquisitions/020Invoicing/010Invoicing_Workflow
https://knowledge.exlibrisgroup.com/Alma/Product_Documentation/010Alma_Online_Help_(English)/020Acquisitions/020Invoicing/060Working_with_Invoices_Waiting_for_Payment
'''


def code(value):
    return value.get('value') if isinstance(value, dict) else value


def label(value):
    if isinstance(value, dict):
        return str(value.get('value', '?')) + ' | ' + str(value.get('desc', '(no description)'))
    return str(value) if value is not None else '(not returned)'


def invoice_alerts(invoice):
    """Normalize observed flat JSON alert and documented/legacy alerts wrappers.

    Keep the original API body intact in evidence. Retained alerts are observations,
    not a reason to claim that every alert blocks processing or payment.
    """
    result = []
    for name in ('alert', 'alerts'):
        value = invoice.get(name)
        if isinstance(value, dict) and 'alert' in value:
            value = value['alert']
        values = value if isinstance(value, list) else ([value] if value else [])
        for alert in values:
            if alert not in result:
                result.append(alert)
    return result


def snapshot(invoice):
    payment = invoice.get('payment') or {}
    return {**{key: invoice.get(key) for key in STATE_FIELDS},
            'payment': payment, 'payment_method': invoice.get('payment_method'),
            'total_amount': invoice.get('total_amount'), 'currency': invoice.get('currency'),
            'vendor': invoice.get('vendor'), 'owner': invoice.get('owner'),
            'alerts': invoice_alerts(invoice)}


def pay_blockers(invoice):
    if not invoice:
        return ['Load the selected invoice with GET first.']
    checks = [
        (code(invoice.get('invoice_status')) == 'ACTIVE', 'Base state must be ACTIVE.'),
        (code(invoice.get('invoice_workflow_status')) == 'Ready to be Paid',
         'Workflow must be Waiting for Payment (API code: Ready to be Paid).'),
        (code(invoice.get('invoice_approval_status')) in ('APPROVED', 'NOT_REQUIRED'),
         'Approval must be APPROVED or NOT_REQUIRED; PENDING is not approval.'),
        (code((invoice.get('payment') or {}).get('payment_status')) == 'NOT_PAID',
         'Payment must be explicitly NOT_PAID; paid/partial/unknown records need review.')]
    return [message for passed, message in checks if not passed]


def payment_body(values):
    required = ('voucher_date', 'voucher_number', 'voucher_amount', 'voucher_currency')
    if set(values) != set(required) or any(not str(values[key]).strip() for key in required):
        raise ValueError('Enter all four payment fields explicitly.')
    values = {key: str(values[key]).strip() for key in required}
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', values['voucher_date']):
        raise ValueError('Use a payment date in YYYY-MM-DD format.')
    date.fromisoformat(values['voucher_date'])
    if len(values['voucher_number']) > 100:
        raise ValueError('Payment identifier must be at most 100 characters.')
    if re.search(r'[\x00-\x1f\x7f]', values['voucher_number']):
        raise ValueError('Payment identifier must not contain control characters.')
    try:
        amount = Decimal(values['voucher_amount'])
    except InvalidOperation as exc:
        raise ValueError('Payment amount must be a finite decimal.') from exc
    if not amount.is_finite():
        raise ValueError('Payment amount must be a finite decimal.')
    currency = values['voucher_currency'].upper()
    if not re.fullmatch('[A-Z]{3}', currency):
        raise ValueError('Use a three-letter currency code; institution acceptance is not validated.')
    # Minimal invoice service payload: never PUT/replay output-only header fields.
    return {'payment': {**values, 'voucher_currency': {'value': currency}}}


def invoice_from_report(report, invoice_id):
    output = report.get('output', {})
    body = output.get('body')
    if (report.get('error_type') or output.get('status_code') != 200
            or not isinstance(body, dict) or str(body.get('id')) != str(invoice_id)):
        raise ValueError('GET did not return the selected invoice with HTTP 200. Inspect actual I/O.')
    return body


class InvoiceDesk:
    def __init__(self, operations, *, executor=execute, saver=save_report, attempted=None):
        self.operations, self.executor, self.saver = operations, executor, saver
        self.invoice_id, self.invoice, self.read_at = '', None, None
        self.payment, self.pending, self.report = None, None, None
        self.paths, self.before, self.comparison = None, None, None
        self.save_error = None
        self.attempted = attempted if attempted is not None else set()
        self.notice = 'Select an invoice ID. Opening this desk sends no request.'

    def select(self, invoice_id):
        invoice_id = invoice_id.strip()
        compose(self.operations['GET ' + PATH], {'invoice_id': invoice_id}, {})
        self.invoice_id, self.invoice, self.read_at = invoice_id, None, None
        self.payment, self.pending, self.before, self.comparison = None, None, None, None
        self.report, self.paths = None, None
        self.save_error = None
        self.notice = 'ID selected. Use GET to load its current state.'

    def run(self, request, annotate=None):
        try:
            self.report = self.executor(request)
        except (Exception, KeyboardInterrupt) as exc:
            self.report = {'environment': 'SANDBOX', 'error_type': type(exc).__name__,
                           'attempted_preview': preview(request),
                           'result': 'outcome_unknown' if request.method != 'GET' else 'failed_without_captured_http_response',
                           'verification': 'No captured response. Read back state before retrying a write.'}
        self.paths = None
        self.save_error = None
        try:
            if annotate:
                annotate(self.report)
        finally:
            try:
                self.paths = self.saver(self.report)
            except OSError as exc:
                self.save_error = 'Capture saving failed (' + type(exc).__name__ + '). Inspect I/O before leaving.'
        return self.report

    def refresh(self):
        request = compose(self.operations['GET ' + PATH], {'invoice_id': self.invoice_id}, {})
        # Failed/aborted reads cannot leave an old invoice looking freshly verified.
        self.invoice = None
        self.comparison = None
        def annotate(report):
            self.invoice = invoice_from_report(report, self.invoice_id)
            self.read_at = report.get('completed_at') or now()
            if self.before is not None:
                after = snapshot(self.invoice)
                self.comparison = {'before': self.before, 'after': after,
                                   'changed_fields': [key for key in after if after[key] != self.before[key]],
                                   'interpretation': 'Observed GET state only; inspect payment, closure and linked PO lines separately.'}
                report['invoice_comparison'] = self.comparison
        self.run(request, annotate)
        return self.invoice

    def blockers(self):
        return (pay_blockers(self.invoice)
                + (['One PAY attempt already made for this invoice in this app run. Reconcile; do not replay.']
                   if self.invoice_id in self.attempted else [])
                + ([] if self.payment else ['Enter the payment details.']))

    def prepare_pay(self):
        self.pending = None
        problems = self.blockers()
        if problems:
            raise ValueError(' '.join(problems))
        self.pending = compose(self.operations['POST ' + PATH], {'invoice_id': self.invoice_id},
                               {'op': 'paid'}, deepcopy(self.payment), 'application/json')
        return self.pending

    def send_pay(self, *, reader=input, writer=print):
        if self.pending is None:
            raise ValueError('Prepare and review a PAY preview first.')
        request, expected = self.pending, deepcopy(self.invoice)
        self.pending = None
        writer('Preflight: one GET of the selected invoice; no write yet.')
        self.refresh()
        if self.invoice != expected:
            raise ValueError('Invoice changed since the preview. Inspect it and prepare a new preview.')
        problems = self.blockers()
        if problems:
            raise ValueError(' '.join(problems))
        display('PAY PREVIEW | SANDBOX | one POST, no automatic follow-up writes', [
            json.dumps(preview(request), ensure_ascii=False, indent=2),
            'This records payment in Alma. It does not transfer money.\n'
            'Transition supported in one scoped case only. After sending, choose Refresh/compare (GET).'
        ], writer=writer)
        if not authorize(request, send=True, reader=reader, writer=writer):
            self.notice = 'PAY cancelled. Only the preflight GET ran.'
            return None
        self.before = deepcopy(snapshot(self.invoice))
        self.attempted.add(self.invoice_id)
        # Set the lock BEFORE dispatch. Even a timeout/interruption must not replay.
        self.notice = 'PAY attempted. Use Refresh/compare; no automatic retry.'
        self.invoice = None
        report = self.run(request, lambda report: report.update(invoice_before=self.before))
        self.notice = 'PAY: ' + report['result'] + '. Choose Refresh/compare (GET).'
        return report

    def sections(self):
        invoice = self.invoice or {}
        payment = invoice.get('payment') or {}
        state = ('Invoice ID: ' + (self.invoice_id or '(choose one)') + '\n'
                 'Number: ' + str(invoice.get('number', '-')) + ' | Vendor: ' + label(invoice.get('vendor')) + '\n'
                 'Base: ' + label(invoice.get('invoice_status')) + '\n'
                 'Workflow code | description: ' + label(invoice.get('invoice_workflow_status')) + '\n'
                 'Approval: ' + label(invoice.get('invoice_approval_status')) + '\n'
                 'Payment: ' + label(payment.get('payment_status')) + '\n'
                 'Alerts recorded: ' + str(len(invoice_alerts(invoice))) + '\n'
                 'Amount: ' + str(invoice.get('total_amount', '-')) + ' ' + label(invoice.get('currency')) + '\n'
                 'Read at: ' + (self.read_at or '(not read)') + (' | state invalidated; refresh required' if not self.invoice and self.read_at else ''))
        proposal = ('Action: PAY -> POST ?op=paid | ' + ('PREVIEW READY' if self.pending else 'not prepared') + '\n'
                    'Payment body: ' + json.dumps(self.payment, ensure_ascii=False) + '\n'
                    'Guided PAY: ' + ('eligible for explicit review (not guaranteed by Alma)' if not self.blockers()
                                      else ' / '.join(self.blockers())))
        result = self.notice
        if self.save_error:
            result += '\n' + self.save_error
        if self.comparison:
            result += '\nChanged fields: ' + (', '.join(self.comparison['changed_fields']) or 'none observed; processing may be asynchronous')
        if self.paths:
            result += '\nCapture: ' + str(self.paths[0])
        return [state, proposal, result,
                '1 Select ID   2 GET / Refresh / compare   3 Payment details\n'
                '4 Preview PAY   5 Send reviewed PAY   6 Actual input/output\n'
                '7 Compare before/after   8 Workflow help   0 Back']


def interactive(operations, *, reader=input, writer=print, executor=execute, saver=save_report):
    desk = InvoiceDesk(operations, executor=executor, saver=saver, attempted=SESSION_PAY_ATTEMPTS)
    while True:
        display('ALMA INVOICE DESK | SANDBOX / EU | PAY validated in one scoped Sandbox case', desk.sections(), writer=writer)
        try:
            choice = reader('Choose: ').strip()
            if choice == '0':
                return 0
            if choice == '1':
                desk.select(reader('Alma Sandbox internal invoice ID (not invoice number): '))
            elif choice == '2':
                desk.refresh()
                desk.notice = 'GET returned selected invoice. Inspect states and actual I/O.'
            elif choice == '3':
                desk.pending = None
                desk.payment = None
                writer('Enter final paid amount/currency; these are not inferred from invoice totals.\n'
                       'All four fields required by this prototype. Ctrl+C cancels.')
                values = {key: reader(prompt) for key, prompt in [
                    ('voucher_date', 'Payment date YYYY-MM-DD: '),
                    ('voucher_number', 'Payment identifier/reference (up to 100 chars): '),
                    ('voucher_amount', 'Final paid amount (decimal, refunds may be negative): '),
                    ('voucher_currency', 'Payment currency (e.g. USD): ')]}
                desk.payment = payment_body(values)
                desk.notice = 'Payment details stored locally; nothing sent.'
            elif choice == '4':
                request = desk.prepare_pay()
                display('EXACT PAY REQUEST PREVIEW | nothing sent', [json.dumps(preview(request), ensure_ascii=False, indent=2)], writer=writer)
                reader('Enter to return to the desk: ')
            elif choice == '5':
                desk.send_pay(reader=reader, writer=writer)
            elif choice == '6':
                writer(json.dumps(desk.report or {'notice': 'No request run yet.'}, ensure_ascii=False, indent=2))
                reader('Enter to return: ')
            elif choice == '7':
                writer(json.dumps(desk.comparison or {'notice': 'After PAY, use Refresh/compare first.'}, ensure_ascii=False, indent=2))
                reader('Enter to return: ')
            elif choice == '8':
                writer(GUIDE)
                reader('Enter to return: ')
            else:
                desk.notice = 'Choose one of the displayed numbers.'
        except (ValueError, OSError) as exc:
            desk.notice = str(exc) + ' No automatic retry; inspect I/O and refresh if a request ran.'
        except (EOFError, KeyboardInterrupt):
            writer('\nLeaving invoice desk. No automatic retry. Reconcile any request already sent.')
            return 0
