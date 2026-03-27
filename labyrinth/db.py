"""
SQLite persistence layer for dreams_and_static beta auth + story progress.

Tables:
  users          — beta user accounts (username, hashed password, invite status)
  auth_sessions  — active login sessions (maps cookie token → username)
  story_progress — per-user story state (scene, profile, conversation history)
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Generator, Optional

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "beta.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    username     TEXT PRIMARY KEY,
    password_hash TEXT,
    invite_used  INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS auth_sessions (
    token        TEXT PRIMARY KEY,
    username     TEXT NOT NULL,
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    last_active  TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (username) REFERENCES users(username)
);

CREATE TABLE IF NOT EXISTS story_progress (
    username          TEXT PRIMARY KEY,
    story_session_id  TEXT NOT NULL,
    scene_id          TEXT NOT NULL,
    player_profile    TEXT NOT NULL DEFAULT '{}',
    conversation_log  TEXT NOT NULL DEFAULT '[]',
    history           TEXT NOT NULL DEFAULT '[]',
    visit_counts      TEXT NOT NULL DEFAULT '{}',
    story_complete    INTEGER NOT NULL DEFAULT 0,
    updated_at        TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (username) REFERENCES users(username)
);
"""


def init_db() -> None:
    """Create tables and ensure the data directory exists."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _connect() as conn:
        conn.executescript(_SCHEMA)


@contextmanager
def _connect() -> Generator[sqlite3.Connection, None, None]:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Users ────────────────────────────────────────────────────────────────────

def get_user(username: str) -> Optional[sqlite3.Row]:
    with _connect() as conn:
        return conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()


def ensure_user(username: str) -> None:
    """Insert user row if it doesn't already exist (no password, invite unused)."""
    with _connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO users (username) VALUES (?)", (username,)
        )


def mark_invite_used(username: str) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE users SET invite_used = 1 WHERE username = ?", (username,)
        )


def set_password_hash(username: str, hashed: str) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE username = ?",
            (hashed, username),
        )


def get_password_hash(username: str) -> Optional[str]:
    row = get_user(username)
    return row["password_hash"] if row else None


def is_invite_used(username: str) -> bool:
    row = get_user(username)
    return bool(row["invite_used"]) if row else True


# ── Auth sessions ─────────────────────────────────────────────────────────────

def create_auth_session(token: str, username: str) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO auth_sessions (token, username) VALUES (?, ?)",
            (token, username),
        )


def get_auth_session_user(token: str) -> Optional[str]:
    """Return username for a valid token, updating last_active. None if invalid."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT username FROM auth_sessions WHERE token = ?", (token,)
        ).fetchone()
        if row:
            conn.execute(
                "UPDATE auth_sessions SET last_active = datetime('now') WHERE token = ?",
                (token,),
            )
            return row["username"]
    return None


def delete_auth_session(token: str) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM auth_sessions WHERE token = ?", (token,))


# ── Story progress ────────────────────────────────────────────────────────────

def save_story_progress(username: str, state: Dict[str, Any]) -> None:
    """Upsert the full session state for a user."""
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO story_progress
                (username, story_session_id, scene_id, player_profile,
                 conversation_log, history, visit_counts, story_complete, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(username) DO UPDATE SET
                story_session_id = excluded.story_session_id,
                scene_id         = excluded.scene_id,
                player_profile   = excluded.player_profile,
                conversation_log = excluded.conversation_log,
                history          = excluded.history,
                visit_counts     = excluded.visit_counts,
                story_complete   = excluded.story_complete,
                updated_at       = datetime('now')
            """,
            (
                username,
                state["story_session_id"],
                state["scene_id"],
                json.dumps(state.get("player_profile", {})),
                json.dumps(state.get("conversation_log", [])),
                json.dumps(state.get("history", [])),
                json.dumps(state.get("visit_counts", {})),
                int(state.get("story_complete", False)),
            ),
        )


def load_story_progress(username: str) -> Optional[Dict[str, Any]]:
    """Return saved session state dict or None if no saved progress."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM story_progress WHERE username = ?", (username,)
        ).fetchone()
    if not row:
        return None
    return {
        "story_session_id": row["story_session_id"],
        "scene_id": row["scene_id"],
        "player_profile": json.loads(row["player_profile"]),
        "conversation_log": json.loads(row["conversation_log"]),
        "history": json.loads(row["history"]),
        "visit_counts": json.loads(row["visit_counts"]),
        "story_complete": bool(row["story_complete"]),
    }
