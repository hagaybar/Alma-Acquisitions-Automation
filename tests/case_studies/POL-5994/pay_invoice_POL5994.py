#!/usr/bin/env python3
"""
Pay Invoice for POL-5994 - Complete Documentation

This script marks the invoice as paid and documents the complete process
for the POL-5994 case study.

Invoice Details:
- Invoice ID: 35925649570004146
- Invoice Number: INV-POL5994-20251023-215508
- POL: POL-5994
- Amount: 25.0 ILS
- Current Status: ACTIVE, NOT_PAID
"""

from almaapitk import AlmaAPIClient
from almaapitk import Acquisitions
import json

def print_section(title):
    """Print formatted section header."""
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)

def print_json(data, title=""):
    """Print formatted JSON data."""
    if title:
        print(f"\n{title}:")
    print(json.dumps(data, indent=2))

def main():
    print("\n" + "*" * 70)
    print(" POL-5994 Invoice Payment Process - Complete Documentation")
    print("*" * 70)

    invoice_id = "35925649570004146"
    invoice_number = "INV-POL5994-20251023-215508"
    pol_id = "POL-5994"

    print(f"\nInvoice to be paid:")
    print(f"  Invoice ID: {invoice_id}")
    print(f"  Invoice Number: {invoice_number}")
    print(f"  POL: {pol_id}")
    print()

    client = AlmaAPIClient(environment='SANDBOX')
    acq = Acquisitions(client)

    try:
        # STEP 1: Get invoice BEFORE payment
        print_section("STEP 1: Retrieve Invoice BEFORE Payment")

        print(f"\nRetrieving current invoice state...")
        invoice_before = acq.get_invoice(invoice_id)

        # Extract key fields
        status_before = invoice_before.get('invoice_status', {}).get('value')
        payment_status_before = invoice_before.get('payment', {}).get('payment_status', {}).get('value')
        workflow_status_before = invoice_before.get('invoice_workflow_status', {}).get('value')
        approval_status_before = invoice_before.get('invoice_approval_status', {}).get('value')
        total_amount = invoice_before.get('total_amount')
        currency = invoice_before.get('currency', {}).get('value')

        print(f"\n✓ Invoice retrieved")
        print(f"\nCurrent State BEFORE Payment:")
        print(f"  Invoice Status: {status_before}")
        print(f"  Payment Status: {payment_status_before}")
        print(f"  Workflow Status: {workflow_status_before}")
        print(f"  Approval Status: {approval_status_before}")
        print(f"  Total Amount: {total_amount} {currency}")

        # STEP 2: Get invoice lines BEFORE payment
        print_section("STEP 2: Retrieve Invoice Lines BEFORE Payment")

        print(f"\nRetrieving invoice lines...")
        lines_before = acq.get_invoice_lines(invoice_id)

        print(f"\n✓ Lines retrieved: {len(lines_before)} line(s)")
        for idx, line in enumerate(lines_before, 1):
            print(f"\n  Line {idx}:")
            print(f"    Line ID: {line.get('id')}")
            print(f"    POL: {line.get('po_line')}")
            print(f"    Price: {line.get('price')}")
            print(f"    Quantity: {line.get('quantity')}")
            print(f"    Total: {line.get('total_price')}")
            print(f"    Status: {line.get('status', {}).get('value')}")
            print(f"    Fully Invoiced: {line.get('fully_invoiced')}")

        # STEP 3: Get POL status BEFORE payment
        print_section("STEP 3: Retrieve POL Status BEFORE Payment")

        print(f"\nRetrieving POL {pol_id}...")
        pol_before = acq.get_pol(pol_id)

        pol_status_before = pol_before.get('status', {}).get('value')
        pol_price = pol_before.get('price', {}).get('sum')
        pol_currency = pol_before.get('price', {}).get('currency', {}).get('value')
        invoice_ref = pol_before.get('invoice_reference')

        print(f"\n✓ POL retrieved")
        print(f"\nPOL State BEFORE Payment:")
        print(f"  POL Number: {pol_before.get('number')}")
        print(f"  POL Status: {pol_status_before}")
        print(f"  POL Price: {pol_price} {pol_currency}")
        print(f"  Invoice Reference: {invoice_ref if invoice_ref else '(empty)'}")
        print(f"  PO Number: {pol_before.get('po_number')}")

        # Check if item is received
        items = acq.extract_items_from_pol_data(pol_before)
        if items:
            item = items[0]
            print(f"\n  Item Info:")
            print(f"    Item ID: {item.get('pid')}")
            print(f"    Barcode: {item.get('barcode')}")
            print(f"    Receive Date: {item.get('receive_date', '(not received)')}")

        # STEP 4: Mark invoice as PAID
        print_section("STEP 4: Mark Invoice as PAID")

        print(f"\nMarking invoice {invoice_id} as paid...")
        print(f"API Call: POST /almaws/v1/acq/invoices/{invoice_id}?op=paid")

        paid_invoice = acq.mark_invoice_paid(invoice_id)

        print(f"\n✓ Invoice marked as paid")

        # STEP 5: Get invoice AFTER payment
        print_section("STEP 5: Retrieve Invoice AFTER Payment")

        print(f"\nRetrieving updated invoice state...")
        invoice_after = acq.get_invoice(invoice_id)

        # Extract key fields after payment
        status_after = invoice_after.get('invoice_status', {}).get('value')
        payment_status_after = invoice_after.get('payment', {}).get('payment_status', {}).get('value')
        workflow_status_after = invoice_after.get('invoice_workflow_status', {}).get('value')
        approval_status_after = invoice_after.get('invoice_approval_status', {}).get('value')

        print(f"\n✓ Invoice retrieved")
        print(f"\nCurrent State AFTER Payment:")
        print(f"  Invoice Status: {status_after}")
        print(f"  Payment Status: {payment_status_after}")
        print(f"  Workflow Status: {workflow_status_after}")
        print(f"  Approval Status: {approval_status_after}")

        # STEP 6: Get POL status AFTER payment
        print_section("STEP 6: Retrieve POL Status AFTER Payment")

        print(f"\nRetrieving POL {pol_id} to check for auto-closure...")
        pol_after = acq.get_pol(pol_id)

        pol_status_after = pol_after.get('status', {}).get('value')
        invoice_ref_after = pol_after.get('invoice_reference')

        print(f"\n✓ POL retrieved")
        print(f"\nPOL State AFTER Payment:")
        print(f"  POL Status: {pol_status_after}")
        print(f"  Invoice Reference: {invoice_ref_after if invoice_ref_after else '(empty)'}")

        # STEP 7: Summary of changes
        print_section("STEP 7: Summary of Changes")

        print(f"\nInvoice Changes:")
        print(f"  Status: {status_before} → {status_after}")
        print(f"  Payment: {payment_status_before} → {payment_status_after}")
        print(f"  Workflow: {workflow_status_before} → {workflow_status_after}")
        print(f"  Approval: {approval_status_before} → {approval_status_after}")

        print(f"\nPOL Changes:")
        print(f"  POL Status: {pol_status_before} → {pol_status_after}")

        if pol_status_before != pol_status_after:
            print(f"\n✓ POL STATUS CHANGED!")
            if pol_status_after == "CLOSED":
                print(f"  ✓ POL auto-closed after invoice payment")
        else:
            print(f"\n⚠️  POL status did NOT change")
            print(f"  Current status remains: {pol_status_after}")
            if pol_status_after != "CLOSED":
                print(f"\n  Possible reasons POL did not close:")
                print(f"    - Item may not be received yet")
                print(f"    - POL configuration may require manual closure")
                print(f"    - Invoice may need to be processed/approved first")

        # STEP 8: Data for documentation
        print_section("STEP 8: Complete Data for Documentation")

        print(f"\nBEFORE PAYMENT:")
        print(f"  Invoice: {status_before} / {payment_status_before}")
        print(f"  POL: {pol_status_before}")

        print(f"\nAFTER PAYMENT:")
        print(f"  Invoice: {status_after} / {payment_status_after}")
        print(f"  POL: {pol_status_after}")

        print(f"\nAPI CALLS MADE:")
        print(f"  1. GET /almaws/v1/acq/invoices/{invoice_id}")
        print(f"  2. GET /almaws/v1/acq/invoices/{invoice_id}/lines")
        print(f"  3. GET /almaws/v1/acq/po-lines/{pol_id}")
        print(f"  4. POST /almaws/v1/acq/invoices/{invoice_id}?op=paid")
        print(f"  5. GET /almaws/v1/acq/invoices/{invoice_id} (verify)")
        print(f"  6. GET /almaws/v1/acq/po-lines/{pol_id} (verify)")

        print_section("PAYMENT PROCESS COMPLETE")
        print(f"\n✓ Invoice {invoice_number} has been marked as paid")
        print(f"✓ All data captured for case study documentation")
        print()

    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
