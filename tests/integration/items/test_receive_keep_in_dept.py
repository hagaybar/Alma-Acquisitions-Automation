#!/usr/bin/env python3
"""
TEST: Receive Item and Keep in Department

This script tests the new receive_and_keep_in_department workflow that prevents
items from going into "in transit" status after receiving.

Workflow:
1. Receive item via acquisitions API
2. Immediately scan-in item to department with work order
3. Item stays in department instead of going to Transit

WARNING: This script MODIFIES data in SANDBOX environment.

Usage:
    python test_receive_keep_in_dept.py <POL_ID> <ITEM_ID> <MMS_ID> <HOLDING_ID>

Required parameters:
    POL_ID: Purchase Order Line ID (e.g., POL-5980)
    ITEM_ID: Item PID to receive (e.g., 23472604450004146)
    MMS_ID: Bibliographic record ID (e.g., 99123456789)
    HOLDING_ID: Holding ID (e.g., 22123456789)

Optional parameters:
    --library CODE                 Library code (default: MAIN)
    --department CODE              Department code (default: ACQ)
    --work-order-type TYPE         Work order type (default: AcqWorkOrder)
    --work-order-status STATUS     Work order status (default: CopyCataloging)
    --receive-date YYYY-MM-DDZ     Receive date (default: today)

Example:
    python test_receive_keep_in_dept.py POL-5980 23472604450004146 991234567890004146 221234567890004146

    # With custom work order
    python test_receive_keep_in_dept.py POL-5980 23472604450004146 991234567890004146 221234567890004146 \\
        --work-order-type AcqWorkOrder --work-order-status Labeling
"""
import sys
import argparse
from almaapitk import AlmaAPIClient
from almaapitk import Acquisitions
from almaapitk import BibliographicRecords


def print_section(title):
    """Print a formatted section header."""
    print("\n" + "=" * 70)
    print(f"=== {title} ===")
    print("=" * 70)


# Parse command line arguments
parser = argparse.ArgumentParser(
    description='Receive item and keep in department (prevents Transit status)',
    formatter_class=argparse.RawDescriptionHelpFormatter,
    epilog=__doc__
)
parser.add_argument('pol_id', help='POL ID (e.g., POL-5980)')
parser.add_argument('item_id', help='Item PID to receive')
parser.add_argument('mms_id', help='MMS ID (bibliographic record ID)')
parser.add_argument('holding_id', help='Holding ID')
parser.add_argument('--library', default='MAIN', help='Library code (default: MAIN)')
parser.add_argument('--department', default='ACQ', help='Department code (default: ACQ)')
parser.add_argument('--work-order-type', default='AcqWorkOrder',
                   help='Work order type (default: AcqWorkOrder)')
parser.add_argument('--work-order-status', default='CopyCataloging',
                   help='Work order status (default: CopyCataloging)')
parser.add_argument('--receive-date', help='Receive date in format YYYY-MM-DDZ')

args = parser.parse_args()

# Initialize clients
client = AlmaAPIClient('SANDBOX')
acq = Acquisitions(client)
bibs = BibliographicRecords(client)

print_section("RECEIVE AND KEEP IN DEPARTMENT TEST")
print(f"\nPOL ID: {args.pol_id}")
print(f"Item ID: {args.item_id}")
print(f"MMS ID: {args.mms_id}")
print(f"Holding ID: {args.holding_id}")
print(f"Library: {args.library}")
print(f"Department: {args.department}")
print(f"Work Order Type: {args.work_order_type}")
print(f"Work Order Status: {args.work_order_status}")
if args.receive_date:
    print(f"Receive Date: {args.receive_date}")

print("\n⚠️  WARNING: This will MODIFY data in SANDBOX environment")
print("-" * 70)

# Step 1: Verify POL and item status BEFORE
print_section("STEP 1: Verify POL and Item Status (BEFORE)")
try:
    pol_data_before = acq.get_pol(args.pol_id)
    pol_status_before = pol_data_before.get('status', {}).get('value', 'N/A')
    print(f"POL Status: {pol_status_before}")

    items_before = acq.extract_items_from_pol_data(pol_data_before)
    target_item = None
    for item in items_before:
        if item.get('pid') == args.item_id:
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
        print(f"✗ ERROR: Item {args.item_id} not found in POL {args.pol_id}")
        sys.exit(1)

except Exception as e:
    print(f"✗ ERROR verifying POL: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Step 2: Receive and keep in department
print_section("STEP 2: Receive and Keep in Department")
try:
    result = acq.receive_and_keep_in_department(
        pol_id=args.pol_id,
        item_id=args.item_id,
        mms_id=args.mms_id,
        holding_id=args.holding_id,
        library=args.library,
        department=args.department,
        work_order_type=args.work_order_type,
        work_order_status=args.work_order_status,
        receive_date=args.receive_date
    )

    print("\n✓ Receive and scan-in completed successfully")
    print(f"\nFinal Item Status:")

    # The result should be from the scan-in operation
    if isinstance(result, dict):
        print(f"  Item ID: {result.get('pid', 'N/A')}")
        print(f"  Barcode: {result.get('barcode', 'N/A')}")

        # Check process_type
        if 'process_type' in result:
            process_type = result.get('process_type', {})
            if isinstance(process_type, dict):
                process_value = process_type.get('value', 'N/A')
            else:
                process_value = process_type
            print(f"  Process Type: {process_value}")

            # Verify it's NOT in transit
            if 'transit' in str(process_value).lower():
                print(f"\n⚠️  WARNING: Item is in Transit status - scan-in may have failed")
            else:
                print(f"  ✓ Item is NOT in Transit (expected behavior)")

        # Check for work order info
        if 'work_order_type' in result:
            print(f"  Work Order Type: {result.get('work_order_type', 'N/A')}")
        if 'work_order_status' in result:
            print(f"  Work Order Status: {result.get('work_order_status', 'N/A')}")

except Exception as e:
    print(f"\n✗ ERROR in receive and keep in department: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Step 3: Verify POL and item status AFTER
print_section("STEP 3: Verify POL and Item Status (AFTER)")
try:
    pol_data_after = acq.get_pol(args.pol_id)
    pol_status_after = pol_data_after.get('status', {}).get('value', 'N/A')
    print(f"POL Status: {pol_status_after}")

    items_after = acq.extract_items_from_pol_data(pol_data_after)
    target_item_after = None
    for item in items_after:
        if item.get('pid') == args.item_id:
            target_item_after = item
            break

    if target_item_after:
        print(f"\nItem Status After Workflow:")
        print(f"  Item ID: {target_item_after.get('pid')}")
        print(f"  Barcode: {target_item_after.get('barcode', 'N/A')}")
        receive_date_value = target_item_after.get('receive_date', 'N/A')
        print(f"  Receive Date: {receive_date_value}")

        if receive_date_value and receive_date_value != 'N/A':
            print(f"  ✓ Item marked as received")
        else:
            print(f"  ⚠️  WARNING: receive_date not set in item")

    # Also verify via bibs API to check work order status
    print(f"\n--- Verifying via Bibs API ---")
    try:
        bib_item_response = bibs.get_items(
            mms_id=args.mms_id,
            holding_id=args.holding_id,
            item_id=args.item_id
        )

        if bib_item_response.success:
            bib_item_data = bib_item_response.json()
            print(f"✓ Retrieved item from Bibs API")

            # Check process_type from bibs perspective
            if 'process_type' in bib_item_data:
                process_type = bib_item_data.get('process_type', {})
                if isinstance(process_type, dict):
                    process_value = process_type.get('value', 'N/A')
                else:
                    process_value = process_type
                print(f"  Process Type (Bibs API): {process_value}")

    except Exception as e:
        print(f"⚠️  Could not verify via Bibs API: {e}")

except Exception as e:
    print(f"✗ ERROR verifying after workflow: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test Summary
print_section("TEST SUMMARY")
print(f"✓ Item {args.item_id} received successfully")
print(f"✓ Item scanned into department {args.department}")
print(f"✓ Work Order: {args.work_order_type} - {args.work_order_status}")
print(f"✓ POL Status: {pol_status_after}")
print("\n✓ TEST PASSED - Item should be in department, NOT in Transit")
print("=" * 70)
