#!/usr/bin/env python3
"""
Complete Invoice Workflow for POL-5994 - Full Documentation

This script demonstrates the COMPLETE and CORRECT invoice workflow:
1. Create invoice
2. Create invoice line
3. PROCESS/APPROVE invoice (mandatory!)
4. Mark invoice as PAID
5. Verify POL state

POL Details:
- POL: POL-5994
- Amount: 25.0 ILS
- Vendor: TestVendor
- Item: 23472684490004146 (AC1-800062117)
"""

from almaapitk import AlmaAPIClient
from almaapitk import Acquisitions
from datetime import datetime
import json

def print_section(title):
    """Print formatted section header."""
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)

def main():
    print("\n" + "*" * 70)
    print(" POL-5994 Complete Invoice Workflow - Full Documentation")
    print("*" * 70)
    print("\nCOMPLETE CORRECT WORKFLOW:")
    print("  1. Create invoice")
    print("  2. Create invoice line")
    print("  3. Process/Approve invoice (MANDATORY)")
    print("  4. Mark invoice as paid")
    print("  5. Verify POL state")
    print()

    pol_id = "POL-5994"

    client = AlmaAPIClient(environment='SANDBOX')
    acq = Acquisitions(client)

    try:
        # STEP 1: Get initial POL state
        print_section("STEP 1: Get Initial POL State")

        print(f"\nRetrieving POL {pol_id}...")
        pol_before = acq.get_pol(pol_id)

        pol_status_before = pol_before.get('status', {}).get('value')
        pol_price = pol_before.get('price', {}).get('sum')
        pol_currency = pol_before.get('price', {}).get('currency', {}).get('value')
        vendor_code = pol_before.get('vendor', {}).get('value')
        invoice_ref_before = pol_before.get('invoice_reference')

        print(f"\n✓ POL retrieved")
        print(f"\nInitial POL State:")
        print(f"  POL Number: {pol_before.get('number')}")
        print(f"  POL Status: {pol_status_before}")
        print(f"  Price: {pol_price} {pol_currency}")
        print(f"  Vendor: {vendor_code}")
        print(f"  Invoice Reference: {invoice_ref_before if invoice_ref_before else '(empty)'}")

        # Check item status
        items = acq.extract_items_from_pol_data(pol_before)
        if items:
            item = items[0]
            receive_date = item.get('receive_date')
            print(f"\n  Item Info:")
            print(f"    Item ID: {item.get('pid')}")
            print(f"    Barcode: {item.get('barcode')}")
            print(f"    Received: {'Yes (' + receive_date + ')' if receive_date else 'No'}")

        # STEP 2: Create Invoice
        print_section("STEP 2: Create Invoice")

        invoice_number = f"INV-POL5994-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        invoice_date = datetime.now().strftime("%Y-%m-%d")

        print(f"\nCreating invoice...")
        print(f"  Invoice Number: {invoice_number}")
        print(f"  Vendor: {vendor_code}")
        print(f"  Amount: {pol_price} {pol_currency}")
        print(f"  Date: {invoice_date}")

        invoice = acq.create_invoice_simple(
            invoice_number=invoice_number,
            invoice_date=invoice_date,
            vendor_code=vendor_code,
            total_amount=float(pol_price),
            currency=pol_currency
        )

        invoice_id = invoice.get('id')
        print(f"\n✓ Invoice created successfully")
        print(f"  Invoice ID: {invoice_id}")

        # Get invoice state after creation
        invoice_after_create = acq.get_invoice(invoice_id)
        status_after_create = invoice_after_create.get('invoice_status', {}).get('value')
        workflow_after_create = invoice_after_create.get('invoice_workflow_status', {}).get('value')
        approval_after_create = invoice_after_create.get('invoice_approval_status', {}).get('value')
        payment_after_create = invoice_after_create.get('payment', {}).get('payment_status', {}).get('value')

        print(f"\n  State After Creation:")
        print(f"    Invoice Status: {status_after_create}")
        print(f"    Workflow Status: {workflow_after_create}")
        print(f"    Approval Status: {approval_after_create}")
        print(f"    Payment Status: {payment_after_create}")

        # STEP 3: Create Invoice Line
        print_section("STEP 3: Create Invoice Line")

        print(f"\nCreating invoice line for POL {pol_id}...")
        print(f"  Amount: {pol_price} {pol_currency}")
        print(f"  Quantity: 1")
        print(f"  Fund Code: auto-detect from POL")

        line = acq.create_invoice_line_simple(
            invoice_id=invoice_id,
            pol_id=pol_id,
            amount=float(pol_price),
            quantity=1,
            currency=pol_currency
        )

        line_id = line.get('id')
        fund_code = line.get('fund_distribution', [{}])[0].get('fund_code', {}).get('value')

        print(f"\n✓ Invoice line created successfully")
        print(f"  Line ID: {line_id}")
        print(f"  Fund Code: {fund_code}")
        print(f"  Total Price: {line.get('total_price')}")

        # STEP 4: PROCESS/APPROVE Invoice (MANDATORY!)
        print_section("STEP 4: Process/Approve Invoice (MANDATORY STEP)")

        print(f"\n⚠️  CRITICAL: Invoice MUST be processed before payment!")
        print(f"\nProcessing invoice {invoice_id}...")
        print(f"API Call: POST /almaws/v1/acq/invoices/{invoice_id}?op=process_invoice")

        processed_invoice = acq.approve_invoice(invoice_id)

        print(f"\n✓ Invoice processed/approved successfully")

        # Get invoice state after processing
        invoice_after_process = acq.get_invoice(invoice_id)
        status_after_process = invoice_after_process.get('invoice_status', {}).get('value')
        workflow_after_process = invoice_after_process.get('invoice_workflow_status', {}).get('value')
        approval_after_process = invoice_after_process.get('invoice_approval_status', {}).get('value')
        payment_after_process = invoice_after_process.get('payment', {}).get('payment_status', {}).get('value')

        print(f"\n  State After Processing:")
        print(f"    Invoice Status: {status_after_process}")
        print(f"    Workflow Status: {workflow_after_process}")
        print(f"    Approval Status: {approval_after_process}")
        print(f"    Payment Status: {payment_after_process}")

        print(f"\n  Changes from Processing:")
        print(f"    Workflow: {workflow_after_create} → {workflow_after_process}")
        print(f"    Approval: {approval_after_create} → {approval_after_process}")

        # STEP 5: Mark Invoice as PAID
        print_section("STEP 5: Mark Invoice as PAID")

        print(f"\nMarking invoice {invoice_id} as paid...")
        print(f"API Call: POST /almaws/v1/acq/invoices/{invoice_id}?op=paid")

        paid_invoice = acq.mark_invoice_paid(invoice_id)

        print(f"\n✓ Invoice marked as paid successfully")

        # Get invoice state after payment
        invoice_after_payment = acq.get_invoice(invoice_id)
        status_after_payment = invoice_after_payment.get('invoice_status', {}).get('value')
        workflow_after_payment = invoice_after_payment.get('invoice_workflow_status', {}).get('value')
        approval_after_payment = invoice_after_payment.get('invoice_approval_status', {}).get('value')
        payment_after_payment = invoice_after_payment.get('payment', {}).get('payment_status', {}).get('value')

        print(f"\n  State After Payment:")
        print(f"    Invoice Status: {status_after_payment}")
        print(f"    Workflow Status: {workflow_after_payment}")
        print(f"    Approval Status: {approval_after_payment}")
        print(f"    Payment Status: {payment_after_payment}")

        print(f"\n  Changes from Payment:")
        print(f"    Payment Status: {payment_after_process} → {payment_after_payment}")

        # STEP 6: Verify POL State
        print_section("STEP 6: Verify POL State After Payment")

        print(f"\nRetrieving POL {pol_id} to check for changes...")
        pol_after = acq.get_pol(pol_id)

        pol_status_after = pol_after.get('status', {}).get('value')
        invoice_ref_after = pol_after.get('invoice_reference')

        print(f"\n✓ POL retrieved")
        print(f"\nPOL State After Payment:")
        print(f"  POL Status: {pol_status_after}")
        print(f"  Invoice Reference: {invoice_ref_after if invoice_ref_after else '(empty)'}")

        print(f"\nPOL Status Change:")
        print(f"  {pol_status_before} → {pol_status_after}")

        if pol_status_after == "CLOSED":
            print(f"\n✓ POL AUTO-CLOSED after invoice payment!")
        elif pol_status_before != pol_status_after:
            print(f"\n⚠️  POL status changed but not to CLOSED")
        else:
            print(f"\n⚠️  POL status did NOT change (remains: {pol_status_after})")
            print(f"\n  Possible reasons:")
            print(f"    - Item not received yet (check item receive_date)")
            print(f"    - POL configuration requires manual closure")
            print(f"    - Additional conditions not met")

        # STEP 7: Complete Summary
        print_section("STEP 7: Complete Workflow Summary")

        print(f"\nCREATED ENTITIES:")
        print(f"  Invoice ID: {invoice_id}")
        print(f"  Invoice Number: {invoice_number}")
        print(f"  Invoice Line ID: {line_id}")
        print(f"  Amount: {pol_price} {pol_currency}")
        print(f"  Fund: {fund_code}")

        print(f"\nSTATE TRANSITIONS:")
        print(f"\n  After Creation:")
        print(f"    Status: {status_after_create}")
        print(f"    Workflow: {workflow_after_create}")
        print(f"    Approval: {approval_after_create}")
        print(f"    Payment: {payment_after_create}")

        print(f"\n  After Processing:")
        print(f"    Status: {status_after_process}")
        print(f"    Workflow: {workflow_after_process}")
        print(f"    Approval: {approval_after_process}")
        print(f"    Payment: {payment_after_process}")

        print(f"\n  After Payment:")
        print(f"    Status: {status_after_payment}")
        print(f"    Workflow: {workflow_after_payment}")
        print(f"    Approval: {approval_after_payment}")
        print(f"    Payment: {payment_after_payment}")

        print(f"\n  POL Status:")
        print(f"    Before: {pol_status_before}")
        print(f"    After: {pol_status_after}")

        print(f"\nAPI CALLS SEQUENCE:")
        print(f"  1. GET /almaws/v1/acq/po-lines/{pol_id} (initial state)")
        print(f"  2. POST /almaws/v1/acq/invoices (create invoice)")
        print(f"  3. GET /almaws/v1/acq/invoices/{invoice_id} (verify creation)")
        print(f"  4. GET /almaws/v1/acq/po-lines/{pol_id} (for fund extraction)")
        print(f"  5. POST /almaws/v1/acq/invoices/{invoice_id}/lines (create line)")
        print(f"  6. POST /almaws/v1/acq/invoices/{invoice_id}?op=process_invoice ✓")
        print(f"  7. GET /almaws/v1/acq/invoices/{invoice_id} (verify processing)")
        print(f"  8. POST /almaws/v1/acq/invoices/{invoice_id}?op=paid ✓")
        print(f"  9. GET /almaws/v1/acq/invoices/{invoice_id} (verify payment)")
        print(f" 10. GET /almaws/v1/acq/po-lines/{pol_id} (verify POL state)")

        print_section("WORKFLOW COMPLETE")
        print(f"\n✓ Invoice {invoice_number} has been created, processed, and paid")
        print(f"✓ All data captured for case study documentation")
        print()

    except Exception as e:
        print(f"\n✗ Error: {e}")
        print(f"\nError occurred during workflow")
        print(f"Check logs for details")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
