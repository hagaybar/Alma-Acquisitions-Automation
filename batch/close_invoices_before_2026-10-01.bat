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
REM  MODE:
REM    ANALYZE  read-only check of the set: possible issues, what would happen
REM    DRY      the closer's dry run: reads Alma, reports, writes nothing
REM    LIVE     processes and pays (asks you to type YES)
REM  The API key is read from ALMA_SB_API_KEY / ALMA_PROD_API_KEY (environment).
REM
REM  BEFORE YOU RUN (operator):
REM    1. The selection must exclude invoice lines with NO FUND (print and e-book).
REM       An invoice paid without a fund cannot be given one afterwards.
REM    2. Run MODE=ANALYZE first and read summary_for_staff.txt.
REM    3. First LIVE run: set LIMIT to a small number (e.g. 5) and check the logs.
REM  See docs\INVOICE_CLOSER.md, "Operator instructions".
REM ==========================================================================

REM ---------------------------- SETTINGS -----------------------------------
REM  SANDBOX or PRODUCTION
set "ENV=SANDBOX"
REM  ANALYZE, DRY or LIVE
set "MODE=ANALYZE"
REM  Input: an Analytics export (INPUT_FILE, .xlsx/.csv/.tsv, relative to this clone)
REM  OR an Alma Order lines (PO_LINE) set (SET_ID). If INPUT_FILE is set, it is used.
set "INPUT_FILE="
set "SET_ID=43266268550004146"
REM  Only the first N invoices (empty = all). Use a small number for a first LIVE run.
set "LIMIT="
REM  Hard cutoff, enforced per invoice in code: invoice date must be earlier
set "DATE_BEFORE=2026-10-01"
REM  Scope: vendor code and owner library code (AC1 = Sourasky Central Library)
set "VENDOR=RIALTO"
set "OWNER=AC1"
REM  Payment record written by op=paid. Not a real payment: it only moves the
REM  invoice to Closed. Empty PAYMENT_DATE = the day the job runs.
set "VOUCHER_TEMPLATE=AUTO-PAY-{invoice_number}"
set "PAYMENT_DATE="
REM  Reports and logs, one sub-folder per run, relative to this clone
set "OUT_DIR=tests\invoice_closer\output"
REM ---------------------------------------------------------------------------

cd /d "%~dp0.."
if not exist "%OUT_DIR%" mkdir "%OUT_DIR%"
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "TS=%%i"
set "CONSOLE=%OUT_DIR%\console_%TS%_%ENV%_%MODE%.txt"

echo Working directory: %CD%
echo Environment: %ENV%   Mode: %MODE%   Set: %SET_ID%   File: %INPUT_FILE%   Limit: %LIMIT%
echo Invoice date before: %DATE_BEFORE%
echo Output: %OUT_DIR%
echo Console copy: %CONSOLE%
echo.

set "SOURCE=--set-id %SET_ID%"
if not "%INPUT_FILE%"=="" set "SOURCE=--file "%INPUT_FILE%""
set "FILTERS=%SOURCE% --env %ENV% --include-physical --invoice-date-before %DATE_BEFORE% --out "%OUT_DIR%""
if not "%VENDOR%"=="" set "FILTERS=%FILTERS% --vendor %VENDOR%"
if not "%OWNER%"=="" set "FILTERS=%FILTERS% --owner %OWNER%"

if /i "%MODE%"=="ANALYZE" goto :analyze
if /i "%MODE%"=="DRY" goto :dry
if /i "%MODE%"=="LIVE" goto :live
echo ERROR: MODE must be ANALYZE, DRY or LIVE.
goto :end

:analyze
echo PRE-ANALYSIS - read only, nothing will be written. This can take a few hours for a large set.
call :run scripts\analyze_set.py %FILTERS%
goto :end

:dry
set "ARGS=%FILTERS% --voucher-number "%VOUCHER_TEMPLATE%""
if not "%PAYMENT_DATE%"=="" set "ARGS=%ARGS% --payment-date %PAYMENT_DATE%"
if not "%LIMIT%"=="" set "ARGS=%ARGS% --limit %LIMIT%"
echo DRY RUN - nothing will be written.
call :run scripts\close_invoices.py %ARGS%
goto :end

:live
set "ARGS=%FILTERS% --voucher-number "%VOUCHER_TEMPLATE%" --live"
if not "%PAYMENT_DATE%"=="" set "ARGS=%ARGS% --payment-date %PAYMENT_DATE%"
if not "%LIMIT%"=="" set "ARGS=%ARGS% --limit %LIMIT%"
if /i "%ENV%"=="PRODUCTION" set "ARGS=%ARGS% --production-approved"
echo ******************************************************************
echo  LIVE MODE: this will process and pay invoices in %ENV%.
if "%LIMIT%"=="" (echo  ALL invoices in the set.) else (echo  Only the first %LIMIT% invoices.)
echo ******************************************************************
set /p "CONFIRM=Type YES to continue: "
if not "%CONFIRM%"=="YES" (
    echo Aborted.
    goto :end
)
call :run scripts\close_invoices.py %ARGS%
goto :end

:run
REM Everything the program prints (including errors) goes to the console copy too.
echo Started %DATE% %TIME% > "%CONSOLE%"
echo Command: poetry run python %* >> "%CONSOLE%"
poetry run python %* >> "%CONSOLE%" 2>&1
set "RC=%ERRORLEVEL%"
echo Finished %DATE% %TIME%, exit code %RC% >> "%CONSOLE%"
type "%CONSOLE%"
exit /b %RC%

:end
echo.
echo Exit code: %ERRORLEVEL%   (0 = clean, 1 = a write failed or is unknown, 2 = did not start)
echo The plain-language summary is summary_for_staff.txt in the newest run folder.
pause
endlocal
