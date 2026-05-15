@echo off
chcp 65001 > nul
cd /d "%~dp0"
echo.
echo ========================================
echo   LIS 即時決策（訊號+現價+持股）
echo ========================================
echo.
echo 整合 4 個資料源 → 給你「買啥/PASS/警示」
echo （約 10 秒）
echo.
.venv\Scripts\python.exe instant_decision.py
echo.
echo 完成，3 秒後關閉視窗...
timeout /t 3 > nul
