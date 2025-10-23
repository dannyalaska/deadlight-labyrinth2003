from __future__ import annotations

import json
import logging
import sqlite3
import threading
from pathlib import Path
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
  from .server import Paragraph, StorySession

logger = logging.getLogger("deadlight.session")


class SessionStore:
  """SQLite-backed session persistence suitable for local runs and testing."""

  def __init__(self, db_path: Path):
    self.db_path = Path(db_path)
    self.db_path.parent.mkdir(parents=True, exist_ok=True)
    self._connection = sqlite3.connect(str(self.db_path), check_same_thread=False)
    self._lock = threading.Lock()
    self._init_schema()

  def _init_schema(self) -> None:
    """Initialize or migrate the database schema."""
    # Check if table exists and what columns it has
    cursor = self._connection.execute(
      "SELECT name FROM sqlite_master WHERE type='table' AND name='sessions'"
    )
    table_exists = cursor.fetchone() is not None
    
    if table_exists:
      # Check if we have the old 'payload' column
      cursor = self._connection.execute("PRAGMA table_info(sessions)")
      columns = {row[1] for row in cursor.fetchall()}
      
      if 'payload' in columns and 'data' not in columns:
        # Migrate from old schema
        logger.info("Migrating database schema from 'payload' to 'data' column")
        self._connection.execute(
          "ALTER TABLE sessions RENAME COLUMN payload TO data"
        )
        self._connection.commit()
    else:
      # Create new table with correct schema
      self._connection.execute(
        """
        CREATE TABLE IF NOT EXISTS sessions (
          id TEXT PRIMARY KEY,
          data TEXT NOT NULL
        )
        """
      )
      self._connection.commit()

  def save_session(self, session_id: str, session: StorySession) -> None:
    session_data = self._serialise_session(session)
    
    # Log session state changes
    logger.info(
        "Session %s state update - scene: %s, paragraphs: %d",
        session_id, session.scene_id, len(session.paragraphs)
    )
    
    with self._lock:
      self._connection.execute(
        "INSERT OR REPLACE INTO sessions (id, data) VALUES (?, ?)",
        (session_id, json.dumps(session_data)),
      )
      self._connection.commit()

  def load_session(self, session_id: str) -> Optional["StorySession"]:
    with self._lock:
      cursor = self._connection.execute(
        "SELECT data FROM sessions WHERE id = ?", (session_id,)
      )
      row = cursor.fetchone()
    if not row:
      return None
    data = json.loads(row[0])
    return self._deserialise_session(data)

  def delete_session(self, session_id: str) -> None:
    with self._lock, self._connection:
      self._connection.execute("DELETE FROM sessions WHERE id = ?", (session_id,))

  def _serialise_session(self, session: "StorySession") -> dict:
    return {
      "id": session.id,
      "profile_name": session.profile_name,
      "scene_id": session.scene_id,
      "emotional_track": session.emotional_track,
      "next_scene_id": session.next_scene_id,
      "pending_decision": session.pending_decision,
      "allow_registration": session.allow_registration,
      "story_complete": session.story_complete,
      "paragraphs": [
        {"id": p.id, "text": p.text, "mutations": p.mutations}
        for p in session.paragraphs
      ],
      "history": session.history,
    }

  def _deserialise_session(self, data: dict) -> "StorySession":
    from .server import Paragraph, StorySession  # local import to avoid cycle

    session = StorySession(
      id=data["id"],
      profile_name=data.get("profile_name"),
      scene_id=data.get("scene_id", "chapter_one.arrival"),
      emotional_track=data.get("emotional_track", "glitchy"),
      next_scene_id=data.get("next_scene_id"),
    )
    session.pending_decision = data.get("pending_decision", False)
    session.allow_registration = data.get("allow_registration", False)
    session.story_complete = data.get("story_complete", False)
    session.history = data.get("history", [])
    paragraphs = [
      Paragraph(id=item["id"], text=item["text"], mutations=item.get("mutations", []))
      for item in data.get("paragraphs", [])
    ]
    session.add_paragraphs(paragraphs)
    return session
