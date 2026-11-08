#!/usr/bin/env python3
"""Look up a documented API contract offline; never calls an API."""
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--method', required=True)
    parser.add_argument('--path', required=True)
    args = parser.parse_args()
    catalog = json.loads((Path(__file__).resolve().parents[1] / 'references/api-contracts.json').read_text())
    key = args.method.upper() + ' ' + args.path
    operation = catalog['operations'].get(key)
    if operation is None:
        parser.error('Operation absent from this snapshot; check the exact documented trailing slash and current official API')
    print(json.dumps({'verdict': 'documented, untested', 'source': catalog['source'], **operation}, indent=2))


if __name__ == '__main__':
    main()
