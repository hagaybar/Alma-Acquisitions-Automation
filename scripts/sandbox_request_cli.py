#!/usr/bin/env python3
"""Interactive request composer for the Acquisitions Sandbox prototype."""
import argparse
import contextlib
from dataclasses import dataclass
from datetime import datetime
import html
import io
import json
import logging
from importlib.metadata import version
from pathlib import Path
import re
import sys
import time
from urllib.parse import quote, urlencode, urlparse
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

from sandbox_get_review import mask_headers, now, scrub


ROOT = Path(__file__).resolve().parents[1]
HOST = 'https://api-eu.hosted.exlibrisgroup.com'
METHODS = ('GET', 'POST', 'PUT', 'DELETE')
AUTH_PARAMS = {'apikey', 'api_key', 'authorization', 'access_token', 'refresh_token', 'password', 'token'}
LABELS = {'invoice': 'Invoices', 'invoice-line': 'Invoice lines', 'invoice-attachment': 'Invoice attachments',
          'vendor': 'Vendors', 'vendor-invoice': 'Invoices for a vendor', 'vendor-po-line': 'PO lines for a vendor',
          'po-line': 'PO lines', 'po-line-item': 'PO line items',
          'fund': 'Funds', 'fund-transaction': 'Fund transactions', 'license': 'Licenses',
          'license-attachment': 'License attachments', 'license-amendment': 'License amendments',
          'currency': 'Currencies', 'fiscal-period': 'Fiscal periods',
          'purchase-request': 'Purchase requests', 'test': 'Acquisitions connection test',
          'library': 'Libraries supporting lookup'}


@dataclass
class Request:
    operation: dict
    path: str
    parameters: dict
    body: object = None
    content_type: str | None = None

    @property
    def method(self):
        return self.operation['method']


def object_name(path):
    if path.startswith('/almaws/v1/conf/libraries'):
        return 'library'
    parts = path.strip('/').split('/')[3:]
    first = parts[0]
    if first == 'invoices':
        return 'invoice-line' if 'lines' in parts else ('invoice-attachment' if 'attachments' in parts else 'invoice')
    if first == 'po-lines':
        return 'po-line-item' if 'items' in parts else 'po-line'
    if first == 'funds':
        return 'fund-transaction' if 'transactions' in parts else 'fund'
    if first == 'vendors':
        return 'vendor-invoice' if 'invoices' in parts else ('vendor-po-line' if 'po-lines' in parts else 'vendor')
    if first == 'licenses':
        return 'license-amendment' if 'amendments' in parts else ('license-attachment' if 'attachments' in parts else 'license')
    return {'vendors': 'vendor', 'currencies': 'currency', 'fiscal-periods': 'fiscal-period',
            'purchase-requests': 'purchase-request', 'test': 'test'}.get(first, first)


def load_operations():
    path = ROOT / 'skills/alma-acquisitions-specialist/references/api-contracts.json'
    catalog = json.loads(path.read_text())
    operations = dict(catalog['operations'])
    library_validation = {'status': 'supporting lookup not live-tested in this catalog', 'last_tested_at': None}
    evidence = path.parent / 'validation-evidence.json'
    if evidence.exists():
        recorded = json.loads(evidence.read_text())
        if any(x.get('id') == 'library-code' and x.get('passed') is True for x in recorded.get('checks', [])):
            observed = next((x for x in recorded.get('operations', []) if x.get('operation') == 'GET /almaws/v1/conf/libraries'), None)
            if observed:
                library_validation = {'status': 'sandbox_tested_partial', 'last_tested_at': observed['tested_at'],
                                      'tested_scope': 'Supplied library code found in returned list; supporting Configuration lookup.'}
    operations['GET /almaws/v1/conf/libraries'] = {
        'method': 'GET', 'path': '/almaws/v1/conf/libraries', 'parameters': [],
        'validation': library_validation}
    return operations


def pairs(values):
    result = {}
    for value in values or []:
        name, separator, content = value.partition('=')
        if not separator or not name or not content:
            raise ValueError('Use NAME=VALUE, for example limit=1')
        if name in result:
            raise ValueError('Duplicate parameter: ' + name)
        result[name] = content
    return result


def convert_parameter(definition, value):
    schema = definition.get('schema', {})
    kind = schema.get('type', 'string')
    if kind == 'integer':
        if isinstance(value, bool) or not re.fullmatch(r'-?\d+', str(value)):
            raise ValueError(definition['name'] + ' must be an integer')
        value = int(value)
        if definition['name'] == 'limit' and not 0 <= value <= 100:
            raise ValueError('limit must be between 0 and 100')
        if definition['name'] == 'offset' and value < 0:
            raise ValueError('offset must not be negative')
        if 'minimum' in schema and value < schema['minimum']:
            raise ValueError(definition['name'] + ' is below its minimum')
        if 'maximum' in schema and value > schema['maximum']:
            raise ValueError(definition['name'] + ' is above its maximum')
    elif kind == 'boolean':
        if str(value).lower() not in ('true', 'false'):
            raise ValueError(definition['name'] + ' must be true or false')
        value = str(value).lower()
    if schema.get('enum') and value not in schema['enum']:
        raise ValueError(definition['name'] + ' must be one of ' + ', '.join(map(str, schema['enum'])))
    return value


def compose(operation, ids, parameters, body=None, content_type=None):
    if operation['method'] not in METHODS:
        raise ValueError('Unsupported method in this prototype')
    definitions = operation.get('parameters', [])
    path_fields = {p['name']: p for p in definitions if p.get('in') == 'path'}
    query_fields = {p['name']: p for p in definitions if p.get('in') == 'query'}
    if set(ids) - set(path_fields):
        raise ValueError('Unknown path parameter: ' + ', '.join(sorted(set(ids) - set(path_fields))))
    if set(parameters) - set(query_fields):
        raise ValueError('Undocumented query parameter: ' + ', '.join(sorted(set(parameters) - set(query_fields))))
    if any(name.lower() in AUTH_PARAMS for name in parameters):
        raise ValueError('Authentication is supplied by the Sandbox SDK, not query arguments')
    path = operation['path']
    for name, definition in path_fields.items():
        if name not in ids or not str(ids[name]).strip():
            raise ValueError('Missing path parameter: ' + name)
        text = str(convert_parameter(definition, ids[name]))
        if text in ('.', '..'):
            raise ValueError('Invalid path identifier')
        path = path.replace('{' + name + '}', quote(text, safe=''))
    if re.search(r'\{[^}]+\}', path) or not path.startswith(('/almaws/v1/acq/', '/almaws/v1/conf/libraries')):
        raise ValueError('Unresolved or unsupported path')
    params = {}
    for name, definition in query_fields.items():
        if name in parameters:
            params[name] = convert_parameter(definition, parameters[name])
        elif definition.get('required'):
            raise ValueError('Missing required query parameter: ' + name)
    if 'op' in params and operation.get('documented_op_values') and params['op'] not in operation['documented_op_values']:
        raise ValueError('Undocumented service action: ' + str(params['op']))
    contract = operation.get('request_body') or {}
    if contract.get('required') and body is None:
        raise ValueError('This operation requires an explicit request body; use --json or --body-file')
    if body is not None:
        if operation['method'] in ('GET', 'DELETE') or not contract:
            raise ValueError('This documented operation does not accept a body in this prototype')
        allowed = contract.get('content', {})
        if content_type not in ('application/json', 'application/xml') or content_type not in allowed:
            raise ValueError('This prototype supports documented JSON/XML bodies only; binary/multipart composition is deferred')
        if content_type == 'application/json' and not isinstance(body, dict):
            raise ValueError('The prototype currently accepts a JSON object body')
        if content_type == 'application/xml':
            ET.fromstring(body)
    return Request(operation, path, params, body, content_type)


def preview(request):
    validation = request.operation.get('validation', {})
    return {'environment': 'SANDBOX', 'method': request.method,
            'url': HOST + request.path + ('?' + urlencode(request.parameters) if request.parameters else ''),
            'parameters': request.parameters, 'content_type': request.content_type,
            'body': scrub(request.body), 'reference_status': validation.get('status', 'not_live_tested'),
            'last_tested_at': validation.get('last_tested_at'),
            'tested_scope': validation.get('tested_scope'),
            'scope': 'One request; HTTP success alone does not verify a business outcome.'}


ACTION_WORDS = {'paid': 'PAY', 'process_invoice': 'PROCESS', 'mark_in_erp': 'MARK_IN_ERP', 'rejected': 'REJECT'}


def confirmation_phrase(request):
    if 'op' in request.parameters:
        op = str(request.parameters['op'])
        return ACTION_WORDS.get(op, op.upper())
    return request.method


def authorize(request, *, send=False, reader=input, writer=print):
    if not send:
        return False
    if request.method == 'GET':
        return True
    phrase = confirmation_phrase(request)
    suffix = ' op=' + str(request.parameters['op']) if 'op' in request.parameters else ''
    writer('This request changes Sandbox data: ' + request.method + ' ' + request.path + suffix)
    writer('Review the body and action above, then type ' + phrase + ' to send.')
    try:
        return reader('Action word (Enter cancels): ').strip().upper() == phrase
    except (EOFError, KeyboardInterrupt):
        return False


def capture_request(client, request):
    report = {'environment': 'SANDBOX', 'started_at': now(), 'timezone': 'Asia/Jerusalem',
              'operation': request.method + ' ' + request.operation['path'], 'result': 'incomplete'}
    if request.method != 'GET':
        report['verification'] = 'Read back the target state before retrying; the business outcome is not verified by this tool.'
    wire = {}

    def remember(response, *args, **kwargs):
        wire['response'] = response
        return response

    hooks = client._session.hooks.setdefault('response', [])
    hooks.append(remember)
    old_redirects = client._session.max_redirects
    client._session.max_redirects = 0
    start = time.perf_counter()
    try:
        kwargs = {'params': request.parameters or None}
        if request.body is not None:
            # AlmaAPITK uses data= when content_type is explicit, so serialize JSON.
            kwargs['data'] = json.dumps(request.body) if request.content_type == 'application/json' else request.body
            kwargs['content_type'] = request.content_type
        getattr(client, request.method.lower())(request.path.lstrip('/'), **kwargs)
    except Exception as exc:
        report['error_type'] = type(exc).__name__
    except KeyboardInterrupt:
        report['error_type'] = 'KeyboardInterrupt'
    finally:
        hooks.remove(remember)
        client._session.max_redirects = old_redirects
    report['completed_at'] = now()
    report['client_duration_seconds'] = round(time.perf_counter() - start, 4)
    raw = wire.get('response')
    if raw is None:
        report['result'] = 'failed_without_captured_http_response' if request.method == 'GET' else 'outcome_unknown'
        return report
    try:
        body = raw.json()
    except ValueError:
        body = raw.text
    report['input'] = {'method': raw.request.method, 'url': scrub(raw.request.url),
                       'headers': mask_headers(raw.request.headers), 'body': scrub(raw.request.body)}
    report['output'] = {'status_code': raw.status_code, 'reason': raw.reason,
                        'headers': mask_headers(raw.headers), 'body': scrub(body)}
    report['result'] = ('http_success_business_outcome_unverified'
                        if 200 <= raw.status_code < 300 and 'error_type' not in report else 'failed')
    if request.method != 'GET' and report.get('error_type') == 'KeyboardInterrupt':
        report['result'] = 'outcome_unknown'
    return report


def execute(request):
    logging.disable(logging.CRITICAL)
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        from almaapitk import AlmaAPIClient
        client = AlmaAPIClient('SANDBOX', timeout=15, max_retries=0)
        try:
            route = urlparse(client.base_url)
            if client.environment != 'SANDBOX' or route.scheme != 'https' or route.hostname != urlparse(HOST).hostname:
                raise ValueError('Unexpected environment or API host')
            report = capture_request(client, request)
            report['sdk_version'] = version('almaapitk')
        finally:
            client.close()
    return report


def save_report(report, directory=None):
    directory = directory or ROOT / 'output/sandbox-review'
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(ZoneInfo('Asia/Jerusalem')).strftime('%Y%m%dT%H%M%S%f')
    target = directory / (stamp + '-request.json')
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    esc = lambda x: html.escape(json.dumps(x, ensure_ascii=False, indent=2))
    page = target.with_suffix('.html')
    page.write_text('<!doctype html><html lang="en"><meta charset="utf-8"><title>Alma Sandbox request review</title>'
                    '<style>body{font:16px/1.5 system-ui;margin:32px auto;max-width:1050px;padding:0 22px}'
                    'pre{padding:18px;background:#f2f5f8;white-space:pre-wrap;overflow-wrap:anywhere}</style>'
                    '<h1>Alma Sandbox request review</h1><p>Local capture with authentication masked. Business outcomes require separate verification.</p>'
                    '<h2>Input</h2><pre>' + esc(report.get('input', {})) + '</pre>'
                    '<h2>Output</h2><pre>' + esc(report.get('output', {})) + '</pre>'
                    '<h2>Execution metadata</h2><pre>' + esc({k: v for k, v in report.items() if k not in ('input', 'output')}) + '</pre></html>')
    return target, page


def choose(title, options, *, reader=input, writer=print):
    writer('\n' + title)
    for number, (label, value) in enumerate(options, 1):
        writer(f'  {number:>2}. {label}')
    writer('   0. Cancel')
    while True:
        text = reader('Choose a number: ').strip()
        if text == '0':
            return None
        if text.isdigit() and 1 <= int(text) <= len(options):
            return options[int(text) - 1][1]
        writer('Enter one of the displayed numbers.')


def prompt_parameter(definition, operation, *, reader=input, writer=print):
    name = definition['name']
    options = operation.get('documented_op_values') if name == 'op' else definition.get('schema', {}).get('enum')
    if options:
        return choose(name + ' options', [(str(x), x) for x in options], reader=reader, writer=writer)
    default = definition.get('schema', {}).get('default')
    hint = f' (documented default {default})' if default not in (None, '') else ''
    while True:
        value = reader(name + hint + ': ').strip()
        if value:
            try:
                return convert_parameter(definition, value)
            except ValueError as exc:
                writer(str(exc))
        else:
            writer('A value is required here; cancel with Ctrl+C.')


def body_from_file(filename, content_type=None):
    path = Path(filename).expanduser()
    text = path.read_text(encoding='utf-8-sig')
    content_type = content_type or ('application/xml' if path.suffix.lower() == '.xml' else 'application/json')
    return (json.loads(text) if content_type == 'application/json' else text), content_type


def interactive(operations, *, reader=input, writer=print, executor=execute, saver=save_report):
    writer('\nALMA REQUEST REVIEW  |  Acquisitions prototype  |  SANDBOX')
    writer('Choose a request, review its complete preview, then decide whether to send it.')
    while True:
        method = choose('Request method', [(x, x) for x in METHODS], reader=reader, writer=writer)
        if method is None:
            return 0
        objects = sorted({object_name(op['path']) for op in operations.values() if op['method'] == method})
        obj = choose('Object', [(LABELS.get(x, x), x) for x in objects], reader=reader, writer=writer)
        if obj is None:
            continue
        choices = [(key, op) for key, op in operations.items() if op['method'] == method and object_name(op['path']) == obj]
        operation = choose('Operation', choices, reader=reader, writer=writer)
        if operation is None:
            continue
        try:
            ids, params = {}, {}
            for definition in operation.get('parameters', []):
                if definition.get('in') == 'path':
                    ids[definition['name']] = prompt_parameter(definition, operation, reader=reader, writer=writer)
                elif definition.get('in') == 'query' and definition.get('required'):
                    value = prompt_parameter(definition, operation, reader=reader, writer=writer)
                    if value is None:
                        raise ValueError('Request cancelled')
                    params[definition['name']] = value
            optional = [p for p in operation.get('parameters', []) if p.get('in') == 'query' and not p.get('required')]
            if any(p['name'] == 'limit' for p in optional):
                params['limit'] = 1
            while optional:
                selected = choose('Optional query parameters', [('Continue with current parameters', False)] +
                                  [(p['name'] + (' = ' + str(params[p['name']]) if p['name'] in params else ''), p) for p in optional],
                                  reader=reader, writer=writer)
                if selected is None:
                    raise ValueError('Request cancelled')
                if selected is False:
                    break
                value = prompt_parameter(selected, operation, reader=reader, writer=writer)
                if value is None:
                    raise ValueError('Request cancelled')
                params[selected['name']] = value
            body, content_type = None, None
            contract = operation.get('request_body') or {}
            if contract:
                writer('Documented body formats: ' + ', '.join(contract.get('content', {})))
                formats = contract.get('content', {})
                choices = []
                if 'application/json' in formats:
                    choices += [('JSON file', 'json-file')]
                if 'application/xml' in formats:
                    choices += [('XML file', 'xml-file')]
                if 'application/json' in formats:
                    choices += [('Enter JSON object', 'inline')]
                if not contract.get('required'):
                    choices.insert(0, ('No request body', 'none'))
                if not choices:
                    raise ValueError('This prototype cannot compose the documented binary/multipart body')
                mode = choose('Request body', choices, reader=reader, writer=writer)
                if mode is None:
                    raise ValueError('Request cancelled')
                if mode == 'inline':
                    body, content_type = json.loads(reader('JSON object (one line): ')), 'application/json'
                elif mode != 'none':
                    body, content_type = body_from_file(reader('File path: ').strip(), 'application/xml' if mode == 'xml-file' else 'application/json')
            request = compose(operation, ids, params, body, content_type)
            from sandbox_terminal import display
            display('REQUEST PREVIEW | SANDBOX / EU', [
                'Method: ' + method + ' | Object: ' + obj + '\nOperation: ' + operation['path'],
                json.dumps(preview(request), ensure_ascii=False, indent=2)
            ], writer=writer)
            action = choose('Next action', [('Send this one Sandbox request', 'send'), ('Return to request selection', 'back')], reader=reader, writer=writer)
            if action != 'send':
                continue
            if not authorize(request, send=True, reader=reader, writer=writer):
                writer('Cancelled. No request sent.')
                continue
            report = executor(request)
            paths = saver(report)
            writer('\nACTUAL INPUT AND OUTPUT\n' + json.dumps(report, ensure_ascii=False, indent=2))
            writer('\nSaved JSON: ' + str(paths[0]) + '\nSaved HTML: ' + str(paths[1]))
        except (ValueError, OSError, ET.ParseError) as exc:
            writer('Request not sent or completed: ' + str(exc))
        if reader('\nCompose another request? [y/N]: ').strip().lower() != 'y':
            return 0


def resolve_operation(operations, args, ids):
    if args.operation:
        if args.operation not in operations:
            raise ValueError('Choose an exact documented operation from --list-operations')
        op = operations[args.operation]
        if args.method and args.method != op['method']:
            raise ValueError('--method conflicts with --operation')
        if args.object and args.object != object_name(op['path']):
            raise ValueError('--object conflicts with --operation')
        return op
    if not args.object:
        raise ValueError('Supply --object or --operation, or start the interactive menu')
    candidates = [op for op in operations.values() if op['method'] == (args.method or 'GET') and object_name(op['path']) == args.object]
    exact = [op for op in candidates if set(re.findall(r'\{([^}]+)\}', op['path'])) == set(ids)]
    if len(exact) != 1:
        alternatives = '\n'.join(op['method'] + ' ' + op['path'] for op in candidates)
        raise ValueError('Supply matching --id NAME=VALUE arguments or an exact --operation. Available:\n' + alternatives)
    return exact[0]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='Examples:\n  sandbox_get_review.py\n  sandbox_get_review.py request --method GET --object vendor --id vendorCode=SYNTHETIC\n  sandbox_get_review.py request --object invoice --param limit=1 --send\n\nLegacy vendor/invoice/lines/pol commands remain available. Use vendor --help for that interface.')
    parser.add_argument('command', nargs='?', choices=['interactive', 'request', 'invoice-desk', 'workflow-wizard'], default='interactive',
                        help='Default: app dashboard. invoice-desk opens guided GET / PAY / compare.')
    parser.add_argument('--method', choices=METHODS)
    parser.add_argument('--object', choices=sorted(LABELS))
    parser.add_argument('--operation', help='Exact documented METHOD /path template')
    parser.add_argument('--id', action='append', default=[], metavar='NAME=VALUE', help='Repeat for each path ID')
    parser.add_argument('--param', action='append', default=[], metavar='NAME=VALUE', help='Repeat for query parameters')
    body_group = parser.add_mutually_exclusive_group()
    body_group.add_argument('--json', dest='json_body', help='Explicit JSON object body')
    body_group.add_argument('--body-file', help='JSON or XML body file')
    parser.add_argument('--content-type', choices=['application/json', 'application/xml'])
    parser.add_argument('--send', action='store_true', help='Send instead of preview; writes still require typing the action word')
    parser.add_argument('--list-operations', action='store_true')
    args = parser.parse_args(argv)
    operations = load_operations()
    try:
        if args.command == 'workflow-wizard':
            from sandbox_workflow_wizard import interactive as workflow_app
            return workflow_app(operations)
        if args.command == 'invoice-desk':
            from sandbox_invoice_desk import interactive as invoice_app
            return invoice_app(operations)
        if args.list_operations:
            for key, op in operations.items():
                if (not args.method or op['method'] == args.method) and (not args.object or object_name(op['path']) == args.object):
                    print(key)
            return 0
        if args.command == 'interactive' and not args.object and not args.operation:
            from sandbox_terminal import home
            from sandbox_invoice_desk import interactive as invoice_app
            from sandbox_workflow_wizard import interactive as workflow_app
            return home(operations, composer=interactive, invoice_app=invoice_app, workflow_app=workflow_app)
        ids, params = pairs(args.id), pairs(args.param)
        operation = resolve_operation(operations, args, ids)
        body, content_type = None, args.content_type
        if args.body_file:
            body, content_type = body_from_file(args.body_file, content_type)
        elif args.json_body is not None:
            if content_type not in (None, 'application/json'):
                raise ValueError('--json requires application/json content type')
            body, content_type = json.loads(args.json_body), content_type or 'application/json'
        request = compose(operation, ids, params, body, content_type)
        print(json.dumps(preview(request), ensure_ascii=False, indent=2))
        if not args.send:
            print('\nPreview only. Add --send to execute; writes require typing the action word.')
            return 0
        if not authorize(request, send=True):
            print('Cancelled. No request sent.')
            return 0
        report = execute(request)
        paths = save_report(report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        print('\nSaved JSON: ' + str(paths[0]) + '\nSaved HTML: ' + str(paths[1]))
        return 0 if report['result'] == 'http_success_business_outcome_unverified' else 1
    except (ValueError, OSError, ET.ParseError) as exc:
        parser.error(str(exc))
    except (EOFError, KeyboardInterrupt):
        print('\nCancelled.')
        return 0


if __name__ == '__main__':
    raise SystemExit(main())
