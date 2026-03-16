#!/usr/bin/env python3
"""
Case Study: Create Invoice for POL-5994

Creates invoice and invoice line for POL-5994 without processing or paying.
"""

from almaapitk import AlmaAPIClient
from almaapitk import Acquisitions
from datetime import datetime

def main():
    print("\n" + "=" * 70)
    print("CASE STUDY: Create Invoice for POL-5994")
    print("=" * 70)
    print("\nPOL Details:")
    print("  POL: POL-5994")
    print("  PO: PO-1771002")
    print("  Vendor: TestVendor")
    print("  Account: TestAccount")
    print("  Amount: To be determined from POL")
    print()

    # Initialize client and acquisitions
    client = AlmaAPIClient(environment='SANDBOX')
    acq = Acquisitions(client)

    try:
        # Step 1: Get POL data to determine amount and fund
        print("\n" + "=" * 70)
        print("STEP 1: Retrieve POL Data")
        print("=" * 70)

        pol_data = acq.get_pol("POL-5994")

        pol_number = pol_data.get('number')
        pol_price = pol_data.get('price', {}).get('sum', '0')
        pol_currency = pol_data.get('price', {}).get('currency', {}).get('value', 'ILS')
        vendor_code = pol_data.get('vendor', {}).get('value', 'TestVendor')

        print(f"POL Number: {pol_number}")
        print(f"POL Price: {pol_price} {pol_currency}")
        print(f"Vendor: {vendor_code}")

        # Step 2: Create Invoice
        print("\n" + "=" * 70)
        print("STEP 2: Create Invoice")
        print("=" * 70)

        invoice_number = f"INV-POL5994-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

        invoice = acq.create_invoice_simple(
            invoice_number=invoice_number,
            invoice_date=datetime.now().strftime("%Y-%m-%d"),
            vendor_code=vendor_code,
            total_amount=float(pol_price),
            currency=pol_currency
        )

        invoice_id = invoice.get('id')
        print(f"\n✓ Invoice created successfully")
        print(f"  Invoice ID: {invoice_id}")
        print(f"  Invoice Number: {invoice_number}")

        # Step 3: Create Invoice Line
        print("\n" + "=" * 70)
        print("STEP 3: Create Invoice Line for POL-5994")
        print("=" * 70)

        line = acq.create_invoice_line_simple(
            invoice_id=invoice_id,
            pol_id="POL-5994",
            amount=float(pol_price),
            quantity=1,
            currency=pol_currency
            # fund_code will be auto-extracted from POL
        )

        print(f"\n✓ Invoice line created successfully")
        print(f"  Line ID: {line.get('id')}")

        # Summary
        print("\n" + "=" * 70)
        print("CASE STUDY SUMMARY")
        print("=" * 70)
        print(f"Invoice ID: {invoice_id}")
        print(f"Invoice Number: {invoice_number}")
        print(f"POL: POL-5994")
        print(f"Amount: {pol_price} {pol_currency}")
        print(f"Status: Created (NOT processed, NOT paid)")
        print()
        print("Next steps for testing:")
        print("  1. Process the invoice: acq.approve_invoice(invoice_id)")
        print("  2. Pay the invoice: acq.mark_invoice_paid(invoice_id)")
        print()
        print("Log files:")
        print(f"  acquisitions.log - Domain layer logs")
        print(f"  api_client.log - HTTP layer logs")
        print()

        # Save invoice details for future reference
        print(f"SAVE THESE VALUES FOR FUTURE TESTING:")
        print(f"  INVOICE_ID={invoice_id}")
        print(f"  INVOICE_NUMBER={invoice_number}")
        print()

    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
