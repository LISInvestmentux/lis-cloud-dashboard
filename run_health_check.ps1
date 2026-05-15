# L.I.S Health Check Launcher (called by Windows Task Scheduler 09:00)
$ErrorActionPreference = "Continue"
$env:PYTHONIOENCODING = "utf-8"

# Use the project-local venv Python so all dependencies are guaranteed available
$PythonExe = "D:\LIS股票投資系統\程式碼\.venv\Scripts\python.exe"

$ProjectRoot = "D:\LIS股票投資系統"
$CodeDir = Join-Path $ProjectRoot "程式碼"
$Today = Get-Date -Format "yyyy-MM-dd"
$LogFile = Join-Path $ProjectRoot ("數據\logs\health_check_" + $Today + ".log")

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
Add-Content -Path $LogFile -Encoding utf8 -Value ">>> 1/2 scheduled_alert 排程提醒 <<<"
& $PythonExe -m modules.scheduled_alert *>> $LogFile
$ExitCode1 = $LASTEXITCODE

Add-Content -Path $LogFile -Encoding utf8 -Value ">>> 2/2 health_audit 反 CC 自查（Phase 36） <<<"
& $PythonExe -m modules.health_audit --push *>> $LogFile
$ExitCode2 = $LASTEXITCODE

if ($ExitCode1 -eq 0 -and $ExitCode2 -eq 0) { $ExitCode = 0 } else { $ExitCode = 1 }
Add-Content -Path $LogFile -Encoding utf8 -Value (">>> Health Check 結束 ExitCode1=" + $ExitCode1 + " ExitCode2=" + $ExitCode2)

Add-Content -Path $LogFile -Encoding utf8 -Value ("End: " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss") + "  ExitCode=" + $ExitCode)
exit $ExitCode
