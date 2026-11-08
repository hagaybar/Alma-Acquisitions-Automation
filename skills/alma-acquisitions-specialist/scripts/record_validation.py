#!/usr/bin/env python3
"""Record reviewed, dated Sandbox GET evidence beside documented API contracts."""
import argparse
from datetime import datetime
import json
from pathlib import Path


SCOPES = {
    'GET /almaws/v1/acq/vendors/{vendorCode}': ('vendor-code', 'Exact lookup of one supplied vendor code.'),
    'GET /almaws/v1/acq/invoices/': ('filters-on-returned-page', 'Vendor-code query, owner, ACTIVE and brief filters on one bounded page; not all query combinations or pages.'),
    'GET /almaws/v1/acq/invoices/{invoice_id}': ('nested-payment-field', 'One invoice detail: nested payment-status shape; no mutation or workflow transition.'),
    'GET /almaws/v1/acq/invoices/{invoice_id}/lines': ('invoice-line-list-shape', 'Invoice-line list shape for one invoice and one bounded page; no line mutations.'),
    'GET /almaws/v1/acq/po-lines/{po_line_id}': ('linked-pol-classification-shape', 'One linked PO-line: type/material/owner/status fields present; no receiving or activation.'),
}


def annotate(catalog, report=None):
    if report is not None:
        if report.get('environment') != 'SANDBOX' or report.get('method') != 'GET':
            raise ValueError('Only Sandbox GET reports are supported')
        for operation in report.get('operations', []):
            if not operation.get('operation', '').startswith('GET '):
                raise ValueError('Report contains a non-GET observation')
            date = datetime.fromisoformat(operation['tested_at'])
            if date.utcoffset() is None:
                raise ValueError('Live test timestamps must include a timezone offset')
    catalog['status'] = 'Documented contract snapshot; live validation is recorded per operation'
    catalog['validation_note'] = 'A tested operation is confirmed only within the recorded scope; date is not a guarantee of current validity.'
    checks = {x['id']: x for x in (report or {}).get('checks', [])}
    observed = {x['operation']: x for x in (report or {}).get('operations', [])}
    for key, operation in catalog['operations'].items():
        validation = operation.setdefault('validation', {
            'status': 'not_live_tested', 'last_tested_at': None,
            'last_result': None, 'evidence_ids': [], 'tested_scope': None,
            'limits': 'No live test for this operation is recorded.'})
        if key not in observed:
            continue
        event = observed[key]
        definition = SCOPES.get(key)
        check = checks.get(definition[0]) if definition else None
        if 'error_type' in event or event.get('http_status') != 200:
            status, outcome = 'sandbox_test_failed', 'failed'
        elif check and check.get('passed') is True and check.get('operation') == key:
            status, outcome = 'sandbox_tested_partial', 'passed_in_tested_scope'
        elif check and check.get('passed') is False:
            status, outcome = 'sandbox_test_failed', 'assertion_failed'
        else:
            status, outcome = 'http_observed_only', 'semantic_assertion_not_established'
        validation.update({
            'status': status, 'last_tested_at': event['tested_at'], 'last_result': outcome,
            'environment': 'SANDBOX', 'sdk_version': report['sdk_version'],
            'evidence_ids': [definition[0]] if definition and check else [],
            'tested_scope': definition[1] if definition else 'HTTP observation only',
            'limits': 'Other records, configurations, parameter combinations and transitions are not established.',
            'evidence_file': 'validation-evidence.json',
        })
    return catalog


def overview(catalog):
    lines = ['# API validation status', '',
             'Official documentation checked: **' + catalog['retrieved_date'] + '**. This is separate from live testing.', '',
             'The last-tested date identifies an observation, not an expiry date or a guarantee. A partial pass covers only its listed scope.', '',
             'See [the redacted live report](validation-evidence.json) for per-operation timestamps and assertions. The supporting libraries GET is outside the Acquisitions catalog.', '',
             '| Operation | Validation | Last tested (Asia/Jerusalem) | Result |',
             '|---|---|---|---|']
    for key, op in catalog['operations'].items():
        v = op['validation']
        lines.append('| `' + key + '` | ' + v['status'] + ' | ' + (v['last_tested_at'] or 'Not tested') + ' | ' + (v['last_result'] or '—') + ' |')
    lines += ['', '## Tested scope', '']
    for key, op in catalog['operations'].items():
        if op['validation']['last_tested_at']:
            lines.append('- `' + key + '`: ' + op['validation']['tested_scope'])
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path)
    parser.add_argument('--write', action='store_true', help='Explicitly update the canonical reference files')
    args = parser.parse_args()
    refs = Path(__file__).resolve().parents[1] / 'references'
    catalog = json.loads((refs / 'api-contracts.json').read_text())
    report = json.loads(args.report.read_text()) if args.report else None
    annotate(catalog, report)
    if args.write:
        (refs / 'api-contracts.json').write_text(json.dumps(catalog, indent=2) + '\n')
        (refs / 'validation-status.md').write_text(overview(catalog))
        if report:
            # Input must be the reviewed redacted probe report, never a raw API payload.
            (refs / 'validation-evidence.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'write': args.write, 'operations': len(catalog['operations']),
                      'tested_operations': sum(bool(x['validation']['last_tested_at']) for x in catalog['operations'].values())}))


if __name__ == '__main__':
    main()
