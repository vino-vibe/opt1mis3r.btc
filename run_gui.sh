#!/usr/bin/env bash
# run_gui.sh — launch the is3r Streamlit dashboard.
# Auto-activates ./venv if present.

set -e
cd "$(dirname "$0")"

if [ -d "venv" ] && [ -z "$VIRTUAL_ENV" ]; then
  # shellcheck disable=SC1091
  source venv/bin/activate
fi

# Headless and no usage-stats prompt — runs cleanly on first launch.
exec streamlit run app.py \
  --server.headless true \
  --browser.gatherUsageStats false \
  --server.port 8501
