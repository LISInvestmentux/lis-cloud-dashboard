@echo off
chcp 65001 > nul
cd /d "%~dp0"
echo.
echo ========================================
echo   LIS 社群截圖處理
echo ========================================
echo.
echo 流程：
echo   1. 截 LINE 社群對話圖
echo   2. 放到 D:\LIS股票投資系統\輸入\社群\
echo      檔名範例：可可群_2026-05-14.png
echo   3. 雙擊本 .bat 自動處理
echo.
echo 處理中（Gemini Vision OCR + 提取訊號）...
echo.
.venv\Scripts\python.exe 處理社群截圖.py
echo.
pause
