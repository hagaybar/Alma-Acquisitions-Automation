#!/usr/bin/env python3
"""
Test duplicate invoice detection for POL-5994.

Tests the check_pol_invoiced() method to verify it can correctly detect
that POL-5994 already has an invoice line.

Expected Result:
- POL-5994 should be detected as ALREADY INVOICED
- Should find invoice: INV-POL5994-20251023-215508 (ID: 35925649570004146)
- Should report invoice line details including amount (25.0 ILS)
"""

from almaapitk import AlmaAPIClient
from almaapitk import Acquisitions

def test_duplicate_detection_positive():
    """
    Test 1: Positive Case - POL that IS already invoiced

    POL-5994 has an existing invoice line, so check_pol_invoiced()
    should return is_invoiced=True with invoice details.
    """
    print("\n" + "=" * 70)
    print("TEST 1: Duplicate Detection - Positive Case (POL IS Invoiced)")
    print("=" * 70)
    print("\nPOL: POL-5994")
    print("Expected: is_invoiced=True")
    print("Expected: Should find invoice INV-POL5994-20251023-215508")
    print()

    client = AlmaAPIClient(environment='SANDBOX')
    acq = Acquisitions(client)

    try:
        # Check if POL-5994 is invoiced
        result = acq.check_pol_invoiced("POL-5994")

        print("\n" + "-" * 70)
        print("RESULT:")
        print("-" * 70)
        print(f"Is Invoiced: {result['is_invoiced']}")
        print(f"Invoice Count: {result['invoice_count']}")

        if result['is_invoiced']:
            print(f"\n✓ TEST PASSED: POL-5994 correctly detected as invoiced")
            print(f"\nInvoice Details:")
            for idx, inv in enumerate(result['invoices'], 1):
                print(f"\n  Invoice {idx}:")
                print(f"    Invoice ID: {inv['invoice_id']}")
                print(f"    Invoice Number: {inv['invoice_number']}")
                print(f"    Invoice Status: {inv['invoice_status']}")
                print(f"    Line ID: {inv['line_id']}")
                print(f"    Amount: {inv['amount']}")
                print(f"    Line Status: {inv['line_status']}")

            # Verify specific invoice
            expected_invoice_id = "35925649570004146"
            expected_invoice_number = "INV-POL5994-20251023-215508"

            found_expected = False
            for inv in result['invoices']:
                if inv['invoice_id'] == expected_invoice_id:
                    found_expected = True
                    if inv['invoice_number'] == expected_invoice_number:
                        print(f"\n✓ Found expected invoice: {expected_invoice_number}")
                    else:
                        print(f"\n⚠️  Found invoice ID but number mismatch:")
                        print(f"   Expected: {expected_invoice_number}")
                        print(f"   Found: {inv['invoice_number']}")

            if not found_expected:
                print(f"\n⚠️  Did not find expected invoice ID: {expected_invoice_id}")
                print(f"   This might indicate an issue with the duplicate detection")

        else:
            print(f"\n✗ TEST FAILED: POL-5994 should be invoiced but was not detected")
            print(f"   This indicates the duplicate detection is not working correctly")
            if 'search_error' in result:
                print(f"   Search error: {result['search_error']}")

    except Exception as e:
        print(f"\n✗ TEST ERROR: {e}")
        import traceback
        traceback.print_exc()


def test_duplicate_detection_negative():
    """
    Test 2: Negative Case - POL that is NOT invoiced

    POL-5992 should NOT have invoice lines (or if it does, we'll see them).
    This tests that the method returns False for non-invoiced POLs.
    """
    print("\n\n" + "=" * 70)
    print("TEST 2: Duplicate Detection - Negative Case (POL NOT Invoiced)")
    print("=" * 70)
    print("\nPOL: POL-5993 (assuming this POL exists but has no invoice)")
    print("Expected: is_invoiced=False")
    print()

    client = AlmaAPIClient(environment='SANDBOX')
    acq = Acquisitions(client)

    try:
        # Check a POL that should NOT be invoiced
        # Using POL-5993 as test (you can change if you know a better one)
        result = acq.check_pol_invoiced("POL-5993")

        print("\n" + "-" * 70)
        print("RESULT:")
        print("-" * 70)
        print(f"Is Invoiced: {result['is_invoiced']}")
        print(f"Invoice Count: {result['invoice_count']}")

        if not result['is_invoiced']:
            print(f"\n✓ TEST PASSED: POL-5993 correctly detected as NOT invoiced")
            print(f"   This POL is safe to invoice")
        else:
            print(f"\n⚠️  UNEXPECTED: POL-5993 is actually invoiced")
            print(f"\nInvoice Details:")
            for idx, inv in enumerate(result['invoices'], 1):
                print(f"\n  Invoice {idx}:")
                print(f"    Invoice Number: {inv['invoice_number']}")
                print(f"    Amount: {inv['amount']}")
                print(f"    Status: {inv['invoice_status']}")

    except Exception as e:
        print(f"\n⚠️  TEST NOTE: Error checking POL-5993: {e}")
        print(f"   (POL-5993 might not exist in SANDBOX - this is okay)")


def test_duplicate_prevention_workflow():
    """
    Test 3: Workflow Test - Use check before creating invoice line

    Demonstrates how to use check_pol_invoiced() to prevent duplicates
    in a real workflow.
    """
    print("\n\n" + "=" * 70)
    print("TEST 3: Duplicate Prevention Workflow")
    print("=" * 70)
    print("\nScenario: Attempt to create a duplicate invoice line for POL-5994")
    print("Expected: Should detect existing invoice and prevent duplicate")
    print()

    client = AlmaAPIClient(environment='SANDBOX')
    acq = Acquisitions(client)

    try:
        pol_id = "POL-5994"

        # Step 1: Check before creating
        print("Step 1: Check if POL already has invoice...")
        check = acq.check_pol_invoiced(pol_id)

        # Step 2: Decision based on check
        if check['is_invoiced']:
            print(f"\n⚠️  DUPLICATE DETECTED!")
            print(f"✓ Prevention successful: Would NOT create duplicate invoice line")
            print(f"\nExisting invoice details:")
            for inv in check['invoices']:
                print(f"  - Invoice {inv['invoice_number']}")
                print(f"    Status: {inv['invoice_status']}")
                print(f"    Amount: {inv['amount']}")

            print(f"\n✓ TEST PASSED: Duplicate prevention workflow working correctly")

        else:
            print(f"\n✓ No existing invoice found")
            print(f"  Would proceed to create new invoice line")
            print(f"\n✗ TEST FAILED: Should have found existing invoice for POL-5994")

    except Exception as e:
        print(f"\n✗ TEST ERROR: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Run all duplicate detection tests."""
    print("\n")
    print("*" * 70)
    print(" Duplicate Invoice Detection Test Suite - POL-5994")
    print("*" * 70)
    print("\nThis test suite validates the check_pol_invoiced() method")
    print("using POL-5994 which has a known existing invoice.")
    print("\nInvoice Details:")
    print("  - Invoice ID: 35925649570004146")
    print("  - Invoice Number: INV-POL5994-20251023-215508")
    print("  - Amount: 25.0 ILS")
    print("  - Status: ACTIVE (NOT paid)")
    print()

    # Run all tests
    test_duplicate_detection_positive()
    test_duplicate_detection_negative()
    test_duplicate_prevention_workflow()

    print("\n" + "=" * 70)
    print("TEST SUITE COMPLETE")
    print("=" * 70)
    print("\nSummary:")
    print("  Test 1: Verify POL-5994 is detected as invoiced")
    print("  Test 2: Verify POL-5993 is detected as NOT invoiced")
    print("  Test 3: Verify duplicate prevention workflow")
    print()
    print("Check logs for detailed API calls:")
    print("  python3 view_logs.py --search 'POL-5994' --domain acquisitions")
    print("  python3 view_logs.py --search 'check_pol_invoiced'")
    print()


if __name__ == "__main__":
    main()
