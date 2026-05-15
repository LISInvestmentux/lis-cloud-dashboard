@echo off
chcp 65001 > nul
cd /d "%~dp0"
echo.
echo ========================================
echo   LIS 持股表單啟動中...
echo ========================================
echo.
echo 瀏覽器會自動開啟 http://localhost:8501
echo 關閉這個視窗即可結束
echo.
.venv\Scripts\streamlit.exe run portfolio_app.py
pause
