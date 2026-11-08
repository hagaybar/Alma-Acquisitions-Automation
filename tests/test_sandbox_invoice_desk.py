"""Offline PAY experiments: only fake executors; no Alma/network requests."""
from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import sandbox_invoice_desk as app
import sandbox_request_cli as cli
import sandbox_terminal as terminal


def invoice():
    return {'id': 'synthetic-001', 'number': 'example',
            'invoice_status': {'value': 'ACTIVE', 'desc': 'Active'},
            'invoice_workflow_status': {'value': 'Ready to be Paid', 'desc': 'Waiting for Payment'},
            'invoice_approval_status': {'value': 'APPROVED', 'desc': 'Approved'},
            'payment': {'payment_status': {'value': 'NOT_PAID', 'desc': 'Not Paid'}},
            'vendor': {'value': 'SYNTHETIC'}, 'currency': {'value': 'USD'}, 'total_amount': '10.00'}


def values(**changes):
    return {'voucher_date': '2026-11-08', 'voucher_number': 'SYNTHETIC-PAY-001',
            'voucher_amount': '10.00', 'voucher_currency': 'USD', **changes}


class FakeExecutor:
    def __init__(self):
        self.current = invoice()
        self.calls = []
        self.status = 200
        self.result = 'http_success_business_outcome_unverified'

    def __call__(self, request):
        self.calls.append(request)
        return {'result': self.result,
                'input': {'method': request.method, 'url': cli.preview(request)['url'],
                          'body': deepcopy(request.body)},
                'output': {'status_code': self.status, 'body': deepcopy(self.current)},
                'completed_at': '2026-11-08T12:00:00+02:00'}


@pytest.fixture
def desk(tmp_path):
    fake = FakeExecutor()
    instance = app.InvoiceDesk(cli.load_operations(), executor=fake,
                               saver=lambda report: cli.save_report(report, tmp_path))
    instance.select('synthetic-001')
    return instance, fake


def prepare(desk):
    desk.refresh()
    desk.payment = app.payment_body(values())
    return desk.prepare_pay()


def confirm(request):
    return lambda _: cli.confirmation_phrase(request)


def test_payment_payload_is_minimal_invoice_object():
    body = app.payment_body(values(voucher_currency='usd'))
    assert body == {'payment': {**values(), 'voucher_currency': {'value': 'USD'}}}
    assert 'payment_status' not in body['payment']  # op=paid is the action, not PUT status.
    assert app.payment_body(values(voucher_amount='-5.00'))['payment']['voucher_amount'] == '-5.00'


@pytest.mark.parametrize('changes', [
    {'voucher_date': '2026-02-30'}, {'voucher_date': '20261108'}, {'voucher_number': ''},
    {'voucher_number': 'x' * 101}, {'voucher_amount': 'NaN'}, {'voucher_amount': 'Infinity'},
    {'voucher_amount': 'abc'}, {'voucher_currency': 'XX'}, {'voucher_number': 'x\x1b[2J'}])
def test_invalid_payment_details_do_not_build_request(changes):
    with pytest.raises(ValueError):
        app.payment_body(values(**changes))


@pytest.mark.parametrize('field,value', [
    ('invoice_status', 'CLOSED'), ('invoice_workflow_status', 'Waiting to be Sent'),
    ('invoice_workflow_status', 'InReview'), ('invoice_approval_status', 'PENDING'),
    ('invoice_approval_status', 'REJECTED'), ('invoice_approval_status', None)])
def test_unsupported_states_block_guided_pay(desk, field, value):
    instance, fake = desk
    fake.current[field] = {'value': value}
    instance.refresh()
    instance.payment = app.payment_body(values())
    with pytest.raises(ValueError):
        instance.prepare_pay()
    assert all(request.method == 'GET' for request in fake.calls)


@pytest.mark.parametrize('value', ['PAID', 'FULLY_PAID', 'PARTIALLY_PAID', None])
def test_paid_or_unknown_payment_is_not_replayed(desk, value):
    instance, fake = desk
    fake.current['payment']['payment_status'] = {'value': value}
    instance.refresh()
    instance.payment = app.payment_body(values())
    with pytest.raises(ValueError, match='NOT_PAID'):
        instance.prepare_pay()


def test_no_request_until_explicit_get_and_previews_never_send(desk):
    instance, fake = desk
    assert fake.calls == []
    request = prepare(instance)
    assert [call.method for call in fake.calls] == ['GET']
    assert request.method == 'POST' and request.parameters == {'op': 'paid'}
    assert request.body == app.payment_body(values())


def test_wrong_confirmation_only_performs_preflight_get(desk):
    instance, fake = desk
    prepare(instance)
    assert instance.send_pay(reader=lambda _: 'yes', writer=lambda _: None) is None
    assert [call.method for call in fake.calls] == ['GET', 'GET']
    assert not instance.attempted


def test_changed_invoice_aborts_before_confirmation_or_post(desk):
    instance, fake = desk
    prepare(instance)
    fake.current['total_amount'] = '11.00'
    with pytest.raises(ValueError, match='changed since'):
        instance.send_pay(reader=lambda _: pytest.fail('Must not confirm stale preview'), writer=lambda _: None)
    assert [call.method for call in fake.calls] == ['GET', 'GET']
    assert instance.pending is None


@pytest.mark.parametrize('status,other_id', [(500, False), (200, True)])
def test_bad_preflight_invalidates_state_and_preserves_actual_error_capture(desk, status, other_id):
    instance, fake = desk
    prepare(instance)
    fake.status = status
    if other_id:
        fake.current['id'] = 'other-synthetic'
    with pytest.raises(ValueError, match='selected invoice'):
        instance.send_pay(reader=lambda _: pytest.fail('Bad GET reached confirmation'), writer=lambda _: None)
    assert instance.invoice is None
    assert json.loads(instance.paths[0].read_text())['output']['status_code'] == status
    assert all(call.method == 'GET' for call in fake.calls)


def test_one_confirmed_post_then_explicit_readback_and_comparison(desk):
    instance, fake = desk
    request = prepare(instance)
    result = instance.send_pay(reader=confirm(request), writer=lambda _: None)
    assert [call.method for call in fake.calls] == ['GET', 'GET', 'POST']
    assert result['result'] == 'http_success_business_outcome_unverified'
    assert 'invoice_before' in json.loads(instance.paths[0].read_text())
    assert 'invoice_before' in instance.paths[1].read_text()
    fake.current['payment']['payment_status'] = {'value': 'PAID', 'desc': 'Paid'}
    fake.current['invoice_status'] = {'value': 'CLOSED', 'desc': 'Closed'}
    instance.refresh()
    assert [call.method for call in fake.calls] == ['GET', 'GET', 'POST', 'GET']
    assert set(instance.comparison['changed_fields']) == {'invoice_status', 'payment'}
    assert 'invoice_comparison' in json.loads(instance.paths[0].read_text())
    assert 'invoice_comparison' in instance.paths[1].read_text()
    with pytest.raises(ValueError, match='already made'):
        instance.prepare_pay()


def test_uncertain_post_locks_same_invoice_even_after_reselection(desk):
    instance, fake = desk
    request = prepare(instance)
    original = instance.executor

    def timeout(request):
        if request.method == 'POST':
            fake.calls.append(request)
            return {'result': 'outcome_unknown', 'error_type': 'TimeoutError'}
        return original(request)

    instance.executor = timeout
    assert instance.send_pay(reader=confirm(request), writer=lambda _: None)['result'] == 'outcome_unknown'
    instance.select('synthetic-001')
    instance.refresh()
    instance.payment = app.payment_body(values())
    with pytest.raises(ValueError, match='already made'):
        instance.prepare_pay()
    assert sum(call.method == 'POST' for call in fake.calls) == 1


def test_capture_save_failure_does_not_lose_write_attempt_lock(desk):
    instance, fake = desk
    request = prepare(instance)

    def fail_save(report):
        raise OSError('synthetic disk failure')

    instance.saver = fail_save
    instance.send_pay(reader=confirm(request), writer=lambda _: None)
    assert 'saving failed' in instance.save_error
    assert instance.report['input']['method'] == 'POST'
    assert instance.invoice_id in instance.attempted


@pytest.mark.parametrize('error', [RuntimeError, KeyboardInterrupt])
def test_unexpected_dispatch_failure_preserves_unknown_outcome_not_previous_get(desk, error):
    instance, fake = desk
    request = prepare(instance)
    original = instance.executor

    def fail(request):
        if request.method == 'POST':
            raise error('synthetic')
        return original(request)

    instance.executor = fail
    report = instance.send_pay(reader=confirm(request), writer=lambda _: None)
    assert report['result'] == 'outcome_unknown'
    assert 'input' not in report
    assert report['attempted_preview']['method'] == 'POST'
    assert instance.invoice_id in instance.attempted


def test_interactive_desk_cancel_and_payment_preview_use_only_fake_gets(tmp_path):
    fake, output = FakeExecutor(), []
    answers = iter(['1', 'synthetic-001', '2', '3', '2026-11-08', 'SYNTHETIC-PAY-001',
                    '10.00', 'USD', '4', '', '5', 'NO', '0'])
    assert app.interactive(cli.load_operations(), reader=lambda _: next(answers), writer=output.append,
                           executor=fake, saver=lambda report: cli.save_report(report, tmp_path)) == 0
    transcript = '\n'.join(output)
    assert 'Workflow code | description' in transcript
    assert 'Ready to be Paid | Waiting for Payment' in transcript
    assert 'EXACT PAY REQUEST PREVIEW' in transcript
    assert 'PAY cancelled' in transcript
    assert [call.method for call in fake.calls] == ['GET', 'GET']


def test_panel_wraps_values_without_truncating_and_neutralizes_terminal_controls():
    value = 'synthetic-' + '1234567890' * 12
    rendered = terminal.panel('SANDBOX', [value, '\x1b[2Jmalicious'], width=50)
    assert all(len(line) <= 50 for line in rendered.splitlines())
    assert '\x1b' not in rendered
    assert '1234567890' in rendered


def test_home_menu_routes_without_api_side_effects():
    calls = []
    answers = iter(['2', '1', '0'])
    terminal.home({}, reader=lambda _: next(answers), writer=lambda _: None,
                  invoice_app=lambda *args, **kwargs: calls.append('invoice'),
                  composer=lambda *args, **kwargs: calls.append('composer'))
    assert calls == ['invoice', 'composer']


@pytest.mark.parametrize('payload', [
    {'alert': [{'value': 'SYNTHETIC_ALERT', 'desc': 'Retained after closure'}]},
    {'alerts': {'alert': [{'value': 'SYNTHETIC_ALERT', 'desc': 'Retained after closure'}]}},
    {'alerts': [{'value': 'SYNTHETIC_ALERT', 'desc': 'Retained after closure'}]}])
def test_flat_and_wrapped_alerts_are_preserved_in_snapshot(payload):
    record = invoice()
    record.update(payload)
    assert app.snapshot(record)['alerts'] == [{'value': 'SYNTHETIC_ALERT', 'desc': 'Retained after closure'}]


def test_alert_change_is_visible_even_when_invoice_state_does_not_change():
    before, after = invoice(), invoice()
    after['alert'] = [{'value': 'SYNTHETIC_NEW_ALERT'}]
    assert app.snapshot(before) != app.snapshot(after)
