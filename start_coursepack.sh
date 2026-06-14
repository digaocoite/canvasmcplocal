#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 was not found. Please install Python 3.10 or newer."
  exit 1
fi

if [ ! -x ".venv/bin/python" ]; then
  echo "Creating local Python environment. This happens only the first time..."
  python3 -m venv .venv
fi

echo "Installing/updating required packages..."
.venv/bin/python -m pip install -r requirements.txt

echo "Opening CoursePack Local at http://127.0.0.1:3333"
echo "Leave this terminal open while using the app. Press CTRL+C to stop it."
.venv/bin/python run_web.py
