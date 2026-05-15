# L.I.S 美股收盤覆盤卡 Launcher (04:05 EST 美股盤後)
$ErrorActionPreference = "Continue"
$env:PYTHONIOENCODING = "utf-8"

$PythonExe = "D:\LIS股票投資系統\程式碼\.venv\Scripts\python.exe"
$ProjectRoot = "D:\LIS股票投資系統"
$CodeDir = Join-Path $ProjectRoot "程式碼"
$Today = Get-Date -Format "yyyy-MM-dd"
$LogFile = Join-Path $ProjectRoot ("數據\logs\us_close_" + $Today + ".log")

$LogDir = Split-Path $LogFile -Parent
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
}

Add-Content -Path $LogFile -Encoding utf8 -Value ""
Add-Content -Path $LogFile -Encoding utf8 -Value "=========================================="
Add-Content -Path $LogFile -Encoding utf8 -Value ("Start: " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss"))
Add-Content -Path $LogFile -Encoding utf8 -Value "=========================================="

Set-Location $CodeDir
Add-Content -Path $LogFile -Encoding utf8 -Value ">>> 美股收盤覆盤卡 (Phase 36.13) <<<"
& $PythonExe push_美股覆盤.py *>> $LogFile
$ExitCode = $LASTEXITCODE

Add-Content -Path $LogFile -Encoding utf8 -Value (">>> 結束 ExitCode=" + $ExitCode)
Add-Content -Path $LogFile -Encoding utf8 -Value ("End: " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss") + "  ExitCode=" + $ExitCode)
exit $ExitCode
