"""Wizard behavior and crash recovery using synthetic records and fake I/O only."""
from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from sandbox_request_cli import confirmation_phrase, load_operations
from sandbox_workflow import Workflow, compare, load_definition, DEFAULT_DEFINITION
from sandbox_workflow_store import Store, digest
import sandbox_workflow_wizard as wizard


def invoice():
    return {'id': 'synthetic-001', 'number': 'SYNTHETIC', 'owner': {'value': 'AC1'},
            'vendor': {'value': 'RIALTO'}, 'invoice_status': {'value': 'ACTIVE'},
            'invoice_workflow_status': {'value': 'InReview', 'desc': 'In Review'},
            'invoice_approval_status': {'value': 'PENDING'},
            'payment': {'payment_status': {'value': 'NOT_PAID'}}}


class FakeAlma:
    def __init__(self):
        self.invoice = invoice()
        self.lines = [{'id': 'line-1', 'po_line': 'synthetic-pol', 'price': 10}]
        self.pol = {'number': 'synthetic-pol', 'status': {'value': 'SENT'}}
        self.calls = []
        self.write_behavior = 'normal'
        self.line_status = 200
        self.line_total = None

    def __call__(self, request):
        self.calls.append(request)
        status = 200
        if request.method == 'GET':
            if '/po-lines/' in request.path:
                body = self.pol
            elif request.path.endswith('/lines'):
                offset = int(request.parameters.get('offset', 0))
                rows = self.lines[offset:offset + 100]
                body = {'invoice_line': rows, 'total_record_count': self.line_total if self.line_total is not None else len(self.lines)}
                status = self.line_status
            else:
                body = self.invoice
        else:
            if self.write_behavior == 'timeout':
                raise TimeoutError('synthetic')
            if self.write_behavior == 'reject':
                return {'result': 'failed', 'output': {'status_code': 400, 'body': {'error': 'synthetic rejection'}}}
            if request.method == 'POST' and request.parameters['op'] == 'process_invoice':
                self.invoice['invoice_workflow_status'] = {'value': 'Ready to be Paid', 'desc': 'Waiting for Payment'}
                self.invoice['invoice_approval_status'] = {'value': 'APPROVED'}
                if self.write_behavior == 'unexpected_payment':
                    self.invoice['payment']['voucher_amount'] = 'unexpected'
            elif request.method == 'POST':
                self.invoice['payment'].update(deepcopy(request.body['payment']))
                self.invoice['payment']['payment_status'] = {'value': 'PAID'}
                self.invoice['payment']['voucher_date'] += 'Z'
                self.invoice['payment']['voucher_amount'] = 10
                self.invoice['invoice_status'] = {'value': 'CLOSED'}
                self.invoice['invoice_workflow_status'] = {'value': 'CLOSED'}
            elif '/lines/' in request.path:
                self.lines[0].update(request.body)
            else:
                self.invoice.update(request.body)
            body = self.invoice
        return {'environment': 'SANDBOX', 'result': 'http_success_business_outcome_unverified',
                'input': {'method': request.method, 'url': 'https://example.invalid' + request.path,
                          'headers': {'Authorization': '[REDACTED]'}, 'body': deepcopy(request.body)},
                'output': {'status_code': status, 'body': deepcopy(body)}}


@pytest.fixture
def setup(tmp_path):
    store, api = Store(tmp_path / 'evidence'), FakeAlma()
    flow = Workflow.create(store, load_operations(), 'synthetic-001', configuration_note='Synthetic test configuration',
                           executor=api, sleep=lambda _: None)
    return flow, api


def process_plan(flow):
    flow.observe()
    return flow.plan('process', 'Processing advances this invoice without altering payment.',
                     [wizard.expectation('invoice.invoice_workflow_status.value', 'Ready to be Paid')])


def dispatch_count(api):
    return sum(request.method != 'GET' for request in api.calls)


def test_create_pins_definition_configuration_and_commit_without_api_calls(setup):
    flow, api = setup
    assert not api.calls
    manifest = flow.store.manifest(flow.run_id)
    assert manifest['definition_sha256'] == digest(manifest['definition'])
    assert manifest['definition']['configuration']['active_erp_integration'] is False
    assert 'source_commit' in manifest and manifest['configuration_confirmed_at']


def test_complete_baseline_inspects_lines_and_linked_orders_and_planning_is_local(setup):
    flow, api = setup
    step = process_plan(flow)
    assert len(api.calls) == 3 and dispatch_count(api) == 0
    assert step['before']['lines']['line-1']['po_line'] == 'synthetic-pol'
    assert 'synthetic-pol' in step['before']['po_lines']
    assert step['request']['parameters'] == {'op': 'process_invoice'}


def test_process_is_one_confirmed_write_with_automatic_gets_and_comparison(setup):
    flow, api = setup
    step = process_plan(flow)
    result = flow.perform(step, confirmer=lambda _: True)
    assert dispatch_count(api) == 1
    assert result['verdict'] == 'supported_for_this_case'
    assert result['closure_verified'] is False
    assert all(check['passed'] for check in result['checks'])
    assert api.calls[-1].method == 'GET'
    assert any(item['path'] == 'invoice.invoice_approval_status.value' for item in result['changes'])
    report = flow.store.report(flow.run_id)
    assert report['steps'][0]['latest_verification']['verdict'] == result['verdict']
    page = (flow.store.folder(flow.run_id) / 'report.html').read_text()
    assert 'expected' in page and 'actual' in page and 'Authorization' in page


def test_cancel_never_dispatches_and_records_preflight_only(setup):
    flow, api = setup
    step = process_plan(flow)
    assert flow.perform(step, confirmer=lambda _: False) is None
    assert dispatch_count(api) == 0
    assert flow.latest('cancelled')
    assert not flow.latest('dispatch_started')


@pytest.mark.parametrize('target', ['invoice', 'line', 'pol'])
def test_preflight_detects_changes_in_any_inspected_record(setup, target):
    flow, api = setup
    step = process_plan(flow)
    if target == 'invoice':
        api.invoice['number'] = 'changed'
    elif target == 'line':
        api.lines[0]['price'] = 20
    else:
        api.pol['status'] = {'value': 'CLOSED'}
    with pytest.raises(ValueError, match='changed since planning'):
        flow.perform(step, confirmer=lambda _: pytest.fail('Stale preflight reached confirmation'))
    assert dispatch_count(api) == 0
    assert flow.latest('preflight_changed')


def test_paid_in_review_processes_without_paying_again(setup):
    flow, api = setup
    api.invoice['payment']['payment_status']['value'] = 'PAID'
    step = process_plan(flow)
    result = flow.perform(step, confirmer=lambda _: True)
    assert result['verdict'] == 'supported_for_this_case'
    assert [request.parameters['op'] for request in api.calls if request.method == 'POST'] == ['process_invoice']
    with pytest.raises(ValueError, match='NOT_PAID'):
        flow.plan('pay', 'must not replay payment', [wizard.expectation('invoice.invoice_status.value', 'CLOSED')])


def test_unexpected_payment_change_contradicts_invariant_and_holds_next_write(setup):
    flow, api = setup
    step = process_plan(flow)
    api.write_behavior = 'unexpected_payment'
    result = flow.perform(step, confirmer=lambda _: True)
    assert result['verdict'] == 'contradicted'
    assert flow.unresolved() == [(flow.run_id, step['step_id'])]
    assert any(not check['passed'] and check['path'] == 'invoice.payment' for check in result['checks'])


def test_pay_records_explicit_simulation_and_verifies_all_voucher_values(setup):
    flow, api = setup
    api.invoice['invoice_workflow_status'] = {'value': 'Ready to be Paid'}
    api.invoice['invoice_approval_status'] = {'value': 'APPROVED'}
    flow.observe()
    body = {'payment': {'voucher_date': '2026-11-08', 'voucher_number': 'SYNTHETIC',
                        'voucher_amount': '10.00', 'voucher_currency': {'value': 'USD'}}}
    checks = [wizard.expectation('invoice.invoice_status.value', 'CLOSED'),
              wizard.expectation('invoice.payment.payment_status.value', 'PAID'),
              wizard.expectation('invoice.payment.voucher_date', '2026-11-08', 'date_equals'),
              wizard.expectation('invoice.payment.voucher_amount', '10.00', 'decimal_equals'),
              wizard.expectation('invoice.payment.voucher_currency.value', 'USD'),
              wizard.expectation('invoice.payment.voucher_number', 'SYNTHETIC')]
    # Expected fields may not yet exist in baseline. PAY supplies them explicitly.
    step = flow.plan('pay', 'Record a Sandbox simulation', checks, body=body, payment_intent='sandbox_simulation')
    result = flow.perform(step, confirmer=lambda _: True)
    assert dispatch_count(api) == 1 and result['closure_verified']
    assert step['payment_intent'] == 'sandbox_simulation'
    assert result['verdict'] == 'supported_for_this_case'


def test_date_and_decimal_comparison_tolerate_documented_representation_differences():
    checks = [wizard.expectation('invoice.date', '2026-11-08', 'date_equals'),
              wizard.expectation('invoice.amount', '10.00', 'decimal_equals')]
    assert all(row['passed'] for row in compare(checks, {}, {'invoice': {'date': '2026-11-08Z', 'amount': 10}}))


@pytest.mark.parametrize('action,body,line_id,path,value', [
    ('update_invoice', {'number': 'SYNTHETIC-CORRECTED'}, None, 'invoice.number', 'SYNTHETIC-CORRECTED'),
    ('update_line', {'price': 11}, 'line-1', 'lines.line-1.price', 11)])
def test_explicit_corrections_are_verified_in_the_affected_record(setup, action, body, line_id, path, value):
    flow, api = setup
    flow.observe()
    step = flow.plan(action, 'Test one correction', [wizard.expectation(path, value)], body=body, line_id=line_id)
    assert flow.perform(step, confirmer=lambda _: True)['verdict'] == 'supported_for_this_case'
    assert dispatch_count(api) == 1
    assert next(request for request in api.calls if request.method == 'PUT').body == body


def test_unknown_or_out_of_scope_invoice_and_incomplete_lines_block_writes(setup):
    flow, api = setup
    api.invoice['owner'] = {'value': 'OTHER'}
    with pytest.raises(ValueError, match='outside this run scope'):
        flow.observe()
    assert flow.observation() is None
    api.invoice['owner'] = {'value': 'AC1'}
    api.line_total = 10
    with pytest.raises(ValueError, match='incomplete'):
        flow.observe()
    assert flow.observation() is None and dispatch_count(api) == 0


def test_line_pagination_reads_complete_collection_before_planning(setup):
    flow, api = setup
    api.lines = [{'id': 'synthetic-' + str(number), 'price': number} for number in range(101)]
    resources = flow.observe()
    assert len(resources['lines']) == 101
    assert [int(request.parameters['offset']) for request in api.calls if request.path.endswith('/lines')] == [0, 100]


def test_failed_get_invalidates_previously_valid_baseline(setup):
    flow, api = setup
    process_plan(flow)
    api.line_status = 500
    with pytest.raises(ValueError, match='GET failed'):
        flow.observe()
    assert flow.observation() is None
    with pytest.raises(ValueError, match='baseline'):
        flow.plan('process', 'unsafe', [wizard.expectation('invoice.invoice_status.value', 'CLOSED')])


def test_persistence_failure_before_dispatch_means_no_write(setup, monkeypatch):
    flow, api = setup
    step = process_plan(flow)
    original = flow.store.append

    def fail(run_id, kind, data):
        if kind == 'dispatch_started':
            raise OSError('synthetic full disk')
        return original(run_id, kind, data)

    monkeypatch.setattr(flow.store, 'append', fail)
    with pytest.raises(OSError):
        flow.perform(step, confirmer=lambda _: True)
    assert dispatch_count(api) == 0


def test_crash_after_write_before_response_save_resumes_without_replay(setup, monkeypatch):
    flow, api = setup
    step = process_plan(flow)
    original = flow.store.append

    def fail(run_id, kind, data):
        if kind == 'http' and data['phase'] == 'mutation':
            raise OSError('synthetic response-save failure')
        return original(run_id, kind, data)

    monkeypatch.setattr(flow.store, 'append', fail)
    with pytest.raises(OSError):
        flow.perform(step, confirmer=lambda _: True)
    assert dispatch_count(api) == 1
    monkeypatch.setattr(flow.store, 'append', original)
    resumed = Workflow(Store(flow.store.root), load_operations(), flow.run_id, executor=api, sleep=lambda _: None)
    with pytest.raises(ValueError, match='already attempted'):
        resumed.perform(step, confirmer=lambda _: True)
    result = resumed.verify(step)
    assert result['verdict'] == 'state_observed_request_outcome_unknown'
    resumed.interpret(step['step_id'], 'Inspected the read-back; payment unchanged. Proceed to a different reviewed step.', resolve=True)
    assert not resumed.unresolved()
    assert dispatch_count(api) == 1


def test_timeout_is_bounded_inconclusive_and_blocks_new_run_for_same_invoice(setup):
    flow, api = setup
    step = process_plan(flow)
    api.write_behavior = 'timeout'
    result = flow.perform(step, confirmer=lambda _: True)
    assert result['verdict'] == 'inconclusive'
    assert dispatch_count(api) == 1
    assert len([event for event in flow.events() if event['kind'] == 'observation' and event['data']['phase'] == 'verification']) == 3
    other = Workflow.create(Store(flow.store.root), load_operations(), 'synthetic-001',
                            configuration_note='Synthetic confirmation', executor=api, sleep=lambda _: None)
    other_step = process_plan(other)
    with pytest.raises(ValueError, match='earlier write'):
        other.perform(other_step, confirmer=lambda _: True)
    assert dispatch_count(api) == 1


def test_http_rejection_retains_error_and_does_not_become_business_success(setup):
    flow, api = setup
    step = process_plan(flow)
    api.write_behavior = 'reject'
    result = flow.perform(step, confirmer=lambda _: True)
    assert not result['request_accepted'] and result['verdict'] == 'request_failed'
    assert any(event['kind'] == 'http' and event['data']['report'].get('output', {}).get('status_code') == 400
               for event in flow.events())


def test_altering_plan_or_manifest_is_detected_before_write(setup):
    flow, api = setup
    step = process_plan(flow)
    edited = deepcopy(step)
    edited['checks'][0]['value'] = 'CLOSED'
    with pytest.raises(ValueError, match='Plan changed'):
        flow.perform(edited, confirmer=lambda _: True)
    path = flow.store.folder(flow.run_id) / 'manifest.json'
    record = json.loads(path.read_text())
    record['data']['invoice_id'] = 'other'
    path.write_text(json.dumps(record))
    with pytest.raises(ValueError, match='integrity'):
        flow.events()
    assert dispatch_count(api) == 0


def test_event_edit_is_detected_and_old_expectations_are_never_overwritten(setup):
    flow, api = setup
    step = process_plan(flow)
    path = flow.store.folder(flow.run_id) / 'events' / f'{flow.latest("planned")["sequence"]:06d}.json'
    event = json.loads(path.read_text())
    event['data']['hypothesis'] = 'edited'
    path.write_text(json.dumps(event))
    with pytest.raises(ValueError, match='integrity'):
        flow.events()


def test_definition_revision_is_new_local_file_and_run_stays_frozen(setup):
    flow, api = setup
    original = deepcopy(flow.definition)
    path = flow.revise_definition('Proposed lesson; this is synthetic evidence, not live validation.')
    revised = load_definition(path)
    assert revised['version'] == original['version'] + 1
    assert revised['parent_sha256'] == digest(original)
    assert flow.store.manifest(flow.run_id)['definition'] == original
    assert not api.calls


def test_concurrent_wizard_store_is_excluded_by_process_lock(setup):
    flow, api = setup
    other = Store(flow.store.root)
    with flow.store.lock():
        with pytest.raises(ValueError, match='Another workflow'):
            with other.lock():
                pytest.fail('Concurrent writer obtained the lock')


def test_full_wizard_process_journey_is_fake_and_records_expected_vs_actual(tmp_path):
    store, api, output = Store(tmp_path / 'evidence'), FakeAlma(), []
    answers = iter(['1', 'synthetic-001', 'CONFIRM SANDBOX CONFIG',
                    '1', '2', '1', '', '1', '', '3',
                    'PROCESS', '', '0'])
    result = wizard.interactive(load_operations(), store=store, executor=api, sleep=lambda _: None,
                                reader=lambda _: next(answers), writer=output.append)
    assert result == 0 and dispatch_count(api) == 1
    transcript = '\n'.join(output)
    assert 'EXPECTED vs ACTUAL' in transcript and 'supported_for_this_case' in transcript
    report = store.report(store.list_runs()[0])
    assert report['steps'][0]['latest_verification']['checks'][0]['passed']


def test_resume_exit_and_local_report_do_not_issue_any_api_calls(setup):
    flow, api = setup
    answers = iter(['CONFIRM SANDBOX CONFIG', '0'])
    assert wizard.interactive(load_operations(), store=flow.store, resume=flow.run_id, executor=api,
                               reader=lambda _: next(answers), writer=lambda _: None) == 0
    flow.store.report(flow.run_id)
    assert not api.calls


def test_revised_hypothesis_is_used_by_future_run_without_changing_old_run(setup):
    flow, api = setup
    path = flow.revise_definition('Synthetic evidence only.', action='process', hypothesis='A revised, still unvalidated hypothesis.')
    revised = load_definition(path)
    future = Workflow.create(flow.store, load_operations(), 'synthetic-001', definition=revised,
                             configuration_note='Synthetic confirmation', executor=api)
    assert future.definition['hypotheses']['process'] == 'A revised, still unvalidated hypothesis.'
    assert flow.definition['hypotheses']['process'] != future.definition['hypotheses']['process']


def test_stale_reconciliation_cannot_release_hold_after_another_observation(setup):
    flow, api = setup
    step = process_plan(flow)
    api.write_behavior = 'reject'
    flow.perform(step, confirmer=lambda _: True)
    flow.observe()
    with pytest.raises(ValueError, match='read-back reconciliation'):
        flow.interpret(step['step_id'], 'Synthetic explanation', resolve=True)


def test_unknown_state_and_approval_hold_have_no_automatic_write_route(setup):
    flow, api = setup
    for state in ('InApproval', 'Waiting to be Sent', 'UNKNOWN'):
        api.invoice['invoice_workflow_status'] = {'value': state}
        resources = flow.observe()
        assert all(flow.action_blockers(action, resources) for action in flow.definition['actions'])
    assert dispatch_count(api) == 0
