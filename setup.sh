#!/usr/bin/env bash
# One-time setup for macOS / Linux.
set -e
cd "$(dirname "$0")/backend"
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
[ -f .env ] || cp .env.example .env
python -m app.ml.train
python scripts/seed.py
cd ../frontend && npm install
echo "Done. Run ./start.sh"
