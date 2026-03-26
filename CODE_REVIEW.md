> Snapshot: October 27, 2025

# Deadlight 2003 — Architecture Notes

## Project Shape
- **Goal**: Tilt-reactive techno-horror vignette. Everything is now data-driven from `chapter_one_demo.json`.
- **Stack**: FastAPI backend + static HTML/JS frontend + optional Streamlit console.
- **LLM Dependency**: Removed. Narrative text comes from curated seeds that the engine personalises per reader.

---

## Backend
**Files**
- `labyrinth/story_engine.py` — JSON scene loader + in-memory session manager.
- `labyrinth/server.py` — FastAPI surface exposing health, chapter metadata, sessions, progress, and registration.

**Highlights**
- Chapter file parsed at boot; branch metadata preserved.
- Sessions are UUID keyed, tracked in memory (no SQLite). History is kept for potential analytics.
- `POST /api/progress` accepts `advance`, `decision`, or `cta` events. Branch blocking raises 409 to signal the UI to choose.
- Registration data persisted to `data/registrations.json`; sessions flagged as `registered` for UI updates.

**Future Hooks**
- Swap in Redis/SQLite session storage if persistence becomes necessary.
- Extend `story_engine` to support per-scene overlays (sound, assets) without touching API contracts.

---

## Frontend (Static)
**Files**
- `index.html` — Slim shell with chapter header, scene pane, control pane, and registration overlay.
- `styles.css` — CRT terminal aesthetic, responsive grid layout, tilt widget styling.
- `script.js` — Fetches metadata, starts sessions, renders scenes, handles tilt/decisions, registration, and snackbars.

**Behaviour**
- Tilt support auto-enabled on branch scenes that request orientation. Graceful fallback to buttons.
- Local storage caches profile for registration overlay convenience.
- Snackbar messaging replaces console errors for UX clarity.

---

## Streamlit Companion
**File**
- `streamlit_app_v2.py`

**Purpose**
- Gives writers/designers a quick console to test branches without running the static UI.
- Uses the same API helpers (`api_post`, `send_progress`, `register_reader`) and mirrors the minimal state kept in sessions.

---

## Data
- `story_app_architecture.md` — Vision doc that informed the rebuild.
- `chapter_one_demo.json` — Current authoritative scene graph. Update this file to add beats, change branch targets, or tweak text.

---

## Testing
- `tests/test_api.py` — Exercises the new API contract end-to-end: metadata, branching, CTA, registration.
- `tests/test_streamlit_helpers.py` — Unit covers Streamlit helper functions with a fake `st`.

`pytest` remains the quick regression check.

---

## Known Gaps & Next Steps
1. **Narrative Depth** — Currently uses prompt seeds as-is. Next iteration could stitch multiple JSON fields or run them through a chosen LLM offline.
2. **Session Persistence** — In-memory sessions reset on restart. Decide when to reintroduce a store.
3. **Asset Hooks** — JSON schema could be extended with audio/visual cues once assets exist.
4. **Analytics** — Branch + CTA interactions only logged in session history; piping to an analytics sink would inform future chapters.
