@echo off
cd /d "%~dp0"

echo Updating local repository...
git pull --rebase origin main
if errorlevel 1 (
    echo ERROR: Git pull failed. Stopping.
    exit /b 1
)

echo Updating auction house prices...
python scripts\update_prices.py
if errorlevel 1 (
    echo ERROR: Python price update failed.
    exit /b 1
)

echo Checking for price changes...
git add prices.json

git diff --cached --quiet
if %errorlevel%==0 (
    echo No price changes detected. Nothing to push.
    exit /b 0
)

echo Committing price updates...
git commit -m "Automated price update"
if errorlevel 1 exit /b 1

echo Pushing updates to GitHub...
git push origin main
if errorlevel 1 (
    echo ERROR: Git push failed.
    exit /b 1
)

echo Successfully updated GitHub!
exit /b 0
