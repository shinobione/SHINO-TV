@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
echo.
echo SHINO // TV - PRIVATE OWNER REVIEW BUILD (NO DEVICE FLASH)
echo ---------------------------------------------------------
echo.
if "%~3"=="" goto usage
if not exist "tools\build_private_owner_packet.py" (
  echo ERROR: Launch this script from a full Git checkout of SHINO-TV.
  exit /b 1
)
where py >nul 2>&1
if errorlevel 1 (
  echo ERROR: Python 3 Windows launcher is missing.
  exit /b 1
)
echo This operation requires a LOCAL original OEM ZIP and a private output folder.
echo It will NOT contact your SmallTV, send an OTA or upload to GitHub.
echo It will refuse a dirty checkout, stale credentials or a wrong Git SHA.
echo.
py -3 tools\build_private_owner_packet.py --official-zip "%~1" --out-dir "%~2" --expected-source-sha "%~3"
if errorlevel 1 (
  echo.
  echo BUILD NOT APPROVED / STOPPED. Review locally; never upload a partial BIN.
  exit /b 1
)
echo.
echo PRIVATE REVIEW KIT GENERATED. STILL NOT PERMISSION TO FLASH.
exit /b 0

:usage
echo Usage:
echo   start-private-owner-build.cmd "FULL_PATH_TO_OFFICIAL_V9.0.44_ZIP" "NEW_PRIVATE_OUTPUT_FOLDER_OUTSIDE_GIT" "FULL_40_CHARACTER_REVIEWED_GIT_SHA"
echo.
echo Prerequisites: full clean Git checkout, installed Python 3, PlatformIO and esptool.
echo No pip installs, network probing or device operation are launched by this .cmd.
exit /b 2
