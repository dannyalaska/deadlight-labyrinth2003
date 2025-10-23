# Deadlight 2003 — Chapter One Teaser

Python-backed teaser for the AI Labyrinth project. FastAPI serves the static chapter experience plus JSON endpoints that drive the interactive flow.

## Setup
- Install Python 3.11+ and [Poetry](https://python-poetry.org/).
- Install dependencies: `poetry install`.
- Copy the sample env: `cp .env.example .env` and drop your real key(s) in there (kept out of git).

## Run Locally
- (Optional) export `ANTHROPIC_API_KEY` to let the maze call Claude/Opus for live narrative:
  - macOS/Linux: `export ANTHROPIC_API_KEY=sk-ant-...`
  - Windows (PowerShell): `$Env:ANTHROPIC_API_KEY = "sk-ant-..."`
- Start the server: `poetry run uvicorn labyrinth.server:app --reload`.
- Open `http://127.0.0.1:8000` in a desktop browser.

### Streamlit Prototype
- With the API running, launch the Streamlit UI: `poetry run streamlit run streamlit_app.py`.
- The sidebar shows live scene metadata (scene id, emotional track, maze theme) and exposes advance/decision controls for desktop testing.
- Update `MAZE_API_BASE` in `.env` if your FastAPI server runs on a different host/port.
- One-liner helper: `./start_labyrinth.sh --open-ui` spins up both services (uses Poetry when available).

## Testing On Phone
- Find your local IP (e.g., `ipconfig getifaddr en0` on macOS).
- Start the server for LAN access: `poetry run uvicorn labyrinth.server:app --host 0.0.0.0 --port 8000`.
- On your phone (same Wi-Fi), open `http://YOUR_IP:8000`.
- iOS Safari needs tilt permission; tap “Enable Tilt Controls” when prompted.

## Tests
- Run the automated suite: `poetry run pytest`.
- Functional coverage exercises the FastAPI scene flow, ensuring decisions and maze branches behave as expected.

## Story Controls
- Scene scaffolding lives in `labyrinth/story_blueprint.py` (scene ids, prompts, emotional tracks, decision wiring).
- Sessions + branching are handled in `labyrinth/server.py` by `SessionManager` using those blueprints.
- Without an API key the maze falls back to `StaticStoryGenerator` so you can demo offline.
- With a key, `ClaudeStoryGenerator` asks Anthropic for JSON describing each beat; tweak the system prompt and request payload inside that class.
- Paragraph mutations for look-back behaviour are queued per paragraph; update lists in the generator helpers when you want new glitches.
- Session state and history persist in the SQLite path pointed to by `LABYRINTH_DB_PATH` (defaults to `data/maze_state.db`). Remove the file if you want a clean slate.
- Enable LangSmith tracing by setting `LANGSMITH_TRACING=1` (and `LANGCHAIN_API_KEY`) to capture generation diagnostics during user tests.
