from almaapitk import AlmaAPIClient
from almaapitk import Acquisitions

client = AlmaAPIClient('SANDBOX')
acq = Acquisitions(client)

# Verify by getting the invoice again

# Get invoice
updated_invoice = acq.get_invoice("31970014450004146")

# Extract payment status correctly (nested in payment object)
payment = updated_invoice.get('payment', {})
payment_status = payment.get('payment_status', {})
status_value = payment_status.get('value', 'Unknown')

print(f"✓ Payment Status: {status_value}")

summary = acq.get_invoice_summary("31970014450004146")
print(f"Payment Status: {summary['payment_status']}")