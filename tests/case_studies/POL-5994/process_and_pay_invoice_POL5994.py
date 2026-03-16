#!/usr/bin/env python3
"""
Process and Pay Invoice for POL-5994 - Complete Documentation

CORRECTED WORKFLOW:
1. Process/Approve invoice FIRST (mandatory step)
2. Then mark as paid

Invoice Details:
- Invoice ID: 35925649570004146
- Invoice Number: INV-POL5994-20251023-215508
- POL: POL-5994
- Amount: 25.0 ILS
- Current Status: ACTIVE, NOT_PAID, PENDING approval
"""

from almaapitk import AlmaAPIClient
from almaapitk import Acquisitions
import json

def print_section(title):
    """Print formatted section header."""
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)

def main():
    print("\n" + "*" * 70)
    print(" POL-5994 Invoice Processing & Payment - Complete Documentation")
    print("*" * 70)
    print("\nCORRECT WORKFLOW:")
    print("  Step 1: Process/Approve invoice (mandatory)")
    print("  Step 2: Mark invoice as paid")
    print()

    invoice_id = "35925649570004146"
    invoice_number = "INV-POL5994-20251023-215508"
    pol_id = "POL-5994"

    print(f"Invoice to be processed and paid:")
    print(f"  Invoice ID: {invoice_id}")
    print(f"  Invoice Number: {invoice_number}")
    print(f"  POL: {pol_id}")
    print()

    client = AlmaAPIClient(environment='SANDBOX')
    acq = Acquisitions(client)

    try:
        # STEP 1: Get invoice BEFORE processing
        print_section("STEP 1: Retrieve Invoice State BEFORE Processing")

        print(f"\nRetrieving current invoice state...")
        invoice_before = acq.get_invoice(invoice_id)

        status_before = invoice_before.get('invoice_status', {}).get('value')
        payment_status_before = invoice_before.get('payment', {}).get('payment_status', {}).get('value')
        workflow_status_before = invoice_before.get('invoice_workflow_status', {}).get('value')
        approval_status_before = invoice_before.get('invoice_approval_status', {}).get('value')

        print(f"\n✓ Invoice retrieved")
        print(f"\nState BEFORE Processing:")
        print(f"  Invoice Status: {status_before}")
        print(f"  Payment Status: {payment_status_before}")
        print(f"  Workflow Status: {workflow_status_before}")
        print(f"  Approval Status: {approval_status_before}")

        # STEP 2: Get POL status BEFORE processing
        print_section("STEP 2: Retrieve POL Status BEFORE Processing")

        pol_before = acq.get_pol(pol_id)
        pol_status_before = pol_before.get('status', {}).get('value')

        print(f"\n✓ POL retrieved")
        print(f"  POL Status: {pol_status_before}")

        # Check item status
        items = acq.extract_items_from_pol_data(pol_before)
        if items:
            item = items[0]
            receive_date = item.get('receive_date')
            print(f"  Item Received: {'Yes (' + receive_date + ')' if receive_date else 'No'}")

        # STEP 3: Process/Approve invoice (MANDATORY)
        print_section("STEP 3: Process/Approve Invoice (MANDATORY STEP)")

        print(f"\nProcessing invoice {invoice_id}...")
        print(f"API Call: POST /almaws/v1/acq/invoices/{invoice_id}?op=process_invoice")

        processed_invoice = acq.approve_invoice(invoice_id)

        print(f"\n✓ Invoice processed/approved successfully")

        # STEP 4: Get invoice AFTER processing
        print_section("STEP 4: Retrieve Invoice State AFTER Processing")

        invoice_after_process = acq.get_invoice(invoice_id)

        status_after_process = invoice_after_process.get('invoice_status', {}).get('value')
        payment_status_after_process = invoice_after_process.get('payment', {}).get('payment_status', {}).get('value')
        workflow_status_after_process = invoice_after_process.get('invoice_workflow_status', {}).get('value')
        approval_status_after_process = invoice_after_process.get('invoice_approval_status', {}).get('value')

        print(f"\n✓ Invoice retrieved")
        print(f"\nState AFTER Processing:")
        print(f"  Invoice Status: {status_after_process}")
        print(f"  Payment Status: {payment_status_after_process}")
        print(f"  Workflow Status: {workflow_status_after_process}")
        print(f"  Approval Status: {approval_status_after_process}")

        print(f"\nChanges from Processing:")
        print(f"  Invoice Status: {status_before} → {status_after_process}")
        print(f"  Workflow: {workflow_status_before} → {workflow_status_after_process}")
        print(f"  Approval: {approval_status_before} → {approval_status_after_process}")

        # STEP 5: Mark invoice as PAID
        print_section("STEP 5: Mark Invoice as PAID")

        print(f"\nMarking invoice {invoice_id} as paid...")
        print(f"API Call: POST /almaws/v1/acq/invoices/{invoice_id}?op=paid")

        paid_invoice = acq.mark_invoice_paid(invoice_id)

        print(f"\n✓ Invoice marked as paid successfully")

        # STEP 6: Get invoice AFTER payment
        print_section("STEP 6: Retrieve Invoice State AFTER Payment")

        invoice_after_payment = acq.get_invoice(invoice_id)

        status_after_payment = invoice_after_payment.get('invoice_status', {}).get('value')
        payment_status_after_payment = invoice_after_payment.get('payment', {}).get('payment_status', {}).get('value')
        workflow_status_after_payment = invoice_after_payment.get('invoice_workflow_status', {}).get('value')
        approval_status_after_payment = invoice_after_payment.get('invoice_approval_status', {}).get('value')

        print(f"\n✓ Invoice retrieved")
        print(f"\nState AFTER Payment:")
        print(f"  Invoice Status: {status_after_payment}")
        print(f"  Payment Status: {payment_status_after_payment}")
        print(f"  Workflow Status: {workflow_status_after_payment}")
        print(f"  Approval Status: {approval_status_after_payment}")

        print(f"\nChanges from Payment:")
        print(f"  Payment Status: {payment_status_after_process} → {payment_status_after_payment}")
        print(f"  Invoice Status: {status_after_process} → {status_after_payment}")

        # STEP 7: Get POL status AFTER payment
        print_section("STEP 7: Retrieve POL Status AFTER Payment")

        print(f"\nRetrieving POL {pol_id} to check for auto-closure...")
        pol_after = acq.get_pol(pol_id)

        pol_status_after = pol_after.get('status', {}).get('value')
        invoice_ref_after = pol_after.get('invoice_reference')

        print(f"\n✓ POL retrieved")
        print(f"\nPOL State AFTER Payment:")
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

        # STEP 8: Complete Summary
        print_section("STEP 8: Complete Workflow Summary")

        print(f"\nINITIAL STATE:")
        print(f"  Invoice: {status_before} / {payment_status_before} / {workflow_status_before} / {approval_status_before}")
        print(f"  POL: {pol_status_before}")

        print(f"\nAFTER PROCESSING (Step 1):")
        print(f"  Invoice: {status_after_process} / {payment_status_after_process} / {workflow_status_after_process} / {approval_status_after_process}")

        print(f"\nFINAL STATE (After Payment):")
        print(f"  Invoice: {status_after_payment} / {payment_status_after_payment} / {workflow_status_after_payment} / {approval_status_after_payment}")
        print(f"  POL: {pol_status_after}")

        print(f"\nAPI CALLS SEQUENCE:")
        print(f"  1. GET /almaws/v1/acq/invoices/{invoice_id} (before)")
        print(f"  2. GET /almaws/v1/acq/po-lines/{pol_id} (before)")
        print(f"  3. POST /almaws/v1/acq/invoices/{invoice_id}?op=process_invoice ✓")
        print(f"  4. GET /almaws/v1/acq/invoices/{invoice_id} (after process)")
        print(f"  5. POST /almaws/v1/acq/invoices/{invoice_id}?op=paid ✓")
        print(f"  6. GET /almaws/v1/acq/invoices/{invoice_id} (after payment)")
        print(f"  7. GET /almaws/v1/acq/po-lines/{pol_id} (verify POL closure)")

        print_section("WORKFLOW COMPLETE")
        print(f"\n✓ Invoice {invoice_number} has been processed and paid")
        print(f"✓ All data captured for case study documentation")
        print()

    except Exception as e:
        print(f"\n✗ Error: {e}")
        print(f"\nError occurred at current step")
        print(f"Partial results may be available in logs")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
