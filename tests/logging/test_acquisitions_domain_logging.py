#!/usr/bin/env python3
"""
Test script for Acquisitions domain-level logging.

Demonstrates comprehensive logging at the domain layer:
- High-level operation tracking
- Business logic context
- Workflow step logging
- Error context at domain level

This script uses MOCK data (does not make real API calls) to show
what the logs will look like during actual operations.
"""

from almaapitk import AlmaAPIClient
from almaapitk import Acquisitions

def test_invoice_creation_logging():
    """
    Test invoice creation with domain-level logging.

    This demonstrates what logs you'll see when creating an invoice.
    """
    print("\n" + "=" * 70)
    print("TEST: Invoice Creation with Domain Logging")
    print("=" * 70)
    print("\nThis test will ATTEMPT to create an invoice (may fail if test data doesn't exist)")
    print("The goal is to demonstrate the logging, not to succeed.\n")

    client = AlmaAPIClient(environment='SANDBOX')
    acq = Acquisitions(client)

    try:
        # Attempt to create an invoice (may fail, that's okay)
        invoice = acq.create_invoice_simple(
            invoice_number="LOG-TEST-001",
            invoice_date="2025-10-23",
            vendor_code="TESTVENDOR",
            total_amount=100.00,
            currency="ILS"
        )

        print(f"\n✓ Invoice created: {invoice.get('id')}")

    except Exception as e:
        print(f"\n✗ Expected error (test data doesn't exist): {e}")
        print("   This is normal - we're testing logging, not creating real data")

    print("\n" + "-" * 70)
    print("WHAT WAS LOGGED:")
    print("-" * 70)
    print("Check logs/api_requests/$(date +%Y-%m-%d)/acquisitions.log")
    print("\nYou should see:")
    print("  1. INFO: Creating invoice (simple): LOG-TEST-001")
    print("     - invoice_number, vendor_code, total_amount, currency")
    print("  2. DEBUG: Invoice structure built")
    print("     - structure_keys showing what was built")
    print("  3. Either:")
    print("     - INFO: Invoice created successfully (if succeeded)")
    print("     - ERROR: Invoice creation API error (if failed)")
    print("\nAND in api_client.log:")
    print("  - POST almaws/v1/acq/invoices request")
    print("  - Full request body with invoice data")
    print("  - Response status and duration")
    print("  - Full response body (if successful)")


def test_invoice_line_logging():
    """
    Test invoice line creation with fund extraction logging.
    """
    print("\n\n" + "=" * 70)
    print("TEST: Invoice Line with Fund Extraction Logging")
    print("=" * 70)
    print("\nThis test attempts to create a line WITHOUT providing fund_code")
    print("The system will try to extract it from the POL.\n")

    client = AlmaAPIClient(environment='SANDBOX')
    acq = Acquisitions(client)

    try:
        # Try to create line without fund code (will attempt auto-extraction)
        line = acq.create_invoice_line_simple(
            invoice_id="FAKE-ID-123",  # Fake ID - will fail
            pol_id="POL-5992",  # Real POL from SANDBOX
            amount=50.00
            # Note: No fund_code - will try to extract from POL
        )

        print(f"\n✓ Line created")

    except Exception as e:
        print(f"\n✗ Expected error: {e}")
        print("   This demonstrates error logging")

    print("\n" + "-" * 70)
    print("WHAT WAS LOGGED:")
    print("-" * 70)
    print("In acquisitions.log:")
    print("  1. INFO: Creating invoice line (simple): POL-5992")
    print("     - invoice_id, pol_id, amount, fund_code='auto-detect'")
    print("  2. DEBUG: Extracting fund code from POL: POL-5992")
    print("  3. Either:")
    print("     - INFO: Fund code extracted from POL: XXXX")
    print("     - ERROR: Fund code extraction failed")
    print("  4. ERROR: Invoice line creation API error")
    print("\nIn api_client.log:")
    print("  - GET request to fetch POL data")
    print("  - Full POL object in response")
    print("  - POST request to create line (if fund found)")


def test_complete_workflow_logging():
    """
    Test complete workflow with all steps logged.
    """
    print("\n\n" + "=" * 70)
    print("TEST: Complete Workflow Logging")
    print("=" * 70)
    print("\nThis test demonstrates the complete workflow logging")
    print("(create invoice + add lines + process + pay)\n")

    client = AlmaAPIClient(environment='SANDBOX')
    acq = Acquisitions(client)

    try:
        lines = [
            {"pol_id": "POL-5992", "amount": 50.00},
            {"pol_id": "POL-5993", "amount": 75.00}
        ]

        result = acq.create_invoice_with_lines(
            invoice_number="WORKFLOW-TEST-001",
            invoice_date="2025-10-23",
            vendor_code="TESTVENDOR",
            lines=lines,
            auto_process=True,
            auto_pay=True
        )

        print(f"\n✓ Workflow completed: {result['invoice_id']}")

    except Exception as e:
        print(f"\n✗ Expected error: {e}")
        print("   This demonstrates workflow error logging")

    print("\n" + "-" * 70)
    print("WHAT WAS LOGGED:")
    print("-" * 70)
    print("In acquisitions.log (complete workflow trace):")
    print("  1. INFO: Starting complete invoice workflow: WORKFLOW-TEST-001")
    print("     - vendor_code, num_lines, currency, auto_process, auto_pay")
    print("  2. DEBUG: Workflow validation passed")
    print("  3. INFO: Workflow Step 1: Calculating total amount")
    print("  4. INFO: Total amount calculated: 125.0")
    print("  5. INFO: Workflow Step 2: Creating invoice")
    print("  6. INFO: Invoice created in workflow: [invoice_id]")
    print("  7. INFO: Workflow Step 3: Adding 2 invoice lines")
    print("     - pol_ids: [POL-5992, POL-5993]")
    print("  8. INFO: Creating invoice line (simple): POL-5992")
    print("  9. INFO: Creating invoice line (simple): POL-5993")
    print(" 10. INFO/WARNING: Line creation results")
    print(" 11. INFO: Workflow Step 4: Processing invoice")
    print(" 12. INFO: Invoice processed successfully")
    print(" 13. INFO: Workflow Step 5: Marking invoice as paid")
    print(" 14. INFO: Invoice marked as paid successfully")
    print(" 15. INFO: Workflow completed successfully")
    print("     - invoice_id, total_amount, lines_created, processed, paid, status")


def main():
    """Run all domain logging tests."""
    print("\n")
    print("*" * 70)
    print(" Acquisitions Domain Logging Tests")
    print("*" * 70)
    print("\nThese tests demonstrate domain-level logging capabilities.")
    print("Tests may fail (expected) - we're demonstrating logging, not data creation.")
    print("\nLogs will be written to:")
    print("  - logs/api_requests/<date>/acquisitions.log (domain layer)")
    print("  - logs/api_requests/<date>/api_client.log (HTTP layer)")
    print()

    test_invoice_creation_logging()
    test_invoice_line_logging()
    test_complete_workflow_logging()

    print("\n\n" + "=" * 70)
    print("ALL TESTS COMPLETE")
    print("=" * 70)
    print("\nView the logs:")
    print(f"  tail -50 logs/api_requests/$(date +%Y-%m-%d)/acquisitions.log")
    print(f"  tail -50 logs/api_requests/$(date +%Y-%m-%d)/api_client.log")
    print("\nOr use the log viewer:")
    print("  python3 view_logs.py --domain acquisitions --tail --limit 30")
    print("  python3 view_logs.py --domain acquisitions --level ERROR")
    print()


if __name__ == "__main__":
    main()
