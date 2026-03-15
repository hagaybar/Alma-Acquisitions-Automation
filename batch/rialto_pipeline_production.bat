@echo off
TITLE Rialto Pipeline - PRODUCTION DAEMON MODE

echo ========================================
echo RIALTO PIPELINE - PRODUCTION DAEMON MODE
echo ========================================
echo.
echo WARNING: Running in PRODUCTION mode!
echo.
echo Monitoring input folder for new PDFs...
echo Checking every hour (3600 seconds)
echo Press Ctrl+C to stop monitoring
echo.

REM Change to the repository directory
cd /d D:\Scripts\Prod\Alma-Acquisitions-Automation

REM Verify we're in the right place
echo Working directory: %CD%
echo.

poetry run python -m workflows.rialto.pipeline --config D:\Scripts\Prod\Rialto\config.json --environment PRODUCTION --daemon --live

pause
