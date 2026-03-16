#!/usr/bin/env python3
import sys
from almaapitk import AlmaAPIClient
from almaapitk import Acquisitions

  # Get POL ID from command line
if len(sys.argv) < 2:
    print("Usage: python test_get_pol.py <POL_ID>")
    sys.exit(1)

pol_id = sys.argv[1]

# Initialize
client = AlmaAPIClient('SANDBOX')
acq = Acquisitions(client)

print(f"\nTesting Get POL: {pol_id}")
print("=" * 60)

try:
    # Get POL data
    pol_data = acq.get_pol(pol_id)

    # Display results
    print("\n✓ SUCCESS: POL retrieved")
    print(f"\nPOL Number: {pol_data.get('number', 'N/A')}")
    print(f"Status: {pol_data.get('status', {}).get('value', 'N/A')}")
    print(f"Type: {pol_data.get('type', {}).get('value', 'N/A')}")
    print(f"Vendor: {pol_data.get('vendor', {}).get('value', 'N/A')} - {pol_data.get('vendor', {}).get('desc', 'N/A')}")

    # Items
    if 'item' in pol_data:
        items = pol_data['item'] if isinstance(pol_data['item'], list) else [pol_data['item']]
        print(f"Items: {len(items)} item(s)")
    else:
        print("Items: No items found")

    print("\n=== All POL Fields ===")
    for key in sorted(pol_data.keys()):
        print(f"  - {key}")

    print("\n✓ TEST PASSED")

except Exception as e:
    print(f"\n✗ TEST FAILED: {e}")
    sys.exit(1)