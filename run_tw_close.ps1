# L.I.S 台股收盤前 Launcher
$ErrorActionPreference = "Continue"
$env:PYTHONIOENCODING = "utf-8"

$PythonExe = "D:\LIS股票投資系統\程式碼\.venv\Scripts\python.exe"
$ProjectRoot = "D:\LIS股票投資系統"
$CodeDir = Join-Path $ProjectRoot "程式碼"
$Today = Get-Date -Format "yyyy-MM-dd"
$LogFile = Join-Path $ProjectRoot ("數據\logs\tw_close_" + $Today + ".log")

$LogDir = Split-Path $LogFile -Parent
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
}

Add-Content -Path $LogFile -Encoding utf8 -Value ""
Add-Content -Path $LogFile -Encoding utf8 -Value "=========================================="
Add-Content -Path $LogFile -Encoding utf8 -Value ("Start: " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss"))
Add-Content -Path $LogFile -Encoding utf8 -Value "=========================================="

Set-Location $CodeDir

Add-Content -Path $LogFile -Encoding utf8 -Value ">>> 1/2 intraday tw_close 盤中觸發 <<<"
& $PythonExe -m modules.intraday tw_close *>> $LogFile
$ExitCode1 = $LASTEXITCODE

Start-Sleep -Seconds 3

Add-Content -Path $LogFile -Encoding utf8 -Value ">>> 2/2 push_台股收盤 覆盤卡 (Phase 33.3) <<<"
& $PythonExe push_台股收盤.py *>> $LogFile
$ExitCode2 = $LASTEXITCODE

if ($ExitCode1 -eq 0 -and $ExitCode2 -eq 0) { $ExitCode = 0 } else { $ExitCode = 1 }
Add-Content -Path $LogFile -Encoding utf8 -Value (">>> ExitCode1=" + $ExitCode1 + " ExitCode2=" + $ExitCode2)
Add-Content -Path $LogFile -Encoding utf8 -Value ("End: " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss") + "  ExitCode=" + $ExitCode)
exit $ExitCode
