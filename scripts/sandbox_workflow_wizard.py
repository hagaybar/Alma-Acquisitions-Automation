"""Guided, journaled Central Library/RIALTO Sandbox experiments. No automatic writes."""
import argparse
import json
from pathlib import Path

from sandbox_invoice_desk import label, payment_body
from sandbox_request_cli import authorize, body_from_file, choose, load_operations
from sandbox_terminal import display
from sandbox_workflow import DEFAULT_DEFINITION, DEFAULT_STORE, Workflow, load_definition, routing
from sandbox_workflow_store import Store


def expectation(path, value, operator='equals'):
    return {'path': path, 'operator': operator, 'value': value, 'role': 'expectation'}


def custom_checks(reader, writer):
    writer('Use an inspected field, e.g. invoice.number or lines.<line-id>.price.\n'
           'Values accept JSON numbers/objects/strings; unquoted text is treated as a string.')
    checks = []
    while True:
        path = reader('Expected field path (Enter finishes): ').strip()
        if not path:
            return checks
        text = reader('Expected value: ').strip()
        try:
            value = json.loads(text)
        except ValueError:
            value = text
        checks.append(expectation(path, value))


def build_step(workflow, reader, writer):
    resources = workflow.observation()
    actions = ['process', 'pay', 'update_invoice', 'update_line']
    labels = {'process': 'PROCESS: advance invoice workflow (not automatic approval)',
              'pay': 'PAY: record payment confirmation', 'update_invoice': 'PUT invoice: explicit correction body',
              'update_line': 'PUT invoice line: explicit correction body'}
    options = []
    for action in actions:
        blockers = workflow.action_blockers(action, resources)
        options.append((labels[action] + (' [HOLD: ' + ' '.join(blockers) + ']' if blockers else ''), action))
    action = choose('Choose one experiment', options, reader=reader, writer=writer)
    if action is None:
        return None
    blockers = workflow.action_blockers(action, resources)
    if blockers:
        raise ValueError(' '.join(blockers))
    writer('\nStarting hypothesis: ' + workflow.definition['hypotheses'][action])
    hypothesis = reader('Your hypothesis (Enter keeps the text above): ').strip() or workflow.definition['hypotheses'][action]
    body, content_type, line_id, intent = None, 'application/json', None, None
    if action == 'process':
        target = choose('What do you expect this one PROCESS call to do?', [
            ('Reach Waiting for Payment (API Ready to be Paid)', 'Ready to be Paid'),
            ('Reach manual approval', 'InApproval'), ('Close the invoice', 'CLOSED'),
            ('Remain In Review (a diagnostic experiment)', 'InReview'),
            ('Enter my own field expectations', 'custom')], reader=reader, writer=writer)
        if target is None:
            return None
        checks = custom_checks(reader, writer) if target == 'custom' else [expectation(
            'invoice.invoice_status.value' if target == 'CLOSED' else 'invoice.invoice_workflow_status.value', target)]
    elif action == 'pay':
        intent = choose('What does this payment information represent?', [
            ('An explicitly labelled Sandbox simulation', 'sandbox_simulation'),
            ('An existing payment whose details I have confirmed', 'confirmed_existing_payment')], reader=reader, writer=writer)
        if intent is None:
            return None
        values = {key: reader(prompt) for key, prompt in [
            ('voucher_date', 'Payment date YYYY-MM-DD: '), ('voucher_number', 'Payment identifier/reference: '),
            ('voucher_amount', 'Final paid amount: '), ('voucher_currency', 'Payment currency: ')]}
        body = payment_body(values)
        checks = [expectation('invoice.invoice_status.value', 'CLOSED'),
                  expectation('invoice.payment.payment_status.value', 'PAID'),
                  expectation('invoice.payment.voucher_number', body['payment']['voucher_number']),
                  expectation('invoice.payment.voucher_date', body['payment']['voucher_date'], 'date_equals'),
                  expectation('invoice.payment.voucher_amount', body['payment']['voucher_amount'], 'decimal_equals'),
                  expectation('invoice.payment.voucher_currency.value', body['payment']['voucher_currency']['value'])]
    else:
        writer('PUT is a documented update, not a merge patch. Review the full body: lists such as notes\n'
               'can replace existing lists. This prototype does not validate the complete body schema.\n'
               'Payment information must remain unchanged in a correction experiment.')
        if action == 'update_line':
            line_id = choose('Select an inspected invoice line', [(key, key) for key in resources['lines']], reader=reader, writer=writer)
            if line_id is None:
                return None
        body, content_type = body_from_file(reader('JSON/XML correction body file: ').strip())
        checks = custom_checks(reader, writer)
    step = workflow.plan(action, hypothesis, checks, body=body, content_type=content_type,
                         line_id=line_id, payment_intent=intent)
    display('SAVED EXPERIMENT | no write sent', [
        'Step: ' + step['step_id'] + '\nHypothesis: ' + step['hypothesis'],
        json.dumps(step['preview'], ensure_ascii=False, indent=2),
        'EXPECTED RESULTS (frozen for this step)\n' + json.dumps(step['checks'], ensure_ascii=False, indent=2),
        'Choose Run saved step to obtain fresh preflight GETs and confirm the one write.'], writer=writer)
    reader('Enter to return to the wizard: ')
    return step


def show_result(result, writer):
    if result is None:
        writer('Cancelled. No write sent; preflight GETs were recorded.')
        return
    display('EXPECTED vs ACTUAL | ' + result['verdict'], [
        'Closure verified by GET: ' + str(result['closure_verified']) + '\n'
        'Request accepted: ' + str(result['request_accepted']) + '\n'
        'Reason: ' + str(result.get('reason') or '-'),
        json.dumps(result['checks'], ensure_ascii=False, indent=2),
        'ALL OBSERVED CHANGES\n' + json.dumps(result['changes'], ensure_ascii=False, indent=2),
        'Original expectations and evidence are retained. No next write runs automatically.'], writer=writer)


def run_screen(workflow, *, reader=input, writer=print):
    notice = 'Opening/resuming a run sends nothing. Inspect or reconcile before deciding on a write.'
    while True:
        resources = workflow.observation()
        invoice = resources['invoice'] if resources else {}
        step_event, verified = workflow.latest('planned'), workflow.latest('verification')
        state = '\n'.join(name + ': ' + label(invoice.get(name)) for name in
                          ('invoice_status', 'invoice_workflow_status', 'invoice_approval_status'))
        payment = label((invoice.get('payment') or {}).get('payment_status'))
        display('INVOICE WORKFLOW WIZARD | SANDBOX / EU | no active ERP integration', [
            'Run: ' + workflow.run_id + ' | Workflow version: ' + str(workflow.definition['version']) + '\n'
            'Invoice ID: ' + workflow.invoice_id + '\n' + state + '\nPayment: ' + payment,
            routing(invoice) if resources else 'Baseline missing/incomplete: complete inspection required.',
            'Saved step: ' + (step_event['data']['step_id'] + ' / ' + step_event['data']['action'] if step_event else '-') + '\n'
            'Latest verdict: ' + (verified['data']['verdict'] if verified else '(not tested)') + '\n' + notice,
            '1 Inspect / refresh (automatic GETs)\n2 Build one experiment\n3 Run saved step (confirm one write)\n'
            '4 Reconcile attempted step (automatic GETs only)\n5 Full evidence / report\n'
            '6 Add interpretation / resolve a hold\n7 Propose a revised workflow version\n0 Back'
        ], writer=writer)
        try:
            choice = reader('Choose: ').strip()
            if choice == '0':
                return 0
            if choice == '1':
                writer('GET inspection: invoice, all lines within bounds, and linked PO lines. No writes.')
                workflow.observe()
                notice = 'Baseline recorded. Inspect the route and build one experiment.'
            elif choice == '2':
                step = build_step(workflow, reader, writer)
                notice = 'Experiment saved; nothing sent.' if step else 'Experiment selection cancelled.'
            elif choice == '3':
                if not step_event:
                    raise ValueError('Build an experiment first.')
                step = step_event['data']
                writer('Preflight GETs will check the invoice, lines and linked orders against the saved baseline.')

                def confirm(request):
                    display('ONE WRITE TO CONFIRM | SANDBOX', [json.dumps(step['preview'], ensure_ascii=False, indent=2),
                            'Hypothesis: ' + step['hypothesis'], 'Expected checks:\n' + json.dumps(step['checks'], indent=2),
                            'After confirmation: one write, then automatic bounded GET verification.'], writer=writer)
                    return authorize(request, send=True, reader=reader, writer=writer)

                result = workflow.perform(step, confirmer=confirm)
                show_result(result, writer)
                reader('Enter to return: ')
                notice = 'Result recorded; inspect expectations and actual changes before the next decision.'
            elif choice == '4':
                attempted = [event for event in workflow.events() if event['kind'] == 'dispatch_started']
                if not attempted:
                    raise ValueError('No attempted step in this run. Use Inspect instead.')
                identifier = choose('Choose an attempted step to reconcile',
                                    [(event['data']['step_id'], event['data']['step_id']) for event in attempted],
                                    reader=reader, writer=writer)
                if identifier:
                    step = next(event['data'] for event in workflow.events()
                                if event['kind'] == 'planned' and event['data']['step_id'] == identifier)
                    show_result(workflow.verify(step), writer)
                    reader('Enter to return: ')
            elif choice == '5':
                report = workflow.store.report(workflow.run_id)
                writer(json.dumps(report, ensure_ascii=False, indent=2))
                writer('JSON / HTML: ' + str(workflow.store.folder(workflow.run_id) / 'report.html'))
                reader('Enter to return: ')
            elif choice == '6':
                plans = [event['data'] for event in workflow.events() if event['kind'] == 'planned']
                identifier = choose('Which step?', [(step['step_id'], step['step_id']) for step in plans], reader=reader, writer=writer)
                if identifier:
                    note = reader('Interpretation and evidence/reason: ').strip()
                    phrase = 'RESOLVE ' + identifier
                    writer('Resolution lifts a hold after successful read-back; it does not change the verdict or replay a request.\n'
                           'To resolve, type ' + phrase + '; Enter records a note only.')
                    workflow.interpret(identifier, note, resolve=reader('Decision: ').strip() == phrase)
                    notice = 'Interpretation appended; original evidence preserved.'
            elif choice == '7':
                action = choose('Revise a hypothesis, or record a lesson only',
                                [('Record a lesson only', 'lesson')] + [(action, action) for action in workflow.definition['actions']],
                                reader=reader, writer=writer)
                if action is None:
                    continue
                hypothesis = reader('Revised hypothesis: ').strip() if action != 'lesson' else None
                path = workflow.revise_definition(reader('Evidence / lesson and its limits: ').strip(),
                                                  action=None if action == 'lesson' else action, hypothesis=hypothesis)
                notice = 'New local workflow version: ' + str(path) + '. Existing run unchanged.'
            else:
                notice = 'Choose a displayed number.'
            workflow.store.report(workflow.run_id)
        except (ValueError, OSError, KeyError) as exc:
            notice = str(exc) + ' No automatic write retry. Preserve evidence and reconcile any attempted step.'
        except (EOFError, KeyboardInterrupt):
            writer('\nStopped. Saved evidence remains; resume with the run ID. No automatic replay.')
            return 0


def interactive(operations, *, reader=input, writer=print, store=None, resume=None, executor=None, sleep=None):
    store = store or Store(DEFAULT_STORE)
    options = [('New experiment run', 'new')] + [(identifier, identifier) for identifier in store.list_runs()]
    identifier = resume or choose('Workflow test runs', options, reader=reader, writer=writer)
    if identifier is None:
        return 0
    kwargs = {key: value for key, value in [('executor', executor), ('sleep', sleep)] if value is not None}
    if identifier == 'new':
        candidates = [DEFAULT_DEFINITION] + sorted((store.root / 'workflows').glob('*.json'))
        path = candidates[0] if len(candidates) == 1 else choose('Workflow definition (copied into the run)',
                       [(path.name, path) for path in candidates], reader=reader, writer=writer)
        if path is None:
            return 0
        definition = load_definition(path)
        invoice_id = reader('Alma Sandbox internal invoice ID (not invoice number): ').strip()
        writer('Confirm the current Sandbox context: Central Library AC1 / RIALTO;\n'
               'invoice_skip_erp=true; handle_invoice_payment=true; NO active ERP integration.\n'
               'This is your confirmation, not a configuration API observation.')
        if reader('Type CONFIRM SANDBOX CONFIG (Enter cancels): ').strip() != 'CONFIRM SANDBOX CONFIG':
            return 0
        workflow = Workflow.create(store, operations, invoice_id, definition=definition,
                                   configuration_note='Operator confirmed displayed Sandbox settings; no active ERP integration.', **kwargs)
    else:
        workflow = Workflow(store, operations, identifier, **kwargs)
        writer('Resuming saved expectations. Confirm settings still match: ERP skipped, payment handling enabled, no active ERP integration.')
        if reader('Type CONFIRM SANDBOX CONFIG (Enter cancels): ').strip() != 'CONFIRM SANDBOX CONFIG':
            return 0
        workflow.append('configuration_reconfirmed', {'configuration': workflow.definition['configuration'], 'source': 'operator on resume'})
    return run_screen(workflow, reader=reader, writer=writer)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--resume', metavar='RUN_ID', help='Resume through inspection/reconciliation, never automatic replay')
    parser.add_argument('--list-runs', action='store_true', help='List local run IDs without API calls')
    parser.add_argument('--report', metavar='RUN_ID', help='Generate and print a local evidence report without API calls')
    args = parser.parse_args(argv)
    store = Store(DEFAULT_STORE)
    try:
        if args.list_runs:
            print('\n'.join(store.list_runs()) or 'No runs recorded.')
            return 0
        if args.report:
            print(json.dumps(store.report(args.report), ensure_ascii=False, indent=2))
            print('HTML: ' + str(store.folder(args.report) / 'report.html'))
            return 0
        return interactive(load_operations(), store=store, resume=args.resume)
    except (ValueError, OSError, KeyError) as exc:
        parser.error(str(exc))
    except (EOFError, KeyboardInterrupt):
        print('\nStopped. No automatic replay; resume a saved run through reconciliation.')
        return 0


if __name__ == '__main__':
    raise SystemExit(main())
