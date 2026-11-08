"""Offline evidence-report tests: scope, failure history, dates and redaction."""
from datetime import datetime
import importlib.metadata
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1] / 'skills/alma-acquisitions-specialist'


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / (name + '.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


class APIError(Exception):
    status_code = 403


class Client:
    base_url = 'https://api-eu.hosted.exlibrisgroup.com'

    def __init__(self, environment, **kwargs):
        assert environment == 'SANDBOX'
        assert kwargs == {'timeout': 15, 'max_retries': 0}
        self.closed = False
        self.empty = False
        self.fail = False

    def get(self, path, params=None):
        if path == 'almaws/v1/conf/libraries':
            data = {'library': [{'code': 'PRIVATE-LIBRARY'}]}
        elif path.startswith('almaws/v1/acq/vendors/'):
            if self.fail:
                raise APIError('PRIVATE-EXCEPTION-CONTENT')
            data = {'code': 'PRIVATE-VENDOR'}
        elif path == 'almaws/v1/acq/invoices':
            records = [] if self.empty else [{'id': 'PRIVATE-INVOICE', 'owner': {'value': 'PRIVATE-LIBRARY'},
                                              'vendor': {'value': 'PRIVATE-VENDOR'},
                                              'invoice_status': {'value': 'ACTIVE'}}]
            data = {'invoice': records, 'total_record_count': 0 if self.empty else 20}
        elif path.endswith('/lines'):
            data = {'invoice_line': [{'po_line': 'PRIVATE-POL'}], 'total_record_count': 1}
        elif path.startswith('almaws/v1/acq/invoices/'):
            data = {'payment': {'payment_status': {'value': 'NOT_PAID'}}}
        elif path.startswith('almaws/v1/acq/po-lines/'):
            data = {key: {'value': 'synthetic'} for key in ('type', 'material_type', 'owner', 'status')}
        else:
            raise AssertionError('Unexpected endpoint')
        return SimpleNamespace(status_code=200, json=lambda: data)

    def close(self):
        self.closed = True


def probe(monkeypatch, *, fail=False, empty=False):
    client = Client('SANDBOX', timeout=15, max_retries=0)
    client.fail, client.empty = fail, empty
    monkeypatch.setitem(sys.modules, 'almaapitk', SimpleNamespace(AlmaAPIClient=lambda *a, **kw: client))
    monkeypatch.setattr(importlib.metadata, 'version', lambda name: 'synthetic-sdk')
    report = load('probe_read_contracts').run('PRIVATE-LIBRARY', 'PRIVATE-VENDOR', 3)
    assert client.closed
    return report


def test_success_has_dated_operation_evidence_and_no_private_values(monkeypatch):
    report = probe(monkeypatch)
    assert report['result'] == 'passed_in_tested_scope'
    assert len(report['operations']) == 6
    assert report['coverage_complete'] is False
    for item in report['operations']:
        assert datetime.fromisoformat(item['tested_at']).utcoffset() is not None
        assert item['http_status'] == 200
    assert 'PRIVATE-' not in json.dumps(report)


def test_failure_retains_prior_read_evidence_without_exception_content(monkeypatch):
    report = probe(monkeypatch, fail=True)
    assert report['result'] == 'failed'
    assert report['checks'][0]['passed'] is True
    assert len(report['operations']) == 2
    assert report['operations'][1]['http_status'] == 403
    assert 'PRIVATE-' not in json.dumps(report)


def test_empty_population_does_not_claim_filter_or_detail_validation(monkeypatch):
    report = probe(monkeypatch, empty=True)
    assert report['result'] == 'partial'
    assert report['checks'][-1]['passed'] is None
    assert len(report['operations']) == 3
    assert not any(x['id'] == 'nested-payment-field' for x in report['checks'])


def test_documentation_date_is_separate_from_null_live_test_date():
    module = load('describe_contract')
    result = module.describe_operation({'source': 'official', 'retrieved_date': '2026-11-08',
                                       'operations': {'GET /example': {'method': 'GET', 'path': '/example'}}},
                                      'GET', '/example')
    assert result['documentation_checked_on'] == '2026-11-08'
    assert result['validation']['last_tested_at'] is None
    assert result['validation']['status'] == 'not_live_tested'


def test_http_success_does_not_validate_semantics_or_other_operations():
    module = load('record_validation')
    get_key = 'GET /almaws/v1/acq/invoices/{invoice_id}'
    post_key = 'POST /almaws/v1/acq/invoices/{invoice_id}'
    catalog = {'operations': {get_key: {}, post_key: {}}}
    report = {'environment': 'SANDBOX', 'method': 'GET', 'sdk_version': 'synthetic',
              'operations': [{'operation': get_key, 'tested_at': '2026-11-08T10:00:00+02:00', 'http_status': 200}],
              'checks': []}
    module.annotate(catalog, report)
    assert catalog['operations'][get_key]['validation']['status'] == 'http_observed_only'
    assert catalog['operations'][post_key]['validation']['last_tested_at'] is None


def test_production_report_cannot_annotate_sandbox_validity():
    module = load('record_validation')
    import pytest
    with pytest.raises(ValueError, match='Sandbox GET'):
        module.annotate({'operations': {}}, {'environment': 'PRODUCTION', 'method': 'GET'})
