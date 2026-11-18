@echo off
setlocal
TITLE Invoice closer - invoices dated before 2026-10-01

REM ==========================================================================
REM  Invoice closer: process and pay invoices dated before 1 Oct 2026, and close
REM  their electronic order lines. Print orders are paid only (never received).
REM
REM  Runs from the clone this file sits in (DevSandbox or Prod), so the same
REM  script serves both. Edit only the SETTINGS block.
REM
REM  Default is a DRY RUN: it reads Alma and reports what it would do.
REM  The API key is read from ALMA_SB_API_KEY / ALMA_PROD_API_KEY (environment).
REM ==========================================================================

REM ---------------------------- SETTINGS -----------------------------------
REM  SANDBOX or PRODUCTION
set "ENV=SANDBOX"
REM  DRY or LIVE
set "MODE=DRY"
REM  Excel export of the Alma set (one row per invoice; column invoice_number)
set "INPUT_FILE=D:\Scripts\Data\invoice_closer\input\TODO.xlsx"
REM  Hard cutoff, enforced per invoice in code: invoice date must be earlier
set "DATE_BEFORE=2026-10-01"
REM  Scope (leave empty for any). TODO: confirm
set "VENDOR=TODO"
set "OWNER=TODO"
REM  Payment record written by op=paid. TODO: confirm format and date
set "VOUCHER_TEMPLATE=TODO-{invoice_number}"
set "PAYMENT_DATE="
REM  Where reports and logs go (one sub-folder per run). TODO: agree in step 1e
set "OUT_DIR=D:\Scripts\Data\invoice_closer\output"
REM ---------------------------------------------------------------------------

cd /d "%~dp0.."
echo Working directory: %CD%
echo Environment: %ENV%   Mode: %MODE%
echo Input: %INPUT_FILE%
echo Invoice date before: %DATE_BEFORE%
echo Output: %OUT_DIR%
echo.

if not exist "%INPUT_FILE%" (
    echo ERROR: input file not found: %INPUT_FILE%
    goto :end
)

set "ARGS=--file "%INPUT_FILE%" --env %ENV% --include-physical --invoice-date-before %DATE_BEFORE% --out "%OUT_DIR%""
if not "%VENDOR%"=="" set "ARGS=%ARGS% --vendor %VENDOR%"
if not "%OWNER%"=="" set "ARGS=%ARGS% --owner %OWNER%"
if not "%VOUCHER_TEMPLATE%"=="" set "ARGS=%ARGS% --voucher-number "%VOUCHER_TEMPLATE%""
if not "%PAYMENT_DATE%"=="" set "ARGS=%ARGS% --payment-date %PAYMENT_DATE%"

if /i "%MODE%"=="LIVE" (
    echo ******************************************************************
    echo  LIVE MODE: this will process and pay invoices in %ENV%.
    echo ******************************************************************
    set /p "CONFIRM=Type YES to continue: "
    call :live
    goto :end
)

echo DRY RUN - nothing will be written.
echo.
poetry run python scripts\close_invoices.py %ARGS%
goto :end

:live
if not "%CONFIRM%"=="YES" (
    echo Aborted.
    goto :eof
)
if /i "%ENV%"=="PRODUCTION" (
    poetry run python scripts\close_invoices.py %ARGS% --live --production-approved
) else (
    poetry run python scripts\close_invoices.py %ARGS% --live
)
goto :eof

:end
echo.
echo Exit code: %ERRORLEVEL%   (0 = clean, 1 = a write failed or is unknown, 2 = did not start)
pause
endlocal
