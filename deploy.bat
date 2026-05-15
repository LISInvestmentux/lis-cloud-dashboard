@echo off
chcp 65001 > nul
REM LIS Cloud Sync (Phase 33.2)
REM Usage: double-click
REM   1. sync portfolio.json to GitHub Gist
REM   2. if code changed, git push to lis-cloud-dashboard

setlocal enabledelayedexpansion
cd /d "%~dp0"

REM Read GITHUB_TOKEN from .env for git push auth
set "GH_TOKEN="
for /f "usebackq tokens=1,* delims==" %%a in ("..\API\.env") do (
    if "%%a"=="GITHUB_TOKEN" set "GH_TOKEN=%%b"
)

echo ============================================
echo  LIS Cloud Sync
echo ============================================
echo.

REM Step 1: sync Gist
echo [1/2] Sync portfolio.json to Gist...
".venv\Scripts\python.exe" sync_to_gist.py
if errorlevel 1 (
    echo [WARN] Gist sync failed, continue to git push
)
echo.

REM Step 2: check code changes
echo [2/2] Check code changes...
git status --short
git diff-index --quiet HEAD
if errorlevel 1 (
    echo.
    echo [INFO] Code changed, ready to commit + push
    set /p MSG="Commit message (Enter for default): "
    if "!MSG!"=="" set "MSG=Update LIS cloud"
    git add .
    git commit -m "!MSG!"

    if "!GH_TOKEN!"=="" (
        echo [WARN] GITHUB_TOKEN not in .env, trying plain push...
        git push
    ) else (
        echo [INFO] Using token from .env...
        git push https://LISInvestmentux:!GH_TOKEN!@github.com/LISInvestmentux/lis-cloud-dashboard.git HEAD:main
    )

    if errorlevel 1 (
        echo [ERROR] Push failed. Check GITHUB_TOKEN in .env
    ) else (
        echo [OK] Pushed. Streamlit Cloud will redeploy in 1 min.
    )
) else (
    echo [INFO] No code change, only Gist synced.
)
echo.

echo ============================================
echo  Done! Cloud Dashboard:
echo  https://lis-ryan-2026.streamlit.app
echo ============================================
pause
