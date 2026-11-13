@echo off
cd /d "%~dp0"
python update_prices.py
git add prices.json
git commit -m "Automated price update"
git push