"""
TEST: Complete Rialto EDI Vendor Flow - POL-5984
Purpose: Test complete workflow with new fiscal year (2025-2026) POL

Test Data:
- POL ID:     POL-5984
- Item ID:    23472624530004146
- Invoice ID: 35899324020004146
- PO:         PO-1766001
- Vendor:     ProQuest, LLC/RIALTO
- Fiscal Year: 2025-2026 (01/10/2025 - 30/09/2026)
- Type:       Print Book - One Time

Test Workflow:
1. Verify POL and Invoice initial states
2. Receive item (mark as received)
3. Mark invoice as paid
4. Verify POL auto-closure (NEW FISCAL YEAR TEST)

Expected Outcome:
- Item status changes to "received"
- Invoice payment_status changes to "PAID"
- Invoice status changes to "CLOSED"
- POL status changes to "CLOSED" (if auto-closure is configured)
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from almaapitk import Acquisitions
from almaapitk import AlmaAPIClient
from datetime import datetime
import json


def print_section(title):
    """Print formatted section header"""
    print("\n" + "="*80)
    print(f" {title}")
    print("="*80)


def print_status(label, value, emoji=""):
    """Print status line with optional emoji"""
    print(f"{emoji} {label}: {value}")


def main():
    print_section("RIALTO COMPLETE FLOW TEST - POL-5984 (Fiscal Year 2025-2026)")
    print(f"Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Environment: SANDBOX")

    # Initialize
    client = AlmaAPIClient('SANDBOX')
    acq = Acquisitions(client)

    # Test data
    pol_id = "POL-5984"
    item_id = "23472624530004146"
    invoice_id = "35899324020004146"

    print(f"\nTest Configuration:")
    print(f"  POL ID:     {pol_id}")
    print(f"  Item ID:    {item_id}")
    print(f"  Invoice ID: {invoice_id}")

    # Store results
    test_results = {
        "test_date": datetime.now().isoformat(),
        "pol_id": pol_id,
        "item_id": item_id,
        "invoice_id": invoice_id,
        "stages": {}
    }

    # ========================================================================
    # STAGE 1: Verify Initial State
    # ========================================================================
    print_section("STAGE 1: Verify Initial State")

    try:
        # Get POL
        print(f"Retrieving POL: {pol_id}")
        pol_data = acq.get_pol(pol_id)
        pol_status_before = pol_data.get('status', {}).get('value', 'Unknown')
        pol_type = pol_data.get('type', {}).get('value', 'Unknown')

        print_status("POL Status (Before)", pol_status_before, "📋")
        print_status("POL Type", pol_type)

        # Get Invoice
        print(f"\nRetrieving Invoice: {invoice_id}")
        invoice_data = acq.get_invoice(invoice_id)
        invoice_status_before = invoice_data.get('invoice_status', {}).get('value', 'Unknown')

        payment = invoice_data.get('payment', {})
        payment_status_before = payment.get('payment_status', {}).get('value', 'Unknown')

        invoice_number = invoice_data.get('number', 'Unknown')
        total_amount = invoice_data.get('total_amount', 'N/A')
        currency = invoice_data.get('currency', {}).get('value', 'ILS')

        print_status("Invoice Number", invoice_number, "📄")
        print_status("Invoice Status (Before)", invoice_status_before)
        print_status("Payment Status (Before)", payment_status_before)
        print_status("Total Amount", f"{total_amount} {currency}")

        # Get Item
        print(f"\nExtracting item information from POL...")
        items = acq.extract_items_from_pol_data(pol_data)

        target_item = None
        for item in items:
            if item.get('pid') == item_id:
                target_item = item
                break

        if not target_item:
            print(f"✗ Item {item_id} not found in POL")
            return

        item_barcode = target_item.get('barcode', 'N/A')
        item_receive_date_before = target_item.get('receive_date')

        print_status("Item Barcode", item_barcode, "📦")
        print_status("Item Receive Status (Before)",
                    "Received" if item_receive_date_before else "Not Received")

        test_results["stages"]["initial_state"] = {
            "pol_status": pol_status_before,
            "invoice_status": invoice_status_before,
            "payment_status": payment_status_before,
            "item_received": bool(item_receive_date_before)
        }

        print("\n✓ Initial state verification complete")

    except Exception as e:
        print(f"\n✗ Failed to verify initial state: {e}")
        import traceback
        traceback.print_exc()
        return

    # ========================================================================
    # STAGE 2: Receive Item
    # ========================================================================
    print_section("STAGE 2: Receive Item")

    if item_receive_date_before:
        print(f"⚠ Item already received on {item_receive_date_before}")
        print("  Skipping item receiving step")
        test_results["stages"]["receive_item"] = {
            "skipped": True,
            "reason": "Item already received"
        }
    else:
        try:
            print(f"Receiving item {item_id} for POL {pol_id}...")

            # Receive with current date
            receive_date = datetime.now().strftime('%Y-%m-%d') + "Z"

            received_item = acq.receive_item(
                pol_id=pol_id,
                item_id=item_id,
                receive_date=receive_date
            )

            print(f"✓ Item received successfully!")
            print_status("Receive Date", receive_date, "✅")

            test_results["stages"]["receive_item"] = {
                "success": True,
                "receive_date": receive_date
            }

        except Exception as e:
            print(f"\n✗ Failed to receive item: {e}")
            test_results["stages"]["receive_item"] = {
                "success": False,
                "error": str(e)
            }
            import traceback
            traceback.print_exc()
            # Continue with test even if receiving fails

    # ========================================================================
    # STAGE 3: Mark Invoice as Paid
    # ========================================================================
    print_section("STAGE 3: Mark Invoice as Paid")

    if payment_status_before == "PAID" or payment_status_before == "FULLY_PAID":
        print(f"⚠ Invoice already marked as paid ({payment_status_before})")
        print("  Skipping invoice payment step")
        test_results["stages"]["pay_invoice"] = {
            "skipped": True,
            "reason": f"Already paid ({payment_status_before})"
        }
    else:
        try:
            print(f"Marking invoice {invoice_id} as paid...")

            paid_invoice = acq.mark_invoice_paid(invoice_id)

            # Verify payment status changed
            payment_after = paid_invoice.get('payment', {})
            payment_status_after = payment_after.get('payment_status', {}).get('value', 'Unknown')
            invoice_status_after = paid_invoice.get('invoice_status', {}).get('value', 'Unknown')

            print(f"✓ Invoice marked as paid successfully!")
            print_status("Payment Status (After)", payment_status_after, "✅")
            print_status("Invoice Status (After)", invoice_status_after)

            test_results["stages"]["pay_invoice"] = {
                "success": True,
                "payment_status_before": payment_status_before,
                "payment_status_after": payment_status_after,
                "invoice_status_before": invoice_status_before,
                "invoice_status_after": invoice_status_after
            }

        except Exception as e:
            print(f"\n✗ Failed to mark invoice as paid: {e}")
            test_results["stages"]["pay_invoice"] = {
                "success": False,
                "error": str(e)
            }
            import traceback
            traceback.print_exc()

    # ========================================================================
    # STAGE 4: Verify POL Status (Check for Auto-Closure)
    # ========================================================================
    print_section("STAGE 4: Verify POL Status - Auto-Closure Check")

    try:
        print(f"Retrieving updated POL status...")

        pol_data_after = acq.get_pol(pol_id)
        pol_status_after = pol_data_after.get('status', {}).get('value', 'Unknown')

        print_status("POL Status (Before)", pol_status_before, "📋")
        print_status("POL Status (After)", pol_status_after, "📋")

        if pol_status_after == "CLOSED":
            print("\n✅ SUCCESS! POL auto-closed after receiving item and paying invoice")
            print("   This confirms POL auto-closure is working in the new fiscal year!")
            test_results["stages"]["pol_closure"] = {
                "auto_closed": True,
                "status_before": pol_status_before,
                "status_after": pol_status_after
            }
        elif pol_status_before != pol_status_after:
            print(f"\n⚠ POL status changed from {pol_status_before} to {pol_status_after}")
            print("   But POL did not fully close. May require additional steps.")
            test_results["stages"]["pol_closure"] = {
                "auto_closed": False,
                "status_changed": True,
                "status_before": pol_status_before,
                "status_after": pol_status_after
            }
        else:
            print(f"\n⚠ POL status unchanged: {pol_status_after}")
            print("   POL did not auto-close. Possible reasons:")
            print("   1. Time delay - closure may be batch processed")
            print("   2. Manual closure required in this environment")
            print("   3. Additional requirements not met")
            print("   4. Configuration issue in SANDBOX")
            test_results["stages"]["pol_closure"] = {
                "auto_closed": False,
                "status_changed": False,
                "status_before": pol_status_before,
                "status_after": pol_status_after
            }

    except Exception as e:
        print(f"\n✗ Failed to verify POL status: {e}")
        test_results["stages"]["pol_closure"] = {
            "error": str(e)
        }

    # ========================================================================
    # STAGE 5: Final Summary
    # ========================================================================
    print_section("TEST SUMMARY - POL-5984 (Fiscal Year 2025-2026)")

    print(f"\nPOL ID:            {pol_id}")
    print(f"Item ID:           {item_id}")
    print(f"Invoice ID:        {invoice_id}")
    print(f"Fiscal Year:       2025-2026")

    print("\n" + "-"*80)
    print("STAGE RESULTS:")
    print("-"*80)

    # Initial state
    print("\n1. Initial State:       ✓ Verified")

    # Item receiving
    receive_stage = test_results["stages"].get("receive_item", {})
    if receive_stage.get("skipped"):
        print(f"2. Receive Item:        ⊘ Skipped ({receive_stage.get('reason')})")
    elif receive_stage.get("success"):
        print("2. Receive Item:        ✓ Success")
    else:
        print("2. Receive Item:        ✗ Failed")

    # Invoice payment
    pay_stage = test_results["stages"].get("pay_invoice", {})
    if pay_stage.get("skipped"):
        print(f"3. Pay Invoice:         ⊘ Skipped ({pay_stage.get('reason')})")
    elif pay_stage.get("success"):
        print("3. Pay Invoice:         ✓ Success")
    else:
        print("3. Pay Invoice:         ✗ Failed")

    # POL closure
    closure_stage = test_results["stages"].get("pol_closure", {})
    if closure_stage.get("auto_closed"):
        print("4. POL Auto-Closure:    ✅ SUCCESS - POL CLOSED!")
    elif closure_stage.get("status_changed"):
        print("4. POL Auto-Closure:    ⚠ Status changed but not closed")
    elif closure_stage.get("error"):
        print("4. POL Auto-Closure:    ✗ Error checking status")
    else:
        print("4. POL Auto-Closure:    ⚠ No auto-closure observed")

    # ========================================================================
    # Save Results
    # ========================================================================
    print("\n" + "-"*80)

    output_file = f"/home/hagaybar/projects/AlmaAPITK/src/tests/test_results_pol_5984_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    try:
        with open(output_file, 'w') as f:
            json.dump(test_results, f, indent=2)
        print(f"✓ Test results saved to: {output_file}")
    except Exception as e:
        print(f"⚠ Failed to save results: {e}")

    print("\n" + "="*80)

    # Return status for further investigation
    if closure_stage.get("auto_closed"):
        print("\n🎉 TEST COMPLETE - POL AUTO-CLOSURE CONFIRMED IN NEW FISCAL YEAR!")
    else:
        print("\n⚠ TEST COMPLETE - POL AUTO-CLOSURE NOT OBSERVED")
        print("   Recommend: Check POL status in Alma UI after 24-48 hours")

    print("\n")


if __name__ == "__main__":
    main()
