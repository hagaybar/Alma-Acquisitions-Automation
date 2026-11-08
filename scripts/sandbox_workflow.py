"""State-based Sandbox experiments. All external I/O is injected for offline tests."""
from copy import deepcopy
from datetime import date
from decimal import Decimal, InvalidOperation
from importlib.metadata import PackageNotFoundError, version
import json
from pathlib import Path
import subprocess
import time
import uuid

from sandbox_invoice_desk import code, pay_blockers, payment_body
from sandbox_request_cli import ROOT, Request, compose, execute, now, preview
from sandbox_workflow_store import Store, atomic_json, digest


INVOICE = '/almaws/v1/acq/invoices/{invoice_id}'
LINE = INVOICE + '/lines/{invoice_line_id}'
DEFAULT_DEFINITION = ROOT / 'workflow-tests/workflows/invoice-closure-v1.json'
DEFAULT_STORE = ROOT / 'output/workflow-tests'


def load_definition(path):
    definition = json.loads(Path(path).read_text(encoding='utf-8'))
    if (definition.get('schema_version') != 1 or definition.get('scope') !=
            {'environment': 'SANDBOX', 'owner': 'AC1', 'vendor': 'RIALTO'}):
        raise ValueError('This wizard requires the Central Library / RIALTO Sandbox definition.')
    if definition.get('configuration') != {'invoice_skip_erp': True, 'handle_invoice_payment': True, 'active_erp_integration': False}:
        raise ValueError('This prototype requires ERP skip, payment handling, and no active ERP integration.')
    return definition


def field(data, path):
    current = data
    for part in path.split('.'):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return {'field_missing': path}
    return current


def compare(checks, before, after):
    results = []
    for check in checks:
        actual = field(after, check['path'])
        expected = field(before, check['path']) if check['operator'] == 'unchanged' else check['value']
        present = not (isinstance(actual, dict) and 'field_missing' in actual)
        operator = check['operator']
        passed = present and (actual in expected if operator == 'one_of' else actual == expected)
        if present and operator in ('date_equals', 'decimal_equals'):
            try:
                if operator == 'date_equals':
                    passed = date.fromisoformat(str(actual).removesuffix('Z')) == date.fromisoformat(str(expected).removesuffix('Z'))
                else:
                    passed = Decimal(str(actual)).is_finite() and Decimal(str(actual)) == Decimal(str(expected))
            except (ValueError, InvalidOperation):
                passed = False
        results.append({**check, 'expected': expected, 'actual': actual, 'passed': passed})
    return results


def changes(before, after, prefix=''):
    if isinstance(before, dict) and isinstance(after, dict):
        result = []
        for key in sorted(set(before) | set(after)):
            path = prefix + '.' + key if prefix else key
            if key not in before or key not in after:
                result.append({'path': path, 'before': before.get(key, {'absent': True}),
                               'after': after.get(key, {'absent': True})})
            else:
                result.extend(changes(before[key], after[key], path))
        return result
    return [] if before == after else [{'path': prefix, 'before': before, 'after': after}]


def routing(invoice):
    base = code(invoice.get('invoice_status'))
    workflow = code(invoice.get('invoice_workflow_status'))
    paid = code((invoice.get('payment') or {}).get('payment_status'))
    if base == 'CLOSED':
        return 'Already CLOSED: verify and leave unchanged; flag other inconsistencies separately.'
    if base != 'ACTIVE':
        return 'HOLD: unknown base status; no guided mutation.'
    if workflow == 'InReview':
        return 'Inspect lines and payment facts; one PROCESS experiment may advance review. Approval is not guaranteed.'
    if workflow == 'InApproval':
        return 'HOLD: approval stage. No verified API approval action; processing is not assumed approval.'
    if workflow == 'Waiting to be Sent':
        return 'HOLD: historical ERP stage. No active ERP integration and ERP is skipped; do not mark in ERP.'
    if workflow == 'Ready to be Paid':
        return ('HOLD: paid but Waiting for Payment. Continuation API needs research; do not PAY again.'
                if paid != 'NOT_PAID' else 'Waiting for Payment: establish payment intent, then consider one PAY experiment.')
    return 'HOLD: unfamiliar workflow state; capture evidence and investigate.'


class Workflow:
    def __init__(self, store, operations, run_id, *, executor=execute, sleep=time.sleep, clock=time.monotonic):
        self.store, self.operations, self.run_id = store, operations, run_id
        self.executor, self.sleep, self.clock = executor, sleep, clock
        self.manifest = store.manifest(run_id)
        self.invoice_id = self.manifest['invoice_id']
        self.definition = self.manifest['definition']

    @classmethod
    def create(cls, store, operations, invoice_id, *, definition=None, configuration_note='', **kwargs):
        definition = deepcopy(definition or load_definition(DEFAULT_DEFINITION))
        compose(operations['GET ' + INVOICE], {'invoice_id': invoice_id}, {})
        if not configuration_note.strip():
            raise ValueError('Record confirmation of the current Sandbox configuration and no active ERP integration.')
        try:
            sdk = version('almaapitk')
        except PackageNotFoundError:
            sdk = 'not installed in this interpreter; executor may be simulated'
        commit = subprocess.run(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
        run_id = store.create({'invoice_id': invoice_id, 'environment': 'SANDBOX', 'definition': definition,
                               'definition_sha256': digest(definition), 'configuration_confirmation': configuration_note,
                               'configuration_confirmed_at': now(), 'source_commit': commit, 'sdk_version': sdk})
        return cls(store, operations, run_id, **kwargs)

    def events(self):
        self.store.manifest(self.run_id)
        return self.store.events(self.run_id)

    def append(self, kind, data):
        return self.store.append(self.run_id, kind, data)

    def latest(self, kind):
        return next((event for event in reversed(self.events()) if event['kind'] == kind), None)

    def observation(self):
        started, finished = self.latest('observation_started'), self.latest('observation')
        if not finished or (started and started['sequence'] > finished['sequence']):
            return None
        return finished['data']['resources']

    def request(self, method, path, ids=None, params=None, body=None, content_type=None):
        return compose(self.operations[method + ' ' + path], {'invoice_id': self.invoice_id, **(ids or {})}
                       if '{invoice_id}' in path else (ids or {}), params or {}, body, content_type)

    def call(self, request, phase, step_id=None):
        try:
            report = self.executor(request)
        except (Exception, KeyboardInterrupt) as exc:
            report = {'environment': 'SANDBOX', 'result': 'outcome_unknown' if request.method != 'GET' else 'read_failed',
                      'error_type': type(exc).__name__, 'attempted_preview': preview(request)}
        self.append('http', {'step_id': step_id, 'phase': phase, 'report': report})
        return report

    def get(self, path, ids=None, params=None, *, phase, step_id, deadline):
        if deadline is not None and self.clock() >= deadline:
            raise ValueError('Read verification deadline reached; outcome needs reconciliation.')
        request = self.request('GET', path, ids, params)
        report = self.call(request, phase, step_id)
        output = report.get('output', {})
        if report.get('error_type') or output.get('status_code') != 200 or not isinstance(output.get('body'), dict):
            raise ValueError('GET failed or returned an unexpected body; actual I/O is saved.')
        return output['body']

    def observe(self, *, phase='baseline', step_id=None, deadline=None):
        with self.store.lock():
            self.append('observation_started', {'phase': phase, 'step_id': step_id})
            try:
                invoice = self.get(INVOICE, params={'view': 'full'}, phase=phase, step_id=step_id, deadline=deadline)
                scope = self.definition['scope']
                if (str(invoice.get('id')) != self.invoice_id or code(invoice.get('owner')) != scope['owner']
                        or code(invoice.get('vendor')) != scope['vendor']):
                    raise ValueError('Invoice identity, owner or vendor is outside this run scope. No write allowed.')
                lines, total = {}, None
                for page in range(self.definition['bounds']['line_pages']):
                    body = self.get(INVOICE + '/lines', params={'limit': 100, 'offset': page * 100},
                                    phase=phase, step_id=step_id, deadline=deadline)
                    rows = body.get('invoice_line', [])
                    if not isinstance(rows, list):
                        raise ValueError('Unexpected invoice-line collection')
                    if total is None:
                        total = body.get('total_record_count')
                    for row in rows:
                        if not row.get('id') or str(row['id']) in lines:
                            raise ValueError('Missing/duplicate invoice-line ID; completeness is unverified.')
                        lines[str(row['id'])] = row
                    if not rows or (total is not None and len(lines) >= int(total)) or (total is None and len(rows) < 100):
                        break
                else:
                    raise ValueError('Invoice-line page bound reached; incomplete inspection blocks writes.')
                if total is not None and len(lines) != int(total):
                    raise ValueError('Invoice-line count changed or is incomplete; inspect again before a write.')
                pol_ids = sorted({str(code(line.get('po_line'))) for line in lines.values() if code(line.get('po_line'))})
                if len(pol_ids) > self.definition['bounds']['po_lines']:
                    raise ValueError('Linked-order inspection bound exceeded; incomplete inspection blocks writes.')
                orders = {}
                for identifier in pol_ids:
                    order = self.get('/almaws/v1/acq/po-lines/{po_line_id}', {'po_line_id': identifier},
                                     phase=phase, step_id=step_id, deadline=deadline)
                    if str(order.get('number')) != identifier:
                        raise ValueError('Linked PO-line identity mismatch')
                    orders[identifier] = order
                resources = {'invoice': invoice, 'lines': lines, 'po_lines': orders}
                self.append('observation', {'phase': phase, 'step_id': step_id, 'resources': resources,
                                             'route': routing(invoice), 'complete_within_bounds': True})
                return resources
            except (ValueError, TypeError) as exc:
                self.append('observation_failed', {'phase': phase, 'step_id': step_id, 'reason': str(exc)})
                raise

    def action_blockers(self, action, resources):
        if not resources:
            return ['Obtain a complete baseline inspection first.']
        invoice = resources['invoice']
        if code(invoice.get('invoice_status')) != 'ACTIVE':
            return ['Only ACTIVE invoices can enter an experiment; CLOSED is a no-op.']
        workflow = code(invoice.get('invoice_workflow_status'))
        if action == 'process':
            return [] if workflow == 'InReview' else ['PROCESS is currently restricted to an In Review experiment.']
        if action == 'pay':
            return pay_blockers(invoice)
        if action in ('update_invoice', 'update_line'):
            return [] if workflow == 'InReview' else ['Guided corrections are currently restricted to In Review.']
        return ['This action is not supported by the frozen workflow definition.']

    def plan(self, action, hypothesis, checks, *, body=None, content_type='application/json', line_id=None, payment_intent=None):
        with self.store.lock():
            resources = self.observation()
            blockers = self.action_blockers(action, resources)
            if action not in self.definition['actions']:
                blockers.append('Action is not in this workflow version.')
            if blockers:
                raise ValueError(' '.join(blockers))
            if not hypothesis.strip() or not checks:
                raise ValueError('A hypothesis and at least one explicit expectation are required.')
            for check in checks:
                if (check.get('operator') not in ('equals', 'one_of', 'unchanged', 'date_equals', 'decimal_equals')
                        or not check.get('path', '').startswith(('invoice.', 'lines.', 'po_lines.'))
                        or (check['operator'] != 'unchanged' and 'value' not in check)
                        or (check['operator'] == 'one_of' and not isinstance(check['value'], list))):
                    raise ValueError('Invalid expected-result check')
                if (check['operator'] == 'unchanged' and isinstance(field(resources, check['path']), dict)
                        and 'field_missing' in field(resources, check['path'])):
                    raise ValueError('Expected-result field is absent from baseline: ' + check['path'])
            invariants = [{'path': 'invoice.owner', 'operator': 'unchanged', 'role': 'invariant'},
                          {'path': 'invoice.vendor', 'operator': 'unchanged', 'role': 'invariant'}]
            if action in ('process', 'update_invoice', 'update_line'):
                invariants.append({'path': 'invoice.payment', 'operator': 'unchanged', 'role': 'invariant'})
            if action == 'process':
                request = self.request('POST', INVOICE, params={'op': 'process_invoice'}, body={}, content_type='application/json')
            elif action == 'pay':
                if payment_intent not in ('sandbox_simulation', 'confirmed_existing_payment'):
                    raise ValueError('Record whether this is a Sandbox simulation or a confirmed existing payment.')
                validated = payment_body({key: value for key, value in body['payment'].items()
                                          if key != 'voucher_currency'} | {'voucher_currency': code(body['payment']['voucher_currency'])})
                request = self.request('POST', INVOICE, params={'op': 'paid'}, body=validated, content_type='application/json')
            else:
                ids = {}
                if action == 'update_line':
                    if line_id not in resources['lines']:
                        raise ValueError('Choose a line from the inspected invoice.')
                    ids['invoice_line_id'] = line_id
                request = self.request('PUT', LINE if ids else INVOICE, ids, body=body, content_type=content_type)
            step = {'step_id': 'step-' + uuid.uuid4().hex[:12], 'action': action, 'hypothesis': hypothesis,
                    'checks': deepcopy(checks) + invariants, 'before': deepcopy(resources),
                    'request': {'operation': request.operation, 'path': request.path, 'parameters': request.parameters,
                                'body': request.body, 'content_type': request.content_type},
                    'preview': preview(request), 'payment_intent': payment_intent,
                    'configuration': self.definition['configuration']}
            self.append('planned', step)
            return step

    def unresolved(self):
        pending = []
        for run_id in self.store.list_runs():
            manifest = self.store.manifest(run_id)
            if manifest['invoice_id'] != self.invoice_id:
                continue
            events = self.store.events(run_id)
            for event in events:
                if event['kind'] != 'dispatch_started':
                    continue
                step_id = event['data']['step_id']
                related = [item for item in events if item['data'].get('step_id') == step_id]
                verified = [item for item in related if item['kind'] == 'verification']
                resolved = any(item['kind'] == 'resolved' for item in related)
                if not resolved and (not verified or verified[-1]['data']['verdict'] != 'supported_for_this_case'):
                    pending.append((run_id, step_id))
        return pending

    def perform(self, step, *, confirmer):
        with self.store.lock():
            # Reload the original plan; callers cannot alter expectations or payloads.
            saved = next((event['data'] for event in self.events() if event['kind'] == 'planned'
                          and event['data']['step_id'] == step['step_id']), None)
            if saved != step:
                raise ValueError('Plan changed; save a new experiment instead of altering the run.')
            if any(event['kind'] == 'dispatch_started' and event['data']['step_id'] == step['step_id'] for event in self.events()):
                raise ValueError('This step was already attempted. Reconcile with GET; never replay it.')
            if self.unresolved():
                raise ValueError('An earlier write for this invoice is unresolved. Resume its run and reconcile first.')
            fresh = self.observe(phase='preflight', step_id=step['step_id'])
            if fresh != step['before']:
                self.append('preflight_changed', {'step_id': step['step_id'], 'changes': changes(step['before'], fresh)})
                raise ValueError('Records changed since planning. No write sent; inspect and create a new step.')
            blockers = self.action_blockers(step['action'], fresh)
            if blockers:
                raise ValueError(' '.join(blockers))
            request = Request(**step['request'])
            fingerprint = digest({'request': step['request'], 'before': fresh})
            for run_id in self.store.list_runs():
                if any(event['kind'] == 'dispatch_started' and event['data'].get('fingerprint') == fingerprint
                       for event in self.store.events(run_id)):
                    raise ValueError('The same request against this same state was already attempted; no duplicate dispatch.')
            if not confirmer(request):
                self.append('cancelled', {'step_id': step['step_id'], 'reason': 'Operator did not confirm. Preflight GETs only.'})
                return None
            self.append('confirmed', {'step_id': step['step_id'], 'request_preview_sha256': digest(step['preview'])})
            # Durable marker BEFORE sending: a crash here is deliberately uncertain.
            self.append('dispatch_started', {'step_id': step['step_id'], 'fingerprint': fingerprint})
            self.call(request, 'mutation', step['step_id'])
            return self.verify(step)

    def verify(self, step):
        with self.store.lock():
            events = self.events()
            saved = next((event['data'] for event in events if event['kind'] == 'planned'
                          and event['data']['step_id'] == step['step_id']), None)
            if saved != step:
                raise ValueError('Plan changed; reconciliation must use the original saved expectations.')
            if not any(event['kind'] == 'dispatch_started' and event['data']['step_id'] == step['step_id'] for event in events):
                raise ValueError('No dispatched step to reconcile. Inspect the baseline instead.')
            policy = self.definition['verification']
            maximum = min(5, max(1, int(policy['max_reads'])))
            deadline = self.clock() + min(30, max(1, float(policy['deadline_seconds'])))
            after, results, reason = None, [], None
            mutation = next((event['data']['report'] for event in reversed(events)
                             if event['kind'] == 'http' and event['data']['phase'] == 'mutation'
                             and event['data']['step_id'] == step['step_id']), None)
            accepted = bool(mutation and mutation.get('result') == 'http_success_business_outcome_unverified')
            output = mutation.get('output', {}) if mutation else {}
            error_body = output.get('body')
            api_error = isinstance(error_body, dict) and (error_body.get('errorsExist') is True or bool(error_body.get('errorList')))
            rejected = bool(output.get('status_code') and (not 200 <= output['status_code'] < 300 or api_error))
            if rejected:
                accepted = False
            for attempt in range(maximum):
                try:
                    after = self.observe(phase='verification', step_id=step['step_id'], deadline=deadline)
                    results = compare(step['checks'], step['before'], after)
                    if all(result['passed'] for result in results) or any(
                            not result['passed'] and result.get('role') == 'invariant' for result in results):
                        break
                except ValueError as exc:
                    reason = str(exc)
                    break
                if attempt + 1 < maximum and self.clock() < deadline:
                    self.sleep(min(float(policy['interval_seconds']), max(0, deadline - self.clock())))
            if reason:
                verdict = 'inconclusive'
            elif any(not result['passed'] and result.get('role') == 'invariant' for result in results):
                verdict = 'contradicted'
            elif rejected:
                verdict = 'request_failed'
            elif results and all(result['passed'] for result in results):
                verdict = 'supported_for_this_case' if accepted else 'state_observed_request_outcome_unknown'
            else:
                verdict = 'inconclusive'
            result = {'step_id': step['step_id'], 'verdict': verdict, 'request_accepted': accepted,
                      'checks': results, 'reason': reason, 'changes': changes(step['before'], after) if after else [],
                      'observation_sequence': self.latest('observation')['sequence'] if after and not reason else None,
                      'closure_verified': bool(after and code(after['invoice'].get('invoice_status')) == 'CLOSED'),
                      'scope': 'Observed state after this step; no claim of sole causation or linked-order closure.'}
            self.append('verification', result)
            return result

    def interpret(self, step_id, note, *, resolve=False):
        with self.store.lock():
            if not note.strip():
                raise ValueError('An explanation is required.')
            if not any(event['kind'] == 'planned' and event['data']['step_id'] == step_id for event in self.events()):
                raise ValueError('Unknown step')
            if resolve:
                recent = self.latest('verification')
                if (not recent or recent['data']['step_id'] != step_id or not recent['data']['checks']
                        or recent['data'].get('reason') or self.observation() is None
                        or recent['data'].get('observation_sequence') != self.latest('observation')['sequence']):
                    raise ValueError('Perform a successful read-back reconciliation of this step before resolving it.')
            self.append('resolved' if resolve else 'interpretation', {'step_id': step_id, 'note': note,
                       'scope': 'Operator interpretation; original expectations, verdict and I/O remain unchanged.'})

    def revise_definition(self, lesson, *, action=None, hypothesis=None):
        with self.store.lock():
            if not lesson.strip():
                raise ValueError('Describe the proposed revision and its evidence limits.')
            definition = deepcopy(self.definition)
            if action is not None:
                if action not in definition['actions'] or not hypothesis or not hypothesis.strip():
                    raise ValueError('Select a supported action and provide its revised hypothesis.')
                definition['hypotheses'][action] = hypothesis.strip()
            definition['version'] += 1
            definition['parent_sha256'] = digest(self.definition)
            definition['lessons'].append({'at': now(), 'run_id': self.run_id, 'note': lesson,
                                         'evidence_head': self.events()[-1]['sha256'],
                                         'status': 'operator-proposed lesson; review before promotion'})
            path = self.store.root / 'workflows' / (str(definition['version']) + '-' + digest(definition)[:12] + '.json')
            atomic_json(path, definition)
            self.append('definition_proposed', {'path': str(path), 'definition_sha256': digest(definition)})
            return path
