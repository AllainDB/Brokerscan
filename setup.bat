@echo off
echo === BrokerScan Setup ===

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install from https://python.org and check "Add to PATH".
    pause
    exit /b 1
)

echo [1/3] Installing Python dependencies...
python -m pip install --upgrade pip --quiet
python -m pip install -r requirements.txt --quiet

echo [2/3] Installing Playwright Chromium browser...
python -m playwright install chromium

echo [3/3] Done.
echo.
echo Run your first scan:
echo   python brokerscan.py --name "Your Name" --city "Your City" --state FL --priority HIGH
pause
