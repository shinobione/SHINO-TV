@echo off
setlocal
cd /d "%~dp0.."
echo SHINO OFFLINE CHECK - builds only public test firmware. NO DEVICE/COM/FLASH.
where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    py -3 tools\shino_offline_gate.py
) else (
    python tools\shino_offline_gate.py
)
exit /b %ERRORLEVEL%
