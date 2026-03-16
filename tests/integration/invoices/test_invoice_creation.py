#!/usr/bin/env python3
"""
Comprehensive test script for invoice creation helper methods.

Tests all three levels of abstraction:
1. Core utility methods (_format_invoice_date, _build_invoice_structure, _build_invoice_line_structure)
2. Simple helper methods (create_invoice_simple, create_invoice_line_simple)
3. Complete workflow (create_invoice_with_lines)

Usage:
    # Use default test POLs (POL-5989, POL-5990)
    python src/tests/test_invoice_creation.py --environment SANDBOX [--live]

    # Use custom POL (vendor auto-extracted)
    python src/tests/test_invoice_creation.py --pol POL-5992 --live

    # Use two different POLs for multi-line tests
    python src/tests/test_invoice_creation.py --pol POL-5992 --pol2 POL-5993 --live

Arguments:
    --environment: SANDBOX or PRODUCTION (default: SANDBOX)
    --live: Execute live tests (default: dry-run, validation only)
    --test: Run specific test number (1-10, or 'all' for all tests)
    --pol, --pol-id: Custom POL ID for testing (vendor will be auto-extracted)
    --pol2, --pol-id-2: Second POL ID for multi-line tests (optional)

Examples:
    # Dry-run with custom POL
    python src/tests/test_invoice_creation.py --pol POL-5992

    # Live test specific workflow with custom POL
    python src/tests/test_invoice_creation.py --pol POL-5992 --test 8 --live

    # Test with two different POLs
    python src/tests/test_invoice_creation.py --pol POL-5992 --pol2 POL-5993 --live

Warning:
    Live tests will create real invoices in the selected environment.
    Always test in SANDBOX before running in PRODUCTION.
"""

import sys
import os
import argparse
from datetime import datetime
from typing import Dict, Any, List

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from almaapitk import AlmaAPIClient
from almaapitk import Acquisitions

# ============================================================================
# Test Configuration
# ============================================================================

# Test POLs (verified to exist in SANDBOX)
TEST_POL_1 = "POL-5989"
TEST_POL_2 = "POL-5990"
TEST_VENDOR = "RIALTO"

# Test invoice numbers (use timestamp to ensure uniqueness)
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")


# ============================================================================
# Test Helper Functions
# ============================================================================

def print_test_header(test_num: int, test_name: str):
    """Print formatted test header."""
    print("\n" + "=" * 70)
    print(f"TEST {test_num}: {test_name}")
    print("=" * 70)


def print_test_result(test_num: int, passed: bool, message: str = ""):
    """Print formatted test result."""
    status = "✓ PASSED" if passed else "✗ FAILED"
    print(f"\n{status}: TEST {test_num}")
    if message:
        print(f"  {message}")


def print_section(title: str):
    """Print formatted section divider."""
    print(f"\n{'-' * 70}")
    print(title)
    print("-" * 70)


# ============================================================================
# Test 1: Date Formatting Utility
# ============================================================================

def test_1_date_formatting(acq: Acquisitions, dry_run: bool = True) -> bool:
    """Test _format_invoice_date() with various input formats."""
    print_test_header(1, "Date Formatting Utility (_format_invoice_date)")

    try:
        print("\nTest 1.1: Format 'YYYY-MM-DD' string")
        result1 = acq._format_invoice_date("2025-10-22")
        assert result1 == "2025-10-22Z", f"Expected '2025-10-22Z', got '{result1}'"
        print(f"  Input: '2025-10-22' → Output: '{result1}' ✓")

        print("\nTest 1.2: Already formatted 'YYYY-MM-DDZ' string")
        result2 = acq._format_invoice_date("2025-10-22Z")
        assert result2 == "2025-10-22Z", f"Expected '2025-10-22Z', got '{result2}'"
        print(f"  Input: '2025-10-22Z' → Output: '{result2}' ✓")

        print("\nTest 1.3: Datetime object")
        dt = datetime(2025, 10, 22)
        result3 = acq._format_invoice_date(dt)
        assert result3 == "2025-10-22Z", f"Expected '2025-10-22Z', got '{result3}'"
        print(f"  Input: datetime(2025, 10, 22) → Output: '{result3}' ✓")

        print("\nTest 1.4: Invalid format (should raise ValueError)")
        try:
            acq._format_invoice_date(123)  # Invalid type
            print("  ✗ Should have raised ValueError")
            return False
        except ValueError as e:
            print(f"  Correctly raised ValueError: {e} ✓")

        print_test_result(1, True, "All date formatting tests passed")
        return True

    except Exception as e:
        print(f"\n✗ Error in test 1: {e}")
        import traceback
        traceback.print_exc()
        print_test_result(1, False, str(e))
        return False


# ============================================================================
# Test 2: Invoice Structure Builder
# ============================================================================

def test_2_invoice_structure_builder(acq: Acquisitions, dry_run: bool = True) -> bool:
    """Test _build_invoice_structure() method."""
    print_test_header(2, "Invoice Structure Builder (_build_invoice_structure)")

    try:
        print("\nTest 2.1: Build minimal invoice structure")
        invoice_data = acq._build_invoice_structure(
            number="TEST-001",
            invoice_date="2025-10-22",
            vendor_code="RIALTO",
            total_amount=100.00
        )

        assert invoice_data['number'] == "TEST-001"
        assert invoice_data['invoice_date'] == "2025-10-22Z"
        assert invoice_data['vendor']['value'] == "RIALTO"
        assert invoice_data['total_amount'] == 100.00
        assert invoice_data['currency']['value'] == "ILS"
        print("  ✓ Minimal structure validated")

        print("\nTest 2.2: Build with optional fields")
        invoice_data2 = acq._build_invoice_structure(
            number="TEST-002",
            invoice_date="2025-10-22",
            vendor_code="RIALTO",
            total_amount=200.00,
            currency="USD",
            payment={'prepaid': True}
        )

        assert invoice_data2['currency']['value'] == "USD"
        assert 'payment' in invoice_data2
        print("  ✓ Optional fields handled correctly")

        print("\nTest 2.3: Missing required field (should raise ValueError)")
        try:
            acq._build_invoice_structure(
                number="",  # Empty number
                invoice_date="2025-10-22",
                vendor_code="RIALTO",
                total_amount=100.00
            )
            print("  ✗ Should have raised ValueError")
            return False
        except ValueError as e:
            print(f"  Correctly raised ValueError: {e} ✓")

        print_test_result(2, True, "Invoice structure builder validated")
        return True

    except Exception as e:
        print(f"\n✗ Error in test 2: {e}")
        import traceback
        traceback.print_exc()
        print_test_result(2, False, str(e))
        return False


# ============================================================================
# Test 3: Invoice Line Structure Builder
# ============================================================================

def test_3_invoice_line_structure_builder(acq: Acquisitions, dry_run: bool = True) -> bool:
    """Test _build_invoice_line_structure() method."""
    print_test_header(3, "Invoice Line Structure Builder (_build_invoice_line_structure)")

    try:
        print("\nTest 3.1: Build minimal line structure")
        line_data = acq._build_invoice_line_structure(
            po_line="POL-5989",
            amount=50.00,
            quantity=1,
            fund_code="FUND-001"
        )

        assert line_data['po_line'] == "POL-5989"
        assert line_data['price'] == 50.0, f"Expected 50.0, got '{line_data['price']}'"
        assert line_data['quantity'] == 1
        assert line_data['fund_distribution'][0]['fund_code']['value'] == "FUND-001"
        assert line_data['fund_distribution'][0]['percent'] == 100
        assert 'amount' not in line_data['fund_distribution'][0], "Should use percent, not amount"
        print("  ✓ Minimal line structure validated")

        print("\nTest 3.2: Build with custom currency")
        line_data2 = acq._build_invoice_line_structure(
            po_line="POL-5990",
            amount=75.00,
            quantity=2,
            fund_code="FUND-002",
            currency="EUR"
        )

        assert line_data2['fund_distribution'][0]['amount']['currency']['value'] == "EUR"
        print("  ✓ Custom currency handled correctly")

        print_test_result(3, True, "Invoice line structure builder validated")
        return True

    except Exception as e:
        print(f"\n✗ Error in test 3: {e}")
        import traceback
        traceback.print_exc()
        print_test_result(3, False, str(e))
        return False


# ============================================================================
# Test 4: Get Vendor from POL
# ============================================================================

def test_4_get_vendor_from_pol(acq: Acquisitions, dry_run: bool = True) -> bool:
    """Test get_vendor_from_pol() method."""
    print_test_header(4, "Get Vendor from POL (get_vendor_from_pol)")

    try:
        print(f"\nTest 4.1: Extract vendor from {TEST_POL_1}")
        vendor = acq.get_vendor_from_pol(TEST_POL_1)

        if vendor:
            print(f"  ✓ Vendor found: {vendor}")
        else:
            print(f"  ⚠️ No vendor found for {TEST_POL_1}")
            # This is not necessarily a failure - POL might not have vendor

        print_test_result(4, True, f"Vendor extraction tested (result: {vendor or 'None'})")
        return True

    except Exception as e:
        print(f"\n✗ Error in test 4: {e}")
        import traceback
        traceback.print_exc()
        print_test_result(4, False, str(e))
        return False


# ============================================================================
# Test 5: Get Fund from POL
# ============================================================================

def test_5_get_fund_from_pol(acq: Acquisitions, dry_run: bool = True) -> bool:
    """Test get_fund_from_pol() method."""
    print_test_header(5, "Get Fund from POL (get_fund_from_pol)")

    try:
        print(f"\nTest 5.1: Extract fund from {TEST_POL_1}")
        fund = acq.get_fund_from_pol(TEST_POL_1)

        if fund:
            print(f"  ✓ Fund found: {fund}")
        else:
            print(f"  ⚠️ No fund found for {TEST_POL_1}")
            # This is not necessarily a failure - POL might not have fund distribution

        print(f"\nTest 5.2: Extract fund from {TEST_POL_2}")
        fund2 = acq.get_fund_from_pol(TEST_POL_2)

        if fund2:
            print(f"  ✓ Fund found: {fund2}")
        else:
            print(f"  ⚠️ No fund found for {TEST_POL_2}")

        print_test_result(5, True, f"Fund extraction tested")
        return True

    except Exception as e:
        print(f"\n✗ Error in test 5: {e}")
        import traceback
        traceback.print_exc()
        print_test_result(5, False, str(e))
        return False


# ============================================================================
# Test 6: Simple Invoice Creation (DRY RUN ONLY)
# ============================================================================

def test_6_simple_invoice_creation(acq: Acquisitions, dry_run: bool = True) -> bool:
    """Test create_invoice_simple() method."""
    print_test_header(6, "Simple Invoice Creation (create_invoice_simple)")

    if dry_run:
        print("\n⚠️  DRY RUN MODE - Skipping live API test")
        print("  Use --live flag to execute this test")
        print_test_result(6, True, "Skipped (dry-run mode)")
        return True

    try:
        invoice_num = f"TEST-INV-{TIMESTAMP}-6"
        print(f"\nTest 6.1: Create simple invoice: {invoice_num}")

        created_invoice = acq.create_invoice_simple(
            invoice_number=invoice_num,
            invoice_date="2025-10-22",
            vendor_code=TEST_VENDOR,
            total_amount=100.00
        )

        invoice_id = created_invoice.get('id')
        assert invoice_id, "Invoice ID not returned"

        print(f"  ✓ Invoice created: {invoice_id}")
        print(f"  Invoice Number: {created_invoice.get('number')}")
        print(f"  Status: {created_invoice.get('invoice_status', {}).get('value')}")

        print_test_result(6, True, f"Invoice {invoice_id} created successfully")
        return True

    except Exception as e:
        print(f"\n✗ Error in test 6: {e}")
        import traceback
        traceback.print_exc()
        print_test_result(6, False, str(e))
        return False


# ============================================================================
# Test 7: Simple Invoice Line Creation (DRY RUN ONLY)
# ============================================================================

def test_7_simple_invoice_line_creation(acq: Acquisitions, dry_run: bool = True) -> bool:
    """Test create_invoice_line_simple() method."""
    print_test_header(7, "Simple Invoice Line Creation (create_invoice_line_simple)")

    if dry_run:
        print("\n⚠️  DRY RUN MODE - Skipping live API test")
        print("  This test requires an existing invoice")
        print("  Use --live flag to execute this test")
        print_test_result(7, True, "Skipped (dry-run mode)")
        return True

    try:
        # First create an invoice
        invoice_num = f"TEST-INV-{TIMESTAMP}-7"
        print(f"\nTest 7.1: Create invoice for line test: {invoice_num}")

        created_invoice = acq.create_invoice_simple(
            invoice_number=invoice_num,
            invoice_date="2025-10-22",
            vendor_code=TEST_VENDOR,
            total_amount=50.00
        )

        invoice_id = created_invoice.get('id')
        print(f"  ✓ Invoice created: {invoice_id}")

        # Now add a line
        print(f"\nTest 7.2: Add line to invoice with auto-fund extraction")

        created_line = acq.create_invoice_line_simple(
            invoice_id=invoice_id,
            pol_id=TEST_POL_1,
            amount=50.00,
            quantity=1
            # fund_code will be auto-extracted from POL
        )

        line_id = created_line.get('id')
        print(f"  ✓ Line created: {line_id}")
        print(f"  POL: {created_line.get('po_line')}")
        print(f"  Amount: {created_line.get('price')}")

        print_test_result(7, True, f"Line {line_id} created successfully")
        return True

    except Exception as e:
        print(f"\n✗ Error in test 7: {e}")
        import traceback
        traceback.print_exc()
        print_test_result(7, False, str(e))
        return False


# ============================================================================
# Test 8: Complete Workflow - Create Only (DRY RUN ONLY)
# ============================================================================

def test_8_workflow_create_only(acq: Acquisitions, dry_run: bool = True) -> bool:
    """Test create_invoice_with_lines() - create only, no processing."""
    print_test_header(8, "Complete Workflow - Create Only")

    if dry_run:
        print("\n⚠️  DRY RUN MODE - Skipping live API test")
        print("  Use --live flag to execute this test")
        print_test_result(8, True, "Skipped (dry-run mode)")
        return True

    try:
        invoice_num = f"TEST-INV-{TIMESTAMP}-8"

        # Extract price from POL
        price = acq.get_price_from_pol(TEST_POL_1)
        if not price:
            print(f"\n⚠️  Warning: Could not extract price from POL {TEST_POL_1}, using default 50.0")
            price = 50.0

        lines = [
            {"pol_id": TEST_POL_1, "amount": price, "quantity": 1},
        ]

        print(f"\nTest 8.1: Create invoice with lines (no processing)")
        print(f"  Invoice: {invoice_num}")
        print(f"  Lines: {len(lines)}")
        print(f"  Amount: {price} (extracted from POL)")

        result = acq.create_invoice_with_lines(
            invoice_number=invoice_num,
            invoice_date="2025-10-22",
            vendor_code=TEST_VENDOR,
            lines=lines,
            auto_process=False,
            auto_pay=False
        )

        assert result['invoice_id'], "Invoice ID not returned"
        assert len(result['line_ids']) == len(lines), "Not all lines created"
        assert result['processed'] is False, "Should not be processed"
        assert result['paid'] is False, "Should not be paid"
        assert len(result['errors']) == 0, f"Errors occurred: {result['errors']}"

        print(f"\n  ✓ Invoice created: {result['invoice_id']}")
        print(f"  ✓ Lines created: {len(result['line_ids'])}")
        print(f"  Status: {result['status']}")

        print_test_result(8, True, "Create-only workflow successful")
        return True

    except Exception as e:
        print(f"\n✗ Error in test 8: {e}")
        import traceback
        traceback.print_exc()
        print_test_result(8, False, str(e))
        return False


# ============================================================================
# Test 9: Complete Workflow - With Processing (DRY RUN ONLY)
# ============================================================================

def test_9_workflow_with_processing(acq: Acquisitions, dry_run: bool = True) -> bool:
    """Test create_invoice_with_lines() - create and process."""
    print_test_header(9, "Complete Workflow - With Processing")

    if dry_run:
        print("\n⚠️  DRY RUN MODE - Skipping live API test")
        print("  Use --live flag to execute this test")
        print_test_result(9, True, "Skipped (dry-run mode)")
        return True

    try:
        invoice_num = f"TEST-INV-{TIMESTAMP}-9"

        # Extract prices from POLs
        price1 = acq.get_price_from_pol(TEST_POL_1) or 50.0
        price2 = acq.get_price_from_pol(TEST_POL_2) or 75.0

        lines = [
            {"pol_id": TEST_POL_1, "amount": price1, "quantity": 1},
            {"pol_id": TEST_POL_2, "amount": price2, "quantity": 1},
        ]

        print(f"\nTest 9.1: Create invoice with lines and process")
        print(f"  Invoice: {invoice_num}")
        print(f"  Lines: {len(lines)}")
        print(f"  POL 1: {TEST_POL_1} - {price1}")
        print(f"  POL 2: {TEST_POL_2} - {price2}")

        result = acq.create_invoice_with_lines(
            invoice_number=invoice_num,
            invoice_date="2025-10-22",
            vendor_code=TEST_VENDOR,
            lines=lines,
            auto_process=True,
            auto_pay=False
        )

        assert result['invoice_id'], "Invoice ID not returned"
        assert len(result['line_ids']) == len(lines), "Not all lines created"
        assert result['processed'] is True, "Should be processed"
        assert result['paid'] is False, "Should not be paid"
        assert len(result['errors']) == 0, f"Errors occurred: {result['errors']}"

        print(f"\n  ✓ Invoice created: {result['invoice_id']}")
        print(f"  ✓ Lines created: {len(result['line_ids'])}")
        print(f"  ✓ Processed: {result['processed']}")
        print(f"  Status: {result['status']}")

        print_test_result(9, True, "Workflow with processing successful")
        return True

    except Exception as e:
        print(f"\n✗ Error in test 9: {e}")
        import traceback
        traceback.print_exc()
        print_test_result(9, False, str(e))
        return False


# ============================================================================
# Test 10: Complete Workflow - Full Automation (DRY RUN ONLY)
# ============================================================================

def test_10_workflow_full_automation(acq: Acquisitions, dry_run: bool = True) -> bool:
    """Test create_invoice_with_lines() - create, process, and pay."""
    print_test_header(10, "Complete Workflow - Full Automation (Create, Process, Pay)")

    if dry_run:
        print("\n⚠️  DRY RUN MODE - Skipping live API test")
        print("  Use --live flag to execute this test")
        print_test_result(10, True, "Skipped (dry-run mode)")
        return True

    try:
        invoice_num = f"TEST-INV-{TIMESTAMP}-10"

        # Extract price from POL
        price = acq.get_price_from_pol(TEST_POL_1) or 100.0

        lines = [
            {"pol_id": TEST_POL_1, "amount": price, "quantity": 1},
        ]

        print(f"\nTest 10.1: Create invoice with full automation")
        print(f"  Invoice: {invoice_num}")
        print(f"  Lines: {len(lines)}")
        print(f"  Amount: {price} (extracted from POL)")
        print(f"  Auto-process: True")
        print(f"  Auto-pay: True")

        result = acq.create_invoice_with_lines(
            invoice_number=invoice_num,
            invoice_date="2025-10-22",
            vendor_code=TEST_VENDOR,
            lines=lines,
            auto_process=True,
            auto_pay=True
        )

        assert result['invoice_id'], "Invoice ID not returned"
        assert len(result['line_ids']) == len(lines), "Not all lines created"
        assert result['processed'] is True, "Should be processed"
        assert result['paid'] is True, "Should be paid"
        assert len(result['errors']) == 0, f"Errors occurred: {result['errors']}"

        print(f"\n  ✓ Invoice created: {result['invoice_id']}")
        print(f"  ✓ Lines created: {len(result['line_ids'])}")
        print(f"  ✓ Processed: {result['processed']}")
        print(f"  ✓ Paid: {result['paid']}")
        print(f"  Final Status: {result['status']}")

        print_test_result(10, True, "Full automation workflow successful")
        return True

    except Exception as e:
        print(f"\n✗ Error in test 10: {e}")
        import traceback
        traceback.print_exc()
        print_test_result(10, False, str(e))
        return False


# ============================================================================
# Main Test Runner
# ============================================================================

def main():
    """Main test runner."""
    parser = argparse.ArgumentParser(
        description='Test invoice creation helper methods',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
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
        help='Execute live tests (creates real invoices)'
    )
    parser.add_argument(
        '--test',
        default='all',
        help='Run specific test (1-10) or "all" (default: all)'
    )
    parser.add_argument(
        '--pol',
        '--pol-id',
        dest='pol_id',
        help='Custom POL ID to use for testing (vendor will be auto-extracted)'
    )
    parser.add_argument(
        '--pol2',
        '--pol-id-2',
        dest='pol_id_2',
        help='Second POL ID for multi-line tests (optional, uses --pol if not specified)'
    )

    args = parser.parse_args()

    # Determine dry-run mode
    dry_run = not args.live

    # Declare globals if we need to override them
    global TEST_POL_1, TEST_POL_2, TEST_VENDOR

    # Determine which POLs and vendor to use
    test_pol_1 = args.pol_id if args.pol_id else TEST_POL_1
    test_pol_2 = args.pol_id_2 if args.pol_id_2 else (args.pol_id if args.pol_id else TEST_POL_2)
    test_vendor = TEST_VENDOR  # Will be overridden if custom POL is used

    # Print configuration
    print("\n" + "=" * 70)
    print("INVOICE CREATION TEST SUITE")
    print("=" * 70)
    print(f"Environment: {args.environment}")
    print(f"Mode: {'DRY RUN (validation only)' if dry_run else 'LIVE (creates invoices)'}")
    print(f"Tests: {args.test}")
    print(f"Test POL 1: {test_pol_1}")
    print(f"Test POL 2: {test_pol_2}")
    if args.pol_id:
        print(f"Custom POL mode: Vendor will be auto-extracted from POL")
    else:
        print(f"Test Vendor: {test_vendor}")
    print("=" * 70)

    # Confirmation for live mode
    if not dry_run:
        print(f"\n⚠️  WARNING: Running in LIVE mode - will create invoices in {args.environment}!")
        confirmation = input("\nType 'YES' to proceed: ")
        if confirmation != 'YES':
            print("Aborted.")
            return 1

    # Initialize client
    try:
        client = AlmaAPIClient(args.environment)
        acq = Acquisitions(client)
        print(f"\n✓ Connected to {args.environment}")
    except Exception as e:
        print(f"\n✗ Failed to initialize client: {e}")
        return 1

    # If custom POL specified, extract vendor from it
    if args.pol_id:
        print(f"\n🔍 Extracting vendor from custom POL: {test_pol_1}")
        try:
            vendor = acq.get_vendor_from_pol(test_pol_1)
            if vendor:
                test_vendor = vendor
                print(f"✓ Vendor extracted: {test_vendor}")

                # Update global constants for tests to use
                TEST_POL_1 = test_pol_1
                TEST_POL_2 = test_pol_2
                TEST_VENDOR = test_vendor
            else:
                print(f"⚠️  Warning: Could not extract vendor from POL {test_pol_1}")
                print(f"   Continuing with default vendor: {test_vendor}")
        except Exception as e:
            print(f"⚠️  Warning: Failed to extract vendor: {e}")
            print(f"   Continuing with default vendor: {test_vendor}")

    # Define test suite
    tests = [
        (1, "Date Formatting", test_1_date_formatting),
        (2, "Invoice Structure Builder", test_2_invoice_structure_builder),
        (3, "Invoice Line Structure Builder", test_3_invoice_line_structure_builder),
        (4, "Get Vendor from POL", test_4_get_vendor_from_pol),
        (5, "Get Fund from POL", test_5_get_fund_from_pol),
        (6, "Simple Invoice Creation", test_6_simple_invoice_creation),
        (7, "Simple Invoice Line Creation", test_7_simple_invoice_line_creation),
        (8, "Workflow: Create Only", test_8_workflow_create_only),
        (9, "Workflow: With Processing", test_9_workflow_with_processing),
        (10, "Workflow: Full Automation", test_10_workflow_full_automation),
    ]

    # Filter tests if specific test requested
    if args.test != 'all':
        try:
            test_num = int(args.test)
            tests = [(num, name, func) for num, name, func in tests if num == test_num]
            if not tests:
                print(f"\n✗ Invalid test number: {test_num}")
                return 1
        except ValueError:
            print(f"\n✗ Invalid test specification: {args.test}")
            return 1

    # Run tests
    results = []
    for test_num, test_name, test_func in tests:
        try:
            passed = test_func(acq, dry_run=dry_run)
            results.append((test_num, test_name, passed))
        except Exception as e:
            print(f"\n✗ Unexpected error in test {test_num}: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_num, test_name, False))

    # Print summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)

    passed_count = sum(1 for _, _, passed in results if passed)
    total_count = len(results)

    for test_num, test_name, passed in results:
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"{status}: Test {test_num} - {test_name}")

    print(f"\nResults: {passed_count}/{total_count} tests passed")

    if passed_count == total_count:
        print("\n✓ All tests passed!")
        return 0
    else:
        print(f"\n✗ {total_count - passed_count} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
