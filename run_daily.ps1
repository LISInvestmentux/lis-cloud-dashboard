# L.I.S Daily Report Launcher (called by Windows Task Scheduler)
$ErrorActionPreference = "Continue"
$env:PYTHONIOENCODING = "utf-8"

# Use the project-local venv Python so all dependencies are guaranteed available
$PythonExe = "D:\LIS股票投資系統\程式碼\.venv\Scripts\python.exe"

$ProjectRoot = "D:\LIS股票投資系統"
$CodeDir = Join-Path $ProjectRoot "程式碼"
$Today = Get-Date -Format "yyyy-MM-dd"
$LogFile = Join-Path $ProjectRoot ("數據\logs\run_" + $Today + ".log")

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
# Phase 33.1：先跑 T+2 自動交割（賣股款入帳）
Add-Content -Path $LogFile -Encoding utf8 -Value ">>> 階段 0: T+2 自動交割 <<<"
& $PythonExe -m modules.settlement_auto *>> $LogFile

# Phase 33.1 升級：先跑舊版 main.py（保留 KOL/Enjoy/etc 推播），再跑新版 LIS全套晨報
Add-Content -Path $LogFile -Encoding utf8 -Value ">>> 階段 1: main.py 舊版推播 <<<"
& $PythonExe main.py *>> $LogFile
$ExitCode1 = $LASTEXITCODE
Add-Content -Path $LogFile -Encoding utf8 -Value (">>> main.py 結束 ExitCode=" + $ExitCode1)

Add-Content -Path $LogFile -Encoding utf8 -Value ""
Add-Content -Path $LogFile -Encoding utf8 -Value ">>> 階段 2: LIS全套晨報.py 新版整合 <<<"
& $PythonExe LIS全套晨報.py *>> $LogFile
$ExitCode2 = $LASTEXITCODE
Add-Content -Path $LogFile -Encoding utf8 -Value (">>> LIS全套晨報 結束 ExitCode=" + $ExitCode2)

# 兩個都成功才返回 0
if ($ExitCode1 -eq 0 -and $ExitCode2 -eq 0) {
    $ExitCode = 0
} else {
    $ExitCode = 1
}

Add-Content -Path $LogFile -Encoding utf8 -Value ("End: " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss") + "  ExitCode=" + $ExitCode)

# Phase 32.5：失敗時自動推 LINE 警示
if ($ExitCode -ne 0) {
    & $PythonExe -m modules.scheduled_alert ALERT "LIS_Daily_Report" $ExitCode $LogFile 2>&1 | Out-Null
}

exit $ExitCode
