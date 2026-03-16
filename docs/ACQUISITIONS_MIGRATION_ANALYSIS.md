# Acquisitions Projects Migration Analysis

## Executive Summary

This document analyzes three related projects within `AlmaAPITK/src/projects/` for extraction to standalone repositories:

| Project | Status | Complexity | Recommendation |
|---------|--------|------------|----------------|
| **RialtoProduction** | Production-ready | High | Extract as standalone repo |
| **Acquisitions** | Production-ready | Medium | Merge into Rialto OR extract separately |
| **subscriptions_pilot** | Early stage | Low | Keep in monorepo until implemented |

**Key Finding**: All projects already use modern `almaapitk` imports (no legacy `src.*` imports), making extraction straightforward from an import perspective.

---

## 1. Project Inventories

### 1.1 RialtoProduction (`src/projects/RialtoProduction/`)

**Purpose**: Automated POL workflow processing - PDF monitoring, item receiving, invoice payment, closure verification.

**Files Inventory**:

| Category | Files | Purpose |
|----------|-------|---------|
| **Python Scripts** | `rialto_pipeline.py` (700 LOC) | Main PDF monitoring daemon |
| | `rialto_complete_workflow.py` (650 LOC) | POL workflow processor (TSV input) |
| | `utility/extract_pol_list.py` (300 LOC) | PDF POL extraction |
| **Config Templates** | `config/rialto_pipeline_config.example.json` | Pipeline settings |
| | `config/rialto_workflow_config.example.json` | Workflow settings |
| **Batch Files** | `batch/rialto_pipeline_sandbox.bat` | SANDBOX single run |
| | `batch/rialto_pipeline_sandbox_single.bat` | SANDBOX single run variant |
| | `batch/rialto_pipeline_production.bat` | PRODUCTION daemon mode |
| | `batch/rialto_pipeline_mock_test.bat` | Mock testing |
| | `batch/remote_config_example.json` | Remote deployment config |
| **Documentation** | `README.md` | Quick start guide |
| | `RIALTO_WORKFLOW_README.md` | Complete user guide |
| | `docs/POL-5989_TEST_SUMMARY.md` | Validation report |
| | `docs/rialto_project_flow_findings.md` | Technical findings |
| | `docs/rialto_project_tests.txt` | Test tracking |
| **Example Data** | `input/example_pols.tsv` | Example input format |
| | `input/example_pols_sb_2.tsv` | Additional examples |
| **Directories** | `processed/`, `failed/`, `logs/`, `output/` | Runtime directories |

**Total**: ~1,650 LOC Python, 4 batch files, 5 documentation files

**Dependencies**:
- `almaapitk` (AlmaAPIClient, Acquisitions, BibliographicRecords, AlmaAPIError)
- `PyPDF2` (PDF text extraction)
- `pandas` (optional, for data processing)

**Import Analysis** (all modern):
```python
from almaapitk import AlmaAPIClient, AlmaAPIError, Acquisitions, BibliographicRecords
```

---

### 1.2 Acquisitions (`src/projects/Acquisitions/`)

**Purpose**: Invoice processing and ERP-to-Alma integration.

**Files Inventory**:

| Category | Files | Purpose |
|----------|-------|---------|
| **Python Scripts** | `scripts/bulk_invoice_processor.py` (450 LOC) | Automated daily invoice processing |
| | `scripts/acquisitions_test_script.py` (450 LOC) | Enhanced version with better error handling |
| | `scripts/erp_integration/erp_to_alma_invoice.py` (600 LOC) | ERP system integration |
| **Config Files** | `configs/invoice_processor_config.json` | Production config |
| | `configs/sample_invoice_processor_config.json` | Template |
| **Input Data** | `input/invoices/*.xlsx` | Invoice Excel files |
| | `input/erp_data/*.xlsx` | ERP data files |
| | `input/erp_data/*.tsv` | Mapping data |
| **Archive** | `archive/README.md` | Superseded docs |
| | `archive/RIALTO_FLOW_FINDINGS.md` | Old technical docs |
| | `archive/test_for_rialto_project.txt` | Old tests |
| **Documentation** | `README.md` | Project overview |
| | `rialto_project_flow_findings.md` | Technical findings |
| | `rialto_project_tests.txt` | Test tracking |

**Total**: ~1,500 LOC Python, 2 config files

**Dependencies**:
- `almaapitk` (AlmaAPIClient, Acquisitions, AlmaAPIError)
- `pandas` (Excel processing)
- `openpyxl` (Excel reading)

**Import Analysis** (all modern):
```python
from almaapitk import AlmaAPIClient, Acquisitions, AlmaAPIError
```

---

### 1.3 subscriptions_pilot (`src/projects/subscriptions_pilot/`)

**Purpose**: Pilot for external subscriptions data integration.

**Files Inventory**:

| Category | Files | Purpose |
|----------|-------|---------|
| **Data Files** | `data/external_prices_template.csv` | Price template |
| | `data/multi_field_test_data.csv` | Test data |
| | `data/pilot_test_data.csv` | Primary test data |
| | `data/sample_external_data_report.tsv` | Sample report |
| **Directories** | `logs/` | Runtime logs |

**Total**: 0 LOC Python (data preparation phase only)

**Status**: No implementation yet - only data structure definitions

---

## 2. Relationship Analysis

### 2.1 Shared Subject Matter

All three projects deal with **Alma Acquisitions workflows**:

```
┌─────────────────────────────────────────────────────────────────┐
│                     Alma Acquisitions Domain                     │
├─────────────────┬─────────────────────┬────────────────────────┤
│   Acquisitions  │  RialtoProduction   │  subscriptions_pilot   │
├─────────────────┼─────────────────────┼────────────────────────┤
│ Invoice marking │ Item receiving      │ Subscription prices    │
│ ERP integration │ Invoice payment     │ (not implemented)      │
│ POL updates     │ POL closure         │                        │
│                 │ PDF monitoring      │                        │
└─────────────────┴─────────────────────┴────────────────────────┘
```

### 2.2 Code Overlap

| Capability | Acquisitions | RialtoProduction | Overlap |
|------------|--------------|------------------|---------|
| Invoice status checking | ✅ | ✅ | Similar patterns |
| Invoice payment marking | ✅ | ✅ | Nearly identical |
| POL retrieval | ✅ | ✅ | Similar patterns |
| Error handling | ✅ (enhanced) | ✅ | Could share |
| Dry-run mode | ✅ | ✅ | Same pattern |
| CSV/TSV output | ✅ | ✅ | Same pattern |
| PDF extraction | ❌ | ✅ | Unique to Rialto |
| ERP integration | ✅ | ❌ | Unique to Acquisitions |
| Daemon mode | ❌ | ✅ | Unique to Rialto |

### 2.3 Documentation Overlap

Files appearing in both projects:
- `rialto_project_flow_findings.md` (identical content)
- `rialto_project_tests.txt` (similar content)

This suggests these were originally one project that was split or duplicated.

---

## 3. Migration Options

### Option A: Single Unified Repository (RECOMMENDED)

**Name**: `Alma-Acquisitions-Automation`

**Rationale**:
- Shared domain knowledge (Acquisitions API patterns)
- Significant code overlap (invoice handling, POL processing)
- Shared documentation already exists
- Single deployment target (Masedet)
- Easier maintenance with unified error handling

**Proposed Structure**:
```
Alma-Acquisitions-Automation/
├── pyproject.toml
├── README.md
├── .gitignore
│
├── workflows/
│   ├── __init__.py
│   ├── rialto/                         # RialtoProduction scripts
│   │   ├── __init__.py
│   │   ├── pipeline.py                 # rialto_pipeline.py
│   │   ├── workflow.py                 # rialto_complete_workflow.py
│   │   └── pdf_extractor.py            # extract_pol_list.py
│   ├── invoices/                       # Acquisitions invoice scripts
│   │   ├── __init__.py
│   │   ├── bulk_processor.py           # bulk_invoice_processor.py
│   │   └── erp_integration.py          # erp_to_alma_invoice.py
│   └── subscriptions/                  # Future: subscriptions_pilot
│       └── __init__.py                 # Placeholder
│
├── common/                             # Shared utilities
│   ├── __init__.py
│   ├── invoice_utils.py                # Shared invoice handling
│   ├── error_handling.py               # Enhanced error parsing
│   └── reporting.py                    # CSV/TSV generation
│
├── config/
│   ├── rialto_pipeline.example.json
│   ├── rialto_workflow.example.json
│   ├── invoice_processor.example.json
│   └── erp_integration.example.json
│
├── batch/
│   ├── rialto_pipeline_sandbox.bat
│   ├── rialto_pipeline_production.bat
│   └── invoice_processor_production.bat
│
├── scripts/
│   └── smoke_project.py
│
├── tests/
│   ├── test_imports.py
│   ├── test_rialto_workflow.py
│   └── test_invoice_processor.py
│
├── docs/
│   ├── RIALTO_WORKFLOW.md
│   ├── INVOICE_PROCESSING.md
│   ├── ERP_INTEGRATION.md
│   ├── API_FINDINGS.md
│   └── TEST_REPORTS/
│       └── POL-5989_SUMMARY.md
│
├── input/                              # .gitkeep
├── output/                             # .gitkeep
├── processed/                          # .gitkeep
├── failed/                             # .gitkeep
└── logs/                               # .gitkeep
```

**Pros**:
- Single source of truth for Acquisitions automation
- Shared utilities reduce code duplication
- Unified testing and documentation
- Single deployment process
- Easier for user to maintain

**Cons**:
- Larger repository
- More complex pyproject.toml
- Both workflows must be tested together

**pyproject.toml**:
```toml
[tool.poetry]
name = "alma-acquisitions-automation"
version = "1.0.0"
description = "Automated Alma Acquisitions workflows: Rialto POL processing and invoice management"
authors = ["Hagay Bar-Or <hagaybar@tauex.tau.ac.il>"]
readme = "README.md"
package-mode = false

[tool.poetry.dependencies]
python = "^3.12"
almaapitk = { git = "https://github.com/hagaybar/AlmaAPITK.git", tag = "v0.2.2" }
pandas = "^2.0"
openpyxl = "^3.1"
PyPDF2 = "^3.0"

[tool.poetry.group.dev.dependencies]
pytest = "^8.0"
```

---

### Option B: Two Separate Repositories

**Repositories**:
1. `Alma-Rialto-Workflow` - RialtoProduction only
2. `Alma-Invoice-Processor` - Acquisitions only

**Rationale**:
- Independent deployment schedules
- Clear ownership boundaries
- Smaller, focused repositories

**Alma-Rialto-Workflow Structure**:
```
Alma-Rialto-Workflow/
├── pyproject.toml
├── README.md
├── rialto_pipeline.py
├── rialto_complete_workflow.py
├── utility/
│   └── extract_pol_list.py
├── config/
│   ├── pipeline.example.json
│   └── workflow.example.json
├── batch/
│   └── *.bat
├── docs/
├── scripts/smoke_project.py
└── tests/
```

**Alma-Invoice-Processor Structure**:
```
Alma-Invoice-Processor/
├── pyproject.toml
├── README.md
├── bulk_invoice_processor.py
├── erp_integration/
│   └── erp_to_alma_invoice.py
├── config/
│   └── *.example.json
├── scripts/smoke_project.py
└── tests/
```

**Pros**:
- Clear separation of concerns
- Independent versioning
- Smaller codebases

**Cons**:
- Duplicated error handling code
- Duplicated invoice patterns
- Two repos to maintain
- Documentation split

---

### Option C: Defer subscriptions_pilot

**Recommendation**: Keep `subscriptions_pilot` in AlmaAPITK until:
1. Python implementation exists
2. Clear requirements defined
3. Testing completed

**Rationale**:
- No code to extract (data files only)
- No import dependencies to manage
- Can be added to unified repo later

---

## 4. Detailed Extraction Steps

### 4.1 Pre-Extraction Checklist

- [x] Verify imports use `almaapitk` (not `src.*`) - **CONFIRMED**
- [ ] Create empty GitHub repository
- [ ] Review all config files for real paths/credentials
- [ ] Identify all batch files needing path updates
- [ ] Document current production paths

### 4.2 Files to Copy (Option A)

**From RialtoProduction**:
```
rialto_pipeline.py → workflows/rialto/pipeline.py
rialto_complete_workflow.py → workflows/rialto/workflow.py
utility/extract_pol_list.py → workflows/rialto/pdf_extractor.py
config/*.example.json → config/
batch/*.bat → batch/
docs/* → docs/
input/*.tsv → input/ (examples only)
README.md, RIALTO_WORKFLOW_README.md → docs/
```

**From Acquisitions**:
```
scripts/bulk_invoice_processor.py → workflows/invoices/bulk_processor.py
scripts/acquisitions_test_script.py → (merge into bulk_processor or discard)
scripts/erp_integration/erp_to_alma_invoice.py → workflows/invoices/erp_integration.py
configs/*.json → config/ (examples only)
README.md → docs/
```

### 4.3 Files NOT to Copy

**Never commit**:
- `input/invoices/*.xlsx` (real invoice data)
- `input/erp_data/*.xlsx` (real ERP data)
- `configs/invoice_processor_config.json` (production config)
- Any file with real Windows paths

**Archive/Skip**:
- `archive/*` (superseded documentation)
- `subscriptions_pilot/*` (not ready)

### 4.4 Import Modifications Required

**Current (already correct)**:
```python
from almaapitk import AlmaAPIClient, Acquisitions, BibliographicRecords
```

**No changes needed** - all scripts already use modern imports.

### 4.5 Path Modifications Required

**rialto_pipeline.py**:
- Relative imports from `.utility.extract_pol_list` → `from workflows.rialto.pdf_extractor import ...`
- Relative imports from `.rialto_complete_workflow` → `from workflows.rialto.workflow import ...`

**Batch files**:
```batch
# OLD
cd /d D:\Scripts\Prod\AlmaAPITK
poetry run python src\projects\RialtoProduction\rialto_pipeline.py ...

# NEW
cd /d D:\Scripts\DevSandbox\Alma-Acquisitions-Automation
poetry run python -m workflows.rialto.pipeline ...
```

---

## 5. Testing Requirements

### 5.1 Smoke Tests

**Import verification** (`scripts/smoke_project.py`):
```python
#!/usr/bin/env python3
"""Smoke test - verifies all imports work correctly."""
import sys

def main():
    print("Testing almaapitk imports...")
    from almaapitk import AlmaAPIClient, Acquisitions, BibliographicRecords
    print("  Core imports: OK")

    print("\nTesting workflow imports...")
    from workflows.rialto.pipeline import RialtoPipeline
    from workflows.rialto.workflow import RialtoWorkflowProcessor
    from workflows.rialto.pdf_extractor import POLExtractor
    from workflows.invoices.bulk_processor import AutomatedInvoiceProcessor
    from workflows.invoices.erp_integration import ERPToAlmaIntegration
    print("  Workflow imports: OK")

    print("\nAll imports successful!")
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

### 5.2 Unit Tests

**test_imports.py**:
```python
"""Test that all imports use almaapitk public API only."""
import unittest
import re
from pathlib import Path

class TestImports(unittest.TestCase):
    def test_no_legacy_imports(self):
        """Ensure no forbidden legacy imports exist."""
        forbidden_patterns = [
            r"from\s+src\.",
            r"import\s+src\.",
            r"from\s+client\.",
            r"from\s+domains\.",
        ]

        project_root = Path(__file__).parent.parent
        python_files = list(project_root.glob("**/*.py"))

        for py_file in python_files:
            content = py_file.read_text()
            for pattern in forbidden_patterns:
                matches = re.findall(pattern, content)
                self.assertEqual(
                    len(matches), 0,
                    f"Found forbidden import {pattern!r} in {py_file}"
                )
```

### 5.3 Validation Sequence

1. **Local (WSL)**:
   ```bash
   cd Alma-Acquisitions-Automation
   poetry install
   poetry run python scripts/smoke_project.py
   poetry run python -m pytest tests/ -v
   ```

2. **DevSandbox (Masedet)**:
   ```powershell
   cd D:\Scripts\DevSandbox\Alma-Acquisitions-Automation
   poetry install
   poetry run python scripts\smoke_project.py

   # Rialto dry-run
   poetry run python -m workflows.rialto.workflow --tsv input\example_pols.tsv

   # Invoice processor dry-run
   poetry run python -m workflows.invoices.bulk_processor --config config\invoice_processor.example.json
   ```

3. **Production**: Follow DEV_MIGRATION.md promotion checklist

---

## 6. Recommendations

### Primary Recommendation

**Option A: Single Unified Repository**

**Justification**:
1. **Domain Cohesion**: Both projects operate on the same Alma Acquisitions domain
2. **Code Reuse**: Invoice handling patterns are nearly identical
3. **Maintenance**: Single repo is easier for user to maintain
4. **Documentation**: Technical findings are already duplicated between projects
5. **Deployment**: Same target machine (Masedet)

### subscriptions_pilot

**Defer extraction** until:
- Python implementation exists
- Requirements are finalized
- Can be added as `workflows/subscriptions/` module

### Immediate Actions

1. **Create GitHub repo**: `Alma-Acquisitions-Automation`
2. **Extract RialtoProduction first** (most complete, best tested)
3. **Integrate Acquisitions scripts** into same repo
4. **Update batch files** with new paths
5. **Test in DevSandbox** before production

### Future Considerations

- **Shared utilities**: Extract common invoice handling into `common/` module
- **Enhanced error handling**: Port the improved error parsing from `acquisitions_test_script.py` to all scripts
- **Unified CLI**: Consider single entry point with subcommands (`alma-acq rialto`, `alma-acq invoice`)

---

## 7. Timeline Estimate

| Phase | Duration | Tasks |
|-------|----------|-------|
| **Phase 1** | 1-2 hours | Create repo, copy RialtoProduction files |
| **Phase 2** | 1 hour | Integrate Acquisitions scripts |
| **Phase 3** | 1 hour | Update imports and paths |
| **Phase 4** | 1 hour | Create tests and smoke scripts |
| **Phase 5** | 1-2 hours | DevSandbox validation |
| **Phase 6** | 30 min | Documentation updates |
| **Total** | 5-8 hours | Full extraction and validation |

---

## Appendix A: Complete File List

### RialtoProduction (27 items)

```
RialtoProduction/
├── rialto_pipeline.py
├── rialto_complete_workflow.py
├── README.md
├── RIALTO_WORKFLOW_README.md
├── .gitignore
├── batch/
│   ├── rialto_pipeline_sandbox.bat
│   ├── rialto_pipeline_sandbox_single.bat
│   ├── rialto_pipeline_production.bat
│   ├── rialto_pipeline_mock_test.bat
│   └── remote_config_example.json
├── config/
│   ├── rialto_pipeline_config.example.json
│   └── rialto_workflow_config.example.json
├── docs/
│   ├── POL-5989_TEST_SUMMARY.md
│   ├── rialto_project_flow_findings.md
│   └── rialto_project_tests.txt
├── input/
│   ├── example_pols.tsv
│   └── example_pols_sb_2.tsv
├── utility/
│   └── extract_pol_list.py
├── processed/.gitkeep
├── failed/.gitkeep
├── logs/.gitkeep
└── output/
```

### Acquisitions (15 items)

```
Acquisitions/
├── README.md
├── rialto_project_flow_findings.md
├── rialto_project_tests.txt
├── scripts/
│   ├── bulk_invoice_processor.py
│   ├── acquisitions_test_script.py
│   └── erp_integration/
│       └── erp_to_alma_invoice.py
├── configs/
│   ├── invoice_processor_config.json (DO NOT COPY)
│   └── sample_invoice_processor_config.json
├── input/
│   ├── invoices/ (DO NOT COPY)
│   └── erp_data/ (DO NOT COPY)
├── archive/
│   ├── README.md
│   ├── RIALTO_FLOW_FINDINGS.md
│   └── test_for_rialto_project.txt
└── output/
```

### subscriptions_pilot (6 items)

```
subscriptions_pilot/
├── data/
│   ├── external_prices_template.csv
│   ├── multi_field_test_data.csv
│   ├── pilot_test_data.csv
│   └── sample_external_data_report.tsv
└── logs/.gitkeep
```

---

*Document generated: 2026-03-15*
*Based on: DEV_MIGRATION.md v1.2*
