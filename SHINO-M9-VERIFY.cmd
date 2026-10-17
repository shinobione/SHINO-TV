@echo off
setlocal
cd /d "%~dp0"
echo.
echo SHINO // TV - MISSION 9 PRIVATE CANDIDATE VERIFICATION
echo Read-only local BIN / manifest / ELF / layout audit
echo NO COM, NO UART, NO OTA, NO DEVICE, NO FLASH
echo.
where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    py -3 tools\test_shino_owner_candidate_verify.py
    if errorlevel 1 goto :hold
    py -3 tools\shino_owner_candidate_verify.py
) else (
    python tools\test_shino_owner_candidate_verify.py
    if errorlevel 1 goto :hold
    python tools\shino_owner_candidate_verify.py
)
if errorlevel 1 goto :hold
echo.
echo PASS OFFLINE ONLY - PHYSICAL INSTALL REMAINS DISABLED
echo Share only: research-local\m9-owner\candidate-verify.json
echo NEVER share owner-credentials.json or the firmware BIN
pause
exit /b 0
:hold
echo.
echo NO-GO. Existing private binary was not modified.
pause
exit /b 2
