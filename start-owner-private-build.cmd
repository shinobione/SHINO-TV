@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
echo.
echo SHINO // TV - PRIVATE FIRST-INSTALL EVIDENCE PACKAGE
echo ===================================================
echo LOCAL WINDOWS BUILD ONLY. THIS DOES NOT CONNECT TO OR FLASH THE TV.
echo.
echo Creates an original official application reference and ONE exact V2
echo firmware with paired private WPA2 / Digest secrets in your user folder.
echo NO serial port, no device web request, no OTA/upload/erase operation.
echo.
echo You MUST use a clean git clone of the reviewed PR source, not a ZIP.
echo Do not use a SHA from an older PR or paste any private credentials here.
echo.
where git >nul 2>&1
if errorlevel 1 (
  echo Git is required to validate the exact reviewed source commit.
  pause
  exit /b 1
)
where py >nul 2>&1
if errorlevel 1 (
  echo Python 3 launcher "py" is required.
  pause
  exit /b 1
)
set "REVIEW_SHA=%~1"
if not defined REVIEW_SHA (
  set /p "REVIEW_SHA=Paste the FULL 40-character reviewed Git commit SHA: "
)
if not defined REVIEW_SHA (
  echo No reviewed source commit supplied. Stopped safely.
  pause
  exit /b 1
)
echo.
echo Installing/checking LOCAL compiler and offline-image inspection packages...
py -3 -m pip install "platformio>=6.1,<7" "esptool>=5,<6"
if errorlevel 1 (
  echo Package install failed. No firmware image was prepared.
  pause
  exit /b 1
)
echo.
echo Output root: %USERPROFILE%\SHINO-TV-private-builds
echo KEEP THIS FOLDER PRIVATE AND OUTSIDE SYNCED/CLOUD SHARES.
echo The exact manufacturer ZIP is downloaded from its immutable historical
echo source and cryptographically checked. No SmallTV connection is attempted.
echo.
py -3 tools\build_owner_private_packet.py --expected-source-sha "%REVIEW_SHA%" --output-root "%USERPROFILE%\SHINO-TV-private-builds"
if errorlevel 1 (
  echo.
  echo STOP: local build verification failed. Any INCOMPLETE folder is NOT usable.
  echo No firmware or flash operation was sent to your TV.
  pause
  exit /b 1
)
echo.
echo PRIVATE LOCAL EVIDENCE PACKAGE COMPLETE. NOT APPROVED FOR FLASHING.
echo Keep images, policy and credentials paired and private.
pause
