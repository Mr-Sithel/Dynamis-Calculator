@echo off
cd /d "%~dp0"
echo Running Python scraper...
python scripts\update_prices.py
if errorlevel 1 (
    echo [ERROR] Python script failed!
    pause
    exit /b
)

echo Checking Git status...
git status

echo Staging changes...
git add prices.json

echo Committing...
git commit -m "Automated price update"

echo Pushing to GitHub...
git push
echo Done!
pause