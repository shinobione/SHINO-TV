@echo off
setlocal
cd /d "%~dp0.."
echo.
echo SHINO // TV - M9 OWNER PRIVATE TRANSITION BUILD
echo LOCAL COMPUTER ONLY - NO UART / COM / DEVICE / OTA / FLASH
echo.
where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    set "PYTHON=py -3"
) else (
    set "PYTHON=python"
)
%PYTHON% tools\test_shino_owner_transition.py
if errorlevel 1 goto :hold
if not exist "research-local\m9-owner\owner-credentials.json" (
    echo Creating unique owner identity and maintenance credentials locally...
    %PYTHON% tools\shino_owner_transition.py init
    if errorlevel 1 goto :hold
)
echo.
echo Private secrets are local and are NEVER included in GitHub.
echo They must not be uploaded, pasted in chat, or shared with anyone.
echo.
echo Building private 4m2m transition image in ignored workspace...
%PYTHON% tools\shino_owner_transition.py build
if errorlevel 1 goto :hold
echo.
echo Build successful. PHYSICAL FLASH STILL NO-GO.
echo Send only research-local\m9-owner\transition-report.json for review.
echo Never send owner-credentials.json, private source, or firmware BIN.
pause
exit /b 0
:hold
echo.
echo NO-GO - Check the error. No device touched.
pause
exit /b 2
