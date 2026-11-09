#!/usr/bin/env python3
"""Bounded, GET-only Alma Sandbox observations with dated, redacted evidence."""
import argparse
import contextlib
from datetime import datetime
import io
import json
import logging
from urllib.parse import quote, urlparse
from zoneinfo import ZoneInfo


def timestamp():
    return datetime.now(ZoneInfo('Asia/Jerusalem')).isoformat(timespec='seconds')


def value(obj):
    return obj.get('value') if isinstance(obj, dict) else obj


def run(library_code, vendor_code, limit):
    from almaapitk import AlmaAPIClient
    from importlib.metadata import version
    report = {'environment': 'SANDBOX', 'sdk_version': version('almaapitk'),
              'started_at': timestamp(), 'timezone': 'Asia/Jerusalem', 'method': 'GET',
              'scope': 'bounded read contracts only; no write/transition claims',
              'operations': [], 'checks': []}
    client = None
    try:
        client = AlmaAPIClient('SANDBOX', timeout=15, max_retries=0)
        route = urlparse(client.base_url)
        if route.scheme != 'https' or route.hostname != 'api-eu.hosted.exlibrisgroup.com':
            raise ValueError('Unexpected API route')

        def get(path, contract_path, params=None):
            observation = {'operation': 'GET ' + contract_path,
                           'tested_at': timestamp(), 'parameter_names': sorted(params or {})}
            report['operations'].append(observation)
            try:
                response = client.get(path, params=params)
                observation['http_status'] = response.status_code
                if response.status_code != 200:
                    raise ValueError('Non-200 read')
                return response.json()
            except Exception as exc:
                observation['error_type'] = type(exc).__name__
                status = getattr(exc, 'status_code', None)
                if isinstance(status, int):
                    observation['http_status'] = status
                raise

        libraries = get('almaws/v1/conf/libraries', '/almaws/v1/conf/libraries').get('library', [])
        report['checks'].append({'id': 'library-code', 'operation': 'GET /almaws/v1/conf/libraries',
                                 'passed': any(x.get('code') == library_code for x in libraries)})
        vendor = get('almaws/v1/acq/vendors/' + quote(vendor_code, safe=''),
                     '/almaws/v1/acq/vendors/{vendorCode}')
        report['checks'].append({'id': 'vendor-code', 'operation': 'GET /almaws/v1/acq/vendors/{vendorCode}',
                                 'passed': vendor.get('code') == vendor_code})
        page = get('almaws/v1/acq/invoices', '/almaws/v1/acq/invoices/',
                   {'q': 'vendor_code~' + vendor_code, 'owner': library_code,
                    'base_status': 'ACTIVE', 'view': 'brief', 'limit': str(limit)})
        invoices = page.get('invoice', [])
        report['invoice_search'] = {'q_field': 'vendor_code', 'owner': 'supplied-library-code',
                                    'vendor': 'supplied-vendor-code', 'base_status': 'ACTIVE',
                                    'view': 'brief', 'limit': limit,
                                    'requested_path_variant': '/almaws/v1/acq/invoices'}
        report['api_total_active_population'] = page.get('total_record_count')
        report['returned'] = len(invoices)
        report['coverage_complete'] = len(invoices) == page.get('total_record_count')
        if not invoices:
            report['checks'].append({'id': 'filters-on-returned-page',
                                     'operation': 'GET /almaws/v1/acq/invoices/',
                                     'passed': None, 'reason': 'No records to inspect'})
            return report
        report['checks'].append({'id': 'filters-on-returned-page',
                                 'operation': 'GET /almaws/v1/acq/invoices/', 'passed': all(
            value(x.get('owner')) == library_code and value(x.get('vendor')) == vendor_code
            and value(x.get('invoice_status')) == 'ACTIVE' for x in invoices)})
        invoice_id = quote(str(invoices[0]['id']), safe='')
        invoice = get('almaws/v1/acq/invoices/' + invoice_id, '/almaws/v1/acq/invoices/{invoice_id}')
        report['checks'].append({'id': 'nested-payment-field',
                                 'operation': 'GET /almaws/v1/acq/invoices/{invoice_id}',
                                 'passed': isinstance(invoice.get('payment'), dict)
                                 and isinstance(invoice['payment'].get('payment_status'), dict),
                                 'top_level_payment_status_present': 'payment_status' in invoice})
        lines = get('almaws/v1/acq/invoices/' + invoice_id + '/lines',
                    '/almaws/v1/acq/invoices/{invoice_id}/lines', {'limit': '100'})
        entries = lines.get('invoice_line', [])
        report['first_invoice_line_count_returned'] = len(entries)
        report['first_invoice_line_total'] = lines.get('total_record_count')
        report['checks'].append({'id': 'invoice-line-list-shape',
                                 'operation': 'GET /almaws/v1/acq/invoices/{invoice_id}/lines',
                                 'passed': isinstance(entries, list)})
        refs = [value(x.get('po_line')) for x in entries if value(x.get('po_line'))]
        if refs:
            pol = get('almaws/v1/acq/po-lines/' + quote(str(refs[0]), safe=''),
                      '/almaws/v1/acq/po-lines/{po_line_id}')
            present = [x for x in ('type', 'material_type', 'owner', 'status') if x in pol]
            report['checks'].append({'id': 'linked-pol-classification-shape',
                                     'operation': 'GET /almaws/v1/acq/po-lines/{po_line_id}',
                                     'passed': all(value(pol.get(x)) is not None
                                                   for x in ('type', 'material_type', 'owner', 'status')),
                                     'classification_fields_present': present})
        else:
            report['checks'].append({'id': 'linked-pol-classification-shape',
                                     'operation': 'GET /almaws/v1/acq/po-lines/{po_line_id}',
                                     'passed': None, 'reason': 'No linked PO-line in inspected invoice'})
    except Exception as exc:
        report['error_type'] = type(exc).__name__
    finally:
        if client is not None:
            client.close()
        report['completed_at'] = timestamp()
        failed = 'error_type' in report or any(x['passed'] is False for x in report['checks'])
        incomplete = any(x['passed'] is None for x in report['checks'])
        report['result'] = 'failed' if failed else ('partial' if incomplete else 'passed_in_tested_scope')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library-code', required=True)
    parser.add_argument('--vendor-code', required=True)
    parser.add_argument('--limit', type=int, default=3)
    parser.add_argument('--live-readonly', action='store_true', help='Explicitly opt into bounded Sandbox GETs')
    args = parser.parse_args()
    if not args.live_readonly or not 1 <= args.limit <= 10:
        parser.error('Use --live-readonly and a limit from 1 to 10')
    if not args.library_code.strip() or not args.vendor_code.strip():
        parser.error('Nonempty configuration codes are required')
    logging.disable(logging.CRITICAL)
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        try:
            report = run(args.library_code, args.vendor_code, args.limit)
        except Exception as exc:
            report = {'environment': 'SANDBOX', 'completed_at': timestamp(),
                      'result': 'failed', 'error_type': type(exc).__name__}
    print(json.dumps(report, indent=2))
    return 1 if report['result'] == 'failed' else 0


if __name__ == '__main__':
    raise SystemExit(main())
