from almaapitk import AlmaAPIClient
from almaapitk import Acquisitions

client = AlmaAPIClient('SANDBOX')
acq = Acquisitions(client)

# Test getting the invoice
# invoice_data = acq.get_invoice("23520664130004146")
# summary = acq.get_invoice_summary("23520664130004146")
# print(summary)
# print("\n✓ TEST PASSED")
lines = acq.get_invoice_lines("31970014450004146")
print(f"✓ Found {len(lines)} invoice line(s)")

# DEBUG: Print the actual line object
print("\n[DEBUG] Line object keys:", list(lines[0].keys()))
print("[DEBUG] Line object:", lines[0])

for i, line in enumerate(lines, 1):
    print(f"\nLine {i}:")
    print(f"  Line Number: {line.get('number', 'N/A')}")
    print(f"  POL Number: {line.get('po_line', 'N/A')}")
    print(f"  Price: {line.get('price', 'N/A')}")
    print(f"  Quantity: {line.get('quantity', 'N/A')}")
    print(f"  Total Price: {line.get('total_price', 'N/A')}")