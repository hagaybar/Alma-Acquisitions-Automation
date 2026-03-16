#!/usr/bin/env python3
"""
Complete invoice creation workflow test script with full safety guards.

This script creates an invoice for a given POL ID using Level 3 automation
(create_invoice_with_lines) with comprehensive safety checks.

Usage:
    # Dry-run (validation only - no invoice created)
    python tests/integration/invoices/test_create_invoice_from_pol.py POL-5989

    # Live test - creates and APPROVES invoice (default behavior)
    python tests/integration/invoices/test_create_invoice_from_pol.py POL-5989 --live

    # Full automation - create, approve, and pay
    python tests/integration/invoices/test_create_invoice_from_pol.py POL-5989 --live --auto-pay

    # Create without auto-approval (must use --no-auto-process)
    python tests/integration/invoices/test_create_invoice_from_pol.py POL-5989 --live --no-auto-process

    # Use custom invoice number
    python tests/integration/invoices/test_create_invoice_from_pol.py POL-5989 --live --invoice-number INV-2025-001

    # Specify environment
    python tests/integration/invoices/test_create_invoice_from_pol.py POL-5989 --live --environment PRODUCTION

Arguments:
    POL_ID: Purchase Order Line ID (required)
    --environment: SANDBOX or PRODUCTION (default: SANDBOX)
    --live: Execute live invoice creation (default: dry-run)
    --no-auto-process: Disable automatic invoice approval/processing (ENABLED BY DEFAULT)
    --auto-pay: Automatically mark invoice as paid after processing (default: False)
    --invoice-number: Custom invoice number (default: auto-generated with timestamp)
    --skip-duplicate-check: Skip duplicate invoice check (NOT RECOMMENDED)

Safety Features:
    1. ✅ Checks if POL already has existing invoices (prevents duplicates)
    2. ✅ Extracts actual POL price (prevents amount mismatches)
    3. ✅ Validates POL exists and is accessible
    4. ✅ Auto-extracts vendor and fund from POL
    5. ✅ Automatic duplicate payment protection in mark_invoice_paid()
    6. ✅ Requires explicit --live flag for actual invoice creation
    7. ✅ Confirmation prompt for PRODUCTION environment

Workflow Steps:
    1. Pre-flight validation: Check POL exists
    2. Duplicate check: Verify POL not already invoiced
    3. Extract POL data: Get price, vendor, fund
    4. Create invoice with auto-extracted data
    5. Add invoice line linked to POL
    6. AUTOMATICALLY approve/process invoice (DEFAULT - use --no-auto-process to disable)
    7. Optionally mark invoice as paid (use --auto-pay)
    8. Display comprehensive results with full logging

Examples:
    # Safe dry-run to validate POL
    python tests/integration/invoices/test_create_invoice_from_pol.py POL-5989

    # Create and APPROVE invoice (DEFAULT - ready for payment)
    python tests/integration/invoices/test_create_invoice_from_pol.py POL-5989 --live

    # Create WITHOUT approval (use --no-auto-process for manual review)
    python tests/integration/invoices/test_create_invoice_from_pol.py POL-5989 --live --no-auto-process

    # Complete automation (create, approve, and PAY)
    python tests/integration/invoices/test_create_invoice_from_pol.py POL-5989 --live --auto-pay
"""

import sys
import os
import argparse
from datetime import datetime
from typing import Dict, Any

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from almaapitk import AlmaAPIClient
from almaapitk import Acquisitions
from almaapitk import AlmaAPIError


def print_header(text: str, char: str = "="):
    """Print formatted header."""
    print(f"\n{char * 70}")
    print(text)
    print(f"{char * 70}")


def print_section(text: str):
    """Print formatted section."""
    print(f"\n{'-' * 70}")
    print(text)
    print(f"{'-' * 70}")


def print_result(success: bool, message: str):
    """Print formatted result."""
    status = "✓" if success else "✗"
    print(f"{status} {message}")


def validate_pol(acq: Acquisitions, pol_id: str) -> Dict[str, Any]:
    """
    Validate POL exists and extract data.

    Returns:
        Dict with POL data, or raises exception if validation fails
    """
    print_section(f"Step 1: Validating POL {pol_id}")

    try:
        pol_data = acq.get_pol(pol_id)
        print_result(True, f"POL {pol_id} exists and is accessible")

        # Extract key information
        pol_number = pol_data.get('number')
        pol_status = pol_data.get('status', {}).get('value')
        print(f"  POL Number: {pol_number}")
        print(f"  POL Status: {pol_status}")

        return pol_data

    except AlmaAPIError as e:
        print_result(False, f"POL validation failed: {e}")
        raise


def check_duplicate_invoices(acq: Acquisitions, pol_id: str, skip_check: bool = False) -> bool:
    """
    Check if POL already has invoices.

    Returns:
        True if safe to create invoice, False if duplicates exist
    """
    if skip_check:
        print_section("Step 2: Duplicate Check - SKIPPED (--skip-duplicate-check)")
        print("⚠️  WARNING: Duplicate check disabled - proceed with caution!")
        return True

    print_section("Step 2: Checking for Existing Invoices")

    try:
        check = acq.check_pol_invoiced(pol_id)

        if check['is_invoiced']:
            print_result(False, f"POL {pol_id} already has {check['invoice_count']} invoice(s)")

            print("\n⚠️  EXISTING INVOICES FOUND:")
            for inv in check['invoices']:
                print(f"\n  Invoice Number: {inv['invoice_number']}")
                print(f"    Invoice ID: {inv['invoice_id']}")
                print(f"    Amount: {inv['amount']}")
                print(f"    Status: {inv['invoice_status']}")
                print(f"    Payment: {inv['payment_status']}")

            print("\n⚠️  RECOMMENDATION:")
            print("  - Review existing invoices above")
            print("  - Consider using existing invoice instead of creating new one")
            print("  - Use --skip-duplicate-check ONLY if you are certain you need a new invoice")

            return False
        else:
            print_result(True, f"No existing invoices found for POL {pol_id}")
            return True

    except Exception as e:
        print_result(False, f"Duplicate check failed: {e}")
        raise


def extract_pol_data(acq: Acquisitions, pol_id: str) -> Dict[str, Any]:
    """
    Extract vendor, price, and fund from POL.

    Returns:
        Dict with extracted data
    """
    print_section("Step 3: Extracting POL Data")

    extracted = {}

    # Extract vendor
    try:
        vendor = acq.get_vendor_from_pol(pol_id)
        if vendor:
            extracted['vendor'] = vendor
            print_result(True, f"Vendor extracted: {vendor}")
        else:
            print_result(False, "No vendor found in POL")
            raise ValueError(f"POL {pol_id} has no vendor assigned")
    except Exception as e:
        print_result(False, f"Vendor extraction failed: {e}")
        raise

    # Extract price
    try:
        price = acq.get_price_from_pol(pol_id)
        if price:
            extracted['price'] = price
            print_result(True, f"Price extracted: {price}")
        else:
            print_result(False, "No price found in POL")
            raise ValueError(f"POL {pol_id} has no price assigned")
    except Exception as e:
        print_result(False, f"Price extraction failed: {e}")
        raise

    # Extract fund (optional - will auto-extract during line creation)
    try:
        fund = acq.get_fund_from_pol(pol_id)
        if fund:
            extracted['fund'] = fund
            print_result(True, f"Fund extracted: {fund}")
        else:
            print(f"ℹ️  No fund found in POL (will use default during line creation)")
            extracted['fund'] = None
    except Exception as e:
        print(f"⚠️  Fund extraction warning: {e}")
        extracted['fund'] = None

    return extracted


def create_invoice_workflow(
    acq: Acquisitions,
    pol_id: str,
    pol_data: Dict[str, Any],
    invoice_number: str,
    auto_process: bool = False,
    auto_pay: bool = False,
    dry_run: bool = True
) -> Dict[str, Any]:
    """
    Execute complete invoice creation workflow.

    Returns:
        Dict with workflow results
    """
    if dry_run:
        print_section("Step 4: Invoice Creation - DRY RUN MODE")
        print("ℹ️  Dry-run mode: No invoice will be created")
        print(f"\nWould create invoice with:")
        print(f"  Invoice Number: {invoice_number}")
        print(f"  Vendor: {pol_data['vendor']}")
        print(f"  Amount: {pol_data['price']}")
        print(f"  POL: {pol_id}")
        print(f"  Auto-process: {auto_process}")
        print(f"  Auto-pay: {auto_pay}")

        return {
            'success': True,
            'dry_run': True,
            'invoice_id': None,
            'invoice_number': invoice_number
        }

    print_section("Step 4: Creating Invoice with Complete Workflow")
    print(f"Invoice Number: {invoice_number}")
    print(f"Vendor: {pol_data['vendor']}")
    print(f"Amount: {pol_data['price']}")
    print(f"Auto-process: {auto_process}")
    print(f"Auto-pay: {auto_pay}")

    try:
        # Prepare line data
        lines = [
            {
                "pol_id": pol_id,
                "amount": pol_data['price'],
                "quantity": 1
            }
        ]

        # Execute workflow
        print("\nExecuting create_invoice_with_lines()...")
        result = acq.create_invoice_with_lines(
            invoice_number=invoice_number,
            invoice_date=datetime.now().strftime("%Y-%m-%d"),
            vendor_code=pol_data['vendor'],
            lines=lines,
            auto_process=auto_process,
            auto_pay=auto_pay
        )

        # Check results
        if result['invoice_id']:
            print_result(True, f"Invoice created: {result['invoice_id']}")
            print(f"  Invoice Number: {result['invoice_number']}")
            print(f"  Lines created: {len(result['line_ids'])}")
            print(f"  Processed: {result['processed']}")
            print(f"  Paid: {result['paid']}")
            print(f"  Status: {result['status']}")

            if result['errors']:
                print(f"\n⚠️  Warnings/Errors:")
                for error in result['errors']:
                    print(f"    - {error}")

            return {
                'success': True,
                'dry_run': False,
                **result
            }
        else:
            print_result(False, "Invoice creation failed")
            return {
                'success': False,
                'dry_run': False,
                'errors': result.get('errors', ['Unknown error'])
            }

    except Exception as e:
        print_result(False, f"Invoice creation failed: {e}")
        import traceback
        traceback.print_exc()
        return {
            'success': False,
            'dry_run': False,
            'errors': [str(e)]
        }


def main():
    """Main test runner."""
    parser = argparse.ArgumentParser(
        description='Create invoice from POL with complete safety checks',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        'pol_id',
        help='Purchase Order Line ID (e.g., POL-5989)'
    )
    parser.add_argument(
        '--environment',
        choices=['SANDBOX', 'PRODUCTION'],
        default='SANDBOX',
        help='Alma environment (default: SANDBOX)'
    )
    parser.add_argument(
        '--live',
        action='store_true',
        help='Execute live invoice creation (default: dry-run only)'
    )
    parser.add_argument(
        '--no-auto-process',
        action='store_true',
        help='Disable automatic invoice approval/processing (enabled by default)'
    )
    parser.add_argument(
        '--auto-pay',
        action='store_true',
        help='Automatically mark invoice as paid (invoice is always auto-processed)'
    )
    parser.add_argument(
        '--invoice-number',
        help='Custom invoice number (default: auto-generated with timestamp)'
    )
    parser.add_argument(
        '--skip-duplicate-check',
        action='store_true',
        help='Skip duplicate invoice check (NOT RECOMMENDED)'
    )

    args = parser.parse_args()

    # Auto-process is enabled by default (can be disabled with --no-auto-process)
    auto_process = not args.no_auto_process

    # Validate arguments - auto_pay doesn't need validation since auto_process is always True by default

    # Determine mode
    dry_run = not args.live

    # Generate invoice number if not provided
    invoice_number = args.invoice_number
    if not invoice_number:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        invoice_number = f"TEST-INV-{timestamp}"

    # Print configuration
    print_header("INVOICE CREATION FROM POL - COMPLETE WORKFLOW")
    print(f"POL ID: {args.pol_id}")
    print(f"Environment: {args.environment}")
    print(f"Mode: {'LIVE (creates invoice)' if not dry_run else 'DRY-RUN (validation only)'}")
    print(f"Invoice Number: {invoice_number}")
    print(f"Auto-process: {auto_process} (DEFAULT - always approves invoice)")
    print(f"Auto-pay: {args.auto_pay}")
    print(f"Duplicate check: {'DISABLED' if args.skip_duplicate_check else 'ENABLED'}")

    # Confirmation for live mode
    if not dry_run:
        print(f"\n⚠️  WARNING: Running in LIVE mode")
        print(f"  Environment: {args.environment}")
        print(f"  This will create a REAL invoice in Alma")

        if args.environment == 'PRODUCTION':
            print(f"\n⚠️⚠️⚠️  PRODUCTION ENVIRONMENT ⚠️⚠️⚠️")
            print(f"  This will affect PRODUCTION data!")

        confirmation = input("\nType 'YES' to proceed: ")
        if confirmation != 'YES':
            print("\n✗ Aborted by user")
            return 1

    # Initialize client
    try:
        client = AlmaAPIClient(args.environment)
        acq = Acquisitions(client)
        print(f"\n✓ Connected to {args.environment}")
    except Exception as e:
        print(f"\n✗ Failed to initialize client: {e}")
        return 1

    # Execute workflow
    try:
        # Step 1: Validate POL
        pol_data_raw = validate_pol(acq, args.pol_id)

        # Step 2: Check for duplicates
        safe_to_proceed = check_duplicate_invoices(acq, args.pol_id, args.skip_duplicate_check)

        if not safe_to_proceed and not args.skip_duplicate_check:
            print_header("WORKFLOW STOPPED - DUPLICATE INVOICES FOUND")
            print("⚠️  Use --skip-duplicate-check to bypass this safety check")
            print("⚠️  Only bypass if you are certain you need a new invoice")
            return 1

        # Step 3: Extract POL data
        pol_data = extract_pol_data(acq, args.pol_id)

        # Step 4: Create invoice
        result = create_invoice_workflow(
            acq=acq,
            pol_id=args.pol_id,
            pol_data=pol_data,
            invoice_number=invoice_number,
            auto_process=auto_process,
            auto_pay=args.auto_pay,
            dry_run=dry_run
        )

        # Print final summary
        print_header("WORKFLOW SUMMARY")

        if result['success']:
            if result['dry_run']:
                print("✓ DRY-RUN VALIDATION SUCCESSFUL")
                print(f"  POL {args.pol_id} is ready for invoice creation")
                print(f"  Add --live flag to create invoice")
            else:
                print("✓ INVOICE CREATION SUCCESSFUL")
                print(f"  Invoice ID: {result['invoice_id']}")
                print(f"  Invoice Number: {result['invoice_number']}")
                print(f"  Lines: {len(result['line_ids'])}")
                print(f"  Status: {result['status']}")
                print(f"  Processed: {result['processed']}")
                print(f"  Paid: {result['paid']}")

                if not result['processed'] and not result['paid']:
                    print(f"\nℹ️  Next steps:")
                    print(f"  - Invoice created but not processed")
                    print(f"  - Review invoice in Alma")
                    print(f"  - Add --auto-process to approve automatically")
                elif result['processed'] and not result['paid']:
                    print(f"\nℹ️  Next steps:")
                    print(f"  - Invoice processed and ready for payment")
                    print(f"  - Add --auto-pay to mark as paid automatically")
                else:
                    print(f"\n✓ Complete workflow finished - invoice fully processed")

            return 0
        else:
            print("✗ WORKFLOW FAILED")
            if 'errors' in result:
                print("\nErrors:")
                for error in result['errors']:
                    print(f"  - {error}")
            return 1

    except Exception as e:
        print_header("WORKFLOW FAILED")
        print(f"✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
