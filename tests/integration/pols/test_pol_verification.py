#!/usr/bin/env python3
"""
Test script for POL verification - checks POL status and item receive status.
Can be used to verify POLs for Rialto workflow testing.

Usage:
    python test_pol_verification.py <POL_ID>

Example:
    python test_pol_verification.py POL-5980
"""
import sys
from almaapitk import AlmaAPIClient
from almaapitk import Acquisitions

# Check command line arguments
if len(sys.argv) < 2:
    print("Usage: python test_pol_verification.py <POL_ID>")
    print("\nExample: python test_pol_verification.py POL-5980")
    sys.exit(1)

pol_id = sys.argv[1]

# Initialize
client = AlmaAPIClient('SANDBOX')
acq = Acquisitions(client)

print(f"Verifying {pol_id} in SANDBOX environment")
print("=" * 70)

try:
    # Get POL data
    pol_data = acq.get_pol(pol_id)

    print(f"\n=== POL DETAILS ===")
    print(f"POL ID: {pol_data.get('number', 'N/A')}")
    print(f"Status: {pol_data.get('status', {}).get('value', 'N/A')}")
    print(f"Type: {pol_data.get('type', {}).get('value', 'N/A')}")
    print(f"Vendor: {pol_data.get('vendor', {}).get('value', 'N/A')} - {pol_data.get('vendor', {}).get('desc', 'N/A')}")

    # Check invoice reference
    invoice_ref = pol_data.get('invoice_reference')
    print(f"Invoice Reference: {invoice_ref if invoice_ref else 'None'}")

    # Extract items
    items = acq.extract_items_from_pol_data(pol_data)

    print(f"\n=== ITEMS ANALYSIS ===")
    print(f"Total Items Found: {len(items)}")

    if items:
        unreceived_items = []
        received_items = []

        for item in items:
            item_id = item.get('pid')
            receive_date = item.get('receive_date')
            barcode = item.get('barcode', 'N/A')
            description = item.get('description', 'N/A')

            if receive_date:
                received_items.append({
                    'item_id': item_id,
                    'barcode': barcode,
                    'receive_date': receive_date,
                    'description': description
                })
            else:
                unreceived_items.append({
                    'item_id': item_id,
                    'barcode': barcode,
                    'description': description
                })

        print(f"\nReceived Items: {len(received_items)}")
        if received_items:
            for item in received_items:
                print(f"  - Item ID: {item['item_id']}")
                print(f"    Barcode: {item['barcode']}")
                print(f"    Received: {item['receive_date']}")
                print(f"    Description: {item['description']}")

        print(f"\nUnreceived Items: {len(unreceived_items)}")
        if unreceived_items:
            for item in unreceived_items:
                print(f"  - Item ID: {item['item_id']} ✓")
                print(f"    Barcode: {item['barcode']}")
                print(f"    Description: {item['description']}")
                print(f"    Status: UNRECEIVED - Ready for receiving")

        print("\n" + "=" * 70)

        if unreceived_items:
            print("✓ VERIFICATION SUCCESSFUL")
            print(f"✓ {pol_id} has {len(unreceived_items)} unreceived item(s)")
            print(f"✓ First unreceived item ID: {unreceived_items[0]['item_id']}")
            print("✓ Ready for item receiving tests")
        else:
            print("✗ VERIFICATION NOTICE")
            print("✗ All items already received")
            print("✗ Need different POL for receiving tests")
    else:
        print("✗ No items found in POL")

    print("\n" + "=" * 70)

except Exception as e:
    print(f"\n✗ ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
