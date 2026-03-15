#!/usr/bin/env python3
"""
Rialto Pipeline - Automated PDF to POL Processing

This script monitors a folder for incoming Rialto invoice PDFs, extracts POL numbers,
and processes them through the complete Rialto workflow.

Pipeline Flow:
    1. Monitor input folder for new PDFs (placed by Power Automate)
    2. Extract POL numbers from each PDF
    3. Process POLs through the Rialto workflow (receive, pay, close)
    4. Move processed PDFs to processed/ or failed/ folder
    5. Generate reports and logs

Run Modes:
    - Single run: Process any pending PDFs and exit
    - Daemon mode: Run continuously, checking folder at specified interval

Usage:
    # Single run (for cron/systemd)
    python rialto_pipeline.py --input-folder ./input

    # Daemon mode (runs continuously)
    python rialto_pipeline.py --input-folder ./input --daemon --interval 3600

    # With confirmation prompt (for testing)
    python rialto_pipeline.py --input-folder ./input --confirm --live

Author: Claude Code
Date: 2025-01-14
"""

import argparse
import json
import logging
import os
import shutil
import signal
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from almaapitk import AlmaAPIClient

# Internal project imports (relative within RialtoProduction)
from .pdf_extractor import POLExtractor, POLExtractionResult
from .workflow import RialtoWorkflowProcessor, DEFAULT_CONFIG


@dataclass
class PipelineConfig:
    """Configuration for the Rialto pipeline."""
    input_folder: Path
    processed_folder: Path
    failed_folder: Path
    output_folder: Path
    log_folder: Path
    environment: str = "SANDBOX"
    dry_run: bool = True
    confirm: bool = False
    daemon: bool = False
    mock: bool = False  # Mock mode - no API calls at all
    interval: int = 3600  # seconds between checks in daemon mode
    workflow_config: Dict[str, str] = field(default_factory=lambda: DEFAULT_CONFIG.copy())

    @classmethod
    def from_args(cls, args: argparse.Namespace) -> "PipelineConfig":
        """Create config from command line arguments."""
        input_folder = Path(args.input_folder).resolve()
        base_folder = input_folder.parent

        return cls(
            input_folder=input_folder,
            processed_folder=Path(args.processed_folder).resolve() if args.processed_folder else base_folder / "processed",
            failed_folder=Path(args.failed_folder).resolve() if args.failed_folder else base_folder / "failed",
            output_folder=Path(args.output_folder).resolve() if args.output_folder else base_folder / "output",
            log_folder=Path(args.log_folder).resolve() if args.log_folder else base_folder / "logs",
            environment=args.environment,
            dry_run=not args.live,
            confirm=args.confirm,
            daemon=args.daemon,
            mock=args.mock,
            interval=args.interval,
            workflow_config={
                "library": args.library,
                "department": args.department,
                "work_order_type": args.work_order_type,
                "work_order_status": args.work_order_status,
            }
        )

    @classmethod
    def from_json(cls, json_path: str, args: argparse.Namespace) -> "PipelineConfig":
        """Create config from JSON file, with CLI args as overrides."""
        with open(json_path, 'r') as f:
            config_data = json.load(f)

        # Start with JSON values
        input_folder = Path(config_data.get("input_folder", args.input_folder)).resolve()
        base_folder = input_folder.parent

        # CLI args override JSON values
        return cls(
            input_folder=input_folder,
            processed_folder=Path(args.processed_folder or config_data.get("processed_folder", base_folder / "processed")).resolve(),
            failed_folder=Path(args.failed_folder or config_data.get("failed_folder", base_folder / "failed")).resolve(),
            output_folder=Path(args.output_folder or config_data.get("output_folder", base_folder / "output")).resolve(),
            log_folder=Path(args.log_folder or config_data.get("log_folder", base_folder / "logs")).resolve(),
            environment=args.environment or config_data.get("environment", "SANDBOX"),
            dry_run=not args.live if args.live else not config_data.get("live", False),
            confirm=args.confirm or config_data.get("confirm", False),
            daemon=args.daemon or config_data.get("daemon", False),
            mock=args.mock or config_data.get("mock", False),
            interval=args.interval or config_data.get("interval", 3600),
            workflow_config={
                "library": args.library or config_data.get("workflow_settings", {}).get("library", DEFAULT_CONFIG["library"]),
                "department": args.department or config_data.get("workflow_settings", {}).get("department", DEFAULT_CONFIG["department"]),
                "work_order_type": args.work_order_type or config_data.get("workflow_settings", {}).get("work_order_type", DEFAULT_CONFIG["work_order_type"]),
                "work_order_status": args.work_order_status or config_data.get("workflow_settings", {}).get("work_order_status", DEFAULT_CONFIG["work_order_status"]),
            }
        )


@dataclass
class PDFProcessingResult:
    """Result of processing a single PDF."""
    pdf_path: str
    pdf_name: str
    success: bool
    pol_count: int = 0
    pols_processed: int = 0
    pols_successful: int = 0
    pols_failed: int = 0
    extraction_result: Optional[POLExtractionResult] = None
    workflow_results: List[Dict[str, Any]] = field(default_factory=list)
    error_message: Optional[str] = None
    processing_time: float = 0.0
    moved_to: Optional[str] = None


class RialtoPipeline:
    """
    Main pipeline orchestrator for Rialto PDF processing.

    Monitors an input folder for new PDFs, extracts POL numbers,
    and processes them through the complete Rialto workflow.
    """

    def __init__(self, config: PipelineConfig):
        """
        Initialize the pipeline.

        Args:
            config: Pipeline configuration
        """
        self.config = config
        self.logger = self._setup_logging()
        self.extractor = POLExtractor(logger=self.logger)
        self.running = True
        self.results: List[PDFProcessingResult] = []

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _setup_logging(self) -> logging.Logger:
        """Configure logging for the pipeline."""
        # Ensure log folder exists
        self.config.log_folder.mkdir(parents=True, exist_ok=True)

        # Create logger
        logger = logging.getLogger("rialto_pipeline")
        logger.setLevel(logging.DEBUG)

        # Clear existing handlers
        logger.handlers.clear()

        # File handler - detailed logs
        log_file = self.config.log_folder / f"pipeline_{datetime.now().strftime('%Y%m%d')}.log"
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

        # Console handler - info and above
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

        return logger

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        self.logger.info(f"Received signal {signum}, shutting down...")
        self.running = False

    def _ensure_folders(self) -> None:
        """Create required folders if they don't exist."""
        folders = [
            self.config.input_folder,
            self.config.processed_folder,
            self.config.failed_folder,
            self.config.output_folder,
            self.config.log_folder,
        ]
        for folder in folders:
            folder.mkdir(parents=True, exist_ok=True)
            self.logger.debug(f"Ensured folder exists: {folder}")

    def _find_pending_pdfs(self) -> List[Path]:
        """Find PDF files in the input folder."""
        pdfs = list(self.config.input_folder.glob("*.pdf"))
        pdfs.extend(self.config.input_folder.glob("*.PDF"))
        # Remove duplicates (case-insensitive filesystems)
        unique_pdfs = list({p.resolve(): p for p in pdfs}.values())
        return sorted(unique_pdfs, key=lambda p: p.stat().st_mtime)

    def _move_pdf(self, pdf_path: Path, destination_folder: Path) -> Optional[Path]:
        """
        Move a PDF to the destination folder.

        Args:
            pdf_path: Source PDF path
            destination_folder: Destination folder

        Returns:
            New path if successful, None otherwise
        """
        try:
            # Add timestamp to filename if file already exists
            dest_path = destination_folder / pdf_path.name
            if dest_path.exists():
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                stem = pdf_path.stem
                suffix = pdf_path.suffix
                dest_path = destination_folder / f"{stem}_{timestamp}{suffix}"

            shutil.move(str(pdf_path), str(dest_path))
            self.logger.info(f"Moved PDF to: {dest_path}")
            return dest_path
        except Exception as e:
            self.logger.error(f"Failed to move PDF {pdf_path}: {e}")
            return None

    def _save_mock_report(self, report_path: Path, mock_results: List[Dict[str, Any]]) -> None:
        """
        Save mock workflow results to a CSV report.

        Args:
            report_path: Path to output CSV file
            mock_results: List of mock result dictionaries
        """
        import csv
        try:
            with open(report_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'POL_ID', 'POL_Number', 'Timestamp', 'Success',
                    'Receive_Status', 'Pay_Invoice_Status', 'Verify_Status',
                    'POL_Closed', 'Errors', 'Mode'
                ])
                for result in mock_results:
                    writer.writerow([
                        result.get('pol_id', 'N/A'),
                        result.get('pol_number', 'N/A'),
                        result.get('timestamp', 'N/A'),
                        'Yes' if result.get('success') else 'No',
                        result.get('steps', {}).get('receive', {}).get('status', 'N/A'),
                        result.get('steps', {}).get('pay_invoice', {}).get('status', 'N/A'),
                        result.get('steps', {}).get('verify', {}).get('status', 'N/A'),
                        'Yes' if result.get('steps', {}).get('verify', {}).get('pol_closed') else 'No',
                        '; '.join(result.get('errors', [])),
                        'MOCK'
                    ])
            self.logger.debug(f"Mock report saved to {report_path}")
        except Exception as e:
            self.logger.error(f"Failed to save mock report: {e}")

    def _process_single_pdf(self, pdf_path: Path) -> PDFProcessingResult:
        """
        Process a single PDF through the complete pipeline.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            PDFProcessingResult with processing details
        """
        start_time = time.time()
        result = PDFProcessingResult(
            pdf_path=str(pdf_path),
            pdf_name=pdf_path.name,
            success=False
        )

        self.logger.info(f"{'='*60}")
        self.logger.info(f"Processing PDF: {pdf_path.name}")
        self.logger.info(f"{'='*60}")

        # Step 1: Extract POLs from PDF
        self.logger.info("Step 1: Extracting POLs from PDF...")
        extraction_result = self.extractor.extract_from_pdf(str(pdf_path))
        result.extraction_result = extraction_result

        if not extraction_result.success:
            result.error_message = f"PDF extraction failed: {extraction_result.error_message}"
            self.logger.error(result.error_message)
            result.processing_time = time.time() - start_time
            return result

        result.pol_count = extraction_result.pol_count
        self.logger.info(f"Extracted {result.pol_count} POL(s) from PDF")

        # Show extracted POLs
        for pol_id in extraction_result.pol_ids:
            self.logger.info(f"  - {pol_id}")

        # Step 2: Confirmation prompt (if enabled)
        if self.config.confirm:
            print(f"\n{'!'*60}")
            print(f"CONFIRMATION REQUIRED")
            print(f"{'!'*60}")
            print(f"PDF: {pdf_path.name}")
            print(f"POLs to process: {result.pol_count}")
            for pol_id in extraction_result.pol_ids:
                print(f"  - {pol_id}")
            print(f"\nEnvironment: {self.config.environment}")
            print(f"Mode: {'LIVE' if not self.config.dry_run else 'DRY RUN'}")

            confirmation = input("\nType 'YES' to proceed, or anything else to skip: ")
            if confirmation != 'YES':
                result.error_message = "Skipped by user confirmation"
                self.logger.info("PDF processing skipped by user")
                result.processing_time = time.time() - start_time
                return result

        # Step 3: Process POLs through workflow (or mock it)
        if self.config.mock:
            # Mock mode - simulate workflow without API calls
            self.logger.info("Step 2: [MOCK MODE] Simulating workflow processing...")
            self.logger.info("[MOCK] No API calls will be made")

            # Generate mock results for each POL
            mock_results = []
            for pol_id in extraction_result.pol_ids:
                mock_result = {
                    'pol_id': pol_id,
                    'pol_number': pol_id,
                    'timestamp': datetime.now().isoformat(),
                    'success': True,
                    'steps': {
                        'receive': {'status': 'mock_success'},
                        'pay_invoice': {'status': 'mock_success'},
                        'verify': {'status': 'mock_success', 'pol_closed': True}
                    },
                    'errors': []
                }
                mock_results.append(mock_result)
                self.logger.info(f"  [MOCK] Simulated processing for {pol_id}: SUCCESS")

            result.workflow_results = mock_results
            result.pols_processed = len(extraction_result.pol_ids)
            result.pols_successful = len(extraction_result.pol_ids)
            result.pols_failed = 0

            # Generate mock report
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_path = self.config.output_folder / f"{pdf_path.stem}_{timestamp}_mock_report.csv"
            self._save_mock_report(report_path, mock_results)
            self.logger.info(f"Mock report saved to: {report_path}")

        else:
            # Normal mode - actual workflow processing
            self.logger.info("Step 2: Processing POLs through workflow...")

            # Initialize workflow processor
            workflow = RialtoWorkflowProcessor(
                environment=self.config.environment,
                config=self.config.workflow_config,
                dry_run=self.config.dry_run
            )

            # Process POLs
            workflow.process_batch(extraction_result.pol_ids)
            result.workflow_results = workflow.results
            result.pols_processed = workflow.stats['total']
            result.pols_successful = workflow.stats['success']
            result.pols_failed = workflow.stats['failed']

            # Generate workflow report
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_path = self.config.output_folder / f"{pdf_path.stem}_{timestamp}_report.csv"
            workflow.save_csv_report(str(report_path))
            self.logger.info(f"Workflow report saved to: {report_path}")

        # Determine overall success
        result.success = (result.pols_failed == 0 and result.pols_successful > 0)
        result.processing_time = time.time() - start_time

        if result.success:
            self.logger.info(f"PDF processing completed successfully ({result.pols_successful}/{result.pol_count} POLs)")
        else:
            self.logger.warning(f"PDF processing completed with issues ({result.pols_successful}/{result.pol_count} POLs successful)")

        return result

    def run_single(self) -> int:
        """
        Run pipeline once: process all pending PDFs and exit.

        Returns:
            Exit code (0 = success, 1 = failures occurred)
        """
        self.logger.info("="*60)
        self.logger.info("RIALTO PIPELINE - SINGLE RUN")
        self.logger.info("="*60)
        self.logger.info(f"Environment: {self.config.environment}")
        if self.config.mock:
            self.logger.info("Mode: MOCK (no API calls)")
        else:
            self.logger.info(f"Mode: {'DRY RUN' if self.config.dry_run else 'LIVE'}")
        self.logger.info(f"Input folder: {self.config.input_folder}")
        self.logger.info(f"Processed folder: {self.config.processed_folder}")
        self.logger.info(f"Failed folder: {self.config.failed_folder}")

        self._ensure_folders()

        # Find pending PDFs
        pending_pdfs = self._find_pending_pdfs()

        if not pending_pdfs:
            self.logger.info("No pending PDFs found in input folder")
            return 0

        self.logger.info(f"Found {len(pending_pdfs)} PDF(s) to process")

        # Process each PDF
        failures = 0
        for idx, pdf_path in enumerate(pending_pdfs, 1):
            self.logger.info(f"\n[{idx}/{len(pending_pdfs)}] Processing: {pdf_path.name}")

            result = self._process_single_pdf(pdf_path)
            self.results.append(result)

            # Move PDF based on result
            # In mock mode or dry run with extracted POLs, always move to processed
            if result.success or self.config.mock or (self.config.dry_run and result.pol_count > 0):
                dest = self._move_pdf(pdf_path, self.config.processed_folder)
                result.moved_to = str(dest) if dest else None
            else:
                dest = self._move_pdf(pdf_path, self.config.failed_folder)
                result.moved_to = str(dest) if dest else None
                failures += 1

        # Print summary
        self._print_summary()

        return 1 if failures > 0 else 0

    def run_daemon(self) -> int:
        """
        Run pipeline as a daemon: continuously monitor folder at specified interval.

        Returns:
            Exit code (0 = clean shutdown)
        """
        self.logger.info("="*60)
        self.logger.info("RIALTO PIPELINE - DAEMON MODE")
        self.logger.info("="*60)
        self.logger.info(f"Environment: {self.config.environment}")
        if self.config.mock:
            self.logger.info("Mode: MOCK (no API calls)")
        else:
            self.logger.info(f"Mode: {'DRY RUN' if self.config.dry_run else 'LIVE'}")
        self.logger.info(f"Check interval: {self.config.interval} seconds")
        self.logger.info(f"Input folder: {self.config.input_folder}")
        self.logger.info("Press Ctrl+C to stop")

        self._ensure_folders()

        while self.running:
            try:
                # Find pending PDFs
                pending_pdfs = self._find_pending_pdfs()

                if pending_pdfs:
                    self.logger.info(f"Found {len(pending_pdfs)} PDF(s) to process")

                    for pdf_path in pending_pdfs:
                        if not self.running:
                            break

                        result = self._process_single_pdf(pdf_path)
                        self.results.append(result)

                        # Move PDF based on result
                        # In mock mode or dry run with extracted POLs, always move to processed
                        if result.success or self.config.mock or (self.config.dry_run and result.pol_count > 0):
                            dest = self._move_pdf(pdf_path, self.config.processed_folder)
                            result.moved_to = str(dest) if dest else None
                        else:
                            dest = self._move_pdf(pdf_path, self.config.failed_folder)
                            result.moved_to = str(dest) if dest else None
                else:
                    self.logger.debug("No pending PDFs found")

                # Wait for next check
                if self.running:
                    self.logger.debug(f"Sleeping for {self.config.interval} seconds...")
                    # Sleep in smaller increments for responsive shutdown
                    for _ in range(self.config.interval):
                        if not self.running:
                            break
                        time.sleep(1)

            except Exception as e:
                self.logger.error(f"Error in daemon loop: {e}")
                if self.running:
                    self.logger.info("Continuing after error...")
                    time.sleep(60)  # Brief pause before retry

        self.logger.info("Daemon shutdown complete")
        self._print_summary()
        return 0

    def _print_summary(self) -> None:
        """Print processing summary."""
        if not self.results:
            return

        self.logger.info("\n" + "="*60)
        self.logger.info("PIPELINE SUMMARY")
        self.logger.info("="*60)

        total_pdfs = len(self.results)
        successful_pdfs = sum(1 for r in self.results if r.success)
        failed_pdfs = total_pdfs - successful_pdfs

        total_pols = sum(r.pol_count for r in self.results)
        processed_pols = sum(r.pols_processed for r in self.results)
        successful_pols = sum(r.pols_successful for r in self.results)

        self.logger.info(f"PDFs processed: {total_pdfs}")
        self.logger.info(f"  Successful: {successful_pdfs}")
        self.logger.info(f"  Failed: {failed_pdfs}")
        self.logger.info(f"POLs extracted: {total_pols}")
        self.logger.info(f"POLs processed: {processed_pols}")
        self.logger.info(f"POLs successful: {successful_pols}")

        # List any failures
        failed_results = [r for r in self.results if not r.success]
        if failed_results:
            self.logger.info("\nFailed PDFs:")
            for r in failed_results:
                self.logger.info(f"  - {r.pdf_name}: {r.error_message}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Rialto Pipeline - Automated PDF to POL Processing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Single run (process pending PDFs and exit)
    python rialto_pipeline.py --input-folder ./input

    # Daemon mode (check every hour)
    python rialto_pipeline.py --input-folder ./input --daemon

    # Daemon with custom interval (30 minutes)
    python rialto_pipeline.py --input-folder ./input --daemon --interval 1800

    # Live mode with confirmation
    python rialto_pipeline.py --input-folder ./input --confirm --live

    # Mock mode - test pipeline without API calls
    python rialto_pipeline.py --input-folder ./input --mock

    # Using config file
    python rialto_pipeline.py --config config/rialto_pipeline_config.json
        """
    )

    # Input/Output folders
    parser.add_argument("--input-folder", "-i",
                        help="Folder to monitor for incoming PDFs")
    parser.add_argument("--processed-folder",
                        help="Folder for successfully processed PDFs (default: ../processed)")
    parser.add_argument("--failed-folder",
                        help="Folder for failed PDFs (default: ../failed)")
    parser.add_argument("--output-folder",
                        help="Folder for reports and output files (default: ../output)")
    parser.add_argument("--log-folder",
                        help="Folder for log files (default: ../logs)")

    # Run mode
    parser.add_argument("--daemon", "-d", action="store_true",
                        help="Run as daemon (continuously monitor folder)")
    parser.add_argument("--interval", type=int, default=3600,
                        help="Seconds between folder checks in daemon mode (default: 3600)")

    # Environment and execution mode
    parser.add_argument("--environment", "-e", choices=["SANDBOX", "PRODUCTION"],
                        default="SANDBOX",
                        help="Alma environment (default: SANDBOX)")
    parser.add_argument("--dry-run", action="store_true", default=True,
                        help="Perform dry run - no modifications (default: True)")
    parser.add_argument("--live", action="store_true",
                        help="Execute live workflow (disables dry-run)")
    parser.add_argument("--confirm", action="store_true",
                        help="Prompt for confirmation before processing each PDF")
    parser.add_argument("--mock", action="store_true",
                        help="Mock mode - test pipeline without any API calls")

    # Workflow configuration
    parser.add_argument("--library", default=DEFAULT_CONFIG["library"],
                        help=f"Library code (default: {DEFAULT_CONFIG['library']})")
    parser.add_argument("--department", default=DEFAULT_CONFIG["department"],
                        help=f"Department code (default: {DEFAULT_CONFIG['department']})")
    parser.add_argument("--work-order-type", default=DEFAULT_CONFIG["work_order_type"],
                        help=f"Work order type (default: {DEFAULT_CONFIG['work_order_type']})")
    parser.add_argument("--work-order-status", default=DEFAULT_CONFIG["work_order_status"],
                        help=f"Work order status (default: {DEFAULT_CONFIG['work_order_status']})")

    # Config file
    parser.add_argument("--config", "-c",
                        help="Path to JSON configuration file")

    args = parser.parse_args()

    # Validate required arguments
    if not args.input_folder and not args.config:
        parser.error("Either --input-folder or --config is required")

    # Load configuration
    if args.config:
        if not os.path.exists(args.config):
            print(f"Error: Config file not found: {args.config}")
            sys.exit(1)
        config = PipelineConfig.from_json(args.config, args)
    else:
        config = PipelineConfig.from_args(args)

    # Validate input folder exists
    if not config.input_folder.exists():
        print(f"Error: Input folder does not exist: {config.input_folder}")
        sys.exit(1)

    # Create and run pipeline
    pipeline = RialtoPipeline(config)

    if config.daemon:
        exit_code = pipeline.run_daemon()
    else:
        exit_code = pipeline.run_single()

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
