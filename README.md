# Deadlight 2003 — Chapter One Teaser

Python-backed teaser for the AI Labyrinth project. FastAPI serves the static chapter experience plus JSON endpoints that drive the interactive flow.

## Setup
- Install Python 3.11+ and [Poetry](https://python-poetry.org/).
- Install dependencies: `poetry install`.
- Copy the sample env: `cp .env.example .env` and drop your real key(s) in there (kept out of git).

## Run Locally
- Start the server: `poetry run uvicorn labyrinth.server:app --reload`.
- Open `http://127.0.0.1:8000` in a desktop browser.

### Streamlit Terminal UI
- Launch both the API and Terminal UI with `./start_terminal_ui.sh` (installs dependencies via Poetry when available).
- To run only the UI against an already-running API: `poetry run streamlit run streamlit_app_v2.py`.
- Features an eerie 2003 terminal aesthetic with scroll-based navigation, CRT scanlines, and text mutation effects.
- Update `MAZE_API_BASE` in `.env` if your FastAPI server runs on a different host/port.

## Testing On Phone
- Find your local IP (e.g., `ipconfig getifaddr en0` on macOS).
- Start the server for LAN access: `poetry run uvicorn labyrinth.server:app --host 0.0.0.0 --port 8000`.
- On your phone (same Wi-Fi), open `http://YOUR_IP:8000`.
- iOS Safari needs tilt permission; tap “Enable Tilt Controls” when prompted.

## Tests
- Run the automated suite: `poetry run pytest`.
- Functional coverage exercises the FastAPI scene flow, ensuring decisions and maze branches behave as expected.

## Story Controls
- Scene definitions live in `chapter_one_demo.json`. Update the JSON to add new beats, tweak transitions, or introduce branches.
- The in-memory engine in `labyrinth/story_engine.py` loads that JSON, manages sessions, and resolves branches / CTAs.
- `labyrinth/server.py` exposes FastAPI endpoints (`/api/session`, `/api/progress`, `/api/register`) used by both the web UI and Streamlit demo.
- The web UI (static `index.html` + `script.js`) consumes the API and handles tilt decisions when a scene requests them.
- The Streamlit companion (`streamlit_app_v2.py`) is a lightweight alternative interface that calls the same endpoints.
