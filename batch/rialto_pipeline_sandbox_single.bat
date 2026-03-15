@echo off
TITLE Rialto Pipeline - SANDBOX SINGLE RUN

echo ========================================
echo RIALTO PIPELINE - SANDBOX SINGLE RUN
echo ========================================
echo.
echo Processing any pending PDFs and exiting...
echo.

REM Change to the repository directory
cd /d D:\Scripts\Prod\Alma-Acquisitions-Automation

REM Verify we're in the right place
echo Working directory: %CD%
echo.

poetry run python -m workflows.rialto.pipeline --config D:\Scripts\Prod\Rialto\config.json --environment SANDBOX --live

pause
