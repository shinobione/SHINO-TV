@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
echo.
echo SHINO // TV - SmallTV Ultra V9.0.44 / READ-ONLY LAN REPORT
echo -----------------------------------------------------------
echo Only GET /v.json /space.json /app.json are used by default.
echo NO firmware, POST, credentials, scanning or flash writes.
echo.
where py >nul 2>&1
if errorlevel 1 (
    echo Python launcher "py" was not found. Install Python for Windows first.
    pause
    exit /b 1
)
set /p "TV_IP=SmallTV private LAN IP (example: 192.168.1.70): "
set "EXTRA="
echo.
set /p "GET_FORM=Also inspect GET /update FORM structure? (O/N, default N): "
if /I "%GET_FORM%"=="O" set "EXTRA=--include-update-page"
if /I "%GET_FORM%"=="Y" set "EXTRA=--include-update-page"
if not exist "research-local" mkdir "research-local"
if exist "research-local\stock-report.json" (
    echo The report already exists. Rename/move it first; no overwrite.
    pause
    exit /b 1
)
echo.
py -3 tools\stock_readonly_report.py --host "%TV_IP%" %EXTRA% --out "research-local\stock-report.json"
if errorlevel 1 (
    echo Report not created. No firmware action was attempted.
    pause
    exit /b 1
)
echo.
echo Report: research-local\stock-report.json
echo Only safe projected values are included. Review it before sharing.
pause
