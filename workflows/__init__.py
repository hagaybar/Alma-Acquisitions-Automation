"""
Alma Acquisitions Automation Workflows

This package contains automated workflows for Alma acquisitions:
- rialto: POL processing for Rialto vendor invoices
- invoices: Invoice processing and ERP integration
"""

from .rialto import POLExtractor, POLExtractionResult, RialtoWorkflowProcessor
from .invoices import AutomatedInvoiceProcessor, ERPToAlmaIntegration

__all__ = [
    # Rialto
    'POLExtractor',
    'POLExtractionResult',
    'RialtoWorkflowProcessor',
    # Invoices
    'AutomatedInvoiceProcessor',
    'ERPToAlmaIntegration',
]
