#!/usr/bin/env python3
"""
Rialto Complete Workflow Processor

This script processes POLs through the complete Rialto workflow:
1. Read POL IDs from TSV file
2. Extract all required identifiers (item PID, invoice ID, MMS ID, holding ID)
3. Receive item and scan into department (keeps item in dept, prevents Transit)
4. Pay linked invoice
5. Verify POL closure and generate report

The workflow ensures items stay in the acquisitions department instead of
going to "in transit" status.

Usage:
    python rialto_complete_workflow.py --tsv pols.tsv
    python rialto_complete_workflow.py --tsv pols.tsv --environment PRODUCTION --live

Required TSV Format:
    Column 1: POL ID (e.g., POL-5989)
    Other columns: Ignored

Configuration:
    Default values for AC1 library:
    - Library: AC1
    - Department: AcqDeptAC1
    - Work Order Type: AcqWorkOrder
    - Work Order Status: CopyCat

Author: Claude Code
Date: 2025-10-21
"""

import sys
import csv
import argparse
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path

from almaapitk import AlmaAPIClient, AlmaAPIError, Acquisitions, BibliographicRecords


# Default configuration (validated in POL-5989 test)
DEFAULT_CONFIG = {
    "library": "AC1",
    "department": "AcqDeptAC1",
    "work_order_type": "AcqWorkOrder",
    "work_order_status": "CopyCat"
}


class RialtoWorkflowProcessor:
    """
    Processes POLs through the complete Rialto workflow.
    """

    def __init__(self, environment: str = 'SANDBOX', config: Dict[str, str] = None, dry_run: bool = True):
        """
        Initialize the Rialto workflow processor.

        Args:
            environment: SANDBOX or PRODUCTION
            config: Configuration dict with library, department, work order settings
            dry_run: If True, performs validation only without modifications
        """
        self.environment = environment
        self.config = config or DEFAULT_CONFIG.copy()
        self.dry_run = dry_run

        # Initialize clients
        self.client = AlmaAPIClient(environment)
        self.acq = Acquisitions(self.client)
        self.bibs = BibliographicRecords(self.client)

        # Results tracking
        self.results = []
        self.stats = {
            'total': 0,
            'success': 0,
            'failed': 0,
            'skipped': 0
        }

    def _find_invoice_for_pol(self, pol_number: str) -> Optional[str]:
        """
        Find invoice ID for a given POL by searching invoice lines.

        This is the authoritative method per technical documentation:
        POL's invoice_reference field is often empty even when invoice is linked.
        The correct linkage is through invoice lines.

        Args:
            pol_number: POL number (e.g., "POL-5991")

        Returns:
            Invoice ID if found, None otherwise
        """
        try:
            # Search for recent invoices (limit to 100 most recent)
            # Note: This could be optimized with specific vendor or date filters
            search_results = self.acq.search_invoices(
                query="invoice_status~WAITING_TO_BE_SENT OR invoice_status~APPROVED OR invoice_status~ACTIVE",
                limit=100
            )

            invoices = search_results.get('invoice', [])
            if not invoices:
                print(f"  No recent invoices found in system")
                return None

            # Check each invoice's lines for reference to this POL
            print(f"  Checking {len(invoices)} recent invoices...")

            for invoice in invoices:
                invoice_id = invoice.get('id')
                if not invoice_id:
                    continue

                try:
                    # Get invoice lines
                    lines = self.acq.get_invoice_lines(invoice_id)

                    # Check if any line references this POL
                    for line in lines:
                        line_pol = line.get('po_line')
                        if line_pol == pol_number:
                            print(f"  Found match in invoice {invoice_id}")
                            return invoice_id

                except Exception as e:
                    # Skip invoices we can't access
                    continue

            print(f"  No invoice found with lines referencing {pol_number}")
            return None

        except Exception as e:
            print(f"  Error searching for invoice: {e}")
            return None

    def read_pols_from_tsv(self, tsv_file: str) -> List[str]:
        """
        Read POL IDs from TSV file (first column).

        Args:
            tsv_file: Path to TSV file

        Returns:
            List of POL IDs
        """
        pol_ids = []

        try:
            with open(tsv_file, 'r', encoding='utf-8') as f:
                reader = csv.reader(f, delimiter='\t')

                # Skip header if present
                header = next(reader, None)
                if header and not header[0].startswith('POL-'):
                    print(f"Header detected: {header[0]}")
                else:
                    # First row is data, not header
                    if header and header[0].startswith('POL-'):
                        pol_ids.append(header[0].strip())

                # Read POL IDs from first column
                for row in reader:
                    if row and row[0].strip():
                        pol_id = row[0].strip()
                        if pol_id:  # Skip empty lines
                            pol_ids.append(pol_id)

            print(f"✓ Read {len(pol_ids)} POL ID(s) from {tsv_file}")
            return pol_ids

        except FileNotFoundError:
            print(f"✗ ERROR: File not found: {tsv_file}")
            sys.exit(1)
        except Exception as e:
            print(f"✗ ERROR reading TSV file: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

    def extract_identifiers_from_pol(self, pol_id: str) -> Optional[Dict[str, Any]]:
        """
        Extract all required identifiers from a POL.

        Args:
            pol_id: POL ID (e.g., POL-5989)

        Returns:
            Dict with all identifiers, or None if extraction fails
        """
        print(f"\n{'='*70}")
        print(f"EXTRACTING IDENTIFIERS FOR {pol_id}")
        print(f"{'='*70}")

        try:
            # Get POL data
            print(f"Retrieving POL data...")
            pol_data = self.acq.get_pol(pol_id)

            # Extract basic POL info
            pol_number = pol_data.get('number', 'N/A')
            pol_status = pol_data.get('status', {}).get('value', 'UNKNOWN')

            print(f"✓ POL Number: {pol_number}")
            print(f"  POL Status: {pol_status}")

            # Extract MMS ID
            resource_metadata = pol_data.get('resource_metadata', {})
            mms_id_data = resource_metadata.get('mms_id', {})
            if isinstance(mms_id_data, dict):
                mms_id = mms_id_data.get('value')
            else:
                mms_id = mms_id_data

            if not mms_id:
                print(f"✗ ERROR: Could not extract MMS ID")
                return None

            print(f"✓ MMS ID: {mms_id}")

            # Extract Holding ID
            locations = pol_data.get('location', [])
            if isinstance(locations, dict):
                locations = [locations]

            if not locations:
                print(f"✗ ERROR: No locations found in POL")
                return None

            location = locations[0]

            # Try direct holding_id field first
            holding_id = location.get('holding_id')

            # If not found, check holding array
            if not holding_id:
                holdings = location.get('holding', [])
                if holdings:
                    if isinstance(holdings, list):
                        holding_id = holdings[0].get('id')
                    else:
                        holding_id = holdings.get('id')

            if not holding_id:
                print(f"✗ ERROR: Could not extract Holding ID")
                return None

            print(f"✓ Holding ID: {holding_id}")

            # Extract library code from location
            library_data = location.get('library', {})
            if isinstance(library_data, dict):
                library_code = library_data.get('value')
            else:
                library_code = library_data

            if library_code:
                print(f"✓ Library: {library_code}")
            else:
                print(f"⚠️  Warning: Could not extract library code, using default")
                library_code = self.config['library']

            # Extract items
            print(f"Extracting items...")
            items = self.acq.extract_items_from_pol_data(pol_data)

            if not items:
                print(f"✗ ERROR: No items found in POL")
                return None

            print(f"✓ Found {len(items)} item(s)")

            # Find unreceived item
            unreceived_items = [item for item in items if not item.get('receive_date')]

            if not unreceived_items:
                print(f"⚠️  All items already received - POL may not need processing")
                # Still return data but flag as already received
                item = items[0]
            else:
                item = unreceived_items[0]
                print(f"✓ Found unreceived item: {item.get('pid')}")

            item_pid = item.get('pid')
            if not item_pid:
                print(f"✗ ERROR: Could not extract item PID")
                return None

            # Extract invoice ID via invoice lines
            print(f"Checking for linked invoice...")

            # First try direct invoice_reference field
            invoice_id = pol_data.get('invoice_reference')

            # If not found, search via invoice lines (more reliable method)
            if invoice_id:
                print(f"✓ Invoice ID (from POL invoice_reference): {invoice_id}")
            else:
                print(f"  No direct invoice_reference in POL")
                print(f"  Searching for invoice via invoice lines...")

                invoice_id = self._find_invoice_for_pol(pol_number)

                if invoice_id:
                    print(f"✓ Invoice ID (via invoice lines search): {invoice_id}")
                else:
                    print(f"⚠️  No invoice found - workflow will skip payment step")

            # Get PO identifier (from POL number or vendor_reference)
            po_identifier = pol_data.get('vendor_reference') or pol_number

            # Compile all identifiers
            identifiers = {
                'pol_id': pol_id,
                'pol_number': pol_number,
                'pol_status': pol_status,
                'mms_id': mms_id,
                'holding_id': holding_id,
                'item_pid': item_pid,
                'item_barcode': item.get('barcode', 'N/A'),
                'item_received': bool(item.get('receive_date')),
                'receive_date': item.get('receive_date'),
                'invoice_id': invoice_id,
                'po_identifier': po_identifier,
                'library_code': library_code,
                'location': location.get('shelving_location', 'N/A')
            }

            print(f"\n✓ Successfully extracted all identifiers")
            return identifiers

        except Exception as e:
            print(f"✗ ERROR extracting identifiers: {e}")
            import traceback
            traceback.print_exc()
            return None

    def process_pol_workflow(self, identifiers: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a single POL through the complete workflow.

        Args:
            identifiers: Dict with all required identifiers

        Returns:
            Dict with processing results
        """
        pol_id = identifiers['pol_id']
        result = {
            'pol_id': pol_id,
            'pol_number': identifiers['pol_number'],
            'timestamp': datetime.now().isoformat(),
            'success': False,
            'steps': {},
            'errors': []
        }

        print(f"\n{'='*70}")
        print(f"PROCESSING WORKFLOW FOR {pol_id}")
        print(f"{'='*70}")

        try:
            # Step 1: Check if item already received
            if identifiers['item_received']:
                print(f"\n⚠️  Item already received on {identifiers['receive_date']}")
                print(f"   Skipping receive step")
                result['steps']['receive'] = {
                    'status': 'skipped',
                    'reason': 'already_received',
                    'date': identifiers['receive_date']
                }
            else:
                # Step 1: Receive item and scan into department
                print(f"\nSTEP 1: Receive item and keep in department")
                print(f"{'─'*70}")

                if self.dry_run:
                    print(f"[DRY RUN] Would receive item {identifiers['item_pid']}")
                    print(f"[DRY RUN] Would scan into department {self.config['department']}")
                    result['steps']['receive'] = {'status': 'dry_run'}
                else:
                    try:
                        receive_result = self.acq.receive_and_keep_in_department(
                            pol_id=pol_id,
                            item_id=identifiers['item_pid'],
                            mms_id=identifiers['mms_id'],
                            holding_id=identifiers['holding_id'],
                            library=identifiers['library_code'],
                            department=self.config['department'],
                            work_order_type=self.config['work_order_type'],
                            work_order_status=self.config['work_order_status']
                        )

                        print(f"✓ Item received and scanned into department")
                        result['steps']['receive'] = {
                            'status': 'success',
                            'item_id': identifiers['item_pid'],
                            'department': self.config['department']
                        }

                    except Exception as e:
                        print(f"✗ ERROR receiving item: {e}")
                        result['errors'].append(f"Receive failed: {str(e)}")
                        result['steps']['receive'] = {'status': 'failed', 'error': str(e)}
                        return result

            # Step 2: Pay invoice (if linked)
            if identifiers['invoice_id']:
                print(f"\nSTEP 2: Pay invoice")
                print(f"{'─'*70}")

                if self.dry_run:
                    print(f"[DRY RUN] Would pay invoice {identifiers['invoice_id']}")
                    result['steps']['pay_invoice'] = {'status': 'dry_run'}
                else:
                    try:
                        # Check invoice status before payment
                        invoice_data = self.acq.get_invoice(identifiers['invoice_id'])
                        invoice_status = invoice_data.get('invoice_status', {}).get('value', 'UNKNOWN')
                        payment_status = invoice_data.get('payment', {}).get('payment_status', {}).get('value', 'UNKNOWN')

                        print(f"  Invoice status: {invoice_status}")
                        print(f"  Payment status: {payment_status}")

                        # Check if already paid
                        if payment_status in ['PAID', 'FULLY_PAID']:
                            print(f"⚠️  Invoice already paid ({payment_status})")
                            result['steps']['pay_invoice'] = {
                                'status': 'skipped',
                                'reason': 'already_paid',
                                'payment_status': payment_status
                            }
                        else:
                            # Check if invoice needs approval before payment
                            if invoice_status == 'WAITING_TO_BE_SENT':
                                print(f"  Invoice in 'WAITING_TO_BE_SENT' status - approving first...")
                                try:
                                    self.acq.approve_invoice(identifiers['invoice_id'])
                                    print(f"  ✓ Invoice approved (WAITING_TO_BE_SENT → APPROVED)")
                                except Exception as e:
                                    print(f"  ⚠️  Warning: Could not approve invoice: {e}")
                                    print(f"  Continuing with payment attempt...")

                            # Pay invoice
                            self.acq.mark_invoice_paid(identifiers['invoice_id'])

                            print(f"✓ Invoice marked as paid")
                            result['steps']['pay_invoice'] = {
                                'status': 'success',
                                'invoice_id': identifiers['invoice_id'],
                                'previous_invoice_status': invoice_status,
                                'previous_payment_status': payment_status
                            }

                    except Exception as e:
                        print(f"✗ ERROR paying invoice: {e}")
                        result['errors'].append(f"Payment failed: {str(e)}")
                        result['steps']['pay_invoice'] = {'status': 'failed', 'error': str(e)}
                        # Continue to verification even if payment failed

            else:
                print(f"\nSTEP 2: Pay invoice")
                print(f"{'─'*70}")
                print(f"⚠️  No invoice linked - skipping payment")
                result['steps']['pay_invoice'] = {'status': 'skipped', 'reason': 'no_invoice'}

            # Step 3: Verify final state
            print(f"\nSTEP 3: Verify final state")
            print(f"{'─'*70}")

            try:
                # Get updated POL data
                updated_pol = self.acq.get_pol(pol_id)
                final_pol_status = updated_pol.get('status', {}).get('value', 'UNKNOWN')

                print(f"Final POL Status: {final_pol_status}")

                # Check if POL closed
                pol_closed = (final_pol_status == 'CLOSED')

                if pol_closed:
                    print(f"✅ POL CLOSED - Workflow complete!")
                else:
                    print(f"⚠️  POL not closed (status: {final_pol_status})")

                # Get item status from POL
                items = self.acq.extract_items_from_pol_data(updated_pol)
                if items:
                    item = items[0]
                    item_receive_date = item.get('receive_date')

                    print(f"Item receive date: {item_receive_date or 'Not received'}")

                result['steps']['verify'] = {
                    'status': 'success',
                    'pol_status': final_pol_status,
                    'pol_closed': pol_closed,
                    'item_received': bool(item_receive_date)
                }

                # Determine overall success
                if not self.dry_run:
                    if pol_closed:
                        result['success'] = True
                    else:
                        result['success'] = False
                        result['errors'].append(f"POL did not close (status: {final_pol_status})")
                else:
                    result['success'] = True  # Dry run always succeeds if no errors

            except Exception as e:
                print(f"✗ ERROR verifying final state: {e}")
                result['errors'].append(f"Verification failed: {str(e)}")
                result['steps']['verify'] = {'status': 'failed', 'error': str(e)}

            return result

        except Exception as e:
            print(f"✗ UNEXPECTED ERROR: {e}")
            import traceback
            traceback.print_exc()
            result['errors'].append(f"Unexpected error: {str(e)}")
            return result

    def process_batch(self, pol_ids: List[str]) -> None:
        """
        Process a batch of POLs through the workflow.

        Args:
            pol_ids: List of POL IDs to process
        """
        self.stats['total'] = len(pol_ids)

        print(f"\n{'='*70}")
        print(f"BATCH PROCESSING: {len(pol_ids)} POL(s)")
        print(f"Mode: {'DRY RUN' if self.dry_run else 'LIVE'}")
        print(f"Environment: {self.environment}")
        print(f"{'='*70}")

        for idx, pol_id in enumerate(pol_ids, 1):
            print(f"\n\n{'#'*70}")
            print(f"POL {idx}/{len(pol_ids)}: {pol_id}")
            print(f"{'#'*70}")

            # Extract identifiers
            identifiers = self.extract_identifiers_from_pol(pol_id)

            if not identifiers:
                print(f"✗ Failed to extract identifiers - SKIPPING")
                self.stats['skipped'] += 1
                self.results.append({
                    'pol_id': pol_id,
                    'success': False,
                    'errors': ['Failed to extract identifiers']
                })
                continue

            # Process workflow
            result = self.process_pol_workflow(identifiers)
            self.results.append(result)

            if result['success']:
                self.stats['success'] += 1
            else:
                self.stats['failed'] += 1

    def generate_report(self, output_file: Optional[str] = None) -> None:
        """
        Generate a summary report of processing results.

        Args:
            output_file: Optional path to save CSV report
        """
        print(f"\n\n{'='*70}")
        print(f"PROCESSING SUMMARY")
        print(f"{'='*70}")

        print(f"\nStatistics:")
        print(f"  Total POLs:    {self.stats['total']}")
        print(f"  Successful:    {self.stats['success']}")
        print(f"  Failed:        {self.stats['failed']}")
        print(f"  Skipped:       {self.stats['skipped']}")

        success_rate = (self.stats['success'] / self.stats['total'] * 100) if self.stats['total'] > 0 else 0
        print(f"  Success Rate:  {success_rate:.1f}%")

        # Detailed results
        print(f"\nDetailed Results:")
        print(f"{'─'*70}")

        for result in self.results:
            pol_id = result['pol_id']
            success = result['success']
            status_symbol = '✅' if success else '✗'

            print(f"\n{status_symbol} {pol_id}")

            if 'steps' in result:
                for step_name, step_data in result['steps'].items():
                    step_status = step_data.get('status', 'unknown')
                    print(f"   {step_name}: {step_status}")

            if result.get('errors'):
                print(f"   Errors:")
                for error in result['errors']:
                    print(f"     - {error}")

        # Save CSV report if requested
        if output_file:
            self.save_csv_report(output_file)
            print(f"\n✓ Report saved to: {output_file}")

    def save_csv_report(self, output_file: str) -> None:
        """
        Save processing results to CSV file.

        Args:
            output_file: Path to output CSV file
        """
        try:
            with open(output_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)

                # Header
                writer.writerow([
                    'POL_ID',
                    'POL_Number',
                    'Timestamp',
                    'Success',
                    'Receive_Status',
                    'Pay_Invoice_Status',
                    'Verify_Status',
                    'POL_Closed',
                    'Errors'
                ])

                # Data rows
                for result in self.results:
                    receive_status = result.get('steps', {}).get('receive', {}).get('status', 'N/A')
                    pay_status = result.get('steps', {}).get('pay_invoice', {}).get('status', 'N/A')
                    verify_status = result.get('steps', {}).get('verify', {}).get('status', 'N/A')
                    pol_closed = result.get('steps', {}).get('verify', {}).get('pol_closed', False)

                    errors = '; '.join(result.get('errors', []))

                    writer.writerow([
                        result.get('pol_id', 'N/A'),
                        result.get('pol_number', 'N/A'),
                        result.get('timestamp', 'N/A'),
                        'Yes' if result.get('success') else 'No',
                        receive_status,
                        pay_status,
                        verify_status,
                        'Yes' if pol_closed else 'No',
                        errors
                    ])

            print(f"✓ CSV report saved successfully")

        except Exception as e:
            print(f"✗ ERROR saving CSV report: {e}")


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(
        description='Process POLs through complete Rialto workflow',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument('--tsv', required=True,
                       help='Path to TSV file with POL IDs (first column)')
    parser.add_argument('--environment', choices=['SANDBOX', 'PRODUCTION'],
                       default='SANDBOX',
                       help='Alma environment (default: SANDBOX)')
    parser.add_argument('--library', default=DEFAULT_CONFIG['library'],
                       help=f'Library code (default: {DEFAULT_CONFIG["library"]})')
    parser.add_argument('--department', default=DEFAULT_CONFIG['department'],
                       help=f'Department code (default: {DEFAULT_CONFIG["department"]})')
    parser.add_argument('--work-order-type', default=DEFAULT_CONFIG['work_order_type'],
                       help=f'Work order type (default: {DEFAULT_CONFIG["work_order_type"]})')
    parser.add_argument('--work-order-status', default=DEFAULT_CONFIG['work_order_status'],
                       help=f'Work order status (default: {DEFAULT_CONFIG["work_order_status"]})')
    parser.add_argument('--output', help='Path to save CSV report')
    parser.add_argument('--dry-run', action='store_true', default=True,
                       help='Perform dry run (default: True)')
    parser.add_argument('--live', action='store_true',
                       help='Execute live workflow (disables dry-run)')

    args = parser.parse_args()

    # Determine dry run mode
    dry_run = not args.live

    # Build configuration
    config = {
        'library': args.library,
        'department': args.department,
        'work_order_type': args.work_order_type,
        'work_order_status': args.work_order_status
    }

    # Create processor
    processor = RialtoWorkflowProcessor(
        environment=args.environment,
        config=config,
        dry_run=dry_run
    )

    # Read POL IDs from TSV
    pol_ids = processor.read_pols_from_tsv(args.tsv)

    if not pol_ids:
        print("✗ No POL IDs found in TSV file")
        sys.exit(1)

    # Confirm before proceeding with live mode
    if not dry_run:
        print(f"\n{'!'*70}")
        print(f"WARNING: Running in LIVE mode - will modify {args.environment} data!")
        print(f"{'!'*70}")
        print(f"\nPOLs to process: {len(pol_ids)}")
        print(f"Configuration:")
        for key, value in config.items():
            print(f"  {key}: {value}")

        confirmation = input(f"\nType 'YES' to proceed: ")
        if confirmation != 'YES':
            print("Aborted by user")
            sys.exit(0)

    # Process batch
    processor.process_batch(pol_ids)

    # Generate report
    processor.generate_report(output_file=args.output)

    # Exit with appropriate code
    if processor.stats['failed'] > 0:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
