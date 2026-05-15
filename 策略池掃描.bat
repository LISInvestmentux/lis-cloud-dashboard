@echo off
chcp 65001 > nul
cd /d "%~dp0"
echo.
echo ========================================
echo   LIS ARK 風策略池掃描
echo ========================================
echo.
echo 8 個策略獨立掃 watchlist：
echo   ETF 深價值 / ETF 進入價值 / ETF 升溫 / 個股深價值
echo   個股突破 / Kelly TOP10 / 黑天鵝抄底 / DCA 定額
echo （約 30 秒，推 carousel 到 LINE）
echo.
.venv\Scripts\python.exe push_strategy_pool.py
echo.
echo 完成，5 秒後關閉視窗...
timeout /t 5 > nul
