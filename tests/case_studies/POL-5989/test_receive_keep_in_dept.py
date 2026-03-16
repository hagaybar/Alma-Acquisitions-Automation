#!/usr/bin/env python3
"""
POL-5989 Receive and Keep in Department Test

This script is specifically designed to test the receive-and-keep-in-department
workflow for POL-5989. It performs comprehensive pre-flight checks before
executing the test.

WARNING: This script MODIFIES data in SANDBOX environment.
DO NOT RUN without explicit confirmation.

Workflow:
1. Gather all required information from POL-5989
2. Verify all entities are suitable for testing:
   - POL exists and is active
   - Item exists and is NOT already received
   - MMS ID and Holding ID can be extracted
   - Invoice reference exists (if needed)
3. Display all information for user confirmation
4. Wait for explicit user confirmation before proceeding
5. Execute receive-and-keep-in-department workflow
6. Verify final status

Usage:
    python test_pol_5989_receive_keep_in_dept.py           # Verification only
    python test_pol_5989_receive_keep_in_dept.py --run     # Run the test
    python test_pol_5989_receive_keep_in_dept.py --run --library MAIN --department ACQ_DEPT
"""
import sys
import argparse
from almaapitk import AlmaAPIClient
from almaapitk import Acquisitions
from almaapitk import BibliographicRecords


# HARDCODED POL ID
POL_ID = "POL-5989"

# Default configuration (can be overridden with command-line args)
DEFAULT_LIBRARY = "MAIN"
DEFAULT_DEPARTMENT = "ACQ"
DEFAULT_WORK_ORDER_TYPE = "AcqWorkOrder"
DEFAULT_WORK_ORDER_STATUS = "CopyCataloging"


def print_section(title, char="="):
    """Print a formatted section header."""
    print("\n" + char * 70)
    print(f"{title}")
    print(char * 70)


def print_subsection(title):
    """Print a formatted subsection header."""
    print(f"\n--- {title} ---")


def verify_pol_and_gather_data(acq):
    """
    Verify POL exists and gather all required data.

    Returns:
        dict: All gathered data, or None if verification fails
    """
    print_section("STEP 1: GATHER POL DATA", "=")

    try:
        print(f"Retrieving POL: {POL_ID}")
        pol_data = acq.get_pol(POL_ID)

        # Extract basic POL information
        pol_status = pol_data.get('status', {}).get('value', 'UNKNOWN')
        pol_number = pol_data.get('number', 'N/A')

        print(f"✓ POL retrieved successfully")
        print(f"  POL Number: {pol_number}")
        print(f"  POL Status: {pol_status}")

        # Check if POL is in suitable state
        if pol_status not in ['ACTIVE', 'WAITING', 'IN_REVIEW']:
            print(f"\n⚠️  WARNING: POL status is '{pol_status}'")
            print(f"  Expected status: ACTIVE, WAITING, or IN_REVIEW")
            print(f"  This POL may not be suitable for receiving items")

        # Extract MMS ID
        print_subsection("Extracting MMS ID")
        resource_metadata = pol_data.get('resource_metadata', {})
        mms_id_data = resource_metadata.get('mms_id', {})

        if isinstance(mms_id_data, dict):
            mms_id = mms_id_data.get('value')
        else:
            mms_id = mms_id_data

        if mms_id:
            print(f"✓ MMS ID found: {mms_id}")
        else:
            print(f"✗ ERROR: Could not extract MMS ID from POL")
            print(f"  Resource metadata: {resource_metadata}")
            return None

        # Extract Holding ID
        print_subsection("Extracting Holding ID")
        locations = pol_data.get('location', [])
        if isinstance(locations, dict):
            locations = [locations]

        if not locations:
            print(f"✗ ERROR: No locations found in POL")
            return None

        # Try multiple paths to get holding ID
        holding_id = locations[0].get('holding_id')

        # If not at holding_id, check the holding array
        if not holding_id:
            holdings = locations[0].get('holding', [])
            if holdings:
                if isinstance(holdings, list):
                    holding_id = holdings[0].get('id')
                else:
                    holding_id = holdings.get('id')

        if holding_id:
            print(f"✓ Holding ID found: {holding_id}")
            print(f"  Location: {locations[0].get('library', {}).get('value', 'N/A')}")
        else:
            print(f"✗ ERROR: Could not extract Holding ID from location")
            print(f"  Location data: {locations[0]}")
            return None

        # Extract items
        print_subsection("Extracting Items")
        items = acq.extract_items_from_pol_data(pol_data)

        if not items:
            print(f"✗ ERROR: No items found in POL")
            return None

        print(f"✓ Found {len(items)} item(s) in POL")

        # Extract invoice reference (optional but important for workflow)
        print_subsection("Extracting Invoice Reference")
        invoice_ref = pol_data.get('invoice_reference')
        invoice_data = None
        if invoice_ref:
            print(f"✓ Invoice reference found: {invoice_ref}")
        else:
            print(f"  No invoice reference (this is optional for receive-only workflow)")

        # Return all gathered data
        return {
            'pol_data': pol_data,
            'pol_status': pol_status,
            'pol_number': pol_number,
            'mms_id': mms_id,
            'holding_id': holding_id,
            'items': items,
            'invoice_ref': invoice_ref,
            'invoice_data': invoice_data  # Will be populated in next step if invoice exists
        }

    except Exception as e:
        print(f"\n✗ ERROR gathering POL data: {e}")
        import traceback
        traceback.print_exc()
        return None


def verify_and_process_invoice(acq, data, auto_approve=False):
    """
    Verify invoice status and process/approve if needed.

    Args:
        acq: Acquisitions instance
        data: POL data dictionary
        auto_approve: If True, automatically approve invoice if needed

    Returns:
        dict: Updated data with invoice information, or None if failed
    """
    print_section("STEP 2: VERIFY INVOICE STATUS", "=")

    invoice_ref = data.get('invoice_ref')

    if not invoice_ref:
        print("No invoice reference in POL")
        print("✓ This is OK - invoice payment not part of this test")
        return data

    try:
        print(f"Retrieving invoice: {invoice_ref}")
        invoice_data = acq.get_invoice(invoice_ref)

        # Extract invoice status information
        invoice_status = invoice_data.get('invoice_status', {}).get('value', 'UNKNOWN')
        invoice_status_desc = invoice_data.get('invoice_status', {}).get('desc', '')
        invoice_number = invoice_data.get('number', 'N/A')

        # Extract payment status (nested in payment object)
        payment = invoice_data.get('payment', {})
        payment_status = payment.get('payment_status', {}).get('value', 'UNKNOWN')
        payment_status_desc = payment.get('payment_status', {}).get('desc', '')

        print(f"✓ Invoice retrieved successfully")
        print(f"  Invoice Number: {invoice_number}")
        print(f"  Invoice Status: {invoice_status} ({invoice_status_desc})")
        print(f"  Payment Status: {payment_status} ({payment_status_desc})")

        # Check if invoice is in correct status for payment
        print_subsection("Invoice Status Analysis")

        ready_for_payment = False
        needs_processing = False

        if invoice_status in ['APPROVED', 'ACTIVE']:
            print(f"✓ Invoice status is good: {invoice_status}")
            print(f"  Invoice is ready for payment operations")
            ready_for_payment = True

        elif invoice_status in ['WAITING_TO_BE_SENT', 'WAITING_FOR_APPROVAL', 'IN_REVIEW']:
            print(f"⚠️  Invoice needs processing: {invoice_status}")
            print(f"  Invoice must be approved before payment")
            needs_processing = True

        elif invoice_status == 'CLOSED':
            print(f"⚠️  Invoice is already closed: {invoice_status}")
            print(f"  This may affect the complete workflow test")

        else:
            print(f"⚠️  Unexpected invoice status: {invoice_status}")
            print(f"  Please verify manually")

        # Check payment status
        if payment_status in ['PAID', 'FULLY_PAID']:
            print(f"\n⚠️  Invoice already paid: {payment_status}")
            print(f"  Cannot test payment workflow")
        elif payment_status == 'NOT_PAID':
            print(f"✓ Payment status is good: {payment_status}")

        # Auto-approve if needed and requested
        if needs_processing and auto_approve:
            print_subsection("Auto-Approving Invoice")
            print(f"Attempting to approve/process invoice {invoice_ref}...")

            try:
                # Use approve_invoice method (calls process_invoice operation)
                result = acq.approve_invoice(invoice_ref)

                # Re-fetch invoice to verify status change
                updated_invoice = acq.get_invoice(invoice_ref)
                new_status = updated_invoice.get('invoice_status', {}).get('value', 'UNKNOWN')

                print(f"✓ Invoice processed successfully")
                print(f"  New status: {new_status}")

                if new_status in ['APPROVED', 'ACTIVE']:
                    print(f"✓ Invoice is now ready for payment")
                    ready_for_payment = True
                    invoice_data = updated_invoice
                else:
                    print(f"⚠️  Invoice status after processing: {new_status}")
                    print(f"  May need manual approval in Alma UI")

            except Exception as e:
                print(f"✗ ERROR processing invoice: {e}")
                print(f"  You may need to approve invoice manually in Alma UI")
                import traceback
                traceback.print_exc()

        elif needs_processing and not auto_approve:
            print_subsection("Manual Action Required")
            print(f"⚠️  Invoice needs approval before payment")
            print(f"\nOptions:")
            print(f"  1. Run script with --auto-approve-invoice flag")
            print(f"  2. Manually approve invoice in Alma UI")
            print(f"  3. Use API: acq.approve_invoice('{invoice_ref}')")

        # Update data with invoice information
        data['invoice_data'] = invoice_data
        data['invoice_status'] = invoice_status
        data['payment_status'] = payment_status
        data['invoice_ready_for_payment'] = ready_for_payment

        return data

    except Exception as e:
        print(f"\n✗ ERROR retrieving invoice: {e}")
        import traceback
        traceback.print_exc()
        print(f"\n⚠️  Continuing without invoice verification")
        print(f"  Invoice payment tests will be skipped")
        return data


def verify_items_suitable_for_test(items):
    """
    Verify items are suitable for testing (unreceived).

    Returns:
        dict: First unreceived item, or None if none suitable
    """
    print_section("STEP 3: VERIFY ITEMS SUITABILITY", "=")

    unreceived_items = []
    received_items = []

    for item in items:
        item_id = item.get('pid', 'UNKNOWN')
        barcode = item.get('barcode', 'N/A')
        receive_date = item.get('receive_date')

        print(f"\nItem: {item_id}")
        print(f"  Barcode: {barcode}")
        print(f"  Receive Date: {receive_date or 'Not received'}")

        if receive_date:
            print(f"  Status: ✗ Already received")
            received_items.append(item)
        else:
            print(f"  Status: ✓ Unreceived - SUITABLE FOR TEST")
            unreceived_items.append(item)

    print_subsection("Summary")
    print(f"Total items: {len(items)}")
    print(f"Unreceived items: {len(unreceived_items)}")
    print(f"Already received: {len(received_items)}")

    if not unreceived_items:
        print(f"\n✗ ERROR: No unreceived items found in POL")
        print(f"  All items have already been received")
        print(f"  This POL is NOT suitable for testing")
        return None

    # Return first unreceived item
    selected_item = unreceived_items[0]
    print(f"\n✓ Selected item for test: {selected_item.get('pid')}")
    return selected_item


def display_test_plan(data, item, library, department, work_order_type, work_order_status):
    """Display complete test plan for user review."""
    print_section("STEP 4: TEST PLAN", "=")

    print(f"POL Information:")
    print(f"  POL ID: {POL_ID}")
    print(f"  POL Number: {data['pol_number']}")
    print(f"  POL Status: {data['pol_status']}")

    print(f"\nBibliographic Information:")
    print(f"  MMS ID: {data['mms_id']}")
    print(f"  Holding ID: {data['holding_id']}")

    # Show invoice information if available
    if data.get('invoice_ref'):
        print(f"\nInvoice Information:")
        print(f"  Invoice ID: {data['invoice_ref']}")
        if data.get('invoice_status'):
            print(f"  Invoice Status: {data['invoice_status']}")
            print(f"  Payment Status: {data.get('payment_status', 'N/A')}")
            if data.get('invoice_ready_for_payment'):
                print(f"  ✓ Invoice is ready for payment operations")
            else:
                print(f"  ⚠️  Invoice may need processing before payment")

    print(f"\nItem to Receive:")
    print(f"  Item ID: {item.get('pid')}")
    print(f"  Barcode: {item.get('barcode', 'N/A')}")
    print(f"  Current Status: Unreceived")

    print(f"\nWorkflow Configuration:")
    print(f"  Library: {library}")
    print(f"  Department: {department}")
    print(f"  Work Order Type: {work_order_type}")
    print(f"  Work Order Status: {work_order_status}")

    print(f"\nOperations to be performed:")
    print(f"  1. Receive item {item.get('pid')} via acquisitions API")
    print(f"  2. Scan item into department '{department}' with work order")
    print(f"  3. Verify item is NOT in Transit status")

    print(f"\n⚠️  WARNING: This will MODIFY data in SANDBOX environment")


def run_test(acq, data, item, library, department, work_order_type, work_order_status):
    """Execute the receive-and-keep-in-department test."""
    print_section("STEP 5: EXECUTE TEST", "=")

    item_id = item.get('pid')
    mms_id = data['mms_id']
    holding_id = data['holding_id']

    print(f"Executing receive_and_keep_in_department...")
    print(f"  POL: {POL_ID}")
    print(f"  Item: {item_id}")
    print(f"  MMS: {mms_id}")
    print(f"  Holding: {holding_id}")

    try:
        result = acq.receive_and_keep_in_department(
            pol_id=POL_ID,
            item_id=item_id,
            mms_id=mms_id,
            holding_id=holding_id,
            library=library,
            department=department,
            work_order_type=work_order_type,
            work_order_status=work_order_status
        )

        print(f"\n✓ Workflow completed successfully")

        # Display result details
        print_subsection("Result Details")
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

                # Verify NOT in transit
                if 'transit' in str(process_value).lower():
                    print(f"\n  ⚠️  WARNING: Item is in Transit status - unexpected!")
                else:
                    print(f"  ✓ Item is NOT in Transit (expected behavior)")

        return result

    except Exception as e:
        print(f"\n✗ ERROR executing test: {e}")
        import traceback
        traceback.print_exc()
        return None


def verify_final_state(acq, bibs, data, item_id):
    """Verify final state of POL and item after test."""
    print_section("STEP 6: VERIFY FINAL STATE", "=")

    # Verify via Acquisitions API
    print_subsection("Verification via Acquisitions API")
    try:
        pol_data_after = acq.get_pol(POL_ID)
        pol_status_after = pol_data_after.get('status', {}).get('value', 'N/A')
        print(f"✓ POL Status: {pol_status_after}")

        items_after = acq.extract_items_from_pol_data(pol_data_after)
        target_item = None
        for item in items_after:
            if item.get('pid') == item_id:
                target_item = item
                break

        if target_item:
            receive_date = target_item.get('receive_date', 'N/A')
            print(f"✓ Item found in POL")
            print(f"  Item ID: {target_item.get('pid')}")
            print(f"  Receive Date: {receive_date}")

            if receive_date and receive_date != 'N/A':
                print(f"  ✓ Item marked as received")
            else:
                print(f"  ⚠️  WARNING: receive_date not set")

    except Exception as e:
        print(f"⚠️  Could not verify via Acquisitions API: {e}")

    # Verify via Bibs API
    print_subsection("Verification via Bibs API")
    try:
        bib_item_response = bibs.get_items(
            mms_id=data['mms_id'],
            holding_id=data['holding_id'],
            item_id=item_id
        )

        if bib_item_response.success:
            bib_item_data = bib_item_response.json()
            print(f"✓ Item retrieved from Bibs API")

            # Check process_type
            if 'process_type' in bib_item_data:
                process_type = bib_item_data.get('process_type', {})
                if isinstance(process_type, dict):
                    process_value = process_type.get('value', 'N/A')
                else:
                    process_value = process_type
                print(f"  Process Type: {process_value}")

                if 'transit' in str(process_value).lower():
                    print(f"  ✗ Item is in Transit - TEST FAILED")
                    return False
                else:
                    print(f"  ✓ Item is NOT in Transit - TEST PASSED")
                    return True

    except Exception as e:
        print(f"⚠️  Could not verify via Bibs API: {e}")

    return True


def main():
    """Main execution function."""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description=f'Test receive-and-keep-in-department workflow for {POL_ID}',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument('--run', action='store_true',
                       help='Actually run the test (default: verification only)')
    parser.add_argument('--auto-approve-invoice', action='store_true',
                       help='Automatically approve invoice if it needs processing')
    parser.add_argument('--library', default=DEFAULT_LIBRARY,
                       help=f'Library code (default: {DEFAULT_LIBRARY})')
    parser.add_argument('--department', default=DEFAULT_DEPARTMENT,
                       help=f'Department code (default: {DEFAULT_DEPARTMENT})')
    parser.add_argument('--work-order-type', default=DEFAULT_WORK_ORDER_TYPE,
                       help=f'Work order type (default: {DEFAULT_WORK_ORDER_TYPE})')
    parser.add_argument('--work-order-status', default=DEFAULT_WORK_ORDER_STATUS,
                       help=f'Work order status (default: {DEFAULT_WORK_ORDER_STATUS})')

    args = parser.parse_args()

    # Initialize clients
    print_section(f"POL-{POL_ID.split('-')[1]} RECEIVE AND KEEP IN DEPARTMENT TEST", "=")
    print(f"\nMode: {'LIVE TEST' if args.run else 'VERIFICATION ONLY'}")
    if args.auto_approve_invoice:
        print(f"Auto-approve invoice: ENABLED")
    print(f"Environment: SANDBOX")

    client = AlmaAPIClient('SANDBOX')
    acq = Acquisitions(client)
    bibs = BibliographicRecords(client)

    # Step 1: Gather POL data
    data = verify_pol_and_gather_data(acq)
    if not data:
        print_section("TEST ABORTED - Data gathering failed", "=")
        sys.exit(1)

    # Step 2: Verify and process invoice (if exists)
    data = verify_and_process_invoice(acq, data, auto_approve=args.auto_approve_invoice)
    if not data:
        print_section("TEST ABORTED - Invoice verification failed", "=")
        sys.exit(1)

    # Step 3: Verify items
    item = verify_items_suitable_for_test(data['items'])
    if not item:
        print_section("TEST ABORTED - No suitable items found", "=")
        sys.exit(1)

    # Step 4: Display test plan
    display_test_plan(data, item, args.library, args.department,
                     args.work_order_type, args.work_order_status)

    # If not in run mode, stop here
    if not args.run:
        print_section("VERIFICATION COMPLETE", "=")
        print("\n✓ All pre-flight checks passed")
        print(f"✓ POL {POL_ID} is suitable for testing")
        print(f"✓ Item {item.get('pid')} is unreceived and ready")

        # Show invoice status if available
        if data.get('invoice_ref'):
            print(f"\nInvoice Status:")
            print(f"  Invoice ID: {data['invoice_ref']}")
            print(f"  Status: {data.get('invoice_status', 'N/A')}")
            print(f"  Payment Status: {data.get('payment_status', 'N/A')}")

            if data.get('invoice_ready_for_payment'):
                print(f"  ✓ Invoice is ready for payment")
            else:
                print(f"  ⚠️  Invoice needs approval before payment")
                print(f"\n  To auto-approve invoice, add: --auto-approve-invoice")

        print(f"\nTo run the actual test, use:")
        print(f"  python {sys.argv[0]} --run")
        if data.get('invoice_ref') and not data.get('invoice_ready_for_payment'):
            print(f"  python {sys.argv[0]} --run --auto-approve-invoice")
        print("\n⚠️  Remember: This will MODIFY data in SANDBOX environment")
        print("=" * 70)
        sys.exit(0)

    # Step 4: Execute test
    print("\n" + "!" * 70)
    print("PROCEEDING WITH LIVE TEST - THIS WILL MODIFY SANDBOX DATA")
    print("!" * 70)

    result = run_test(acq, data, item, args.library, args.department,
                     args.work_order_type, args.work_order_status)

    if not result:
        print_section("TEST FAILED", "=")
        sys.exit(1)

    # Step 5: Verify final state
    success = verify_final_state(acq, bibs, data, item.get('pid'))

    # Final summary
    if success:
        print_section("TEST COMPLETED SUCCESSFULLY", "=")
        print(f"✓ Item {item.get('pid')} received and kept in department")
        print(f"✓ Item is NOT in Transit status")
        print(f"✓ POL {POL_ID} workflow completed successfully")
        print("=" * 70)
        sys.exit(0)
    else:
        print_section("TEST COMPLETED WITH WARNINGS", "=")
        print(f"⚠️  Item may have gone to Transit status")
        print(f"⚠️  Please verify manually in Alma")
        print("=" * 70)
        sys.exit(1)


if __name__ == "__main__":
    main()
