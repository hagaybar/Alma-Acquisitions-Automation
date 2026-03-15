# Alma Acquisitions Automation

Automated workflows for Alma ILS acquisitions operations, including Rialto vendor invoice processing and ERP integration.

## Overview

This repository provides production-ready automation scripts for:

- **Rialto POL Processing**: Complete workflow for processing Purchase Order Lines from Rialto vendor invoices, including PDF extraction, item receiving, invoice payment, and POL closure verification.
- **Invoice Processing**: Bulk invoice processing from Excel reports and ERP-to-Alma invoice integration.

## Features

### Rialto Workflow
- PDF monitoring pipeline for automated processing
- POL number extraction from vendor invoice PDFs
- Complete receive-pay-close workflow
- Scan-in operation to keep items in department (prevents Transit status)
- Daemon mode for continuous folder monitoring
- Comprehensive CSV reporting

### Invoice Workflows
- Bulk invoice processor from Excel reports
- ERP-to-Alma invoice integration
- Automatic POL price updates
- Invoice line creation and payment marking

## Installation

### Prerequisites
- Python 3.12+
- Poetry package manager

### Setup

```bash
# Clone the repository
git clone https://github.com/hagaybar/Alma-Acquisitions-Automation.git
cd Alma-Acquisitions-Automation

# Install dependencies
poetry install

# Activate virtual environment
poetry shell

# Run smoke test to verify installation
python scripts/smoke_project.py
```

### Environment Variables

Set the required API keys:

```bash
export ALMA_SB_API_KEY='your_sandbox_api_key'
export ALMA_PROD_API_KEY='your_production_api_key'
```

## Usage

### Rialto Pipeline

Process PDFs from a monitored folder:

```bash
# Dry run (no modifications)
poetry run python -m workflows.rialto.pipeline --input-folder ./input

# Live execution
poetry run python -m workflows.rialto.pipeline --input-folder ./input --live

# Daemon mode (continuous monitoring)
poetry run python -m workflows.rialto.pipeline --input-folder ./input --daemon --live
```

### Rialto Workflow (TSV Input)

Process POLs from a TSV file:

```bash
# Dry run
poetry run python -m workflows.rialto.workflow --tsv pols.tsv

# Live execution
poetry run python -m workflows.rialto.workflow --tsv pols.tsv --live

# With custom configuration
poetry run python -m workflows.rialto.workflow --tsv pols.tsv \
    --library AC1 \
    --department AcqDeptAC1 \
    --work-order-status CopyCat \
    --live
```

### Invoice Processor

Process invoices from Excel report:

```bash
# Using config file
poetry run python -m workflows.invoices.bulk_processor config/invoice_processor.json
```

### ERP Integration

Transfer invoice data from ERP to Alma:

```bash
# Dry run
poetry run python -m workflows.invoices.erp_integration erp_report.csv mapping.csv --dry-run

# Sandbox execution
poetry run python -m workflows.invoices.erp_integration erp_report.csv mapping.csv

# Production with payment processing
poetry run python -m workflows.invoices.erp_integration erp_report.csv mapping.csv \
    --environment PRODUCTION \
    --process-payments
```

## Configuration

### Rialto Pipeline

Copy and customize the example configuration:

```bash
cp config/rialto_pipeline_config.example.json config/rialto_pipeline_config.json
```

Key settings:
- `input_folder`: Where Power Automate drops incoming PDFs
- `processed_folder`: Successfully processed PDFs are moved here
- `failed_folder`: Failed PDFs are moved here for review
- `environment`: SANDBOX or PRODUCTION
- `daemon`: Enable continuous monitoring mode
- `interval`: Seconds between folder checks in daemon mode

### Invoice Processor

Copy and customize the example configuration:

```bash
cp config/invoice_processor.example.json config/invoice_processor.json
```

Key settings:
- `environment`: SANDBOX or PRODUCTION
- `excel_file_path`: Path to Excel file with invoice IDs
- `output_directory`: Directory for output files
- `max_errors_before_stop`: Stop after N errors (null = no limit)

## Testing

Run all tests:

```bash
# Smoke test (import verification)
poetry run python scripts/smoke_project.py

# Unit tests
poetry run python -m pytest tests/
```

## Project Structure

```
Alma-Acquisitions-Automation/
├── workflows/
│   ├── rialto/                      # Rialto POL processing
│   │   ├── pipeline.py              # PDF monitoring pipeline
│   │   ├── workflow.py              # POL workflow processor
│   │   ├── pdf_extractor.py         # PDF POL extraction utility
│   │   └── __init__.py
│   └── invoices/                    # Invoice processing
│       ├── bulk_processor.py        # Bulk invoice processor
│       ├── erp_integration.py       # ERP-to-Alma integration
│       └── __init__.py
├── config/                          # Configuration templates
│   ├── rialto_pipeline_config.example.json
│   ├── rialto_workflow_config.example.json
│   └── invoice_processor.example.json
├── batch/                           # Windows batch scripts
├── docs/                            # Documentation
│   ├── RIALTO_README.md
│   ├── RIALTO_WORKFLOW_README.md
│   └── ...
├── input/                           # Example input files
│   └── example_pols.tsv
├── scripts/                         # Utility scripts
│   └── smoke_project.py
├── tests/                           # Unit tests
├── common/                          # Shared utilities (placeholder)
├── pyproject.toml                   # Poetry configuration
└── README.md                        # This file
```

## Dependencies

This project depends on `almaapitk` (AlmaAPITK) for Alma API operations:
- `AlmaAPIClient`: HTTP client for Alma API
- `Acquisitions`: POL and invoice operations
- `BibliographicRecords`: Item scan-in operations

## Documentation

See the `docs/` directory for detailed documentation:
- `RIALTO_README.md`: Complete Rialto workflow guide
- `RIALTO_WORKFLOW_README.md`: TSV-based workflow reference
- `POL-5989_TEST_SUMMARY.md`: Test validation report
- `rialto_project_flow_findings.md`: Technical API documentation

## License

See LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests
5. Submit a pull request
