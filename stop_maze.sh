#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  STOPPING DEADLIGHT 2003 MAZE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo

# Kill by PID files if they exist
if [[ -f "$LOG_DIR/uvicorn.pid" ]]; then
  PID=$(cat "$LOG_DIR/uvicorn.pid")
  if kill "$PID" 2>/dev/null; then
    echo "✓ Stopped API server (PID: $PID)"
  fi
  rm -f "$LOG_DIR/uvicorn.pid"
fi

if [[ -f "$LOG_DIR/streamlit.pid" ]]; then
  PID=$(cat "$LOG_DIR/streamlit.pid")
  if kill "$PID" 2>/dev/null; then
    echo "✓ Stopped Streamlit UI (PID: $PID)"
  fi
  rm -f "$LOG_DIR/streamlit.pid"
fi

# Fallback: kill all matching processes
echo "Ensuring all maze processes are stopped..."
pkill -f "uvicorn labyrinth.server" || true
pkill -f "streamlit run.*streamlit_app" || true

sleep 1

echo
echo "✓ Maze shutdown complete"
echo
