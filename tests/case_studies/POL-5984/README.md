# POL-5984 Case Study: Rialto Complete Flow

**Date**: 2025-10-24
**Purpose**: Document and test the complete Rialto acquisition workflow from POL creation to closure

## Overview

This case study documents the complete workflow for POL-5984, a test case for the Rialto EDI vendor integration. The workflow demonstrates the full acquisition cycle: POL creation → Item receiving → Invoice payment → POL closure.

## Files in This Directory

### Test Scripts

1. **test_pol_5984_verification.py**
   - Verifies POL-5984 data structure and status
   - Extracts items and invoice information
   - Tests data extraction utilities
   - Read-only operations (no modifications)

2. **test_rialto_complete_flow.py**
   - Complete workflow test: Receive item → Pay invoice → Verify closure
   - Documents state transitions at each step
   - Captures API responses and timing
   - **Modifies data** - use carefully in SANDBOX

### Data Files

3. **POL-5984_data.json**
   - Complete POL data structure from Alma API
   - Includes items, locations, vendor information
   - Reference for data structure analysis

4. **POL-5984_detailed_data.json**
   - Extended POL data with additional fields
   - Alternative view of POL structure

### Archived Results

5. **archive/test_results_*.json**
   - Historical test run outputs
   - Preserved for reference and comparison
   - Timestamped for tracking changes over time

## Key Workflow Patterns

### Rialto EDI Vendor Pattern

The Rialto workflow follows a specific pattern for EDI vendors:

1. **POL Creation**: One-time POL with EDI vendor
2. **Item Receiving**: Receive physical/electronic item
3. **Invoice Payment**: Mark associated invoice as paid
4. **POL Closure**: POL automatically closes when both receiving and payment complete

### Complete Workflow Code Example

```python
from almaapitk import Acquisitions

# Initialize
acq = Acquisition(environment='SANDBOX')
pol_id = 'POL-5984'

# Step 1: Get POL and extract data
pol_data = acq.get_pol(pol_id)
items = acq.extract_items_from_pol_data(pol_data)
invoice_id = pol_data.get('invoice_reference')

# Step 2: Find unreceived item
unreceived_items = [item for item in items if not item.get('receive_date')]
if unreceived_items:
    item_id = unreceived_items[0]['pid']

    # Step 3: Receive item
    receive_result = acq.receive_item(
        pol_id=pol_id,
        item_id=item_id,
        receive_date='2025-10-24Z',
        department='DEPT_CODE',
        department_library='LIB_CODE'
    )
    print(f"Item received: {receive_result}")

# Step 4: Pay invoice
if invoice_id:
    payment_result = acq.mark_invoice_paid(invoice_id)
    print(f"Invoice paid: {payment_result}")

# Step 5: Verify POL closure
updated_pol = acq.get_pol(pol_id)
pol_status = updated_pol.get('status', {}).get('value')
print(f"POL Status: {pol_status}")  # Should be 'CLOSED'
```

## Critical Data Structure Findings

### POL Items Location

Items are NOT at POL root level. Correct path:
```
POL → location (array) → copy (array of item objects)
```

Each `copy` object represents an item:
- `pid`: Item ID (not `item_id`)
- `receive_date`: Null if unreceived, date string if received
- `barcode`: Item barcode
- `process_type`: Current processing status

### Invoice Reference

Invoice ID is stored in POL:
```python
invoice_id = pol_data.get('invoice_reference')  # Simple string
```

### Receiving Status

To find unreceived items:
```python
items = acq.extract_items_from_pol_data(pol_data)
unreceived = [item for item in items if not item.get('receive_date')]
```

## POL Auto-Closure Conditions

POL-5984 will automatically close when **BOTH** conditions are met:

1. ✓ All items are received
2. ✓ Associated invoice is paid

If only one condition is met, POL remains in SENT status.

## API Methods Tested

- ✓ `acq.get_pol(pol_id)` - Retrieve POL data
- ✓ `acq.extract_items_from_pol_data(pol_data)` - Extract items from location→copy structure
- ✓ `acq.receive_item(pol_id, item_id, ...)` - Receive item (XML endpoint)
- ✓ `acq.get_invoice(invoice_id)` - Retrieve invoice data
- ✓ `acq.mark_invoice_paid(invoice_id)` - Mark invoice as paid
- ✓ Invoice reference extraction from POL data

## Running the Tests

### Verification Test (Read-Only)

```bash
# Safe to run multiple times - no modifications
python3 tests/case_studies/POL-5984/test_pol_5984_verification.py
```

**What it does**:
- Retrieves POL-5984 data
- Extracts and displays items
- Shows invoice reference
- Validates data structure

### Complete Flow Test (Modifies Data)

```bash
# ⚠️ WARNING: Modifies POL and invoice data
# Only run in SANDBOX environment
python3 tests/case_studies/POL-5984/test_rialto_complete_flow.py
```

**What it does**:
1. Receives unreceived items
2. Pays associated invoice
3. Verifies POL closure
4. Saves results to timestamped JSON file

**Prerequisites**:
- POL-5984 must exist with unreceived items
- Associated invoice must exist and not be paid
- SANDBOX environment API key configured

## Lessons Learned

### Item Receiving Endpoint

The item receiving endpoint requires:
- **Content-Type**: `application/xml`
- **Operation**: `op=receive` query parameter
- **Request Body**: Empty `<item/>` or item object with updates

### Invoice Processing Requirement

Before paying an invoice, it must be processed/approved:
```python
# ✅ CORRECT workflow
processed = acq.approve_invoice(invoice_id)  # MANDATORY
paid = acq.mark_invoice_paid(invoice_id)

# ❌ WRONG - will fail
paid = acq.mark_invoice_paid(invoice_id)  # Error 402459
```

### Data Structure Surprises

1. Items nested in `location → copy` structure (not at root)
2. Item ID field is `pid` (not `item_id`)
3. Invoice reference is simple string field in POL
4. Payment status nested in `invoice → payment → payment_status`

## Related Documentation

- **CLAUDE.md** - Lines 633-728: Alma Acquisitions API Reference
- **CLAUDE.md** - Lines 730-782: Verified Working Methods for Rialto Flow
- **CLAUDE.md** - Lines 784-818: Critical Data Structure Findings
- **tests/case_studies/POL-5994/** - Related invoice workflow case study

## Known Issues and Limitations

1. **Test Data Dependency**: Tests require POL-5984 to exist with specific state
2. **Non-Idempotent**: Running tests multiple times changes POL state
3. **Environment Specific**: Results may vary between SANDBOX and PRODUCTION
4. **Timing Sensitive**: Auto-closure may have delays

## Future Enhancements

- [ ] Add setup script to create test POL in known state
- [ ] Add teardown/cleanup to reset POL after testing
- [ ] Implement mock responses for unit testing
- [ ] Add validation for all state transitions
- [ ] Document timing delays for auto-closure
