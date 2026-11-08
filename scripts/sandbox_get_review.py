#!/usr/bin/env python3
"""Run one explicit Alma Sandbox GET and inspect its authentication-masked input/output."""
import argparse
import contextlib
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
from urllib.parse import quote, urlparse
from zoneinfo import ZoneInfo


SECRET_HEADERS = {'authorization', 'proxy-authorization', 'cookie', 'set-cookie', 'x-api-key', 'api-key'}
SECRET_FIELDS = {'apikey', 'api_key', 'access_token', 'refresh_token', 'password', 'secret', 'authorization', 'client_secret'}


def scrub(value):
    if isinstance(value, dict):
        return {k: '[REDACTED AUTHENTICATION]' if k.lower() in SECRET_FIELDS else scrub(v) for k, v in value.items()}
    if isinstance(value, list):
        return [scrub(x) for x in value]
    if isinstance(value, bytes):
        value = value.decode('utf-8', errors='replace')
    if isinstance(value, str):
        return re.sub(r'([?&](?:apikey|api_key|access_token|refresh_token|token|password|signature)=)[^&\s"<>]*',
                      r'\1[REDACTED]', value, flags=re.I)
    return value


def mask_headers(headers):
    return {k: '[REDACTED AUTHENTICATION]' if k.lower() in SECRET_HEADERS else scrub(v) for k, v in headers.items()}


def now():
    return datetime.now(ZoneInfo('Asia/Jerusalem')).isoformat(timespec='milliseconds')


def plan(args):
    need = {'vendor': ('vendor_code',), 'invoices': ('library_code', 'vendor_code'),
            'invoice': ('invoice_id',), 'lines': ('invoice_id',), 'pol': ('po_line_id',)}
    for field in need.get(args.test, ()):
        if not getattr(args, field, None):
            raise ValueError('Missing --' + field.replace('_', '-'))
    if args.limit is not None and not 1 <= args.limit <= 100:
        raise ValueError('--limit must be from 1 to 100')
    if args.test == 'libraries':
        return 'almaws/v1/conf/libraries', {}, 'The response contains a library list.'
    if args.test == 'vendor':
        return 'almaws/v1/acq/vendors/' + quote(args.vendor_code, safe=''), {}, 'The returned vendor code equals the requested code.'
    if args.test == 'invoices':
        return 'almaws/v1/acq/invoices', {'q': 'vendor_code~' + args.vendor_code, 'owner': args.library_code,
                                         'base_status': 'ACTIVE', 'view': 'brief', 'limit': str(args.limit or 1)}, 'Returned records match owner, vendor and ACTIVE; an empty page does not confirm the predicate.'
    if args.test == 'invoice':
        return 'almaws/v1/acq/invoices/' + quote(args.invoice_id, safe=''), {}, 'The requested invoice is returned with nested payment status.'
    if args.test == 'lines':
        return 'almaws/v1/acq/invoices/' + quote(args.invoice_id, safe='') + '/lines', {'limit': str(args.limit or 100)}, 'The response contains an invoice_line list; compare returned length with the reported total.'
    return 'almaws/v1/acq/po-lines/' + quote(args.po_line_id, safe=''), {}, 'Type, material type, owner and status fields are available for interpretation.'


def scalar(value):
    return value.get('value') if isinstance(value, dict) else value


def assertion(args, body):
    if not isinstance(body, dict):
        return False
    if args.test == 'libraries':
        return isinstance(body.get('library'), list)
    if args.test == 'vendor':
        return body.get('code') == args.vendor_code
    if args.test == 'invoices':
        rows = body.get('invoice', [])
        if not rows:
            return None
        return all(scalar(x.get('owner')) == args.library_code and scalar(x.get('vendor')) == args.vendor_code
                   and scalar(x.get('invoice_status')) == 'ACTIVE' for x in rows)
    if args.test == 'invoice':
        return str(body.get('id')) == args.invoice_id and isinstance(body.get('payment', {}).get('payment_status'), dict)
    if args.test == 'lines':
        return isinstance(body.get('invoice_line'), list)
    return all(scalar(body.get(key)) is not None for key in ('type', 'material_type', 'owner', 'status'))


def capture(client, args):
    path, params, expected = plan(args)
    report = {'environment': 'SANDBOX', 'test': args.test, 'started_at': now(),
              'timezone': 'Asia/Jerusalem', 'expected': expected, 'result': 'incomplete'}
    wire = {}

    def remember(response, *unused, **kwargs):
        wire['response'] = response
        return response

    client._session.hooks.setdefault('response', []).append(remember)
    client._session.max_redirects = 0
    start = time.perf_counter()
    try:
        client.get(path, params=params or None)
    except Exception as exc:
        report['error_type'] = type(exc).__name__
    finally:
        client._session.hooks['response'].remove(remember)
    report['completed_at'] = now()
    report['client_duration_seconds'] = round(time.perf_counter() - start, 4)
    raw = wire.get('response')
    if raw is None:
        report['result'] = 'failed_without_captured_http_response'
        return report
    prepared = raw.request
    try:
        body = raw.json()
    except ValueError:
        body = raw.text
    report['input'] = {'method': prepared.method, 'url': scrub(prepared.url),
                       'parameters_supplied': params, 'headers': mask_headers(prepared.headers),
                       'body': scrub(prepared.body)}
    report['output'] = {'status_code': raw.status_code, 'reason': raw.reason,
                        'headers': mask_headers(raw.headers), 'body': scrub(body)}
    passed = assertion(args, body) if raw.status_code == 200 and 'error_type' not in report else False
    report['assertion_passed'] = passed
    report['result'] = 'passed_in_tested_scope' if passed is True else ('not_confirmed' if passed is None else 'failed')
    return report


def main():
    if len(sys.argv) > 1 and sys.argv[1] == 'workflow-wizard':
        from sandbox_workflow_wizard import main as wizard_main
        return wizard_main(sys.argv[2:])
    if len(sys.argv) == 1 or sys.argv[1].startswith('-') or sys.argv[1] in ('interactive', 'request', 'invoice-desk'):
        from sandbox_request_cli import main as request_main
        return request_main(sys.argv[1:])
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('test', choices=['libraries', 'vendor', 'invoices', 'invoice', 'lines', 'pol'])
    parser.add_argument('--library-code')
    parser.add_argument('--vendor-code')
    parser.add_argument('--invoice-id')
    parser.add_argument('--po-line-id')
    parser.add_argument('--limit', type=int)
    parser.add_argument('--live-readonly', action='store_true')
    args = parser.parse_args()
    try:
        path, params, expected = plan(args)
    except ValueError as exc:
        parser.error(str(exc))
    if not args.live_readonly:
        print(json.dumps({'preview_only': True, 'method': 'GET', 'path': path, 'parameters': params,
                          'expected': expected, 'next': 'Add --live-readonly to run this one test.'}, indent=2))
        return 0
    logging.disable(logging.CRITICAL)
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        from almaapitk import AlmaAPIClient
        client = AlmaAPIClient('SANDBOX', timeout=15, max_retries=0)
        try:
            route = urlparse(client.base_url)
            assert client.environment == 'SANDBOX' and route.scheme == 'https' and route.hostname == 'api-eu.hosted.exlibrisgroup.com'
            report = capture(client, args)
            report['sdk_version'] = version('almaapitk')
        finally:
            client.close()
    directory = Path(__file__).resolve().parents[1] / 'output/sandbox-review'
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(ZoneInfo('Asia/Jerusalem')).strftime('%Y%m%dT%H%M%S%f')
    target = directory / (stamp + '-' + args.test + '.json')
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print('\nSaved local input/output: ' + str(target))
    return 1 if report['result'].startswith('failed') else 0


if __name__ == '__main__':
    raise SystemExit(main())
