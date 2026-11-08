"""Offline tests for one-operation hands-on execution and inspectable error output."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace


def module():
    path = Path(__file__).resolve().parents[1] / 'scripts/sandbox_get_review.py'
    spec = importlib.util.spec_from_file_location('sandbox_get_review_test', path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def args(test='vendor'):
    return SimpleNamespace(test=test, vendor_code='SYNTHETIC', library_code='LIB',
                           invoice_id=None, po_line_id=None, limit=None)


class Client:
    def __init__(self, *, status=200, body=None, fail=False):
        self._session = SimpleNamespace(hooks={'response': []}, max_redirects=30)
        self.calls = []
        self.status, self.body, self.fail = status, body, fail

    def get(self, path, params=None):
        self.calls.append((path, params))
        prepared = SimpleNamespace(method='GET', url='https://example.invalid/' + path + '?apikey=SECRET',
                                   headers={'Authorization': 'SECRET', 'Accept': 'application/json'}, body=None)
        raw = SimpleNamespace(status_code=self.status, reason='synthetic', request=prepared,
                              headers={'Set-Cookie': 'SECRET', 'Content-Type': 'application/json'},
                              json=lambda: self.body)
        for hook in self._session.hooks['response']:
            hook(raw)
        if self.fail:
            raise RuntimeError('SECRET EXCEPTION')


def test_vendor_makes_one_get_and_preserves_output_with_authentication_masked():
    m = module()
    client = Client(body={'code': 'SYNTHETIC', 'id': 'synthetic-record-id'})
    report = m.capture(client, args())
    assert len(client.calls) == 1
    assert report['result'] == 'passed_in_tested_scope'
    assert report['output']['body']['id'] == 'synthetic-record-id'
    assert 'SECRET' not in json.dumps(report)
    assert client._session.hooks['response'] == []
    assert client._session.max_redirects == 0


def test_empty_invoice_search_is_not_confirmed():
    m = module()
    client = Client(body={'invoice': [], 'total_record_count': 0})
    report = m.capture(client, args('invoices'))
    assert len(client.calls) == 1
    assert report['result'] == 'not_confirmed'
    assert report['output']['body']['invoice'] == []


def test_http_error_still_has_inspectable_response_content():
    m = module()
    client = Client(status=400, body={'errorList': {'error': [{'errorMessage': 'Unknown vendor'}]}}, fail=True)
    report = m.capture(client, args())
    assert report['result'] == 'failed'
    assert report['output']['status_code'] == 400
    assert report['output']['body']['errorList']['error'][0]['errorMessage'] == 'Unknown vendor'
    assert 'SECRET' not in json.dumps(report)
    assert len(client.calls) == 1


def test_default_is_preview_without_network(monkeypatch, capsys):
    import sys
    m = module()
    monkeypatch.setattr(sys, 'argv', ['sandbox_get_review.py', 'vendor', '--vendor-code', 'SYNTHETIC'])
    assert m.main() == 0
    result = json.loads(capsys.readouterr().out)
    assert result['preview_only'] is True
    assert result['method'] == 'GET'
