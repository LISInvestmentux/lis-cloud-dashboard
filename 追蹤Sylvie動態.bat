@echo off
chcp 65001 > nul
cd /d %~dp0
echo === Sylvie 動態追蹤 ===
echo.
.venv\Scripts\python.exe -m modules.sylvie_tracker
echo.
pause
