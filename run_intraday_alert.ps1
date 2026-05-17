# L.I.S 盤中即時警示 Launcher（Phase 8.4）
$ErrorActionPreference = "Continue"
$env:PYTHONIOENCODING = "utf-8"

$PythonExe = "D:\LIS股票投資系統\程式碼\.venv\Scripts\python.exe"
$ProjectRoot = "D:\LIS股票投資系統"
$CodeDir = Join-Path $ProjectRoot "程式碼"
$Today = Get-Date -Format "yyyy-MM-dd"
$LogFile = Join-Path $ProjectRoot ("數據\logs\intraday_alert_" + $Today + ".log")

$LogDir = Split-Path $LogFile -Parent
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
}

Add-Content -Path $LogFile -Encoding utf8 -Value ""
Add-Content -Path $LogFile -Encoding utf8 -Value "=========================================="
Add-Content -Path $LogFile -Encoding utf8 -Value ("Start: " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss"))
Add-Content -Path $LogFile -Encoding utf8 -Value "=========================================="

Set-Location $CodeDir

# Phase 50 (5/17): 改用 Start-Process -PassThru 拿純 ExitCode
# 避免 PowerShell 5.1 的 NativeCommandError 機制把 stderr 包成 ErrorRecord 污染 $LASTEXITCODE
$tempOut = "$LogFile.tmp_out"
$tempErr = "$LogFile.tmp_err"
$proc = Start-Process -FilePath $PythonExe -ArgumentList "intraday_real_alert.py" `
    -Wait -NoNewWindow -PassThru `
    -RedirectStandardOutput $tempOut `
    -RedirectStandardError $tempErr
$ExitCode = $proc.ExitCode

# 合併 stdout + stderr 到 LogFile
if (Test-Path $tempOut) {
    Get-Content $tempOut -Encoding utf8 | Add-Content $LogFile -Encoding utf8
    Remove-Item $tempOut -Force
}
if (Test-Path $tempErr) {
    $errContent = Get-Content $tempErr -Encoding utf8
    if ($errContent) {
        Add-Content $LogFile -Encoding utf8 -Value "--- stderr ---"
        $errContent | Add-Content $LogFile -Encoding utf8
    }
    Remove-Item $tempErr -Force
}

Add-Content -Path $LogFile -Encoding utf8 -Value ("End: " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss") + "  ExitCode=" + $ExitCode)
exit $ExitCode
