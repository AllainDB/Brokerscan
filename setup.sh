#!/usr/bin/env bash
# BrokerScan setup — run once
set -e

echo "=== BrokerScan Setup ==="

# Check Python
if ! command -v python3 &>/dev/null; then
  echo "[ERROR] Python 3 not found. Install from https://python.org"
  exit 1
fi

echo "[1/3] Installing Python dependencies..."
python3 -m pip install --upgrade pip --quiet
python3 -m pip install -r requirements.txt --quiet

echo "[2/3] Installing Playwright Chromium browser..."
python3 -m playwright install chromium

echo "[3/3] Done."
echo ""
echo "Run your first scan:"
echo "  python3 brokerscan.py --name \"Your Name\" --city \"Your City\" --state \"FL\" --priority HIGH"
