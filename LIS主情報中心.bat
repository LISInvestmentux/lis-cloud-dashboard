@echo off
chcp 65001 > nul
cd /d "%~dp0"
echo.
echo ========================================
echo   LIS 主情報中心（Phase 22-25 全整合）
echo ========================================
echo.
echo 整合：台美連動 / 法人籌碼 / 基本面 / 新聞情緒
echo 4 張卡 carousel 推到 LINE
echo （約 10 秒）
echo.
.venv\Scripts\python.exe push_master_intelligence.py
echo.
echo 完成！5 秒關閉...
timeout /t 5 > nul
