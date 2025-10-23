#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.env"
LOG_DIR="$SCRIPT_DIR/logs"
API_LOG="$LOG_DIR/api.log"
STREAMLIT_LOG="$LOG_DIR/streamlit_v2.log"
DB_DIR="$SCRIPT_DIR/data"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  DEADLIGHT 2003 ◈ TERMINAL UI MODE"
echo "  Eerie 2003 console vibe | Scroll-based navigation"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo

# Stop any existing processes
echo "[cleanup] stopping existing maze processes..."
pkill -f "uvicorn labyrinth.server" || true
pkill -f "streamlit run" || true
sleep 2

mkdir -p "$LOG_DIR" "$DB_DIR"

STREAMLIT_PORT_VALUE="${STREAMLIT_PORT:-8501}"

USE_POETRY=false
if command -v poetry >/dev/null 2>&1; then
  USE_POETRY=true
fi

if $USE_POETRY; then
  echo "[bootstrap] installing dependencies via Poetry..."
  poetry install >/dev/null
else
  echo "[warn] Poetry not found; using system python"
fi

if [[ -f "$ENV_FILE" ]]; then
  echo "[bootstrap] loading environment from $ENV_FILE"
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
else
  echo "[bootstrap] no .env found; relying on existing environment"
fi

# Start API
echo "[start] launching FastAPI (uvicorn) -> $API_LOG"
if $USE_POETRY; then
  nohup poetry run uvicorn labyrinth.server:app --reload --host 0.0.0.0 --port "${PORT:-8000}" \
    >"$API_LOG" 2>&1 &
else
  nohup python -m uvicorn labyrinth.server:app --reload --host 0.0.0.0 --port "${PORT:-8000}" \
    >"$API_LOG" 2>&1 &
fi
echo $! > "$LOG_DIR/uvicorn.pid"

# Start Terminal UI (V2)
echo "[start] launching Terminal UI (Streamlit V2) -> $STREAMLIT_LOG"
if $USE_POETRY; then
  nohup poetry run streamlit run "$SCRIPT_DIR/streamlit_app_v2.py" \
    --server.port "$STREAMLIT_PORT_VALUE" \
    --server.address 0.0.0.0 \
    --server.headless true \
    >"$STREAMLIT_LOG" 2>&1 &
else
  nohup python -m streamlit run "$SCRIPT_DIR/streamlit_app_v2.py" \
    --server.port "$STREAMLIT_PORT_VALUE" \
    --server.address 0.0.0.0 \
    --server.headless true \
    >"$STREAMLIT_LOG" 2>&1 &
fi
echo $! > "$LOG_DIR/streamlit.pid"

sleep 3

echo
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✓ MAZE INITIALIZED"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo
echo "  Terminal UI:  http://192.168.1.230:$STREAMLIT_PORT_VALUE"
echo "  API Server:   http://192.168.1.230:8000"
echo
echo "  Mobile: Use the URLs above on your phone (same WiFi)"
echo
echo "  Logs:"
echo "    API:  tail -f $API_LOG"
echo "    UI:   tail -f $STREAMLIT_LOG"
echo
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
