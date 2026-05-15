# L.I.S 美股盤前 Launcher
$ErrorActionPreference = "Continue"
$env:PYTHONIOENCODING = "utf-8"

$PythonExe = "D:\LIS股票投資系統\程式碼\.venv\Scripts\python.exe"
$ProjectRoot = "D:\LIS股票投資系統"
$CodeDir = Join-Path $ProjectRoot "程式碼"
$Today = Get-Date -Format "yyyy-MM-dd"
$LogFile = Join-Path $ProjectRoot ("數據\logs\us_premarket_" + $Today + ".log")

$LogDir = Split-Path $LogFile -Parent
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
}

Add-Content -Path $LogFile -Encoding utf8 -Value ""
Add-Content -Path $LogFile -Encoding utf8 -Value "=========================================="
Add-Content -Path $LogFile -Encoding utf8 -Value ("Start: " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss"))
Add-Content -Path $LogFile -Encoding utf8 -Value "=========================================="

Set-Location $CodeDir
& $PythonExe -m modules.intraday us_premarket *>> $LogFile
$ExitCode1 = $LASTEXITCODE
Add-Content -Path $LogFile -Encoding utf8 -Value (">>> intraday us_premarket ExitCode=" + $ExitCode1)

# Phase 32.7：加美股焦點卡（賣/守/轉倉/加股 + 閒錢檢查）
Start-Sleep -Seconds 3
& $PythonExe push_美股焦點.py *>> $LogFile
$ExitCode2 = $LASTEXITCODE
Add-Content -Path $LogFile -Encoding utf8 -Value (">>> push_美股焦點 ExitCode=" + $ExitCode2)

if ($ExitCode1 -eq 0 -and $ExitCode2 -eq 0) { $ExitCode = 0 } else { $ExitCode = 1 }
Add-Content -Path $LogFile -Encoding utf8 -Value ("End: " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss") + "  ExitCode=" + $ExitCode)
exit $ExitCode
