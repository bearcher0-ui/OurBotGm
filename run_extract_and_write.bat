@echo off
setlocal ENABLEDELAYEDEXPANSION

REM Change to the directory of this script (should be Dragon-main)
cd /d "%~dp0"

REM Prefer the Python launcher if available, else fallback to python
where py >nul 2>&1
if %ERRORLEVEL%==0 (
    set _PY=py -3
) else (
    set _PY=python
)

echo Running extract_wallets_csv_filtered.py ...
%_PY% extract_wallets_csv_filtered.py
if errorlevel 1 (
    echo extract_wallets_csv_filtered.py failed. Aborting.
    exit /b 1
)

echo Running write_telegram.py ...
%_PY% write_telegram.py
set _ec=%ERRORLEVEL%

endlocal & exit /b %_ec%

