# Deadlight 2003 — Streamlit Console Guide

The Streamlit experience is now a thin console wrapper around the same JSON-driven API used by the web UI. It exists so writers can test branches quickly without deploying the static site.

---

## Starting the Console

```bash
poetry run streamlit run streamlit_app_v2.py
```

Optionally set `MAZE_API_BASE` if the FastAPI server lives somewhere other than `http://127.0.0.1:8000`.

---

## What You Get

- Scene title, goal caption, and body rendered as quoted paragraphs.
- Continue button advances along default transitions until a branch.
- Branch buttons appear when `pending_branch` is true; labels mirror the API (`label → target_scene_title`).
- Registration form shows once the story exposes its CTA.

All state lives in `st.session_state["maze_session"]`. Reloading the app boots a fresh session unless you persist that key manually.

---

## Helper Functions

`streamlit_app_v2.py` exposes small helpers that tests (and future integrations) can call directly:

- `init_session(profile_name=None)` — Seeds a session via `POST /api/session` and caches it.
- `send_progress(event, direction=None)` — Calls `POST /api/progress` and updates cached state.
- `register_reader(name, email)` — POSTs to `/api/register`, updating the session if the server echoes it back.

Each helper surfaces errors through `st.error(...)` so failures are visible during interactive use.

---

## Extending the Console

Ideas for future polish:

1. **Scene metadata** — Display mood/style badges from `scene` payload.
2. **History panel** — Show `session["history"]` for quick debugging.
3. **Tilt simulator** — Add buttons to mimic left/right tilt decisions when testing on desktop.
4. **Session export** — Dump session + history to JSON for design reviews.

Because the underlying API is deterministic, the console stays nimble—no injected CSS or JavaScript required. Focus stays on narrative structure rather than presentation.
