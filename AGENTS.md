# Repository Guidelines

## Project Structure & Module Organization
Core automation code lives in `workflows/`: `workflows/rialto/` handles PDF-to-POL processing, and `workflows/invoices/` handles bulk invoice and ERP integration flows. Shared helpers belong in `common/`. Configuration templates live in `config/` and should be copied to non-example JSON files for local runs. Windows entrypoints are in `batch/`, longer-form documentation is in `docs/`, utility scripts are in `scripts/`, and tests are in `tests/`. Runtime folders such as `input/`, `output/`, `processed/`, `failed/`, and `logs/` are operational artifacts, not source.

## Build, Test, and Development Commands
Use Poetry with Python 3.12.

- `poetry install` installs dependencies.
- `poetry run python scripts/smoke_project.py` checks that the project imports cleanly.
- `poetry run pytest tests/` runs the automated test suite.
- `poetry run python -m workflows.rialto.pipeline --input-folder ./input` runs the Rialto pipeline in dry-run mode.
- `poetry run python -m workflows.rialto.pipeline --input-folder ./input --live` executes live Alma operations.
- `poetry run python -m workflows.invoices.bulk_processor config/invoice_processor.json` runs the invoice bulk processor.

## Coding Style & Naming Conventions
Follow existing Python style: 4-space indentation, type hints where useful, standard-library imports first, and module-level docstrings for executable scripts. Use `snake_case` for functions, variables, modules, and JSON keys; use `PascalCase` for classes such as `RialtoPipeline` and `ERPToAlmaIntegration`. Keep CLI modules under `workflows/...` focused on a single workflow. Prefer descriptive logging over inline comments.

## Testing Guidelines
The current test suite uses `pytest` and `unittest`-style assertions in `tests/test_imports.py`. Add new tests under `tests/` as `test_*.py`, and keep them safe for local and CI execution without live Alma access by default. For workflow changes, pair automated tests with a dry-run command example and validate live behavior in `SANDBOX` before any `PRODUCTION` run.

## Commit & Pull Request Guidelines
Recent history uses short, imperative commit subjects such as `create developer's guid for this repo` and `Initial commit: Extract...`. Keep commits focused, use a concise imperative summary, and add context in the body when behavior or configuration changes. Pull requests should state the workflow affected, note any config or environment-variable changes, include test commands run, and attach sample logs or output snippets when changing pipeline behavior.

## Security & Configuration Tips
Never commit real Alma API keys or environment-specific JSON configs. Use `ALMA_SB_API_KEY` for testing and `ALMA_PROD_API_KEY` only for approved production runs. Prefer example configs in `config/*.example.json`, and keep production execution behind explicit `--live` usage.
