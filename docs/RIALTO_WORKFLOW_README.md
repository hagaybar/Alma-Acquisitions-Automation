# Rialto Complete Workflow Processor

Complete automation of the Rialto POL workflow including item receiving, department scanning, invoice payment, and POL closure verification.

## Overview

This script processes Purchase Order Lines (POLs) through the complete Rialto workflow:

1. **Read POL IDs** from TSV file (first column)
2. **Extract Identifiers** - Automatically extract all required IDs:
   - Item PID
   - Invoice ID (via invoice lines)
   - MMS ID (bibliographic record)
   - Holding ID
   - PO identifier
3. **Receive & Scan** - Receive item and scan into department (prevents Transit status)
4. **Pay Invoice** - Mark linked invoice as paid
5. **Verify Closure** - Confirm POL closed and generate report

## Quick Start

### 1. Prepare TSV File

Create a TSV file with POL IDs in the first column:

```tsv
POL_ID	Notes
POL-5989	First order
POL-6000	Second order
POL-6001	Third order
```

**Important**: Only the first column is used. Other columns are ignored.

### 2. Dry Run (Verification Only)

```bash
python src/projects/rialto_complete_workflow.py --tsv pols.tsv
```

This will:
- ✅ Read and validate all POL IDs
- ✅ Extract all identifiers
- ✅ Verify configuration
- ❌ **NOT modify any data** (dry run mode)

### 3. Live Execution

```bash
python src/projects/rialto_complete_workflow.py --tsv pols.tsv --live
```

This will:
- ✅ Execute the complete workflow
- ✅ Receive items and scan into department
- ✅ Pay invoices
- ✅ Verify POL closure
- ✅ Generate report

## Command-Line Options

### Required Arguments

| Argument | Description | Example |
|----------|-------------|---------|
| `--tsv` | Path to TSV file with POL IDs | `--tsv pols.tsv` |

### Optional Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--environment` | SANDBOX | Alma environment (SANDBOX or PRODUCTION) |
| `--library` | AC1 | Library code |
| `--department` | AcqDeptAC1 | Department code |
| `--work-order-type` | AcqWorkOrder | Work order type |
| `--work-order-status` | CopyCat | Work order status |
| `--output` | None | Path to save CSV report |
| `--dry-run` | True | Perform dry run (default) |
| `--live` | False | Execute live workflow |

## Configuration

### Default Configuration (AC1 Library)

Based on POL-5989 test validation:

```python
{
    "library": "AC1",
    "department": "AcqDeptAC1",
    "work_order_type": "AcqWorkOrder",
    "work_order_status": "CopyCat"
}
```

**Valid Work Order Statuses**:
- `Binding`
- `ClassDep`
- `CopyCat` ✅ (Tested and validated)
- `PhysicalProcess`
- `PhysicalProcess2`
- `Storage`

### Custom Configuration

Override defaults with command-line arguments:

```bash
python src/projects/rialto_complete_workflow.py \
    --tsv pols.tsv \
    --library MAIN \
    --department TECH_SERVICES \
    --work-order-status PhysicalProcess \
    --live
```

## Workflow Steps

### Step 1: Read POL IDs from TSV

```
Input: pols.tsv
├─ Column 1: POL ID (required)
└─ Other columns: Ignored

Output: List of POL IDs
```

### Step 2: Extract Identifiers

For each POL, automatically extracts:

| Identifier | Source | Example |
|------------|--------|---------|
| **POL ID** | Input file | POL-5989 |
| **POL Number** | POL data | POL-5989 |
| **MMS ID** | POL → resource_metadata → mms_id | 9933853677604146 |
| **Holding ID** | POL → location → holding[0] → id | 22472644530004146 |
| **Item PID** | POL → location → copy[0] → pid | 23472664540004146 |
| **Invoice ID** | Invoice lines → po_line match | 35916679020004146 |
| **Library Code** | POL → location → library | AC1 |

### Step 3: Receive Item and Scan Into Department

**Problem Solved**: Items normally go to "in transit" after receiving.

**Solution**: Use `receive_and_keep_in_department()` workflow:

```python
# Receive item
acq.receive_item(pol_id, item_id)

# Immediately scan into department with work order
bibs.scan_in_item(
    mms_id=mms_id,
    holding_id=holding_id,
    item_pid=item_id,
    library="AC1",
    department="AcqDeptAC1",
    work_order_type="AcqWorkOrder",
    status="CopyCat",
    done=False  # Keep in department
)
```

**Result**: Item stays in department with work order, **NOT in Transit** ✅

### Step 4: Pay Invoice

```python
# Check if invoice is linked
if invoice_id:
    # Mark invoice as paid
    acq.mark_invoice_paid(invoice_id)
```

**Status Changes**:
- Payment Status: NOT_PAID → PAID
- Invoice Status: ACTIVE → CLOSED

### Step 5: Verify POL Closure

```python
# Get updated POL data
updated_pol = acq.get_pol(pol_id)
pol_status = updated_pol['status']['value']

# Check if closed
if pol_status == 'CLOSED':
    # Success!
```

**Expected**: POL auto-closes when:
- ✅ All items received
- ✅ All linked invoices paid

## Output

### Console Output

```
======================================================================
BATCH PROCESSING: 3 POL(s)
Mode: LIVE
Environment: SANDBOX
======================================================================

######################################################################
POL 1/3: POL-5989
######################################################################

======================================================================
EXTRACTING IDENTIFIERS FOR POL-5989
======================================================================
Retrieving POL data...
✓ POL Number: POL-5989
  POL Status: WAITING_FOR_INVOICE
✓ MMS ID: 9933853677604146
✓ Holding ID: 22472644530004146
...

✓ Successfully extracted all identifiers

======================================================================
PROCESSING WORKFLOW FOR POL-5989
======================================================================

STEP 1: Receive item and keep in department
──────────────────────────────────────────────────────────────────────
✓ Item received and scanned into department

STEP 2: Pay invoice
──────────────────────────────────────────────────────────────────────
✓ Invoice marked as paid

STEP 3: Verify final state
──────────────────────────────────────────────────────────────────────
Final POL Status: CLOSED
✅ POL CLOSED - Workflow complete!
```

### CSV Report (Optional)

Generated with `--output report.csv`:

| POL_ID | POL_Number | Success | Receive_Status | Pay_Invoice_Status | POL_Closed | Errors |
|--------|------------|---------|----------------|--------------------|-----------|----|
| POL-5989 | POL-5989 | Yes | success | success | Yes | |
| POL-6000 | POL-6000 | Yes | success | success | Yes | |
| POL-6001 | POL-6001 | No | success | failed | No | Payment failed: Invalid invoice |

### Summary Statistics

```
======================================================================
PROCESSING SUMMARY
======================================================================

Statistics:
  Total POLs:    3
  Successful:    2
  Failed:        1
  Skipped:       0
  Success Rate:  66.7%
```

## Examples

### Example 1: Dry Run (Default)

Verify workflow without modifications:

```bash
python src/projects/rialto_complete_workflow.py --tsv my_pols.tsv
```

### Example 2: Process in Sandbox

```bash
python src/projects/rialto_complete_workflow.py \
    --tsv pols.tsv \
    --environment SANDBOX \
    --live
```

### Example 3: Production with Report

```bash
python src/projects/rialto_complete_workflow.py \
    --tsv production_pols.tsv \
    --environment PRODUCTION \
    --output results.csv \
    --live
```

⚠️ **WARNING**: Production mode modifies real data. Always test in SANDBOX first!

### Example 4: Custom Configuration

```bash
python src/projects/rialto_complete_workflow.py \
    --tsv pols.tsv \
    --library TECH \
    --department TECH_ACQ \
    --work-order-status PhysicalProcess \
    --live
```

## Error Handling

### Common Errors and Solutions

| Error | Cause | Solution |
|-------|-------|----------|
| Invalid library code | Wrong library parameter | Use library code from POL data |
| Department not found | Department doesn't exist | Check Alma configuration for valid codes |
| Invalid work order status | Wrong status name | Use one of: Binding, ClassDep, CopyCat, etc. |
| Item already received | POL already processed | Check POL status before processing |
| Invoice not found | No invoice linked to POL | Verify invoice linkage in Alma UI |

### Skipped Steps

The workflow intelligently skips steps when appropriate:

- **Item already received**: Skips receive step, continues to payment
- **Invoice already paid**: Skips payment step, continues to verification
- **No invoice linked**: Skips payment step, continues to verification

## Validation

### Pre-Flight Checks

Before processing each POL, the script validates:

1. ✅ POL exists and is accessible
2. ✅ MMS ID can be extracted
3. ✅ Holding ID can be extracted
4. ✅ At least one item exists
5. ✅ Item PID can be extracted
6. ✅ Library code is valid

### Post-Processing Verification

After workflow completion, verifies:

1. ✅ Item has receive date
2. ✅ Invoice payment status changed
3. ✅ POL status is CLOSED
4. ✅ No errors occurred

## Troubleshooting

### Issue: "Department not found"

**Cause**: Department code doesn't exist in Alma configuration

**Solution**:
1. Check Configuration > Fulfillment > Circulation Desks
2. Find valid department code for your library
3. Use `--department` flag with correct code

### Issue: "Invalid work order status"

**Cause**: Status name doesn't match Alma configuration

**Solution**: Use one of the validated statuses: `CopyCat`, `Binding`, `ClassDep`, etc.

### Issue: "POL did not close"

**Possible causes**:
- Invoice not fully paid
- Multiple items, some not received
- Manual intervention required in Alma

**Solution**: Check POL in Alma UI for specific requirements

### Issue: "No invoice found"

**Cause**: Invoice not linked to POL via invoice lines

**Solution**:
1. Create invoice in Alma
2. Add invoice line referencing the POL
3. Re-run workflow

## Best Practices

### 1. Always Test in Sandbox First

```bash
# Test workflow
python src/projects/rialto_complete_workflow.py \
    --tsv test_pols.tsv \
    --environment SANDBOX \
    --live

# Review results
# If successful, proceed to production
```

### 2. Use Dry Run for Verification

```bash
# Verify all POLs can be processed
python src/projects/rialto_complete_workflow.py \
    --tsv large_batch.tsv
```

### 3. Generate Reports

```bash
# Save detailed report for audit trail
python src/projects/rialto_complete_workflow.py \
    --tsv pols.tsv \
    --output report_$(date +%Y%m%d).csv \
    --live
```

### 4. Process in Batches

For large volumes, process in smaller batches:

```bash
# Split into batches of 50
split -l 50 all_pols.tsv batch_

# Process each batch
for batch in batch_*; do
    python src/projects/rialto_complete_workflow.py \
        --tsv $batch \
        --output ${batch}_report.csv \
        --live
done
```

## Safety Features

### 1. Dry Run by Default

Script runs in dry-run mode unless `--live` flag is provided.

### 2. Confirmation Prompt

In live mode, requires typing "YES" to proceed:

```
WARNING: Running in LIVE mode - will modify SANDBOX data!
POLs to process: 10
Configuration:
  library: AC1
  department: AcqDeptAC1

Type 'YES' to proceed:
```

### 3. Comprehensive Error Tracking

All errors are captured and reported:
- Per-step error tracking
- Detailed error messages
- Continues processing other POLs even if one fails

### 4. Skip Already-Processed Items

Automatically detects and skips:
- Items already received
- Invoices already paid
- POLs already closed

## Performance

### Processing Speed

- ~10-15 seconds per POL (including all API calls)
- ~240-360 POLs per hour
- Batch processing recommended for large volumes

### API Rate Limits

The script respects Alma API rate limits:
- Sandbox: 25 requests/second
- Production: Varies by institution

## Support

### Documentation

- **This File**: Complete usage guide
- **Test Summary**: `/docs/POL-5989_TEST_SUMMARY.md`
- **CLAUDE.md**: Technical implementation details

### Test Data

- **Example TSV**: `example_pols.tsv`
- **Validated POL**: POL-5989 (complete workflow tested)

### Configuration Reference

See `/config/rialto_workflow_config.example.json` for configuration templates.

---

**Version**: 1.0
**Last Updated**: 2025-10-21
**Tested With**: POL-5989 (SANDBOX environment)
**Status**: Production Ready ✅
