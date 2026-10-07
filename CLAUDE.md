# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Project Overview

Alma Acquisitions Automation - Tools and workflows for automating Ex Libris Alma acquisitions operations, including Rialto POL processing.

## Development

- Python project using Ex Libris Alma APIs
- Configuration files with API keys are gitignored (see `.gitignore`)
- Test data files (PDFs, TSVs, etc.) are not committed

## Key Directories

- `workflows/` - Workflow implementations (rialto, invoices)
- `src/` - Core library code (Alma API clients, utilities)
- `docs/` - Documentation and guides
- `config/` - Configuration templates (actual configs are gitignored)
