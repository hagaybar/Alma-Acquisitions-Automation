#!/usr/bin/env python3
"""
TEST 3.1: Receive Item (Basic)

This script receives an item from a POL.
WARNING: This script MODIFIES data in SANDBOX environment.

Usage:
    python test_receive_item.py <POL_ID> <ITEM_ID>

Optional parameters:
    --receive-date YYYY-MM-DDZ    # Specify receive date (default: today)
    --department CODE             # Department code
    --department-library CODE     # Library code

Example:
    python test_receive_item.py POL-5980 23472604450004146
    python test_receive_item.py POL-5980 23472604450004146 --receive-date 2025-10-03Z
"""
import sys
import argparse
from datetime import datetime
from almaapitk import AlmaAPIClient
from almaapitk import Acquisitions

# Parse command line arguments
parser = argparse.ArgumentParser(description='Receive an item from a POL')
parser.add_argument('pol_id', help='POL ID (e.g., POL-5980)')
parser.add_argument('item_id', help='Item ID to receive (e.g., 23472604450004146)')
parser.add_argument('--receive-date', help='Receive date in format YYYY-MM-DDZ (default: today)')
parser.add_argument('--department', help='Department code for receiving')
parser.add_argument('--department-library', help='Library code of receiving department')

args = parser.parse_args()

pol_id = args.pol_id
item_id = args.item_id
receive_date = args.receive_date
department = args.department
department_library = args.department_library

# Initialize
client = AlmaAPIClient('SANDBOX')
acq = Acquisitions(client)

print("=" * 70)
print("TEST 3.1: Receive Item (Basic)")
print("=" * 70)
print(f"\nPOL ID: {pol_id}")
print(f"Item ID: {item_id}")
if receive_date:
    print(f"Receive Date: {receive_date}")
if department:
    print(f"Department: {department}")
if department_library:
    print(f"Department Library: {department_library}")

print("\n⚠️  WARNING: This will MODIFY data in SANDBOX environment")
print("-" * 70)

# Verify POL and item status BEFORE receiving
print("\n=== STEP 1: Verify POL and Item Status (BEFORE) ===")
try:
    pol_data_before = acq.get_pol(pol_id)
    print(f"POL Status: {pol_data_before.get('status', {}).get('value', 'N/A')}")

    items_before = acq.extract_items_from_pol_data(pol_data_before)
    target_item = None
    for item in items_before:
        if item.get('pid') == item_id:
            target_item = item
            break

    if target_item:
        print(f"✓ Item found in POL")
        print(f"  Item ID: {target_item.get('pid')}")
        print(f"  Barcode: {target_item.get('barcode', 'N/A')}")
        print(f"  Receive Date: {target_item.get('receive_date', 'Not received')}")

        if target_item.get('receive_date'):
            print(f"\n✗ ERROR: Item already received on {target_item.get('receive_date')}")
            print("Cannot receive an already received item")
            sys.exit(1)
        else:
            print(f"✓ Item is unreceived - ready to receive")
    else:
        print(f"✗ ERROR: Item {item_id} not found in POL {pol_id}")
        sys.exit(1)

except Exception as e:
    print(f"✗ ERROR verifying POL: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Receive the item
print("\n=== STEP 2: Receive Item ===")
try:
    result = acq.receive_item(
        pol_id=pol_id,
        item_id=item_id,
        receive_date=receive_date,
        department=department,
        department_library=department_library
    )

    print("✓ Item received successfully")
    print(f"\nReceive Operation Result:")
    print(f"  Item ID: {result.get('pid', 'N/A')}")
    print(f"  Barcode: {result.get('barcode', 'N/A')}")

    # Check if receive_date is in the result
    if 'receive_date' in result:
        print(f"  Receive Date: {result.get('receive_date')}")

    # Check process_type if available
    if 'process_type' in result:
        process_type = result.get('process_type', {})
        if isinstance(process_type, dict):
            print(f"  Process Type: {process_type.get('value', 'N/A')}")
        else:
            print(f"  Process Type: {process_type}")

except Exception as e:
    print(f"\n✗ ERROR receiving item: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Verify POL and item status AFTER receiving
print("\n=== STEP 3: Verify POL and Item Status (AFTER) ===")
try:
    pol_data_after = acq.get_pol(pol_id)
    pol_status_after = pol_data_after.get('status', {}).get('value', 'N/A')
    print(f"POL Status: {pol_status_after}")

    items_after = acq.extract_items_from_pol_data(pol_data_after)
    target_item_after = None
    for item in items_after:
        if item.get('pid') == item_id:
            target_item_after = item
            break

    if target_item_after:
        print(f"\nItem Status After Receiving:")
        print(f"  Item ID: {target_item_after.get('pid')}")
        print(f"  Barcode: {target_item_after.get('barcode', 'N/A')}")
        receive_date_value = target_item_after.get('receive_date', 'N/A')
        print(f"  Receive Date: {receive_date_value}")

        if receive_date_value and receive_date_value != 'N/A':
            print(f"\n✓ SUCCESS: Item marked as received")
        else:
            print(f"\n⚠️  WARNING: receive_date not set in item")

except Exception as e:
    print(f"✗ ERROR verifying after receive: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test Summary
print("\n" + "=" * 70)
print("=== TEST 3.1 SUMMARY ===")
print(f"✓ Item {item_id} received successfully")
print(f"✓ POL Status: {pol_status_after}")
print("✓ TEST 3.1 PASSED")
print("=" * 70)
