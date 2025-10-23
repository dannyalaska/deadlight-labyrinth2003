#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.env"
LOG_DIR="$SCRIPT_DIR/logs"
API_LOG="$LOG_DIR/api.log"
STREAMLIT_LOG="$LOG_DIR/streamlit.log"
DB_DIR="$SCRIPT_DIR/data"

usage() {
  cat <<'EOF'
Usage: ./start_labyrinth.sh [--api-only|--ui-only]

Bootstraps the Deadlight 2003 prototype:
  • installs dependencies (prefers Poetry, falls back to .venv + pip)
  • loads environment variables from .env if present
  • starts FastAPI (uvicorn) and Streamlit dashboards in background

Options:
  --api-only      start only the uvicorn server
  --ui-only       start only the Streamlit app (requires API already running)
  --open-ui       open the Streamlit UI in your default browser once running
  -h, --help      show this help message
EOF
}

API_ONLY=false
UI_ONLY=false
OPEN_UI=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --api-only) API_ONLY=true ;;
    --ui-only) UI_ONLY=true ;;
    --open-ui) OPEN_UI=true ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      exit 1
      ;;
  esac
  shift
done

if $API_ONLY && $UI_ONLY; then
  echo "Cannot use --api-only and --ui-only together." >&2
  exit 1
fi

mkdir -p "$LOG_DIR" "$DB_DIR"

STREAMLIT_PORT_VALUE="${STREAMLIT_PORT:-8501}"

USE_POETRY=false
if command -v poetry >/dev/null 2>&1; then
  USE_POETRY=true
fi

if $USE_POETRY; then
  if [[ "${SKIP_REQUIREMENTS:-0}" != "1" ]]; then
    echo "[bootstrap] installing dependencies via Poetry..."
    poetry install >/dev/null
  else
    echo "[bootstrap] skipping poetry install (SKIP_REQUIREMENTS=1)"
  fi
else
  echo "[warn] Poetry not found; falling back to local virtualenv"
  VENV_DIR="$SCRIPT_DIR/.venv"
  if [[ ! -d "$VENV_DIR" ]]; then
    echo "[bootstrap] creating virtual environment..."
    python3 -m venv "$VENV_DIR"
  fi
  # shellcheck disable=SC1090
  source "$VENV_DIR/bin/activate"
  if [[ "${SKIP_REQUIREMENTS:-0}" != "1" ]]; then
    echo "[bootstrap] installing requirements..."
    pip install --upgrade pip >/dev/null
    pip install -r "$SCRIPT_DIR/requirements.txt" >/dev/null
  fi
  ensure_module() {
    local module="$1"
    if ! python -c "import ${module}" >/dev/null 2>&1; then
      echo "[bootstrap] installing missing module: ${module}"
      pip install "${module}" >/dev/null
    fi
  }
  ensure_module uvicorn
  ensure_module streamlit
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

start_api() {
  echo "[start] launching FastAPI (uvicorn) -> $API_LOG"
  if $USE_POETRY; then
    nohup poetry run uvicorn labyrinth.server:app --reload --host 0.0.0.0 --port "${PORT:-8000}" \
      >"$API_LOG" 2>&1 &
  else
    nohup python -m uvicorn labyrinth.server:app --reload --host 0.0.0.0 --port "${PORT:-8000}" \
      >"$API_LOG" 2>&1 &
  fi
  echo $! > "$LOG_DIR/uvicorn.pid"
}

start_ui() {
  echo "[start] launching Streamlit -> $STREAMLIT_LOG"
  if $USE_POETRY; then
    nohup poetry run streamlit run "$SCRIPT_DIR/streamlit_app.py" \
      --server.port "$STREAMLIT_PORT_VALUE" \
      --server.address 0.0.0.0 \
      --server.headless true \
      >"$STREAMLIT_LOG" 2>&1 &
  else
    nohup python -m streamlit run "$SCRIPT_DIR/streamlit_app.py" \
      --server.port "$STREAMLIT_PORT_VALUE" \
      --server.address 0.0.0.0 \
      --server.headless true \
      >"$STREAMLIT_LOG" 2>&1 &
  fi
  echo $! > "$LOG_DIR/streamlit.pid"
}

open_ui_browser() {
  local url="http://localhost:${STREAMLIT_PORT_VALUE}"
  echo "[open] launching browser at $url"
  if $USE_POETRY; then
    poetry run python -m webbrowser "$url" >/dev/null 2>&1 || true
  else
    python -m webbrowser "$url" >/dev/null 2>&1 || true
  fi
}

if ! $UI_ONLY; then
  start_api
fi

if ! $API_ONLY; then
  start_ui
  if [[ "${STREAMLIT_OPEN_BROWSER:-0}" == "1" || "$OPEN_UI" == true ]]; then
    sleep 2
    open_ui_browser
  fi
fi

echo "[status] processes started."
if ! $UI_ONLY; then
  echo "  API log: $API_LOG"
fi
if ! $API_ONLY; then
  echo "  UI log:  $STREAMLIT_LOG"
fi
echo "[hint] use 'tail -f logs/api.log' or 'tail -f logs/streamlit.log' to watch output."
