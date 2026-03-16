#!/usr/bin/env python3
"""
Test script for invoice operations in Acquisitions domain.
Tests invoice retrieval, summary, and line operations.
"""
import sys
from almaapitk import AlmaAPIClient
from almaapitk import Acquisitions

# Get Invoice ID from command line
if len(sys.argv) < 2:
    print("Usage: python test_invoice_operations.py <INVOICE_ID>")
    print("\nExample: python test_invoice_operations.py 2266653")
    sys.exit(1)

invoice_id = sys.argv[1]

# Initialize
client = AlmaAPIClient('SANDBOX')
acq = Acquisitions(client)

print(f"\nTesting Invoice Operations: {invoice_id}")
print("=" * 70)

try:
    # TEST 4.1: Get Invoice by ID
    print("\nTEST 4.1: Get Invoice by ID")
    print("-" * 70)

    invoice_data = acq.get_invoice(invoice_id)

    print(f"\n✓ Invoice Retrieved Successfully")
    print(f"\n=== INVOICE DETAILS ===")
    print(f"Invoice ID: {invoice_data.get('id', 'N/A')}")
    print(f"Invoice Number: {invoice_data.get('number', 'N/A')}")
    print(f"Vendor Code: {invoice_data.get('vendor', {}).get('value', 'N/A')}")
    print(f"Vendor Name: {invoice_data.get('vendor', {}).get('desc', 'N/A')}")
    print(f"Invoice Date: {invoice_data.get('invoice_date', 'N/A')}")
    print(f"Invoice Status: {invoice_data.get('invoice_status', {}).get('value', 'N/A')}")

    # Extract payment status from nested payment object
    payment = invoice_data.get('payment', {})
    payment_status = payment.get('payment_status', {}).get('value', 'N/A')
    print(f"Payment Status: {payment_status}")

    # Amount information - handle both dict and simple numeric types
    total_amount = invoice_data.get('total_amount', 'N/A')
    currency_code = invoice_data.get('currency', {}).get('value', 'N/A')

    if isinstance(total_amount, dict):
        amount_value = total_amount.get('sum', 'N/A')
        amount_currency = total_amount.get('currency', {}).get('value', currency_code)
    else:
        amount_value = total_amount
        amount_currency = currency_code

    print(f"\nTotal Amount: {amount_value} {amount_currency}")

    # Additional useful fields
    print(f"\nCreation Date: {invoice_data.get('creation_date', 'N/A')}")
    print(f"Owner: {invoice_data.get('owner', {}).get('value', 'N/A')}")

    print(f"\n✓ TEST 4.1 PASSED")

    # TEST 4.2: Get Invoice Summary
    print("\n" + "=" * 70)
    print("TEST 4.2: Get Invoice Summary")
    print("-" * 70)

    summary = acq.get_invoice_summary(invoice_id)

    print(f"\n✓ Invoice Summary Retrieved")
    print(f"\n=== INVOICE SUMMARY ===")
    for key, value in summary.items():
        print(f"{key}: {value}")

    print(f"\n✓ TEST 4.2 PASSED")

    # TEST 4.3: Get Invoice Lines
    print("\n" + "=" * 70)
    print("TEST 4.3: Get Invoice Lines")
    print("-" * 70)

    lines = acq.get_invoice_lines(invoice_id)

    print(f"\n✓ Invoice Lines Retrieved: {len(lines)} line(s)")

    if lines:
        print(f"\n=== INVOICE LINES ===")
        for i, line in enumerate(lines, 1):
            print(f"\nLine {i}:")
            print(f"  Line Number: {line.get('line_number', 'N/A')}")
            print(f"  POL Number: {line.get('po_line', 'N/A')}")
            print(f"  Quantity: {line.get('quantity', 'N/A')}")

            # Price information - handle both dict and simple numeric types
            price = line.get('price', 'N/A')
            if isinstance(price, dict):
                price_display = f"{price.get('sum', 'N/A')} {price.get('currency', {}).get('value', 'N/A')}"
            else:
                price_display = str(price)
            print(f"  Price: {price_display}")

            total_price = line.get('total_price', 'N/A')
            if isinstance(total_price, dict):
                total_display = f"{total_price.get('sum', 'N/A')} {total_price.get('currency', {}).get('value', 'N/A')}"
            else:
                total_display = str(total_price)
            print(f"  Total Price: {total_display}")

            # Note if present
            note = line.get('note')
            if note:
                print(f"  Note: {note}")
    else:
        print("\n⚠️  No invoice lines found")

    print(f"\n✓ TEST 4.3 PASSED")

    # Summary of all tests
    print("\n" + "=" * 70)
    print("=== TEST SUMMARY ===")
    print("✓ TEST 4.1: Get Invoice by ID - PASSED")
    print("✓ TEST 4.2: Get Invoice Summary - PASSED")
    print("✓ TEST 4.3: Get Invoice Lines - PASSED")
    print(f"\nAll invoice operations tests completed successfully for Invoice {invoice_id}")
    print("=" * 70)

except Exception as e:
    print(f"\n✗ TEST FAILED: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)