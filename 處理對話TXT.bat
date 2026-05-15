@echo off
chcp 65001 > nul
cd /d "%~dp0"
echo.
echo ========================================
echo   LIS LINE 對話 TXT 處理（Phase 30）
echo ========================================
echo.
echo 流程：
echo   1. LINE 群組 → 設定 → 傳送聊天記錄 → TXT
echo   2. 放到 D:\LIS股票投資系統\輸入\對話TXT\
echo      檔名範例：可可群_2026-05-14.txt
echo   3. 雙擊本 .bat 自動處理
echo.
echo 兩階段過濾：
echo   Stage 1: 關鍵詞（買/賣/漲/賺/本金 等）
echo   Stage 2: Gemini AI 結構化提取
echo.
echo ⚠️ 反CC 提醒：群組訊號 weight 僅 0.1
echo    倖存者偏差 / 從眾偏差 / 時效偏差
echo    當參考不當決策
echo.
.venv\Scripts\python.exe 處理對話TXT.py
echo.
pause
