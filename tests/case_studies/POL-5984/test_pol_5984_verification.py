"""
TEST: POL-5984 Verification Script
Purpose: Verify new POL in fiscal year 2025-2026 and extract key data for testing

POL Details:
- POL ID: POL-5984
- PO: PO-1766001 (In Review)
- Vendor: ProQuest, LLC/RIALTO
- Fiscal Year: 2025-2026 (01/10/2025 - 30/09/2026)
- Type: Print Book - One Time
- Funds: Main TAU Fund (100.0%)

Test Objectives:
1. Verify POL can be retrieved via API
2. Extract POL status
3. Check if items exist and extract item IDs
4. Check if invoice reference exists
5. Display complete POL data for manual review
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


def main():
    print_section("POL-5984 VERIFICATION TEST")
    print(f"Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Environment: SANDBOX")

    # Initialize API client and acquisitions domain
    client = AlmaAPIClient('SANDBOX')
    acq = Acquisitions(client)

    pol_id = "POL-5984"

    # ========================================================================
    # STEP 1: Retrieve POL Data
    # ========================================================================
    print_section("STEP 1: Retrieve POL Data")
    print(f"Fetching POL: {pol_id}")

    try:
        pol_data = acq.get_pol(pol_id)
        print(f"✓ POL retrieved successfully")
    except Exception as e:
        print(f"✗ Failed to retrieve POL: {e}")
        return

    # ========================================================================
    # STEP 2: Extract and Display Key POL Fields
    # ========================================================================
    print_section("STEP 2: POL Key Information")

    pol_number = pol_data.get('number', 'N/A')
    pol_type = pol_data.get('type', {}).get('value', 'N/A')
    pol_status = pol_data.get('status', {}).get('value', 'N/A')
    vendor_code = pol_data.get('vendor', {}).get('value', 'N/A')
    vendor_desc = pol_data.get('vendor', {}).get('desc', 'N/A')
    invoice_reference = pol_data.get('invoice_reference')

    print(f"POL Number:        {pol_number}")
    print(f"POL Type:          {pol_type}")
    print(f"POL Status:        {pol_status}")
    print(f"Vendor Code:       {vendor_code}")
    print(f"Vendor Name:       {vendor_desc}")
    print(f"Invoice Reference: {invoice_reference if invoice_reference else 'Not yet created'}")

    # Price information
    price = pol_data.get('price', {})
    list_price = price.get('list_price', {})
    if isinstance(list_price, dict):
        amount = list_price.get('sum', 'N/A')
        currency = list_price.get('currency', {}).get('value', 'N/A')
    else:
        amount = list_price
        currency = pol_data.get('currency', {}).get('value', 'N/A')

    print(f"List Price:        {amount} {currency}")

    # Fund information
    fund_distribution = pol_data.get('fund_distribution', [])
    if fund_distribution:
        fund = fund_distribution[0] if isinstance(fund_distribution, list) else fund_distribution
        fund_code = fund.get('fund_code', {}).get('value', 'N/A')
        fund_desc = fund.get('fund_code', {}).get('desc', 'N/A')
        fund_percent = fund.get('percent', 'N/A')
        print(f"Fund:              {fund_code} - {fund_desc} ({fund_percent}%)")

    # ========================================================================
    # STEP 3: Extract Items from POL
    # ========================================================================
    print_section("STEP 3: Extract Items from POL")

    try:
        items = acq.extract_items_from_pol_data(pol_data)
        print(f"✓ Found {len(items)} item(s) in POL")

        if items:
            for idx, item in enumerate(items, 1):
                print(f"\n  Item {idx}:")
                print(f"    Item ID (pid):     {item.get('pid', 'N/A')}")
                print(f"    Barcode:           {item.get('barcode', 'N/A')}")
                print(f"    Description:       {item.get('description', 'N/A')}")
                print(f"    Receive Date:      {item.get('receive_date', 'Not received')}")
                print(f"    Process Type:      {item.get('process_type', {}).get('value', 'N/A')}")
                print(f"    Expected Arrival:  {item.get('expected_arrival_date', 'N/A')}")
        else:
            print("  ⚠ No items found in POL (may need to complete PO packaging)")
    except Exception as e:
        print(f"✗ Failed to extract items: {e}")
        items = []

    # ========================================================================
    # STEP 4: Check Invoice Reference
    # ========================================================================
    print_section("STEP 4: Invoice Reference Check")

    if invoice_reference and invoice_reference != "None":
        print(f"✓ Invoice Reference Found: {invoice_reference}")
        print(f"  Attempting to retrieve invoice...")

        try:
            invoice_summary = acq.get_invoice_summary(invoice_reference)
            print(f"✓ Invoice retrieved successfully")
            print(f"\n{invoice_summary}")
        except Exception as e:
            print(f"✗ Failed to retrieve invoice: {e}")
    else:
        print("⚠ No invoice reference found")
        print("  This is expected if PO has not been sent to vendor yet")
        print("  Invoice will be created after manual packaging and PO activation")

    # ========================================================================
    # STEP 5: Determine Next Steps
    # ========================================================================
    print_section("STEP 5: Next Steps and Recommendations")

    if pol_status in ['INREVIEW', 'IN_REVIEW']:
        print("Current Status: POL is in review")
        print("\nNext Actions:")
        print("  1. Navigate to Acquisitions → Manual Packaging")
        print("  2. Locate POL-5984 in the manual packaging queue")
        print("  3. Package POL into PO-1766001")
        print("  4. Activate/Send the PO to vendor")
        print("  5. Re-run this verification script to see updated status")

    elif pol_status in ['READY', 'SENT', 'WAITING_FOR_INVOICE']:
        print("Current Status: POL has been sent to vendor")
        print("\nPOL is ready for testing!")

        if items:
            unreceived_items = [item for item in items if not item.get('receive_date')]
            if unreceived_items:
                print(f"\nUnreceived Items: {len(unreceived_items)}")
                for item in unreceived_items:
                    print(f"  - Item ID: {item.get('pid')}")
                print("\nYou can now test item receiving workflow")
            else:
                print("\n✓ All items already received")

        if invoice_reference:
            print(f"\nInvoice: {invoice_reference}")
            print("You can now test invoice payment workflow")
        else:
            print("\n⚠ No invoice found - may need to be created manually or via EDI")

    else:
        print(f"Current Status: {pol_status}")
        print("\nReview POL status and determine appropriate next steps")

    # ========================================================================
    # STEP 6: Save Full POL Data for Reference
    # ========================================================================
    print_section("STEP 6: Saving Full POL Data")

    output_file = "/home/hagaybar/projects/AlmaAPITK/src/tests/POL-5984_data.json"
    try:
        with open(output_file, 'w') as f:
            json.dump(pol_data, f, indent=2)
        print(f"✓ Full POL data saved to: {output_file}")
        print("  You can review the complete POL structure in this file")
    except Exception as e:
        print(f"✗ Failed to save POL data: {e}")

    # ========================================================================
    # Summary
    # ========================================================================
    print_section("VERIFICATION SUMMARY")
    print(f"POL ID:            {pol_id}")
    print(f"Status:            {pol_status}")
    print(f"Items Found:       {len(items) if items else 0}")
    print(f"Invoice Reference: {'Yes' if invoice_reference and invoice_reference != 'None' else 'No'}")
    print(f"Ready for Testing: {'Yes' if pol_status in ['READY', 'SENT'] and items else 'Not yet - needs packaging/activation'}")

    print("\n" + "="*80 + "\n")


if __name__ == "__main__":
    main()
