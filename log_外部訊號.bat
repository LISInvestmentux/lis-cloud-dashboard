@echo off
chcp 65001 > nul
cd /d "%~dp0"
echo.
echo ========================================
echo   LIS 外部訊號手動 log
echo ========================================
echo.
echo 把太太/可可/大俠/KOL 的訊號 log 進系統
echo 30/60/90 天後自動驗證，累積「來源信任分」
echo.
echo 格式：來源 symbol 類型 進場價 [說明]
echo 例：ARK_可可 00911.TW BUY 50.5 升溫區
echo.
.venv\Scripts\python.exe log_外部訊號.py
echo.
echo 完成！
pause
