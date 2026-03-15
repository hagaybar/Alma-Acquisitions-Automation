#!/usr/bin/env python3
"""
ERP to Alma Invoice Integration Script
Transfers invoice data from ERP system to Alma, creating invoices and updating POLs
"""

import os
import sys
import argparse
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path
import pandas as pd

from almaapitk import AlmaAPIClient, AlmaAPIError, Acquisitions


class ERPToAlmaIntegration:
    """
    Main integration class for ERP to Alma invoice processing.
    Uses the Acquisitions domain for all Alma API operations.
    """
    
    def __init__(self, environment: str = 'SANDBOX'):
        """
        Initialize the integration with Alma API clients.
        
        Args:
            environment: 'SANDBOX' or 'PRODUCTION'
        """
        self.environment = environment
        self.alma_client = AlmaAPIClient(environment)
        self.acquisitions = Acquisitions(self.alma_client)
        self.logger = self._setup_logger()
        
        # Test connection
        if not self.acquisitions.test_connection():
            raise RuntimeError(f"Failed to connect to Alma Acquisitions API ({environment})")
        
        self.logger.info(f"✓ Connected to Alma Acquisitions API ({environment})")
        
        # Statistics tracking
        self.stats = {
            'total_rows': 0,
            'pols_updated': 0,
            'invoices_created': 0,
            'invoice_lines_created': 0,
            'invoices_paid': 0,
            'errors': []
        }
    
    def _setup_logger(self) -> logging.Logger:
        """Setup logging configuration."""
        logger = logging.getLogger('ERPToAlma')
        logger.setLevel(logging.DEBUG)
        
        # Clear existing handlers
        if logger.handlers:
            logger.handlers.clear()
        
        # Create logs directory
        Path('logs').mkdir(exist_ok=True)
        
        # File handler
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        file_handler = logging.FileHandler(
            f'logs/erp_to_alma_{timestamp}.log',
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
        return logger
    
    def load_erp_report(self, file_path: str) -> pd.DataFrame:
        """
        Load ERP purchase report from CSV or Excel file.
        
        Args:
            file_path: Path to ERP report file
            
        Returns:
            DataFrame with ERP data
        """
        self.logger.info(f"Loading ERP report from {file_path}")
        
        try:
            # Check file exists
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File not found: {file_path}")
            
            # Load based on file extension
            if file_path.endswith('.csv'):
                df = pd.read_csv(file_path)
            elif file_path.endswith(('.xlsx', '.xls')):
                df = pd.read_excel(file_path)
            else:
                raise ValueError(f"Unsupported file format: {file_path}")
            
            # Validate required columns
            required_columns = [
                'ERP Number',
                'ERP Voucher Number',
                'ERP Invoice Date',
                'ERP Invoice Number',
                'ERP Final Sum for Payment (IN NIS)'
            ]
            
            missing_columns = [col for col in required_columns 
                              if col not in df.columns]
            
            if missing_columns:
                raise ValueError(f"Missing required columns: {missing_columns}")
            
            # Clean data
            df['ERP Number'] = df['ERP Number'].astype(str).str.strip()
            df['ERP Invoice Number'] = df['ERP Invoice Number'].astype(str).str.strip()
            df['ERP Voucher Number'] = df['ERP Voucher Number'].astype(str).str.strip()
            
            self.logger.info(f"✓ Loaded {len(df)} rows from ERP report")
            self.logger.debug(f"Columns: {list(df.columns)}")
            
            return df
            
        except Exception as e:
            self.logger.error(f"Failed to load ERP report: {e}")
            raise
    
    def load_mapping_report(self, file_path: str) -> Dict[str, str]:
        """
        Load Alma Analytics mapping report.
        
        Args:
            file_path: Path to mapping report file
            
        Returns:
            Dictionary mapping ERP Number to POL ID
        """
        self.logger.info(f"Loading mapping report from {file_path}")
        
        try:
            # Check file exists
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File not found: {file_path}")
            

            # Load based on file extension
            if file_path.endswith('.tsv'):
                df = pd.read_csv(file_path, sep='\t')
            elif file_path.endswith('.csv'):
                df = pd.read_csv(file_path)
            elif file_path.endswith(('.xlsx', '.xls')):
                df = pd.read_excel(file_path)
            else:
                raise ValueError(f"Unsupported file format: {file_path}")
            
            # Validate required columns
            if 'ERP Number' not in df.columns:
                raise ValueError("Missing 'ERP Number' column in mapping file")
            if 'PO Line Reference' not in df.columns:
                raise ValueError("Missing 'PO Line Reference' column in mapping file")
            
            # Create mapping dictionary
            mapping = {}
            for _, row in df.iterrows():
                erp_order = str(row['ERP Number']).strip()
                pol_ref = str(row['PO Line Reference']).strip()
                
                if erp_order and pol_ref and pol_ref != 'nan':
                    mapping[erp_order] = pol_ref
            
            self.logger.info(f"✓ Loaded {len(mapping)} order-to-POL mappings")
            self.logger.debug(f"Sample mapping: {dict(list(mapping.items())[:3])}")
            
            return mapping
            
        except Exception as e:
            self.logger.error(f"Failed to load mapping report: {e}")
            raise
    
    def update_pol_price(self, pol_id: str, amount: float, currency: str = "ILS") -> bool:
        """
        Update Purchase Order Line with new price using the acquisitions domain.
        
        Args:
            pol_id: Purchase Order Line ID
            amount: New amount in specified currency
            currency: Currency code (default: ILS)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.logger.debug(f"Updating POL {pol_id} with amount {amount} {currency}")
            
            # Get current POL data using acquisitions domain
            pol_data = self.acquisitions.get_pol(pol_id)
            
            # Update price fields
            if 'price' not in pol_data:
                pol_data['price'] = {}
            
            pol_data['price']['sum'] = str(amount)
            pol_data['price']['currency'] = {'value': currency}
            
            # Send update using acquisitions domain
            updated_pol = self.acquisitions.update_pol(pol_id, pol_data)
            
            self.logger.info(f"  ✓ Updated POL {pol_id}: {amount} {currency}")
            self.stats['pols_updated'] += 1
            return True
            
        except AlmaAPIError as e:
            self.logger.error(f"  ✗ API error updating POL {pol_id}: {e}")
            self.stats['errors'].append({
                'type': 'pol_update',
                'pol_id': pol_id,
                'error': str(e)
            })
            return False
        except Exception as e:
            self.logger.error(f"  ✗ Failed to update POL {pol_id}: {e}")
            self.stats['errors'].append({
                'type': 'pol_update',
                'pol_id': pol_id,
                'error': str(e)
            })
            return False
    
    # Refactored create_invoice_from_group
    def create_invoice_from_group(self, invoice_num: str, group_df: pd.DataFrame, 
                                 mapping: Dict[str, str], vendor_code: str = "DEFAULT") -> Optional[str]:
        """
        Create an invoice from a group of ERP rows using the acquisitions domain.
        
        Args:
            invoice_num: Invoice number
            group_df: DataFrame with rows for this invoice
            mapping: Dictionary mapping ERP numbers to POL IDs
            vendor_code: Vendor code to use (overrides POL's vendor if not 'DEFAULT')
            
        Returns:
            Invoice ID if successful, None otherwise
        """
        try:
            # Get first row for common invoice data
            first_row = group_df.iloc[0]

            # Get POL ID from first row to fetch vendor code from Alma
            erp_order = str(first_row['ERP Number'])
            pol_id = mapping.get(erp_order)
            
            # Determine the vendor code to use
            vendor_to_use = vendor_code
            if not pol_id:
                self.logger.warning(f"  ⚠️ No POL mapping found for ERP {erp_order}. Using default vendor.")
            elif vendor_code == "DEFAULT":
                # Get vendor code from POL if command-line argument is not specified
                pol_data = self.acquisitions.get_pol(pol_id)
                pol_vendor = pol_data.get('vendor', {}).get('value')
                if pol_vendor:
                    vendor_to_use = pol_vendor
                else:
                    self.logger.warning(f"  ⚠️ No vendor found on POL {pol_id}. Using default vendor.")
            
            # Prepare invoice data
            
            # Calculate total amount
            total_amount = group_df['ERP Final Sum for Payment (IN NIS)'].sum()
            
            self.logger.debug(f"Creating invoice {invoice_num} with total {total_amount} NIS")
            
            # Prepare invoice data
            invoice_data = {
                'number': str(invoice_num),
                'invoice_date': str(first_row['ERP Invoice Date']),
                'vendor': {'value': vendor_to_use},
                'currency': {'value': 'ILS'},
                'total_amount': {
                    'sum': str(total_amount),
                    'currency': {'value': 'ILS'}
                }
            }
            
            # Add voucher number if present
            voucher_num = str(first_row['ERP Voucher Number'])
            if voucher_num and voucher_num != 'nan':
                invoice_data['payment'] = {
                    'voucher_number': voucher_num
                }
            
            # Create invoice using acquisitions domain
            created_invoice = self.acquisitions.create_invoice(invoice_data)
            invoice_id = created_invoice.get('id')
            
            if invoice_id:
                self.logger.info(f"  ✓ Created invoice {invoice_num} (ID: {invoice_id})")
                self.stats['invoices_created'] += 1
                return invoice_id
            else:
                raise ValueError("No invoice ID returned from API")
            
        except AlmaAPIError as e:
            self.logger.error(f"  ✗ API error creating invoice {invoice_num}: {e}")
            self.stats['errors'].append({
                'type': 'invoice_creation',
                'invoice_number': invoice_num,
                'error': str(e)
            })
            return None        

        except Exception as e:
            self.logger.error(f"  ✗ Failed to create invoice {invoice_num}: {e}")
            self.stats['errors'].append({
                'type': 'invoice_creation',
                'invoice_number': invoice_num,
                'error': str(e)
            })
            return None
    
    def add_invoice_line(self, invoice_id: str, pol_id: str, amount: float) -> bool:
        """
        Create an invoice line and link it to a POL using the acquisitions domain.
        
        Args:
            invoice_id: Invoice ID
            pol_id: Purchase Order Line ID
            amount: Line amount
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.logger.debug(f"Creating invoice line for POL {pol_id}: {amount} NIS")
            
            # Prepare line data
            line_data = {
                'po_line': pol_id,
                'price': str(amount),
                'quantity': 1,  # Default to 1
                'invoice_line_type': {'value': 'REGULAR'},
                'fund_distribution': [{
                    'fund_code': {'value': 'DEFAULT'},  # You may need to adjust this
                    'amount': {
                        'sum': str(amount),
                        'currency': {'value': 'ILS'}
                    },
                    'percent': 100
                }]
            }
            
            # Create invoice line using acquisitions domain
            created_line = self.acquisitions.create_invoice_line(invoice_id, line_data)
            
            self.logger.info(f"    ✓ Created invoice line for POL {pol_id}")
            self.stats['invoice_lines_created'] += 1
            return True
            
        except AlmaAPIError as e:
            self.logger.error(f"    ✗ API error creating invoice line for POL {pol_id}: {e}")
            self.stats['errors'].append({
                'type': 'invoice_line_creation',
                'invoice_id': invoice_id,
                'pol_id': pol_id,
                'error': str(e)
            })
            return False
        except Exception as e:
            self.logger.error(f"    ✗ Failed to create invoice line for POL {pol_id}: {e}")
            self.stats['errors'].append({
                'type': 'invoice_line_creation',
                'invoice_id': invoice_id,
                'pol_id': pol_id,
                'error': str(e)
            })
            return False
    
    def process_invoice_group(self, invoice_num: str, group_df: pd.DataFrame, 
                            mapping: Dict[str, str], process_payment: bool = False,
                            vendor_code: str = "DEFAULT") -> Dict[str, Any]:
        """
        Process a group of ERP rows that belong to the same invoice.
        
        Args:
            invoice_num: Invoice number
            group_df: DataFrame with rows for this invoice
            mapping: Dictionary mapping ERP orders to POL IDs
            process_payment: Whether to mark invoice as paid
            vendor_code: Vendor code to use (overrides POL's vendor if not 'DEFAULT')
            
        Returns:
            Processing result dictionary
        """
        result = {
            'invoice_number': invoice_num,
            'success': False,
            'invoice_id': None,
            'pols_processed': [],
            'errors': []
        }
        
        self.logger.info(f"\n{'='*50}")
        self.logger.info(f"Processing invoice: {invoice_num}")
        self.logger.info(f"  Lines to process: {len(group_df)}")

        # Step 1: Create the invoice
        invoice_id = self.create_invoice_from_group(
            invoice_num, 
            group_df, 
            mapping=mapping, # This line was added
            vendor_code=vendor_code
        )
               
        if not invoice_id:
            result['errors'].append("Failed to create invoice")
            return result
        
        result['invoice_id'] = invoice_id
        
        # Step 2: Process each line
        for _, row in group_df.iterrows():
            erp_order = str(row['ERP Number'])
            amount = float(row['ERP Final Sum for Payment (IN NIS)'])
                # Add a print statement here to see the value and its representation
            print(f"DEBUG: Looking for ERP order: '{erp_order}'")
            
            # Check if we have a POL mapping
            if erp_order not in mapping:
                self.logger.warning(f"  ⚠️ No POL mapping for ERP: {erp_order}")
                result['errors'].append(f"No mapping for order {erp_order}")
                continue
            
            pol_id = mapping[erp_order]
            self.logger.info(f"  Processing POL {pol_id} (Order: {erp_order})")
            
            # Update POL price
            if self.update_pol_price(pol_id, amount):
                result['pols_processed'].append(pol_id)
                
                # Create invoice line
                self.add_invoice_line(invoice_id, pol_id, amount)
            else:
                result['errors'].append(f"Failed to update POL {pol_id}")
        
        # Step 3: Process payment if requested
        if process_payment and invoice_id:
            try:
                self.logger.info(f"  Processing payment for invoice {invoice_id}")
                
                # First, we need to process the invoice (approve it)
                self.acquisitions.approve_invoice(invoice_id)
                self.logger.info(f"    ✓ Invoice approved")
                
                # Then mark it as paid
                self.acquisitions.mark_invoice_paid(invoice_id)
                self.logger.info(f"    ✓ Invoice marked as paid")
                self.stats['invoices_paid'] += 1
                
            except Exception as e:
                self.logger.error(f"    ✗ Failed to process payment: {e}")
                result['errors'].append(f"Payment processing failed: {e}")
        
        # Determine overall success
        result['success'] = len(result['pols_processed']) > 0
        
        return result
    
    def run_integration(self, erp_file: str, mapping_file: str, 
                       dry_run: bool = False,
                       process_payments: bool = False,
                       vendor_code: str = "DEFAULT") -> Dict[str, Any]:
        """
        Main integration workflow.
        
        Args:
            erp_file: Path to ERP report
            mapping_file: Path to mapping report
            dry_run: If True, validate without making changes
            process_payments: Whether to mark invoices as paid
            vendor_code: Default vendor code to use
            
        Returns:
            Integration results and statistics
        """
        # Store file paths to be used in other methods
        self.mapping_file = mapping_file

        self.logger.info("="*60)
        self.logger.info("ERP TO ALMA INVOICE INTEGRATION")
        self.logger.info("="*60)
        self.logger.info(f"Environment: {self.environment}")
        self.logger.info(f"Dry Run: {dry_run}")
        self.logger.info(f"Process Payments: {process_payments}")
        self.logger.info(f"Vendor Code: {vendor_code}")
        self.logger.info("="*60)
        
        try:
            # Load data files
            erp_df = self.load_erp_report(erp_file)
            mapping = self.load_mapping_report(mapping_file)
            
            self.stats['total_rows'] = len(erp_df)
            
            # Group by invoice number to avoid duplicates
            grouped = erp_df.groupby('ERP Invoice Number')
            self.logger.info(f"\nFound {len(grouped)} unique invoices to process")
            
            # Process each invoice group
            results = []
            
            for invoice_num, group in grouped:
                if dry_run:
                    # Dry run - just validate and report what would be done
                    self.logger.info(f"\n[DRY RUN] Invoice: {invoice_num}")
                    self.logger.info(f"  Would process {len(group)} lines:")
                    
                    for _, row in group.iterrows():
                        erp_order = str(row['ERP Number'])
                        amount = row['ERP Final Sum for Payment (IN NIS)']
                        
                        if erp_order in mapping:
                            pol_id = mapping[erp_order]
                            self.logger.info(f"    - POL {pol_id}: {amount} NIS")
                        else:
                            self.logger.warning(f"    - No mapping for order {erp_order}")
                else:
                    # Process for real
                    result = self.process_invoice_group(
                        invoice_num, 
                        group, 
                        mapping,
                        process_payment=process_payments,
                        vendor_code=vendor_code
                    )
                    results.append(result)
            
            # Final summary
            self.logger.info("\n" + "="*60)
            self.logger.info("INTEGRATION COMPLETE")
            self.logger.info("="*60)
            self.logger.info(f"Total rows processed: {self.stats['total_rows']}")
            self.logger.info(f"POLs updated: {self.stats['pols_updated']}")
            self.logger.info(f"Invoices created: {self.stats['invoices_created']}")
            self.logger.info(f"Invoice lines created: {self.stats['invoice_lines_created']}")
            
            if process_payments:
                self.logger.info(f"Invoices paid: {self.stats['invoices_paid']}")
            
            self.logger.info(f"Errors encountered: {len(self.stats['errors'])}")
            
            if self.stats['errors']:
                self.logger.error("\nError Summary (first 10):")
                for error in self.stats['errors'][:10]:
                    self.logger.error(f"  - {error['type']}: {error.get('pol_id', error.get('invoice_number', 'N/A'))}")
                    self.logger.error(f"    {error['error']}")
            
            # Save detailed results
            if not dry_run:
                self._save_results(results)
            
            return {
                'statistics': self.stats,
                'results': results if not dry_run else [],
                'dry_run': dry_run
            }
            
        except Exception as e:
            self.logger.error(f"Integration failed: {e}")
            raise
    
    def _save_results(self, results: List[Dict[str, Any]]) -> None:
        """Save detailed results to JSON file."""
        try:
            output_dir = Path('output')
            output_dir.mkdir(exist_ok=True)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = output_dir / f"integration_results_{timestamp}.json"
            
            import json
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'timestamp': timestamp,
                    'environment': self.environment,
                    'statistics': self.stats,
                    'invoice_results': results
                }, f, indent=2)
            
            self.logger.info(f"\nResults saved to: {output_file}")
            
        except Exception as e:
            self.logger.error(f"Failed to save results: {e}")


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description='Transfer invoice data from ERP to Alma',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run to validate data
  python erp_to_alma_invoice.py erp_report.csv mapping.csv --dry-run
  
  # Process in sandbox
  python erp_to_alma_invoice.py erp_report.csv mapping.csv --environment SANDBOX
  
  # Process with payments
  python erp_to_alma_invoice.py erp_report.csv mapping.csv --process-payments
  
  # Production run with a specific vendor
  python erp_to_alma_invoice.py erp_report.csv mapping.csv --environment PRODUCTION --vendor AMAZON
        """
    )
    
    parser.add_argument(
        'erp_file',
        help='Path to ERP purchase report (CSV or Excel)'
    )
    parser.add_argument(
        'mapping_file',
        help='Path to Alma Analytics mapping report (CSV or Excel)'
    )
    parser.add_argument(
        '--environment',
        choices=['SANDBOX', 'PRODUCTION'],
        default='SANDBOX',
        help='Alma environment (default: SANDBOX)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Validate without making changes'
    )
    parser.add_argument(
        '--process-payments',
        action='store_true',
        help='Mark invoices as paid after creation'
    )
    parser.add_argument(
        '--vendor',
        default='DEFAULT',
        help='Vendor code to use for invoices (default: DEFAULT)'
    )
    
    args = parser.parse_args()
    
    # Verify environment variables
    required_env = f"ALMA_{'SB' if args.environment == 'SANDBOX' else 'PROD'}_API_KEY"
    if not os.getenv(required_env):
        print(f"Error: {required_env} environment variable not set")
        print(f"Please set it using: export {required_env}='your_api_key'")
        sys.exit(1)
    
    # Verify input files exist
    if not os.path.exists(args.erp_file):
        print(f"Error: ERP file not found: {args.erp_file}")
        sys.exit(1)
    
    if not os.path.exists(args.mapping_file):
        print(f"Error: Mapping file not found: {args.mapping_file}")
        sys.exit(1)
    
    # Run integration
    try:
        integration = ERPToAlmaIntegration(args.environment)
        results = integration.run_integration(
            args.erp_file,
            args.mapping_file,
            dry_run=args.dry_run,
            process_payments=args.process_payments,
            vendor_code=args.vendor
        )
        
        # Exit with appropriate code
        if results['statistics']['errors']:
            sys.exit(1)  # Exit with error if there were any errors
        else:
            sys.exit(0)  # Success
            
    except Exception as e:
        print(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()