@echo off
setlocal
cd /d "%~dp0"
title SHINO-TV - Live PC Preview
echo.
echo =============================
echo      SHINO // TV PREVIEW
echo =============================
echo.
where py >nul 2>&1
if errorlevel 1 (
  echo Python launcher "py" not found. Install Python 3, then retry.
  pause
  exit /b 1
)
py -c "import psutil" >nul 2>&1
if errorlevel 1 (
  echo The psutil package is missing.
  echo Run: py -m pip install -r companion\requirements.txt
  pause
  exit /b 1
)
echo Local dashboard: http://127.0.0.1:8765/
echo No connection or writes to your SmallTV.
echo Press Ctrl+C in this window to stop the service.
echo.
py companion\metrics_server.py
if errorlevel 1 pause
