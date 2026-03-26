#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WEB_DIR="$SCRIPT_DIR/web"
ENV_FILE="$SCRIPT_DIR/.env"
LOG_DIR="$SCRIPT_DIR/logs"
DATA_DIR="$SCRIPT_DIR/data"
API_LOG="$LOG_DIR/api.log"
NEXT_LOG="$LOG_DIR/next.log"

API_PORT="${PORT:-8000}"
NEXT_PORT="${NEXT_PORT:-3000}"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  DEADLIGHT 2003 ◈ NEXT.JS UI MODE"
echo "  FastAPI backend + Turbopack dev server"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo

if [[ ! -d "$WEB_DIR" ]]; then
  echo "[error] Next.js workspace not found at $WEB_DIR"
  exit 1
fi

# Stop any existing processes
echo "[cleanup] stopping existing maze processes..."
pkill -f "uvicorn labyrinth.server" >/dev/null 2>&1 || true
pkill -f "next dev" >/dev/null 2>&1 || true
sleep 2

mkdir -p "$LOG_DIR" "$DATA_DIR"

USE_POETRY=false
if command -v poetry >/dev/null 2>&1; then
  USE_POETRY=true
fi

if $USE_POETRY; then
  echo "[bootstrap] installing Python dependencies via Poetry..."
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
  echo "[bootstrap] no .env found; relying on current environment"
fi

# Prepare Node toolchain (prefer repo-local build)
NODE_BIN_DIR="$SCRIPT_DIR/tools/node-20.16.0/bin"
if [[ -d "$NODE_BIN_DIR" ]]; then
  export PATH="$NODE_BIN_DIR:$PATH"
fi

if ! command -v node >/dev/null 2>&1; then
  echo "[error] Node.js not found. Install Node 20+ or drop it in $NODE_BIN_DIR."
  exit 1
fi

# Install JS dependencies on first run
if [[ ! -d "$WEB_DIR/node_modules" ]]; then
  echo "[bootstrap] installing Next.js dependencies..."
  (cd "$WEB_DIR" && npm install >/dev/null)
fi

MAZE_API_BASE_URL="${NEXT_PUBLIC_MAZE_API_BASE:-${MAZE_API_BASE:-http://127.0.0.1:$API_PORT}}"

# Start FastAPI
echo "[start] launching FastAPI (uvicorn) -> $API_LOG"
if $USE_POETRY; then
  nohup poetry run uvicorn labyrinth.server:app --reload --host 0.0.0.0 --port "$API_PORT" \
    >"$API_LOG" 2>&1 &
else
  nohup python -m uvicorn labyrinth.server:app --reload --host 0.0.0.0 --port "$API_PORT" \
    >"$API_LOG" 2>&1 &
fi
echo $! > "$LOG_DIR/uvicorn.pid"

# Start Next.js dev server
echo "[start] launching Next.js dev server -> $NEXT_LOG"
(
  cd "$WEB_DIR"
  nohup env NEXT_PUBLIC_MAZE_API_BASE="$MAZE_API_BASE_URL" \
    npm run dev -- --turbo --hostname 0.0.0.0 --port "$NEXT_PORT" \
    >"$NEXT_LOG" 2>&1 &
  echo $! > "$LOG_DIR/next.pid"
)

sleep 3

resolve_ip() {
  if [[ -n "${LABYRINTH_HOST_IP:-}" ]]; then
    printf '%s' "$LABYRINTH_HOST_IP"
    return
  fi

  python3 <<'PY' 2>/dev/null || echo "127.0.0.1"
import socket
host_ip = "127.0.0.1"
try:
  with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
    s.connect(("8.8.8.8", 80))
    host_ip = s.getsockname()[0]
except OSError:
  pass
print(host_ip)
PY
}

HOST_IP="$(resolve_ip)"

echo
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✓ MAZE INITIALIZED"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo
echo "  API Server:   http://$HOST_IP:$API_PORT"
echo "  Next.js UI:   http://$HOST_IP:$NEXT_PORT"
echo
echo "  Logs:"
echo "    API:  tail -f $API_LOG"
echo "    UI:   tail -f $NEXT_LOG"
echo
echo "Press Ctrl+C in each terminal to stop, or run ./stop_maze.sh"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
