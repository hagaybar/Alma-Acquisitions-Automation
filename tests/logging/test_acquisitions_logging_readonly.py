#!/usr/bin/env python3
"""
Test script for Acquisitions domain logging with READ-ONLY API calls.

Makes real API calls to Alma SANDBOX environment to generate actual logs.
All calls are read-only (GET requests) - no data modification.

Operations tested:
- Get POL by ID
- Get invoice by ID
- Get invoice lines
- Search invoices
"""

from almaapitk import AlmaAPIClient
from almaapitk import Acquisitions

# Known test data in SANDBOX (these should exist from previous tests)
TEST_POL_ID = "POL-5992"  # From your recent tests
TEST_INVOICE_ID = "35925542400004146"  # Invoice you created recently

def test_get_pol():
    """Test: Get POL by ID (read-only)."""
    print("\n" + "=" * 70)
    print("TEST 1: Get POL by ID (READ-ONLY)")
    print("=" * 70)

    client = AlmaAPIClient(environment='SANDBOX')
    acq = Acquisitions(client)

    try:
        print(f"Getting POL: {TEST_POL_ID}...")
        pol_data = acq.get_pol(TEST_POL_ID)

        print(f"✓ POL retrieved successfully")
        print(f"  Number: {pol_data.get('number')}")
        print(f"  Type: {pol_data.get('type', {}).get('value')}")
        print(f"  Status: {pol_data.get('status', {}).get('value')}")

        # Check if this logs to acquisitions.log
        print("\n  → This should create logs in:")
        print("     - logs/api_requests/<date>/api_client.log (HTTP GET)")
        print("     - logs/api_requests/<date>/acquisitions.log (domain operation)")

    except Exception as e:
        print(f"✗ Error: {e}")


def test_get_invoice():
    """Test: Get invoice by ID (read-only)."""
    print("\n" + "=" * 70)
    print("TEST 2: Get Invoice by ID (READ-ONLY)")
    print("=" * 70)

    client = AlmaAPIClient(environment='SANDBOX')
    acq = Acquisitions(client)

    try:
        print(f"Getting invoice: {TEST_INVOICE_ID}...")
        invoice_data = acq.get_invoice(TEST_INVOICE_ID)

        print(f"✓ Invoice retrieved successfully")
        print(f"  Number: {invoice_data.get('number')}")
        print(f"  Status: {invoice_data.get('invoice_status', {}).get('value')}")
        print(f"  Total: {invoice_data.get('total_amount')} {invoice_data.get('currency', {}).get('value')}")

    except Exception as e:
        print(f"✗ Error: {e}")


def test_get_invoice_lines():
    """Test: Get invoice lines (read-only)."""
    print("\n" + "=" * 70)
    print("TEST 3: Get Invoice Lines (READ-ONLY)")
    print("=" * 70)

    client = AlmaAPIClient(environment='SANDBOX')
    acq = Acquisitions(client)

    try:
        print(f"Getting lines for invoice: {TEST_INVOICE_ID}...")
        lines = acq.get_invoice_lines(TEST_INVOICE_ID)

        print(f"✓ Invoice lines retrieved successfully")
        print(f"  Number of lines: {lines.get('total_record_count', 0)}")

        invoice_lines = lines.get('invoice_line', [])
        for idx, line in enumerate(invoice_lines[:3], 1):  # Show first 3
            print(f"  Line {idx}: {line.get('total_price')} {line.get('currency', {}).get('value')}")

    except Exception as e:
        print(f"✗ Error: {e}")


def test_search_invoices():
    """Test: Search invoices (read-only)."""
    print("\n" + "=" * 70)
    print("TEST 4: Search Invoices (READ-ONLY)")
    print("=" * 70)

    client = AlmaAPIClient(environment='SANDBOX')
    acq = Acquisitions(client)

    try:
        # Search for recent invoices
        print("Searching for recent invoices in SANDBOX...")

        # Use the client directly for search
        response = client.get(
            'almaws/v1/acq/invoices',
            params={
                'limit': 5,
                'offset': 0
            }
        )

        invoices_data = response.json()
        total = invoices_data.get('total_record_count', 0)
        invoices = invoices_data.get('invoice', [])

        print(f"✓ Search completed")
        print(f"  Total invoices found: {total}")
        print(f"  Showing first {len(invoices)} invoices:")

        for idx, inv in enumerate(invoices, 1):
            inv_num = inv.get('number', 'N/A')
            inv_status = inv.get('invoice_status', {}).get('value', 'N/A')
            print(f"    {idx}. {inv_num} - Status: {inv_status}")

    except Exception as e:
        print(f"✗ Error: {e}")


def test_check_pol_invoiced():
    """Test: Check if POL is invoiced (read-only)."""
    print("\n" + "=" * 70)
    print("TEST 5: Check POL Invoiced Status (READ-ONLY)")
    print("=" * 70)

    client = AlmaAPIClient(environment='SANDBOX')
    acq = Acquisitions(client)

    try:
        print(f"Checking if POL {TEST_POL_ID} is invoiced...")
        result = acq.check_pol_invoiced(TEST_POL_ID)

        print(f"✓ Check completed")
        print(f"  Is invoiced: {result.get('is_invoiced')}")
        print(f"  Invoice count: {result.get('invoice_count', 0)}")

        if result.get('invoices'):
            print(f"  Invoices:")
            for inv_id in result['invoices'][:3]:  # Show first 3
                print(f"    - {inv_id}")

    except Exception as e:
        print(f"✗ Error: {e}")


def main():
    """Run all read-only acquisition tests."""
    print("\n")
    print("*" * 70)
    print(" Acquisitions Domain Logging Test - READ-ONLY API Calls")
    print("*" * 70)
    print("\nThis test makes REAL API calls to Alma SANDBOX.")
    print("All calls are READ-ONLY (GET requests) - no data modification.")
    print("\nLogs will be created in:")
    print("  - logs/api_requests/<date>/api_client.log (HTTP layer)")
    print("  - logs/api_requests/<date>/acquisitions.log (domain layer)")
    print()

    # Run tests
    test_get_pol()
    test_get_invoice()
    test_get_invoice_lines()
    test_search_invoices()
    test_check_pol_invoiced()

    print("\n" + "=" * 70)
    print("ALL TESTS COMPLETE")
    print("=" * 70)
    print("\nCheck the logs:")
    print(f"  tail -20 logs/api_requests/$(date +%Y-%m-%d)/api_client.log")
    print(f"  tail -20 logs/api_requests/$(date +%Y-%m-%d)/acquisitions.log")
    print("\nVerify API key redaction:")
    print(f"  grep 'REDACTED' logs/api_requests/$(date +%Y-%m-%d)/api_client.log")
    print()


if __name__ == "__main__":
    main()
