#!/usr/bin/env python3
"""Bounded, GET-only Alma Sandbox contract observations; no payment operations."""
import argparse
import contextlib
import io
import json
import logging
from urllib.parse import quote, urlparse


def value(obj):
    return obj.get('value') if isinstance(obj, dict) else obj


def run(library_code, vendor_code, limit):
    from almaapitk import AlmaAPIClient
    from importlib.metadata import version
    report = {'environment': 'SANDBOX', 'sdk_version': version('almaapitk'), 'method': 'GET',
              'scope': 'bounded read contracts only; no write/transition claims', 'checks': []}
    client = AlmaAPIClient('SANDBOX', timeout=15, max_retries=0)
    try:
        route = urlparse(client.base_url)
        if route.scheme != 'https' or route.hostname != 'api-eu.hosted.exlibrisgroup.com':
            raise ValueError('Unexpected API route')

        def get(path, params=None):
            response = client.get(path, params=params)
            if response.status_code != 200:
                raise ValueError('Non-200 read')
            return response.json()

        libraries = get('almaws/v1/conf/libraries').get('library', [])
        report['checks'].append({'id': 'library-code', 'passed': any(x.get('code') == library_code for x in libraries)})
        vendor = get('almaws/v1/acq/vendors/' + quote(vendor_code, safe=''))
        report['checks'].append({'id': 'vendor-code', 'passed': vendor.get('code') == vendor_code})
        page = get('almaws/v1/acq/invoices', {'q': 'vendor_code~' + vendor_code, 'owner': library_code,
                                             'base_status': 'ACTIVE', 'view': 'brief', 'limit': str(limit)})
        invoices = page.get('invoice', [])
        report['api_total_active_population'] = page.get('total_record_count')
        report['returned'] = len(invoices)
        report['coverage_complete'] = len(invoices) == page.get('total_record_count')
        if not invoices:
            report['checks'].append({'id': 'invoice-state-shapes', 'passed': None, 'reason': 'No records to inspect'})
            return report
        report['checks'].append({'id': 'filters-on-returned-page', 'passed': all(
            value(x.get('owner')) == library_code and value(x.get('vendor')) == vendor_code
            and value(x.get('invoice_status')) == 'ACTIVE' for x in invoices)})
        invoice_id = quote(str(invoices[0]['id']), safe='')
        invoice = get('almaws/v1/acq/invoices/' + invoice_id)
        report['checks'].append({'id': 'nested-payment-field', 'passed': isinstance(invoice.get('payment'), dict)
                                 and isinstance(invoice['payment'].get('payment_status'), dict),
                                 'top_level_payment_status_present': 'payment_status' in invoice})
        lines = get('almaws/v1/acq/invoices/' + invoice_id + '/lines', {'limit': '100'})
        entries = lines.get('invoice_line', [])
        report['first_invoice_line_count_returned'] = len(entries)
        report['first_invoice_line_total'] = lines.get('total_record_count')
        refs = [value(x.get('po_line')) for x in entries if value(x.get('po_line'))]
        if refs:
            pol = get('almaws/v1/acq/po-lines/' + quote(str(refs[0]), safe=''))
            report['checks'].append({'id': 'linked-pol-read', 'passed': isinstance(pol, dict),
                                     'classification_fields_present': [x for x in ('type', 'material_type', 'owner', 'status') if x in pol]})
        return report
    finally:
        client.close()


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
            code = 1 if any(x['passed'] is False for x in report['checks']) else 0
        except Exception as exc:
            report = {'environment': 'SANDBOX', 'result': 'incomplete', 'error_type': type(exc).__name__}
            code = 1
    print(json.dumps(report, indent=2))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
