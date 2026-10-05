#!/bin/bash
cd "$(dirname "$0")"
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    .venv/bin/pip install --upgrade pip
    .venv/bin/pip install ortools fastapi uvicorn
fi
echo "🚀 מפעיל את פותר תשבצי השלד..."
echo "🌐 פתח את הדפדפן בכתובת: http://localhost:8080"
open "http://localhost:8080" 2>/dev/null || true
.venv/bin/uvicorn app:app --host 0.0.0.0 --port 8080
