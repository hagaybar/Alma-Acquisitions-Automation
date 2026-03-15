@echo off
TITLE Rialto Pipeline - MOCK TEST MODE

echo ========================================
echo RIALTO PIPELINE - MOCK TEST MODE
echo ========================================
echo.
echo This runs the pipeline WITHOUT any API calls.
echo Tests: PDF extraction, file handling, logging
echo.

REM Change to the repository directory
cd /d D:\Scripts\Prod\Alma-Acquisitions-Automation

REM Verify we're in the right place
echo Working directory: %CD%
echo.

poetry run python -m workflows.rialto.pipeline --config D:\Scripts\Prod\Rialto\config.json --mock

pause
