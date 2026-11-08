#!/usr/bin/env python3
"""Look up a documented API contract and its dated validation evidence offline."""
import argparse
import json
from pathlib import Path


def describe_operation(catalog, method, path):
    operation = catalog['operations'][method.upper() + ' ' + path]
    validation = operation.get('validation', {'status': 'not_live_tested',
                                             'last_tested_at': None, 'evidence_ids': []})
    return {'contract_source': catalog['source'],
            'documentation_checked_on': catalog['retrieved_date'],
            **operation, 'validation': validation}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--method', required=True)
    parser.add_argument('--path', required=True)
    args = parser.parse_args()
    catalog = json.loads((Path(__file__).resolve().parents[1] / 'references/api-contracts.json').read_text())
    try:
        result = describe_operation(catalog, args.method, args.path)
    except KeyError:
        parser.error('Operation absent from this snapshot; check the exact documented trailing slash and current official API')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
