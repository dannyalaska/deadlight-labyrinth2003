#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
#  DEADLIGHT 2003 — Smart Startup Script
#  Handles: .venv, Poetry, bare pip, or system Python
#  Usage: ./start.sh [--api-only] [--port 8000] [--no-browser]
# ─────────────────────────────────────────────────────────────

set -euo pipefail

# ── Navigate to the project root (wherever this script lives) ──
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

LOG_DIR="$SCRIPT_DIR/logs"
API_LOG="$LOG_DIR/api.log"
STREAMLIT_LOG="$LOG_DIR/streamlit.log"
DATA_DIR="$SCRIPT_DIR/data"
PID_FILE="$LOG_DIR/uvicorn.pid"

# ── Parse flags ────────────────────────────────────────────────
API_ONLY=false
OPEN_BROWSER=true
API_PORT="${PORT:-8000}"
STREAMLIT_PORT="${STREAMLIT_PORT:-8501}"
START_STREAMLIT=false

for arg in "$@"; do
  case $arg in
    --api-only)    API_ONLY=true ;;
    --streamlit)   START_STREAMLIT=true ;;
    --no-browser)  OPEN_BROWSER=false ;;
    --port=*)      API_PORT="${arg#--port=}" ;;
  esac
done

mkdir -p "$LOG_DIR" "$DATA_DIR"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  DEADLIGHT 2003  //  STARTUP"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# ── Kill anything already running on our ports ─────────────────
cleanup_ports() {
  local port=$1
  local existing
  existing=$(lsof -ti tcp:"$port" 2>/dev/null || true)
  if [[ -n "$existing" ]]; then
    echo "  [cleanup] killing process on port $port (PID $existing)"
    kill "$existing" 2>/dev/null || true
    sleep 1
  fi
}
cleanup_ports "$API_PORT"
[[ "$START_STREAMLIT" == true ]] && cleanup_ports "$STREAMLIT_PORT"

# ── Detect the best Python to use ─────────────────────────────
PYTHON=""
RUN_CMD=()   # array — safe for paths with spaces (e.g. "Shared with RD backup")
IS_POETRY=false

echo "  [detect] looking for Python environment..."

# Priority 1: local .venv (most reliable — already set up)
if [[ -f "$SCRIPT_DIR/.venv/bin/python" ]]; then
  PYTHON="$SCRIPT_DIR/.venv/bin/python"
  RUN_CMD=("$SCRIPT_DIR/.venv/bin/python" "-m")
  echo "  [detect] ✓ found .venv at .venv/bin/python"

# Priority 2: Poetry (manages its own venv)
elif command -v poetry >/dev/null 2>&1; then
  PYTHON="$(poetry run python -c 'import sys; print(sys.executable)' 2>/dev/null || true)"
  if [[ -n "$PYTHON" ]]; then
    RUN_CMD=("poetry" "run" "python" "-m")
    IS_POETRY=true
    echo "  [detect] ✓ using Poetry environment"
  fi
fi

# Priority 3: python3 on PATH + try to pip-install
if [[ -z "$PYTHON" ]]; then
  if command -v python3 >/dev/null 2>&1; then
    PYTHON="python3"
    RUN_CMD=("python3" "-m")
    echo "  [detect] ✓ using system python3 (will pip-install if needed)"
  elif command -v python >/dev/null 2>&1; then
    PYTHON="python"
    RUN_CMD=("python" "-m")
    echo "  [detect] ✓ using system python"
  else
    echo ""
    echo "  [ERROR] No Python found. Install Python 3.11+ and try again."
    echo "          https://www.python.org/downloads/"
    exit 1
  fi
fi

# ── Check / install dependencies ──────────────────────────────
echo "  [deps] checking dependencies..."

check_pkg() {
  "$PYTHON" -c "import $1" 2>/dev/null
}

MISSING=()
for pkg in fastapi uvicorn pydantic dotenv email_validator; do
  if ! check_pkg "$pkg" 2>/dev/null; then
    MISSING+=("$pkg")
  fi
done

if [[ ${#MISSING[@]} -gt 0 ]]; then
  echo "  [deps] missing packages detected, installing from requirements.txt..."
  if [[ "$IS_POETRY" == true ]]; then
    poetry install --no-interaction
  else
    "$PYTHON" -m pip install -r "$SCRIPT_DIR/requirements.txt" \
      email-validator \
      "pydantic[email]" \
      --quiet --disable-pip-version-check
  fi
  echo "  [deps] ✓ installed"
else
  echo "  [deps] ✓ all good"
fi

# ── Load .env if present ───────────────────────────────────────
if [[ -f "$SCRIPT_DIR/.env" ]]; then
  echo "  [env]  ✓ loading .env"
  set -a
  # shellcheck disable=SC1091
  source "$SCRIPT_DIR/.env"
  set +a
else
  echo "  [env]  (no .env found — using system environment)"
  echo "         Copy .env.example to .env to set your API keys when needed."
fi

# ── Start FastAPI (uvicorn) ────────────────────────────────────
echo ""
echo "  [start] launching API server on port $API_PORT..."

nohup "${RUN_CMD[@]}" uvicorn labyrinth.server:app \
  --reload \
  --host 0.0.0.0 \
  --port "$API_PORT" \
  > "$API_LOG" 2>&1 &
echo $! > "$PID_FILE"
sleep 2

# Verify it actually started
if ! lsof -ti tcp:"$API_PORT" >/dev/null 2>&1; then
  echo ""
  echo "  [ERROR] Server failed to start. Last 20 lines of log:"
  echo "  ─────────────────────────────────────────────────────"
  tail -20 "$API_LOG" || true
  echo ""
  echo "  Full log: $API_LOG"
  exit 1
fi
echo "  [start] ✓ API server running (PID $(cat "$PID_FILE"))"

# ── Optionally start Streamlit UI ─────────────────────────────
if [[ "$START_STREAMLIT" == true ]]; then
  echo "  [start] launching Streamlit UI on port $STREAMLIT_PORT..."
  nohup "${RUN_CMD[@]}" streamlit run "$SCRIPT_DIR/streamlit_app_v2.py" \
    --server.port "$STREAMLIT_PORT" \
    --server.address 0.0.0.0 \
    --server.headless true \
    > "$STREAMLIT_LOG" 2>&1 &
  echo $! > "$LOG_DIR/streamlit.pid"
  sleep 2
  echo "  [start] ✓ Streamlit UI running"
fi

# ── Resolve local IP for phone testing ────────────────────────
LOCAL_IP=$("$PYTHON" -c "
import socket
try:
  s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
  s.connect(('8.8.8.8', 80))
  print(s.getsockname()[0])
  s.close()
except:
  print('127.0.0.1')
" 2>/dev/null || echo "127.0.0.1")

# ── Open browser ──────────────────────────────────────────────
if [[ "$OPEN_BROWSER" == true ]]; then
  URL="http://localhost:$API_PORT"
  if command -v open >/dev/null 2>&1; then          # macOS
    open "$URL" 2>/dev/null || true
  elif command -v xdg-open >/dev/null 2>&1; then    # Linux
    xdg-open "$URL" 2>/dev/null || true
  fi
fi

# ── Done ──────────────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✓ MAZE INITIALIZED"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  Web UI:    http://localhost:$API_PORT"
echo "  API docs:  http://localhost:$API_PORT/docs"
if [[ "$START_STREAMLIT" == true ]]; then
echo "  Terminal:  http://localhost:$STREAMLIT_PORT"
fi
echo ""
echo "  On your phone (same WiFi):"
echo "  Web UI:    http://$LOCAL_IP:$API_PORT"
echo ""
echo "  Logs:"
echo "    API:  tail -f $API_LOG"
echo ""
echo "  To stop:  ./stop_maze.sh"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
