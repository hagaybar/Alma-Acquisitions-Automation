#!/usr/bin/env python3
"""
TEST 5.2: Mark Invoice as Paid

This script marks an invoice as paid in Alma.
WARNING: This script MODIFIES data in SANDBOX environment.

Usage:
    python test_pay_invoice.py <INVOICE_ID>

Example:
    python test_pay_invoice.py 35899258660004146
"""
import sys
import argparse
from almaapitk import AlmaAPIClient
from almaapitk import Acquisitions

# Parse command line arguments
parser = argparse.ArgumentParser(description='Mark an invoice as paid')
parser.add_argument('invoice_id', help='Invoice ID (e.g., 35899258660004146)')

args = parser.parse_args()
invoice_id = args.invoice_id

# Initialize
client = AlmaAPIClient('SANDBOX')
acq = Acquisitions(client)

print("=" * 70)
print("TEST 5.2: Mark Invoice as Paid")
print("=" * 70)
print(f"\nInvoice ID: {invoice_id}")

print("\n⚠️  WARNING: This will MODIFY data in SANDBOX environment")
print("-" * 70)

# Verify invoice status BEFORE marking as paid
print("\n=== STEP 1: Verify Invoice Status (BEFORE) ===")
try:
    invoice_before = acq.get_invoice(invoice_id)

    # Extract details
    invoice_number = invoice_before.get('number', 'N/A')
    vendor = invoice_before.get('vendor', {})
    vendor_code = vendor.get('value', 'N/A')
    vendor_name = vendor.get('desc', 'N/A')
    invoice_status = invoice_before.get('invoice_status', {}).get('value', 'N/A')

    # Extract payment status from nested payment object
    payment = invoice_before.get('payment', {})
    payment_status_obj = payment.get('payment_status', {})
    payment_status_before = payment_status_obj.get('value', 'Unknown')

    # Extract total amount
    total_amount = invoice_before.get('total_amount', 'N/A')
    currency = invoice_before.get('currency', {}).get('value', 'N/A')

    print(f"Invoice Number: {invoice_number}")
    print(f"Vendor: {vendor_code} - {vendor_name}")
    print(f"Invoice Status: {invoice_status}")
    print(f"Payment Status: {payment_status_before}")
    print(f"Total Amount: {total_amount} {currency}")

    # Check if already paid
    if payment_status_before in ['PAID', 'FULLY_PAID']:
        print(f"\n⚠️  WARNING: Invoice is already paid (status: {payment_status_before})")
        print("This operation may be idempotent, continuing...")
    else:
        print(f"✓ Invoice is not paid - ready to mark as paid")

except Exception as e:
    print(f"✗ ERROR verifying invoice: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Mark invoice as paid
print("\n=== STEP 2: Mark Invoice as Paid ===")
try:
    result = acq.mark_invoice_paid(invoice_id)

    print("✓ Invoice payment operation completed")

    # Try to extract payment status from result
    if isinstance(result, dict):
        result_payment = result.get('payment', {})
        result_payment_status = result_payment.get('payment_status', {})
        result_status_value = result_payment_status.get('value', 'N/A')
        print(f"\nOperation Result:")
        print(f"  Payment Status: {result_status_value}")
    else:
        print(f"\nOperation returned: {result}")

except Exception as e:
    print(f"\n✗ ERROR marking invoice as paid: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Verify invoice status AFTER marking as paid
print("\n=== STEP 3: Verify Invoice Status (AFTER) ===")
try:
    invoice_after = acq.get_invoice(invoice_id)

    # Extract payment status from nested payment object
    payment_after = invoice_after.get('payment', {})
    payment_status_obj_after = payment_after.get('payment_status', {})
    payment_status_after = payment_status_obj_after.get('value', 'Unknown')

    invoice_status_after = invoice_after.get('invoice_status', {}).get('value', 'N/A')

    print(f"Invoice Status: {invoice_status_after}")
    print(f"Payment Status: {payment_status_after}")

    # Verify status changed
    if payment_status_after in ['PAID', 'FULLY_PAID']:
        print(f"\n✓ SUCCESS: Invoice marked as paid")
        print(f"✓ Payment status changed: {payment_status_before} → {payment_status_after}")
    else:
        print(f"\n⚠️  WARNING: Payment status is '{payment_status_after}' (expected PAID or FULLY_PAID)")

except Exception as e:
    print(f"✗ ERROR verifying after payment: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test Summary
print("\n" + "=" * 70)
print("=== TEST 5.2 SUMMARY ===")
print(f"✓ Invoice {invoice_id} payment operation completed")
print(f"✓ Payment Status: {payment_status_before} → {payment_status_after}")
print(f"✓ Invoice Status: {invoice_status_after}")

if payment_status_after in ['PAID', 'FULLY_PAID']:
    print("✓ TEST 5.2 PASSED")
else:
    print(f"⚠️  TEST 5.2 COMPLETED (Status: {payment_status_after})")

print("=" * 70)
