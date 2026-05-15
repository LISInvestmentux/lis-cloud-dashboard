# L.I.S 持股配置表單啟動器
# 雙擊或在 PowerShell 執行：powershell -File 開啟資金表單.ps1

$ProjectRoot = "D:\LIS股票投資系統"
$PythonExe = Join-Path $ProjectRoot "程式碼\.venv\Scripts\python.exe"
$FormScript = Join-Path $ProjectRoot "程式碼\portfolio_form.py"

Write-Host ""
Write-Host "==================================" -ForegroundColor Yellow
Write-Host "  L.I.S 持股配置表單啟動中..." -ForegroundColor Yellow
Write-Host "==================================" -ForegroundColor Yellow
Write-Host ""
Write-Host "稍等幾秒，瀏覽器會自動打開"
Write-Host "如果沒打開，手動開啟：http://localhost:8501"
Write-Host ""
Write-Host "用完按 Ctrl+C 關閉此視窗即可"
Write-Host ""

$env:PYTHONIOENCODING = "utf-8"
& $PythonExe -m streamlit run $FormScript --server.headless false --browser.gatherUsageStats false
