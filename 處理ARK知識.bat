@echo off
chcp 65001 > nul
cd /d %~dp0
echo === ARK 知識庫處理 ===
echo.
echo 把教材圖丟到 D:\LIS股票投資系統\數據\ark_knowledge\
echo 跑這個會對新圖做 Gemini Vision OCR + 摘要 + 概念標籤
echo （已處理過的圖會自動跳過）
echo.
.venv\Scripts\python.exe -m modules.ark_knowledge
echo.
pause
