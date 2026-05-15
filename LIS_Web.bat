@echo off
chcp 65001 > nul
cd /d "%~dp0"
title LIS Web Dashboard
echo.
echo ========================================
echo   📊 LIS Web Dashboard (port 8502)
echo ========================================
echo.
echo 🔄 啟動中...
echo.
echo 服務啟動後請開瀏覽器到：
echo   http://localhost:8502
echo.
echo ⚠️ 請保持這個視窗開著（關掉就停止服務）
echo.

REM 等 8 秒後自動開瀏覽器
start "" cmd /c "timeout /t 8 >nul && start http://localhost:8502"

REM 用 call 確保 streamlit 在此 cmd 內執行，不會分離
call .venv\Scripts\streamlit.exe run web_dashboard.py --server.port=8502 --server.headless=true

echo.
echo ⚠️ Streamlit 已停止
pause
