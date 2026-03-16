# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Project Overview

Alma Acquisitions Automation - Tools and workflows for automating Ex Libris Alma acquisitions operations, including Rialto POL processing.

## Babysitter Integration

This project uses the babysitter orchestration system. The `.a5c/` folder contains:

- **runs/** - Run history and state (SHOULD be committed)
- **process/** - Custom process definitions (SHOULD be committed)
- **node_modules/** - SDK dependencies (ignored via .gitignore)
- **cache/** - Compression cache (ignored via .gitignore)
- **logs/** - Hook logs (ignored via .gitignore)

**Important**: When babysitter runs are executed, remember to commit and push meaningful content from `.a5c/` (runs, processes) to preserve orchestration history.

## Development

- Python project using Ex Libris Alma APIs
- Configuration files with API keys are gitignored (see `.gitignore`)
- Test data files (PDFs, TSVs, etc.) are not committed

## Key Directories

- `workflows/` - Workflow implementations (rialto, invoices)
- `src/` - Core library code (Alma API clients, utilities)
- `docs/` - Documentation and guides
- `config/` - Configuration templates (actual configs are gitignored)
