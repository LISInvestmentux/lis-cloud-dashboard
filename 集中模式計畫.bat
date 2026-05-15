@echo off
chcp 65001 > nul
cd /d "%~dp0"
echo.
echo ========================================
echo   LIS ARK 集中模式行動計畫
echo ========================================
echo.
echo 讀 portfolio + Kelly DB + 即時報價
echo 算出 9 檔 ARK 風格集中部位（含賣什麼/留什麼）
echo （約 30 秒）
echo.
.venv\Scripts\python.exe push_concentration.py
echo.
echo 完成，5 秒後關閉視窗...
timeout /t 5 > nul
