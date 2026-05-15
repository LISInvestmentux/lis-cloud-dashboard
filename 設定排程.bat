@echo off
chcp 65001 > nul
cd /d "%~dp0"
echo.
echo ========================================
echo   ⏰ LIS 自動排程設定（4 時段）
echo ========================================
echo.
echo 將建立 / 更新以下 Task Scheduler：
echo.
echo   1. LIS_Daily_Report       每天 08:00 (主推播，已存在)
echo   2. LIS_盤中早盤            每天 09:30 (盤中警示)
echo   3. LIS_盤中午盤            每天 11:30
echo   4. LIS_盤中收前            每天 13:20
echo   5. LIS_美股_22:00          每天 22:00 (美股開盤前)
echo   6. LIS_美股_04:00          每天 04:00 (美股收盤後)
echo.
pause
echo.

set "PS_INTRA=cd /d D:\LIS股票投資系統\程式碼 ^& .venv\Scripts\python.exe -m modules.intraday_alerts"
set "PS_US=cd /d D:\LIS股票投資系統\程式碼 ^& .venv\Scripts\python.exe push_美股晚場.py"

echo 建立盤中早盤排程...
schtasks /create /tn "LIS_盤中早盤" /tr "cmd /c %PS_INTRA%" /sc DAILY /st 09:30 /f
echo.

echo 建立盤中午盤排程...
schtasks /create /tn "LIS_盤中午盤" /tr "cmd /c %PS_INTRA%" /sc DAILY /st 11:30 /f
echo.

echo 建立盤中收前排程...
schtasks /create /tn "LIS_盤中收前" /tr "cmd /c %PS_INTRA%" /sc DAILY /st 13:20 /f
echo.

echo 建立美股 22:00 排程...
schtasks /create /tn "LIS_美股_22:00" /tr "cmd /c %PS_US%" /sc DAILY /st 22:00 /f
echo.

echo 建立美股 04:00 排程...
schtasks /create /tn "LIS_美股_04:00" /tr "cmd /c %PS_US%" /sc DAILY /st 04:00 /f
echo.

echo ✅ 所有排程建立完成！
echo.
echo 查看排程：開「工作排程器」搜尋 LIS
echo 或執行：schtasks /query /tn "LIS*"
echo.
pause
