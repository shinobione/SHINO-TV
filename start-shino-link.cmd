@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
echo.
echo SHINO // LINK - Windows tray pilot (PC telemetry RAM ONLY)
echo --------------------------------------------------------
if not exist "%LOCALAPPDATA%\SHINO-TV\link.json" (
  echo No private local configuration exists.
  echo Configure it first using the instructions in companion\SHINO_LINK.md.
  exit /b 1
)
if not exist "companion\shino_link.py" (
  echo Missing full repository checkout.
  exit /b 1
)
where pyw >nul 2>&1
if errorlevel 1 (
  echo Python Windows GUI launcher pyw not found.
  echo Use: py -3 companion\shino_link.py --tray
  exit /b 1
)
echo Launch requested. Look for SHINO // LINK in the Windows tray.
echo This only starts the configured metrics companion; no TV firmware write.
start "" pyw -3 "%~dp0companion\shino_link.py" --tray
exit /b %errorlevel%
