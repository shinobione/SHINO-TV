@echo off
setlocal
cd /d "%~dp0.."
echo.
echo SHINO // TV - MISSION 9 TRANSITION OFFLINE REVIEW
echo Builds and host tests only. NO DEVICE / COM / FLASH / LIVE OTA.
echo.
where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    py -3 tools\shino_transition_offline_gate.py
) else (
    python tools\shino_transition_offline_gate.py
)
set RET=%ERRORLEVEL%
echo.
echo Review report: research-local\m9-transition-review.json
echo Review log:    research-local\m9-transition-review.log
echo Result code:   %RET%
exit /b %RET%
