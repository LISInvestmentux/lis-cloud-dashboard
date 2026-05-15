@echo off
chcp 65001 > nul
cd /d "%~dp0"
echo.
echo ========================================
echo   🌅 LIS 全套晨報（5 卡完整推播）
echo ========================================
echo.
echo 整合所有 Phase 16-33 模組：
echo   - 全息儀表板（部位/底部/供需/策略池）
echo   - 即時決策（Kelly + 彈藥）
echo   - 主情報中心（台美/法人/基本面/新聞）
echo   - 跨來源共識（4 群+股癌+可可）
echo   - 策略池入選
echo.
echo （約 1 分鐘）
echo.
.venv\Scripts\python.exe LIS全套晨報.py
echo.
echo 完成！5 秒後關閉...
timeout /t 5 > nul
