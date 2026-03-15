#!/usr/bin/env python3
"""
POL Extraction Utility for Rialto Invoice PDFs

Extracts Purchase Order Line (POL) numbers from vendor invoice PDFs.
Can be used as a standalone CLI tool or imported as a module.

Usage (CLI):
    python pdf_extractor.py invoice.pdf
    python pdf_extractor.py invoice.pdf --tsv-output pols.tsv

Usage (Module):
    from workflows.rialto.pdf_extractor import POLExtractor
    extractor = POLExtractor()
    result = extractor.extract_from_pdf("invoice.pdf")
    if result.success:
        print(result.pol_ids)

Author: Claude Code
Date: 2025-10-21
"""

import argparse
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import PyPDF2


@dataclass
class POLExtractionResult:
    """Result of POL extraction from a PDF."""
    success: bool
    pdf_path: str
    pol_ids: List[str] = field(default_factory=list)
    pol_table: List[dict] = field(default_factory=list)
    page_count: int = 0
    error_message: Optional[str] = None

    @property
    def pol_count(self) -> int:
        """Number of unique POLs extracted."""
        return len(self.pol_ids)


class POLExtractor:
    """
    Extracts POL numbers from Rialto vendor invoice PDFs.

    Can extract:
    - Simple POL list (unique, sorted POL IDs)
    - POL table with quantity, price, and currency
    """

    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        Initialize the POL extractor.

        Args:
            logger: Optional logger instance. If not provided, creates one.
        """
        self.logger = logger or logging.getLogger(__name__)

    def extract_from_pdf(self, pdf_path: str) -> POLExtractionResult:
        """
        Extract POL numbers from a PDF file.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            POLExtractionResult with extracted data or error information
        """
        pdf_path = str(pdf_path)  # Handle Path objects

        # Validate file exists
        if not os.path.exists(pdf_path):
            self.logger.error(f"File not found: {pdf_path}")
            return POLExtractionResult(
                success=False,
                pdf_path=pdf_path,
                error_message=f"File not found: {pdf_path}"
            )

        # Validate file extension
        if not pdf_path.lower().endswith('.pdf'):
            self.logger.error(f"Not a PDF file: {pdf_path}")
            return POLExtractionResult(
                success=False,
                pdf_path=pdf_path,
                error_message=f"Not a PDF file: {pdf_path}"
            )

        # Extract text from PDF
        try:
            text, page_count = self._extract_pdf_text(pdf_path)
        except PyPDF2.errors.PdfReadError as e:
            self.logger.error(f"Could not read PDF (corrupted or encrypted): {pdf_path}")
            return POLExtractionResult(
                success=False,
                pdf_path=pdf_path,
                error_message=f"Could not read PDF: {e}"
            )
        except Exception as e:
            self.logger.error(f"Unexpected error reading PDF: {e}")
            return POLExtractionResult(
                success=False,
                pdf_path=pdf_path,
                error_message=f"Unexpected error: {e}"
            )

        # Extract POL data
        pol_ids = self._extract_pol_list(text)
        pol_table = self._extract_pol_table(text)

        if not pol_ids:
            self.logger.warning(f"No POL numbers found in {pdf_path}")
            return POLExtractionResult(
                success=False,
                pdf_path=pdf_path,
                page_count=page_count,
                error_message="No POL numbers found in document"
            )

        self.logger.info(f"Extracted {len(pol_ids)} POL(s) from {pdf_path} ({page_count} pages)")

        return POLExtractionResult(
            success=True,
            pdf_path=pdf_path,
            pol_ids=pol_ids,
            pol_table=pol_table,
            page_count=page_count
        )

    def _extract_pdf_text(self, pdf_path: str) -> tuple[str, int]:
        """
        Extract text content from all pages of a PDF.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            Tuple of (extracted_text, page_count)

        Raises:
            PyPDF2.errors.PdfReadError: If PDF is corrupted or encrypted
        """
        text = ""

        with open(pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            page_count = len(reader.pages)

            self.logger.debug(f"Reading {page_count} pages from {pdf_path}")

            for page_num in range(page_count):
                page = reader.pages[page_num]
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"

        return text, page_count

    def _extract_pol_list(self, text: str) -> List[str]:
        """
        Extract unique, sorted POL numbers from text.

        Args:
            text: Text content to parse

        Returns:
            Sorted list of unique POL numbers (e.g., ['POL-5661', 'POL-5969'])
        """
        pol_pattern = r'POL-\d+'
        pol_matches = re.findall(pol_pattern, text)
        unique_pols = sorted(set(pol_matches))
        return unique_pols

    def _extract_pol_table(self, text: str) -> List[dict]:
        """
        Extract POL table rows with quantity, price, and currency.

        Args:
            text: Text content to parse

        Returns:
            List of dicts: [{'pol': 'POL-5661', 'quantity': '1', 'price': '28.56', 'currency': 'USD'}, ...]
        """
        rows = []

        for line in text.splitlines():
            if "POL-" not in line:
                continue

            tokens = line.split()
            pol = next((t for t in tokens if t.startswith("POL-")), None)
            if not pol:
                continue

            # Find currency (3-letter uppercase code)
            currency_idx = next(
                (i for i, t in enumerate(tokens) if t.isupper() and len(t) == 3),
                None,
            )
            if currency_idx is None or currency_idx + 1 >= len(tokens):
                continue

            price_token = tokens[currency_idx + 1]
            if not self._is_number(price_token):
                continue

            rows.append({
                "pol": pol,
                "quantity": "1",
                "price": price_token,
                "currency": tokens[currency_idx],
            })

        return rows

    @staticmethod
    def _is_number(token: str) -> bool:
        """Check if a string token represents a number."""
        try:
            float(token)
            return True
        except ValueError:
            return False

    def save_pol_list(self, result: POLExtractionResult, output_path: str) -> bool:
        """
        Save POL list to a text file (one POL per line).

        Args:
            result: POLExtractionResult from extract_from_pdf()
            output_path: Path to output file

        Returns:
            True if successful, False otherwise
        """
        if not result.success or not result.pol_ids:
            self.logger.error("Cannot save: no POLs to write")
            return False

        try:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write("\n".join(result.pol_ids))
            self.logger.info(f"Saved POL list to {output_path}")
            return True
        except Exception as e:
            self.logger.error(f"Error saving POL list: {e}")
            return False

    def save_pol_table_tsv(self, result: POLExtractionResult, output_path: str) -> bool:
        """
        Save POL table to a TSV file.

        Args:
            result: POLExtractionResult from extract_from_pdf()
            output_path: Path to output TSV file

        Returns:
            True if successful, False otherwise
        """
        if not result.success:
            self.logger.error("Cannot save: extraction failed")
            return False

        try:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write("POL_ID\tquantity\tprice\tcurrency\n")

                if result.pol_table:
                    # Use table data if available
                    for row in result.pol_table:
                        f.write(f"{row['pol']}\t{row['quantity']}\t{row['price']}\t{row['currency']}\n")
                else:
                    # Fall back to simple POL list
                    for pol_id in result.pol_ids:
                        f.write(f"{pol_id}\t\t\t\n")

            self.logger.info(f"Saved POL table TSV to {output_path}")
            return True
        except Exception as e:
            self.logger.error(f"Error saving POL table: {e}")
            return False


def _build_default_output_path(pdf_path: str, suffix: str) -> str:
    """Build default output path based on PDF filename."""
    base_dir = os.path.dirname(pdf_path)
    base_name = os.path.splitext(os.path.basename(pdf_path))[0]
    return os.path.join(base_dir, f"{base_name}{suffix}")


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Extract POL numbers from Rialto vendor invoice PDFs."
    )
    parser.add_argument("pdf_path", help="Path to the PDF file")
    parser.add_argument(
        "--list-output",
        help="Output path for POL list text file (default: <pdf_name>_pol_list.txt)",
    )
    parser.add_argument(
        "--tsv-output",
        help="Output path for POL table TSV file (default: <pdf_name>_pol_table.tsv)",
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress output except errors"
    )
    args = parser.parse_args()

    # Configure logging
    log_level = logging.WARNING if args.quiet else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)

    print("=== POL Extraction Tool ===\n")

    # Extract POLs
    extractor = POLExtractor(logger=logger)
    result = extractor.extract_from_pdf(args.pdf_path)

    if not result.success:
        print(f"Error: {result.error_message}")
        return 1

    # Display results
    print("Found POL numbers:\n")
    print("\n".join(result.pol_ids))
    print(f"\nTotal POLs found: {result.pol_count}")

    # Save POL list
    list_output = args.list_output or _build_default_output_path(args.pdf_path, "_pol_list.txt")
    if extractor.save_pol_list(result, list_output):
        print(f"\nSaved POL list to '{list_output}'")

    # Save TSV table
    tsv_output = args.tsv_output or _build_default_output_path(args.pdf_path, "_pol_table.tsv")
    if extractor.save_pol_table_tsv(result, tsv_output):
        print(f"Saved POL table to '{tsv_output}'")

    return 0


if __name__ == "__main__":
    exit(main())
