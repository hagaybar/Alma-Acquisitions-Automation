# Alma Acquisitions Automation - Developer Guide

**For developers unfamiliar with Alma ILS**

This guide provides a comprehensive introduction to the Alma-Acquisitions-Automation repository, explaining the underlying Alma concepts, API workflows, and how each component in this codebase operates.

---

## Table of Contents

1. [What is Alma?](#what-is-alma)
2. [Core Acquisitions Concepts](#core-acquisitions-concepts)
3. [The Acquisitions Workflow](#the-acquisitions-workflow)
4. [Repository Architecture](#repository-architecture)
5. [Component Reference](#component-reference)
6. [Dataflow Diagrams](#dataflow-diagrams)
7. [API Operations Summary](#api-operations-summary)
8. [Getting Started](#getting-started)
9. [Testing Guide](#testing-guide)

---

## What is Alma?

**Alma** is an **Integrated Library System (ILS)** developed by Ex Libris (Clarivate). It's used by academic and research libraries worldwide to manage:

- **Acquisitions** - Purchasing books, journals, and other materials
- **Cataloging** - Describing and organizing library materials
- **Fulfillment** - Circulation, loans, and resource sharing
- **Electronic Resources** - E-journals, databases, and digital content

### Key Terminology

| Term | Definition |
|------|------------|
| **MMS ID** | Metadata Management System ID - unique identifier for a bibliographic record |
| **POL** | Purchase Order Line - a single item order within a purchase order |
| **Holding** | Physical location information for a bibliographic record |
| **Item** | A specific physical copy of a bibliographic record |
| **Invoice** | Payment document linked to POLs |
| **Vendor** | Supplier of library materials (e.g., Rialto, Amazon) |

### Environments

Alma provides two environments:

| Environment | Purpose | API Key Variable |
|-------------|---------|------------------|
| **SANDBOX** | Testing and development | `ALMA_SB_API_KEY` |
| **PRODUCTION** | Live library data | `ALMA_PROD_API_KEY` |

**Rule**: Always test in SANDBOX before running anything in PRODUCTION.

---

## Core Acquisitions Concepts

### Purchase Order Line (POL)

A **POL** represents a single item being purchased. It contains:

```
POL
├── number (e.g., "POL-5989")
├── status (ACTIVE, SENT, CLOSED, CANCELLED)
├── vendor (who we're buying from)
├── price (cost information)
├── resource_metadata
│   └── mms_id (link to bibliographic record)
└── location[] (where the item will be shelved)
    ├── library (e.g., "MAIN")
    ├── holding_id (physical location)
    └── copy[] (actual items)
        ├── pid (item identifier)
        ├── barcode
        └── receive_date (null if not yet received)
```

### POL Lifecycle

```
┌─────────────────────────────────────────────────────────────────────┐
│                        POL LIFECYCLE                                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐  │
│   │  ACTIVE  │────▶│   SENT   │────▶│ RECEIVED │────▶│  CLOSED  │  │
│   └──────────┘     └──────────┘     └──────────┘     └──────────┘  │
│        │                                                    ▲        │
│        │              Items received                        │        │
│        │              + Invoice paid ───────────────────────┘        │
│        │                                                             │
│        └──────────────────┐                                          │
│                           ▼                                          │
│                    ┌───────────┐                                     │
│                    │ CANCELLED │                                     │
│                    └───────────┘                                     │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

**POL closes automatically when:**
1. All items are received
2. All linked invoice lines are paid

### Invoice Workflow

Invoices track payment for POLs. The workflow is **strictly ordered**:

```
┌─────────────────────────────────────────────────────────────────────┐
│                     INVOICE WORKFLOW (MANDATORY ORDER)               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   Step 1              Step 2              Step 3            Step 4   │
│   ┌──────────┐       ┌──────────┐       ┌──────────┐     ┌────────┐ │
│   │  CREATE  │──────▶│ADD LINES │──────▶│ APPROVE  │────▶│  PAY   │ │
│   │ INVOICE  │       │(link POL)│       │(MANDATORY)│    │        │ │
│   └──────────┘       └──────────┘       └──────────┘     └────────┘ │
│                                               ▲                      │
│                                               │                      │
│   ⚠️ Error 402459 occurs if you skip ────────┘                      │
│      the APPROVE step!                                               │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

**Invoice States:**

| State | invoice_status | payment_status | approval_status |
|-------|----------------|----------------|-----------------|
| Created | ACTIVE | NOT_PAID | PENDING |
| Approved | ACTIVE | NOT_PAID | APPROVED |
| Paid | CLOSED | PAID | APPROVED |

### Item Receiving

When items arrive at the library, they must be "received" in Alma:

```
┌─────────────────────────────────────────────────────────────────────┐
│                    ITEM RECEIVING OPTIONS                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   Option A: Standard Receive                                         │
│   ┌──────────┐                ┌──────────────┐                      │
│   │ Receive  │───────────────▶│  IN TRANSIT  │──────▶ Shelf         │
│   │   Item   │                │   (default)  │                      │
│   └──────────┘                └──────────────┘                      │
│                                                                      │
│   Option B: Receive + Keep in Department (this repo's approach)     │
│   ┌──────────┐   ┌──────────┐   ┌──────────┐                       │
│   │ Receive  │──▶│ Scan-In  │──▶│   STAYS   │──▶ Process ──▶ Shelf │
│   │   Item   │   │ to Dept  │   │  IN DEPT  │    by staff          │
│   └──────────┘   └──────────┘   └──────────┘                       │
│                                                                      │
│   The scan-in operation creates a "work order" that keeps           │
│   the item in the acquisitions department for processing.           │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## The Acquisitions Workflow

### Complete Rialto Flow (What This Repo Automates)

**Rialto** is a vendor platform that sends electronic invoices. This repo automates the processing:

```
┌─────────────────────────────────────────────────────────────────────┐
│                    RIALTO AUTOMATION FLOW                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   1. VENDOR SENDS PDF INVOICE                                        │
│      ┌─────────────────────┐                                        │
│      │  Invoice PDF        │                                        │
│      │  (contains POL IDs) │                                        │
│      └──────────┬──────────┘                                        │
│                 │                                                    │
│                 ▼                                                    │
│   2. PDF EXTRACTION (pdf_extractor.py)                              │
│      ┌─────────────────────┐                                        │
│      │ Extract POL numbers │  "POL-5989, POL-5990, ..."            │
│      │ using regex         │                                        │
│      └──────────┬──────────┘                                        │
│                 │                                                    │
│                 ▼                                                    │
│   3. FOR EACH POL (workflow.py)                                     │
│      ┌─────────────────────────────────────────────────┐            │
│      │  a. Get POL data from Alma API                  │            │
│      │  b. Extract item PID, MMS ID, holding ID        │            │
│      │  c. Find linked invoice (search invoice lines)  │            │
│      └──────────┬──────────────────────────────────────┘            │
│                 │                                                    │
│                 ▼                                                    │
│   4. RECEIVE ITEM                                                    │
│      ┌─────────────────────────────────────────────────┐            │
│      │  POST /acq/po-lines/{pol}/items/{item}?op=receive│           │
│      │  + scan-in to keep in department                 │           │
│      └──────────┬──────────────────────────────────────┘            │
│                 │                                                    │
│                 ▼                                                    │
│   5. PAY INVOICE                                                     │
│      ┌─────────────────────────────────────────────────┐            │
│      │  POST /acq/invoices/{id}?op=process_invoice     │            │
│      │  POST /acq/invoices/{id}?op=paid                │            │
│      └──────────┬──────────────────────────────────────┘            │
│                 │                                                    │
│                 ▼                                                    │
│   6. VERIFY POL CLOSED                                               │
│      ┌─────────────────────────────────────────────────┐            │
│      │  GET /acq/po-lines/{pol}                        │            │
│      │  Check status == "CLOSED"                       │            │
│      └─────────────────────────────────────────────────┘            │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Repository Architecture

### Directory Structure

```
Alma-Acquisitions-Automation/
│
├── workflows/                    # Main automation workflows
│   ├── __init__.py
│   │
│   ├── rialto/                   # Rialto vendor processing
│   │   ├── __init__.py
│   │   ├── pdf_extractor.py      # Extract POL IDs from PDFs
│   │   ├── workflow.py           # Process POLs (receive, pay, close)
│   │   └── pipeline.py           # Monitor folder, orchestrate workflow
│   │
│   └── invoices/                 # General invoice processing
│       ├── __init__.py
│       ├── bulk_processor.py     # Process invoices from Excel
│       └── erp_integration.py    # ERP-to-Alma invoice sync
│
├── config/                       # Configuration templates
│   ├── rialto_pipeline_config.example.json
│   ├── rialto_workflow_config.example.json
│   └── invoice_processor.example.json
│
├── batch/                        # Windows batch scripts
│   ├── rialto_pipeline_sandbox.bat
│   ├── rialto_pipeline_production.bat
│   └── rialto_pipeline_mock_test.bat
│
├── scripts/                      # Utility scripts
│   └── smoke_project.py          # Verify installation
│
├── tests/                        # Test suite
│   ├── __init__.py
│   └── test_imports.py           # Import verification
│
├── docs/                         # Documentation
│   └── DEVELOPER_GUIDE.md        # This file
│
├── input/                        # Input files (PDFs, TSVs)
├── output/                       # Reports and results
├── processed/                    # Successfully processed files
├── failed/                       # Failed processing files
├── logs/                         # Log files
│
├── pyproject.toml                # Poetry dependencies
└── README.md                     # Quick start guide
```

### Dependencies

This repository depends on `almaapitk` (AlmaAPITK) for all Alma API operations:

```python
from almaapitk import AlmaAPIClient, Acquisitions, BibliographicRecords
```

Key classes from almaapitk:
- `AlmaAPIClient` - HTTP client for Alma API
- `Acquisitions` - POL, invoice, and receiving operations
- `BibliographicRecords` - Item scan-in operations

---

## Component Reference

### 1. PDF Extractor (`workflows/rialto/pdf_extractor.py`)

**Purpose**: Extract POL numbers from vendor invoice PDFs.

#### Classes

| Class | Description |
|-------|-------------|
| `POLExtractionResult` | Dataclass holding extraction results |
| `POLExtractor` | Main extraction logic |

#### Key Methods

```python
class POLExtractor:
    def extract_from_pdf(pdf_path: str) -> POLExtractionResult
        """Extract POL numbers from a PDF file."""

    def save_pol_list(result: POLExtractionResult, output_path: str) -> bool
        """Save POL list to text file."""

    def save_pol_table_tsv(result: POLExtractionResult, output_path: str) -> bool
        """Save POL table with prices to TSV."""
```

#### Data Flow

```
PDF File ──▶ PyPDF2 (text extraction) ──▶ Regex "POL-\d+" ──▶ Unique sorted list
```

---

### 2. Rialto Workflow Processor (`workflows/rialto/workflow.py`)

**Purpose**: Process POLs through complete receive-pay-close workflow.

#### Classes

| Class | Description |
|-------|-------------|
| `RialtoWorkflowProcessor` | Main workflow orchestrator |

#### Key Methods

```python
class RialtoWorkflowProcessor:
    def __init__(environment: str, config: Dict, dry_run: bool)
        """Initialize with Alma client and configuration."""

    def read_pols_from_tsv(tsv_file: str) -> List[str]
        """Read POL IDs from TSV file."""

    def extract_identifiers_from_pol(pol_id: str) -> Optional[Dict]
        """Extract MMS ID, holding ID, item PID from POL."""

    def process_pol_workflow(identifiers: Dict) -> Dict
        """Execute receive → pay → verify workflow."""

    def process_batch(pol_ids: List[str]) -> None
        """Process multiple POLs."""

    def generate_report(output_file: str) -> None
        """Generate CSV report of results."""
```

#### Workflow Steps

```python
# Step 1: Extract identifiers
identifiers = extract_identifiers_from_pol("POL-5989")
# Returns: {
#   'pol_id': 'POL-5989',
#   'mms_id': '9912345...',
#   'holding_id': '22123456...',
#   'item_pid': '23123456...',
#   'invoice_id': '123456789',
#   ...
# }

# Step 2: Receive item and keep in department
acq.receive_and_keep_in_department(
    pol_id=identifiers['pol_id'],
    item_id=identifiers['item_pid'],
    mms_id=identifiers['mms_id'],
    holding_id=identifiers['holding_id'],
    library="AC1",
    department="AcqDeptAC1",
    work_order_type="AcqWorkOrder",
    work_order_status="CopyCat"
)

# Step 3: Pay invoice
acq.approve_invoice(identifiers['invoice_id'])
acq.mark_invoice_paid(identifiers['invoice_id'])

# Step 4: Verify POL closed
updated_pol = acq.get_pol(identifiers['pol_id'])
assert updated_pol['status']['value'] == 'CLOSED'
```

---

### 3. Rialto Pipeline (`workflows/rialto/pipeline.py`)

**Purpose**: Monitor folder for PDFs, orchestrate end-to-end processing.

#### Classes

| Class | Description |
|-------|-------------|
| `PipelineConfig` | Configuration dataclass |
| `PDFProcessingResult` | Result of processing one PDF |
| `RialtoPipeline` | Main pipeline orchestrator |

#### Key Methods

```python
class RialtoPipeline:
    def __init__(config: PipelineConfig)
        """Initialize pipeline with configuration."""

    def run_single() -> int
        """Process pending PDFs once and exit."""

    def run_daemon() -> int
        """Run continuously, checking folder at interval."""
```

#### Pipeline Data Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                       PIPELINE DATA FLOW                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  input/                                                              │
│    │                                                                 │
│    ▼                                                                 │
│  ┌──────────────────┐                                               │
│  │ Find PDFs        │  _find_pending_pdfs()                         │
│  │ *.pdf, *.PDF     │                                               │
│  └────────┬─────────┘                                               │
│           │                                                          │
│           ▼                                                          │
│  ┌──────────────────┐                                               │
│  │ Extract POLs     │  POLExtractor.extract_from_pdf()              │
│  │ from PDF         │                                               │
│  └────────┬─────────┘                                               │
│           │                                                          │
│           ▼                                                          │
│  ┌──────────────────┐                                               │
│  │ Process Workflow │  RialtoWorkflowProcessor.process_batch()      │
│  │ (receive/pay)    │                                               │
│  └────────┬─────────┘                                               │
│           │                                                          │
│           ├───────────────────┐                                      │
│           ▼                   ▼                                      │
│  ┌──────────────────┐  ┌──────────────────┐                         │
│  │  processed/      │  │  failed/         │                         │
│  │  (success)       │  │  (errors)        │                         │
│  └──────────────────┘  └──────────────────┘                         │
│           │                                                          │
│           ▼                                                          │
│  ┌──────────────────┐                                               │
│  │  output/         │  CSV report per PDF                           │
│  │  *_report.csv    │                                               │
│  └──────────────────┘                                               │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

### 4. Bulk Invoice Processor (`workflows/invoices/bulk_processor.py`)

**Purpose**: Process invoices from daily Excel reports.

#### Classes

| Class | Description |
|-------|-------------|
| `AutomatedInvoiceProcessor` | Batch invoice processor |

#### Key Methods

```python
class AutomatedInvoiceProcessor:
    def __init__(config_file: str)
        """Load configuration and connect to Alma."""

    def read_invoice_ids_from_excel() -> List[str]
        """Read invoice IDs from first column."""

    def process_single_invoice(invoice_id: str) -> Dict
        """Mark invoice as paid (skip if already paid)."""

    def process_all_invoices(invoice_ids: List[str]) -> List[Dict]
        """Process all invoices with error handling."""

    def run() -> bool
        """Main execution method."""
```

#### Data Flow

```
Excel Report (invoice IDs)
    │
    ▼
For each invoice:
    │
    ├── Already paid? ──▶ Skip
    │
    └── Not paid ──▶ mark_invoice_paid() ──▶ TSV Report
```

---

### 5. ERP Integration (`workflows/invoices/erp_integration.py`)

**Purpose**: Transfer invoice data from external ERP system to Alma.

#### Classes

| Class | Description |
|-------|-------------|
| `ERPToAlmaIntegration` | ERP-to-Alma synchronization |

#### Key Methods

```python
class ERPToAlmaIntegration:
    def __init__(environment: str)
        """Initialize Alma connection."""

    def load_erp_report(file_path: str) -> pd.DataFrame
        """Load ERP purchase report."""

    def load_mapping_report(file_path: str) -> Dict[str, str]
        """Load ERP Number → POL ID mapping."""

    def update_pol_price(pol_id: str, amount: float) -> bool
        """Update POL with ERP price."""

    def create_invoice_from_group(invoice_num: str, group_df: DataFrame) -> str
        """Create Alma invoice from ERP data."""

    def add_invoice_line(invoice_id: str, pol_id: str, amount: float) -> bool
        """Add line linking invoice to POL."""

    def run_integration(erp_file: str, mapping_file: str, ...) -> Dict
        """Main integration workflow."""
```

#### Data Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                     ERP INTEGRATION FLOW                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────┐     ┌─────────────┐                                │
│  │ ERP Report  │     │ Mapping     │                                │
│  │ (invoices)  │     │ (ERP→POL)   │                                │
│  └──────┬──────┘     └──────┬──────┘                                │
│         │                   │                                        │
│         └─────────┬─────────┘                                        │
│                   │                                                  │
│                   ▼                                                  │
│         ┌─────────────────┐                                         │
│         │ Group by        │                                         │
│         │ Invoice Number  │                                         │
│         └────────┬────────┘                                         │
│                  │                                                   │
│                  ▼                                                   │
│         For each invoice group:                                      │
│         ┌─────────────────────────────────────┐                     │
│         │ 1. Update POL prices                │                     │
│         │ 2. Create invoice in Alma           │                     │
│         │ 3. Add invoice lines (link POLs)    │                     │
│         │ 4. Approve invoice                  │                     │
│         │ 5. Mark as paid (optional)          │                     │
│         └─────────────────────────────────────┘                     │
│                  │                                                   │
│                  ▼                                                   │
│         ┌─────────────────┐                                         │
│         │ JSON Results    │                                         │
│         └─────────────────┘                                         │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Dataflow Diagrams

### Complete System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     ALMA ACQUISITIONS AUTOMATION                            │
│                         COMPLETE SYSTEM VIEW                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   INPUTS                    PROCESSING                    OUTPUTS           │
│   ──────                    ──────────                    ───────           │
│                                                                              │
│   ┌───────────┐                                                             │
│   │  Rialto   │                                                             │
│   │  Invoice  │────┐                                                        │
│   │   PDFs    │    │                                                        │
│   └───────────┘    │         ┌──────────────────┐                           │
│                    ├────────▶│   Rialto         │                           │
│   ┌───────────┐    │         │   Pipeline       │────────▶ processed/       │
│   │   POL     │────┤         │                  │          failed/          │
│   │   TSV     │    │         │  ┌────────────┐  │          output/          │
│   │  Files    │    │         │  │ Extractor  │  │          logs/            │
│   └───────────┘    │         │  └──────┬─────┘  │                           │
│                    │         │         │        │                           │
│                    │         │  ┌──────▼─────┐  │                           │
│                    │         │  │ Workflow   │  │                           │
│                    │         │  │ Processor  │  │                           │
│                    │         │  └────────────┘  │                           │
│                    │         └────────┬─────────┘                           │
│                    │                  │                                     │
│   ┌───────────┐    │                  │                                     │
│   │  Excel    │────┤                  │              ┌──────────────────┐   │
│   │  Invoice  │    │                  │              │                  │   │
│   │  Reports  │    │   ┌──────────────┴──────────────│    ALMA API      │   │
│   └───────────┘    │   │                             │                  │   │
│                    │   │  ┌──────────────────┐       │  ┌────────────┐  │   │
│                    ├──▶│  │   Bulk Invoice   │◀─────▶│  │ /acq/      │  │   │
│                    │   │  │   Processor      │       │  │ po-lines   │  │   │
│   ┌───────────┐    │   │  └──────────────────┘       │  │ invoices   │  │   │
│   │   ERP     │────┤   │                             │  │ items      │  │   │
│   │  Reports  │    │   │  ┌──────────────────┐       │  └────────────┘  │   │
│   └───────────┘    │   │  │   ERP            │◀─────▶│                  │   │
│                    └───│  │   Integration    │       │  ┌────────────┐  │   │
│   ┌───────────┐        │  └──────────────────┘       │  │ /bibs/     │  │   │
│   │  Mapping  │────────┘                             │  │ items      │  │   │
│   │  Files    │                                      │  │ (scan-in)  │  │   │
│   └───────────┘                                      │  └────────────┘  │   │
│                                                      │                  │   │
│                                                      └──────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### API Call Sequence (Rialto Workflow)

```
┌─────────────────────────────────────────────────────────────────────┐
│              API CALL SEQUENCE - RIALTO WORKFLOW                    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   STEP    API ENDPOINT                          OPERATION            │
│   ────    ────────────                          ─────────            │
│                                                                      │
│   1.      GET /acq/po-lines/{pol_id}            Get POL data         │
│                    │                                                 │
│                    ▼                                                 │
│           Extract: mms_id, holding_id, item_pid                     │
│                    │                                                 │
│   2.      GET /acq/invoices?q=pol_number~{pol}  Find linked invoice │
│                    │                                                 │
│                    ▼                                                 │
│           Found invoice_id (or None)                                │
│                    │                                                 │
│   3a.     POST /acq/po-lines/{pol}/items/{item}?op=receive          │
│                    │                            Receive item         │
│                    ▼                                                 │
│   3b.     POST /bibs/{mms}/holdings/{hold}/items/{item}             │
│                    │                            Scan-in to dept      │
│                    ▼                            (creates work order) │
│   4a.     POST /acq/invoices/{inv}?op=process_invoice               │
│                    │                            Approve invoice      │
│                    ▼                                                 │
│   4b.     POST /acq/invoices/{inv}?op=paid      Mark as paid        │
│                    │                                                 │
│                    ▼                                                 │
│   5.      GET /acq/po-lines/{pol_id}            Verify POL closed   │
│                    │                                                 │
│                    ▼                                                 │
│           Assert status == "CLOSED"                                  │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## API Operations Summary

### Acquisitions Domain

| Operation | Method | Endpoint | Description |
|-----------|--------|----------|-------------|
| Get POL | GET | `/acq/po-lines/{pol_id}` | Retrieve POL with items |
| Update POL | PUT | `/acq/po-lines/{pol_id}` | Update POL data |
| Get POL Items | GET | `/acq/po-lines/{pol_id}/items` | List items on POL |
| Receive Item | POST | `/acq/po-lines/{pol}/items/{item}?op=receive` | Mark item received |
| Get Invoice | GET | `/acq/invoices/{invoice_id}` | Retrieve invoice |
| Search Invoices | GET | `/acq/invoices?q=...` | Query invoices |
| Create Invoice | POST | `/acq/invoices` | Create new invoice |
| Add Invoice Line | POST | `/acq/invoices/{inv}/lines` | Add line to invoice |
| Approve Invoice | POST | `/acq/invoices/{inv}?op=process_invoice` | Approve/process |
| Pay Invoice | POST | `/acq/invoices/{inv}?op=paid` | Mark as paid |

### Bibliographic Domain

| Operation | Method | Endpoint | Description |
|-----------|--------|----------|-------------|
| Scan-In Item | POST | `/bibs/{mms}/holdings/{hold}/items/{item}?op=scan` | Scan item to dept |

### Common Query Patterns

```python
# Search invoices by POL
query = "pol_number~POL-5989"

# Search invoices by status
query = "invoice_status~WAITING_TO_BE_SENT"

# Combined search
query = "invoice_status~ACTIVE AND vendor~RIALTO"
```

---

## Getting Started

### Prerequisites

1. Python 3.12+
2. Poetry package manager
3. Alma API keys (SANDBOX and/or PRODUCTION)

### Installation

```bash
# Clone the repository
git clone https://github.com/hagaybar/Alma-Acquisitions-Automation.git
cd Alma-Acquisitions-Automation

# Install dependencies
poetry install

# Set environment variables
export ALMA_SB_API_KEY='your_sandbox_key'
export ALMA_PROD_API_KEY='your_production_key'

# Verify installation
poetry run python scripts/smoke_project.py
```

### Running the Workflows

```bash
# Rialto Pipeline - Mock mode (no API calls)
poetry run python -m workflows.rialto.pipeline --input-folder ./input --mock

# Rialto Pipeline - Sandbox dry-run
poetry run python -m workflows.rialto.pipeline --input-folder ./input

# Rialto Pipeline - Sandbox live
poetry run python -m workflows.rialto.pipeline --input-folder ./input --live

# Rialto Workflow - Process TSV directly
poetry run python -m workflows.rialto.workflow --tsv pols.tsv

# Bulk Invoice Processor
poetry run python -m workflows.invoices.bulk_processor config/invoice_processor.json

# ERP Integration - Dry run
poetry run python -m workflows.invoices.erp_integration erp.csv mapping.csv --dry-run
```

---

## Testing Guide

### Test Levels

| Level | API Calls | Environment | Purpose |
|-------|-----------|-------------|---------|
| **Unit Tests** | No | Any | Verify imports, code structure |
| **Mock Tests** | No | Any | Test PDF extraction, file handling |
| **SANDBOX Tests** | Yes | SANDBOX | Full workflow validation |
| **Production** | Yes | PRODUCTION | Final verification |

### Running Tests

```bash
# Level 1: Unit tests (no API)
poetry run pytest tests/

# Level 1: Smoke test (no API)
poetry run python scripts/smoke_project.py

# Level 2: Mock mode pipeline
poetry run python -m workflows.rialto.pipeline --input-folder ./input --mock

# Level 3: SANDBOX with known test POL
poetry run python -m workflows.rialto.workflow \
    --tsv test_data/test_pols.tsv \
    --environment SANDBOX \
    --dry-run

# Level 3: SANDBOX live test
poetry run python -m workflows.rialto.workflow \
    --tsv test_data/test_pols.tsv \
    --environment SANDBOX \
    --live
```

### Location Considerations

The batch scripts assume a Windows environment at `D:\Scripts\Prod\`:

- **Development/Linux**: Run from WSL or Linux machine
- **Production/Windows**: Run from Windows with proper folder structure
- **API Keys**: Must be set in environment regardless of platform

---

## Troubleshooting

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| Error 402459 | Invoice not approved | Call `approve_invoice()` before `mark_invoice_paid()` |
| Error 401875 | Department not found | Verify department code in Alma configuration |
| Error 401871 | POL not found | Check POL ID exists and isn't closed |
| No POLs extracted | PDF format changed | Check PDF text extraction, adjust regex |
| Invoice already paid | Duplicate processing | Check payment status before paying |

### Debug Tips

1. **Use dry-run mode** first to see what would happen
2. **Check logs** in `logs/` directory for detailed API responses
3. **Test one POL** manually before batch processing
4. **Verify in Alma UI** that configurations exist (departments, work orders)

---

## Contributing

1. Fork the repository
2. Create a feature branch
3. Test in SANDBOX
4. Submit a pull request

See the main repository README for more details.
