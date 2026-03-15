#!/usr/bin/env python3
"""
Smoke test for Alma Acquisitions Automation

Validates that all required imports work correctly.
Exit code 0 = success, 1 = failure.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_almaapitk_imports():
    """Test imports from almaapitk dependency."""
    print("Testing almaapitk imports...")

    from almaapitk import AlmaAPIClient
    from almaapitk import Acquisitions
    from almaapitk import BibliographicRecords

    print("  ✓ AlmaAPIClient")
    print("  ✓ Acquisitions")
    print("  ✓ BibliographicRecords")


def test_rialto_imports():
    """Test imports from workflows.rialto."""
    print("\nTesting workflows.rialto imports...")

    from workflows.rialto import POLExtractor
    from workflows.rialto import POLExtractionResult
    from workflows.rialto import RialtoWorkflowProcessor
    from workflows.rialto.pipeline import RialtoPipeline

    print("  ✓ POLExtractor")
    print("  ✓ POLExtractionResult")
    print("  ✓ RialtoWorkflowProcessor")
    print("  ✓ RialtoPipeline")


def test_invoices_imports():
    """Test imports from workflows.invoices."""
    print("\nTesting workflows.invoices imports...")

    from workflows.invoices import AutomatedInvoiceProcessor
    from workflows.invoices import ERPToAlmaIntegration

    print("  ✓ AutomatedInvoiceProcessor")
    print("  ✓ ERPToAlmaIntegration")


def main():
    """Run all smoke tests."""
    print("=" * 50)
    print("SMOKE TEST: Alma Acquisitions Automation")
    print("=" * 50)

    try:
        test_almaapitk_imports()
        test_rialto_imports()
        test_invoices_imports()

        print("\n" + "=" * 50)
        print("✓ All smoke tests passed!")
        print("=" * 50)
        return 0

    except ImportError as e:
        print(f"\n✗ Import failed: {e}")
        return 1
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
