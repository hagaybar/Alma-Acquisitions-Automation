"""Small dependency-free terminal panels; plain transcripts work without a TTY."""
import os
import re
import shutil
import sys
import textwrap


def safe_text(value):
    return re.sub(r'[\x00-\x1f\x7f-\x9f]', ' ', str(value))


def panel(title, sections, width=None):
    width = max(40, min(width or shutil.get_terminal_size((100, 30)).columns, 110))
    rule = '+' + '-' * (width - 2) + '+'
    lines = [rule]
    for text in [title, *sections]:
        for line in str(text).splitlines() or ['']:
            for wrapped in textwrap.wrap(safe_text(line), width - 4, replace_whitespace=False) or ['']:
                lines.append('| ' + wrapped.ljust(width - 4) + ' |')
        lines.append(rule)
    return '\n'.join(lines)


def display(title, sections, *, writer=print, clear=True):
    # Never emit terminal controls into tests, redirected logs or dumb terminals.
    tty = writer is print and sys.stdout.isatty() and os.environ.get('TERM') != 'dumb'
    if tty and clear:
        writer('\x1b[2J\x1b[H', end='')
    text = panel(title, sections)
    writer(('\x1b[36m' + text + '\x1b[0m') if tty and 'NO_COLOR' not in os.environ else text)


def home(operations, *, reader=input, writer=print, composer=None, invoice_app=None, workflow_app=None):
    while True:
        display('ALMA API LAB  |  SANDBOX / EU  |  Acquisitions prototype', [
            '1  Request composer   GET / POST / PUT / DELETE\n'
            '2  Invoice desk       Inspect / prepare PAY / compare states\n'
            '3  Workflow wizard    Saved hypotheses / one action / automatic GET verification\n'
            '0  Exit',
            'Choose an area. Opening the app sends no requests.\n'
            'PAY is operator-run; one Sandbox case supports its tested transition.'
        ], writer=writer)
        choice = reader('Choose: ').strip()
        if choice == '0':
            return 0
        if choice == '1':
            composer(operations, reader=reader, writer=writer)
        elif choice == '2':
            invoice_app(operations, reader=reader, writer=writer)
        elif choice == '3' and workflow_app is not None:
            workflow_app(operations, reader=reader, writer=writer)
