@echo off
chcp 65001 > nul
cd /d "%~dp0"
echo.
echo ========================================
echo   LIS 即時持股快照
echo ========================================
echo.
echo 抓 22 檔即時股價、算損益、推 LINE...
echo （約 30 秒）
echo.
.venv\Scripts\python.exe instant_snapshot.py
echo.
echo 完成，3 秒後關閉視窗...
timeout /t 3 > nul
