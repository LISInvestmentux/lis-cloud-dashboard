# L.I.S US Order Reminder Launcher (called by Windows Task Scheduler 21:25)
$ErrorActionPreference = "Continue"
$env:PYTHONIOENCODING = "utf-8"

$PythonExe = "D:\LIS股票投資系統\程式碼\.venv\Scripts\python.exe"

$ProjectRoot = "D:\LIS股票投資系統"
$CodeDir = Join-Path $ProjectRoot "程式碼"
$Today = Get-Date -Format "yyyy-MM-dd"
$LogFile = Join-Path $ProjectRoot ("數據\logs\order_reminder_us_" + $Today + ".log")

$LogDir = Split-Path $LogFile -Parent
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
}

Add-Content -Path $LogFile -Encoding utf8 -Value ""
Add-Content -Path $LogFile -Encoding utf8 -Value "=========================================="
Add-Content -Path $LogFile -Encoding utf8 -Value ("Start: " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss"))
Add-Content -Path $LogFile -Encoding utf8 -Value ("Python: " + $PythonExe)
Add-Content -Path $LogFile -Encoding utf8 -Value "=========================================="

Set-Location $CodeDir
Add-Content -Path $LogFile -Encoding utf8 -Value ">>> 1/2 今夜美股行動卡 (Phase 33.2) <<<"
& $PythonExe -c "from dotenv import load_dotenv; from pathlib import Path; load_dotenv(Path('../API/.env')); from modules import us_action_card; ok = us_action_card.推Flex卡(); print(f'us_action_card 推送：{ok}')" *>> $LogFile
$ExitCode1 = $LASTEXITCODE

Start-Sleep -Seconds 3

Add-Content -Path $LogFile -Encoding utf8 -Value ">>> 2/2 美股盤前待掛單提醒 <<<"
& $PythonExe -m modules.order_reminder us *>> $LogFile
$ExitCode2 = $LASTEXITCODE

if ($ExitCode1 -eq 0 -and $ExitCode2 -eq 0) { $ExitCode = 0 } else { $ExitCode = 1 }
Add-Content -Path $LogFile -Encoding utf8 -Value (">>> 結束 ExitCode1=" + $ExitCode1 + " ExitCode2=" + $ExitCode2)
Add-Content -Path $LogFile -Encoding utf8 -Value ("End: " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss") + "  ExitCode=" + $ExitCode)
exit $ExitCode
