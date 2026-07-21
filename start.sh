#!/bin/bash
set -e

# Pull latest code from GitHub
if [ -d ".git" ]; then
  echo "[STARTUP] Pulling latest code..."
  git pull origin main
fi

# Install dependencies
echo "[STARTUP] Installing Python dependencies..."
python -m pip install -r requirements.txt

# Start the launcher
echo "[STARTUP] Starting launcher.py..."
python launcher.py
