@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
echo.
echo SHINO // TV - FS-LESS NATIVE UI / PC-ONLY PREVIEW
echo -----------------------------------------------
echo Extracts HTML+JS from firmware source and serves 127.0.0.1:8766.
echo Shows current Windows metrics. NO TV connection or firmware upload.
echo.
where py >nul 2>&1
if errorlevel 1 (
 echo Python 3 launcher "py" is required.
 pause
 exit /b 1
)
py -3 -m pip install -r companion\requirements.txt
if errorlevel 1 (
 echo Python dependencies could not be installed.
 pause
 exit /b 1
)
echo.
echo Opening preview in browser...
start "" "http://127.0.0.1:8766/"
py -3 tools\preview_fsless_dashboard.py --port 8766
pause
