"""Local workflow evidence: frozen manifests, chained events, derived reports."""
from contextlib import contextmanager
import hashlib
import html
import json
import os
from pathlib import Path
import re
import tempfile
import uuid

from sandbox_get_review import now, scrub


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix='.pending-', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        # Make the rename durable before any external write is allowed.
        if os.name != 'nt':
            folder = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(folder)
            finally:
                os.close(folder)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class Store:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._depth = 0

    @contextmanager
    def lock(self):
        """Serialize cooperating wizard processes, including network dispatch."""
        if self._depth:
            self._depth += 1
            try:
                yield
            finally:
                self._depth -= 1
            return
        with (self.root / '.lock').open('a+b') as stream:
            try:
                if os.name == 'nt':
                    import msvcrt
                    stream.seek(0)
                    stream.write(b'0')
                    stream.flush()
                    stream.seek(0)
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise ValueError('Another workflow operation is using this evidence folder. Try again when it finishes.') from exc
            self._depth = 1
            try:
                yield
            finally:
                self._depth = 0
                if os.name == 'nt':
                    stream.seek(0)
                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(stream, fcntl.LOCK_UN)

    def folder(self, run_id):
        if not re.fullmatch(r'[a-zA-Z0-9_-]{1,90}', run_id):
            raise ValueError('Invalid run ID')
        folder = self.root / 'runs' / run_id
        if folder.resolve().parent != (self.root / 'runs').resolve():
            raise ValueError('Unexpected run path')
        return folder

    def create(self, manifest):
        with self.lock():
            run_id = 'run-' + uuid.uuid4().hex[:16]
            folder = self.folder(run_id)
            folder.mkdir(parents=True)
            manifest = scrub({**manifest, 'run_id': run_id, 'created_at': now()})
            atomic_json(folder / 'manifest.json', {'data': manifest, 'sha256': digest(manifest)})
            self.append(run_id, 'created', {'manifest_sha256': digest(manifest)})
            return run_id

    def manifest(self, run_id):
        record = json.loads((self.folder(run_id) / 'manifest.json').read_text(encoding='utf-8'))
        if digest(record['data']) != record['sha256']:
            raise ValueError('Run manifest integrity check failed. No write allowed.')
        events = self.events(run_id)
        if not events or events[0]['data']['manifest_sha256'] != record['sha256']:
            raise ValueError('Manifest does not match the initial event. No write allowed.')
        return record['data']

    def events(self, run_id):
        previous, records = None, []
        for sequence, path in enumerate(sorted((self.folder(run_id) / 'events').glob('*.json')), 1):
            event = json.loads(path.read_text(encoding='utf-8'))
            signature = event.pop('sha256')
            if (path.name != f'{sequence:06d}.json' or event['sequence'] != sequence
                    or event['previous_sha256'] != previous or digest(event) != signature):
                raise ValueError('Evidence integrity check failed. Preserve files and investigate; no write allowed.')
            event['sha256'] = signature
            records.append(event)
            previous = signature
        return records

    def append(self, run_id, kind, data):
        with self.lock():
            events = self.events(run_id)
            event = {'sequence': len(events) + 1, 'at': now(), 'kind': kind,
                     'previous_sha256': events[-1]['sha256'] if events else None,
                     'data': scrub(data)}
            event['sha256'] = digest(event)
            target = self.folder(run_id) / 'events' / f'{event["sequence"]:06d}.json'
            if target.exists():
                raise ValueError('Refusing to overwrite evidence')
            atomic_json(target, event)
            return event

    def list_runs(self):
        return sorted(path.name for path in (self.root / 'runs').glob('run-*') if path.is_dir())

    def report(self, run_id):
        manifest, events = self.manifest(run_id), self.events(run_id)
        steps = []
        for event in events:
            if event['kind'] != 'planned':
                continue
            data = event['data']
            related = [item for item in events if item['data'].get('step_id') == data['step_id']]
            verifications = [item['data'] for item in related if item['kind'] == 'verification']
            steps.append({'step_id': data['step_id'], 'action': data['action'], 'hypothesis': data['hypothesis'],
                          'expected': data['checks'], 'latest_verification': verifications[-1] if verifications else None,
                          'event_sequences': [item['sequence'] for item in related]})
        summary = {'manifest': manifest, 'steps': steps, 'events': events,
                   'note': 'Derived view. Frozen manifest and events are the source of truth; do not edit them.'}
        folder = self.folder(run_id)
        atomic_json(folder / 'report.json', summary)
        escaped = html.escape(json.dumps(summary, ensure_ascii=False, indent=2))
        (folder / 'report.html').write_text(
            '<!doctype html><html lang="en"><meta charset="utf-8"><title>Invoice workflow evidence</title>'
            '<style>body{font:16px/1.5 system-ui;max-width:1100px;margin:32px auto;padding:20px}'
            'pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f1f5f9;padding:20px}</style>'
            '<h1>Invoice workflow evidence</h1><p>Expected checks, actual comparisons, masked I/O and history.</p>'
            '<pre>' + escaped + '</pre></html>', encoding='utf-8')
        return summary
