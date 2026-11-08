"""Offline behavioral coverage for the Acquisitions request composer."""
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def cli(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / 'scripts'))
    spec = importlib.util.spec_from_file_location('request_cli_under_test', ROOT / 'scripts/sandbox_request_cli.py')
    result = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, result)
    spec.loader.exec_module(result)
    return result


def operation(method='GET', path='/almaws/v1/acq/vendors/{vendorCode}', *, body=False):
    return {'method': method, 'path': path,
            'parameters': [{'name': 'vendorCode', 'in': 'path', 'required': True, 'schema': {'type': 'string'}}],
            'request_body': {'required': True, 'content': {'application/json': {}, 'application/xml': {}}} if body else None}


def test_id_is_encoded_not_interpreted_as_another_path(cli):
    request = cli.compose(operation(), {'vendorCode': 'synthetic/a b'}, {})
    assert request.path.endswith('synthetic%2Fa%20b')
    with pytest.raises(ValueError, match='Invalid path'):
        cli.compose(operation(), {'vendorCode': '..'}, {})


def test_unknown_query_and_missing_id_are_rejected(cli):
    with pytest.raises(ValueError, match='Missing path'):
        cli.compose(operation(), {}, {})
    with pytest.raises(ValueError, match='Undocumented query'):
        cli.compose(operation(), {'vendorCode': 'synthetic'}, {'apikey': 'not-allowed'})


def test_required_body_and_documented_service_action(cli):
    op = operation('POST', '/almaws/v1/acq/invoices/{invoice_id}', body=True)
    op['parameters'] = [{'name': 'invoice_id', 'in': 'path', 'required': True, 'schema': {'type': 'string'}},
                        {'name': 'op', 'in': 'query', 'required': True, 'schema': {'type': 'string'}}]
    op['documented_op_values'] = ['paid', 'process_invoice']
    with pytest.raises(ValueError, match='requires an explicit request body'):
        cli.compose(op, {'invoice_id': 'synthetic'}, {'op': 'paid'})
    with pytest.raises(ValueError, match='Undocumented service action'):
        cli.compose(op, {'invoice_id': 'synthetic'}, {'op': 'close'}, {}, 'application/json')
    request = cli.compose(op, {'invoice_id': 'synthetic'}, {'op': 'paid'}, {}, 'application/json')
    assert request.body == {}
    assert cli.confirmation_phrase(request) == 'PAY'


def test_parameter_types_and_bounds(cli):
    assert cli.convert_parameter({'name': 'enabled', 'schema': {'type': 'boolean'}}, 'TRUE') == 'true'
    with pytest.raises(ValueError, match='between 0 and 100'):
        cli.convert_parameter({'name': 'limit', 'schema': {'type': 'integer'}}, '101')
    with pytest.raises(ValueError, match='integer'):
        cli.convert_parameter({'name': 'limit', 'schema': {'type': 'integer'}}, '1.5')


def test_body_formats_are_validated(cli):
    op = operation('PUT', body=True)
    with pytest.raises(ValueError, match='JSON object'):
        cli.compose(op, {'vendorCode': 'synthetic'}, {}, [], 'application/json')
    with pytest.raises(Exception):
        cli.compose(op, {'vendorCode': 'synthetic'}, {}, '<broken>', 'application/xml')
    request = cli.compose(op, {'vendorCode': 'synthetic'}, {}, '<vendor/>', 'application/xml')
    assert request.body == '<vendor/>'


def test_preview_and_wrong_confirmation_do_not_authorize_writes(cli):
    request = cli.compose(operation('PUT', body=True), {'vendorCode': 'synthetic'}, {}, {}, 'application/json')
    assert cli.authorize(request, send=False, reader=lambda _: pytest.fail('Unexpected prompt')) is False
    assert cli.authorize(request, send=True, reader=lambda _: 'yes', writer=lambda _: None) is False
    assert cli.authorize(request, send=True, reader=lambda _: cli.confirmation_phrase(request), writer=lambda _: None) is True


def test_confirmation_is_the_short_action_word(cli):
    op = operation('POST', '/almaws/v1/acq/invoices/{invoice_id}', body=True)
    op['parameters'] = [{'name': 'invoice_id', 'in': 'path', 'required': True, 'schema': {'type': 'string'}},
                        {'name': 'op', 'in': 'query', 'required': True, 'schema': {'type': 'string'}}]
    op['documented_op_values'] = ['paid', 'process_invoice']
    process = cli.compose(op, {'invoice_id': 'synthetic'}, {'op': 'process_invoice'}, {}, 'application/json')
    put = cli.compose(operation('PUT', body=True), {'vendorCode': 'synthetic'}, {}, {}, 'application/json')
    assert cli.confirmation_phrase(process) == 'PROCESS'
    assert cli.confirmation_phrase(put) == 'PUT'
    quiet = dict(writer=lambda _: None)
    assert cli.authorize(process, send=True, reader=lambda _: ' process ', **quiet) is True
    assert cli.authorize(process, send=True, reader=lambda _: 'PAY', **quiet) is False
    assert cli.authorize(process, send=True, reader=lambda _: '', **quiet) is False


class FakeClient:
    def __init__(self, *, status=200, fail=False):
        self._session = SimpleNamespace(hooks={'response': []}, max_redirects=30)
        self.status, self.fail, self.calls = status, fail, []

    def _call(self, method, path, **kwargs):
        self.calls.append((method, path, kwargs))
        prepared = SimpleNamespace(method=method, url='https://example.invalid/' + path,
                                   headers={'Authorization': 'SECRET'}, body=kwargs.get('data'))
        raw = SimpleNamespace(request=prepared, status_code=self.status, reason='synthetic',
                              headers={'Set-Cookie': 'SECRET'}, json=lambda: {'message': 'synthetic response'})
        for hook in self._session.hooks['response']:
            hook(raw)
        if self.fail:
            raise RuntimeError('SECRET error text')

    def get(self, path, **kwargs):
        return self._call('GET', path, **kwargs)

    def post(self, path, **kwargs):
        return self._call('POST', path, **kwargs)

    def put(self, path, **kwargs):
        return self._call('PUT', path, **kwargs)

    def delete(self, path, **kwargs):
        return self._call('DELETE', path, **kwargs)


@pytest.mark.parametrize('method', ['GET', 'POST', 'PUT', 'DELETE'])
def test_method_dispatch_is_exactly_one_sdk_call(cli, method):
    client = FakeClient()
    request = cli.compose(operation(method), {'vendorCode': 'synthetic'}, {})
    report = cli.capture_request(client, request)
    assert len(client.calls) == 1
    assert client.calls[0][0] == method
    assert report['result'] == 'http_success_business_outcome_unverified'
    assert 'SECRET' not in json.dumps(report)
    assert client._session.hooks['response'] == []
    assert client._session.max_redirects == 30


def test_json_is_serialized_when_explicit_content_type_is_used(cli):
    client = FakeClient()
    request = cli.compose(operation('PUT', body=True), {'vendorCode': 'synthetic'}, {}, {'name': 'Synthetic'}, 'application/json')
    cli.capture_request(client, request)
    sent = client.calls[0][2]
    assert json.loads(sent['data']) == {'name': 'Synthetic'}
    assert sent['content_type'] == 'application/json'


def test_http_error_body_is_retained_without_exception_or_authentication_values(cli):
    client = FakeClient(status=400, fail=True)
    request = cli.compose(operation(), {'vendorCode': 'synthetic'}, {})
    report = cli.capture_request(client, request)
    assert report['result'] == 'failed'
    assert report['output']['body']['message'] == 'synthetic response'
    assert 'SECRET' not in json.dumps(report)


def test_interactive_vendor_get_previews_before_single_send(cli):
    op = operation()
    answers = iter(['1', '1', '1', 'synthetic', '1', 'n'])
    output, sent = [], []

    def execute(request):
        sent.append(request)
        return {'result': 'http_success_business_outcome_unverified', 'input': {'method': 'GET'}, 'output': {'body': {'code': 'synthetic'}}}

    code = cli.interactive({'GET ' + op['path']: op}, reader=lambda _: next(answers), writer=output.append,
                           executor=execute, saver=lambda _: ('local.json', 'local.html'))
    assert code == 0 and len(sent) == 1
    transcript = '\n'.join(output)
    assert transcript.index('REQUEST PREVIEW') < transcript.index('ACTUAL INPUT AND OUTPUT')
    assert 'synthetic' in transcript


def test_interactive_put_cancel_never_calls_executor(cli):
    op = operation('PUT', body=True)
    answers = iter(['3', '1', '1', 'synthetic', '3', '{}', '1', 'NO', '0'])
    result = cli.interactive({'PUT ' + op['path']: op}, reader=lambda _: next(answers), writer=lambda _: None,
                             executor=lambda _: pytest.fail('Cancelled write reached executor'))
    assert result == 0


def test_saved_html_contains_actual_input_and_output(cli, tmp_path):
    report = {'input': {'method': 'GET', 'url': 'https://example.invalid'},
              'output': {'status_code': 200, 'body': {'code': '<synthetic>'}}, 'result': 'unverified'}
    json_path, html_path = cli.save_report(report, tmp_path)
    assert json.loads(json_path.read_text()) == report
    rendered = html_path.read_text()
    assert '&lt;synthetic&gt;' in rendered
    assert '<h2>Input</h2>' in rendered and '<h2>Output</h2>' in rendered


def test_collection_and_detail_resolution_uses_named_ids(cli):
    collection = operation('GET', '/almaws/v1/acq/vendors')
    collection['parameters'] = []
    detail = operation()
    operations = {'GET ' + collection['path']: collection, 'GET ' + detail['path']: detail}
    args = SimpleNamespace(operation=None, object='vendor', method='GET')
    assert cli.resolve_operation(operations, args, {}) is collection
    assert cli.resolve_operation(operations, args, {'vendorCode': 'synthetic'}) is detail


def test_real_catalog_vendor_lookup_is_not_ambiguous_with_vendor_relations(cli):
    args = SimpleNamespace(operation=None, object='vendor', method='GET')
    selected = cli.resolve_operation(cli.load_operations(), args, {'vendorCode': 'synthetic'})
    assert selected['path'] == '/almaws/v1/acq/vendors/{vendorCode}'
    assert cli.object_name('/almaws/v1/acq/vendors/{vendorCode}/invoices') == 'vendor-invoice'


@pytest.mark.parametrize('error', [TimeoutError, KeyboardInterrupt])
def test_write_without_response_has_unknown_outcome_and_no_retry(cli, error):
    class InterruptedClient(FakeClient):
        def put(self, path, **kwargs):
            self.calls.append(('PUT', path, kwargs))
            raise error()

    client = InterruptedClient()
    request = cli.compose(operation('PUT', body=True), {'vendorCode': 'synthetic'}, {}, {}, 'application/json')
    report = cli.capture_request(client, request)
    assert report['result'] == 'outcome_unknown'
    assert 'Read back' in report['verification']
    assert len(client.calls) == 1
    assert client._session.hooks['response'] == []
