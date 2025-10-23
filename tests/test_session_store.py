"""Tests for session storage and persistence."""
import tempfile
from pathlib import Path
import pytest

from labyrinth.state_store import SessionStore
from labyrinth.server import StorySession, Paragraph


def test_session_store_save_and_load():
    """Test basic session save and load operations."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = SessionStore(Path(tmpdir) / "test.db")
        
        # Create a test session
        session = StorySession(
            id="test-session-1",
            profile_name="TestUser",
            scene_id="chapter_one.arrival",
            emotional_track="glitchy"
        )
        
        # Add some paragraphs
        session.add_paragraphs([
            Paragraph(id="p1", text="First paragraph", mutations=[]),
            Paragraph(id="p2", text="Second paragraph", mutations=[]),
        ])
        
        # Save the session
        store.save_session(session.id, session)
        
        # Load it back
        loaded_session = store.load_session(session.id)
        
        assert loaded_session is not None
        assert loaded_session.id == session.id
        assert loaded_session.profile_name == session.profile_name
        assert loaded_session.scene_id == session.scene_id
        assert len(loaded_session.paragraphs) == 2
        assert loaded_session.paragraphs[0].text == "First paragraph"
        assert loaded_session.paragraphs[1].text == "Second paragraph"


def test_session_store_update():
    """Test updating an existing session."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = SessionStore(Path(tmpdir) / "test.db")
        
        # Create and save a session
        session = StorySession(
            id="test-session-2",
            profile_name="TestUser",
            scene_id="chapter_one.arrival"
        )
        session.add_paragraphs([
            Paragraph(id="p1", text="First paragraph", mutations=[]),
        ])
        store.save_session(session.id, session)
        
        # Update the session
        session.add_paragraphs([
            Paragraph(id="p2", text="Second paragraph", mutations=[]),
        ])
        session.scene_id = "chapter_one.fork"
        store.save_session(session.id, session)
        
        # Load and verify
        loaded_session = store.load_session(session.id)
        
        assert loaded_session is not None
        assert loaded_session.scene_id == "chapter_one.fork"
        assert len(loaded_session.paragraphs) == 2


def test_session_store_delete():
    """Test deleting a session."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = SessionStore(Path(tmpdir) / "test.db")
        
        # Create and save a session
        session = StorySession(
            id="test-session-3",
            profile_name="TestUser"
        )
        store.save_session(session.id, session)
        
        # Verify it exists
        loaded_session = store.load_session(session.id)
        assert loaded_session is not None
        
        # Delete it
        store.delete_session(session.id)
        
        # Verify it's gone
        loaded_session = store.load_session(session.id)
        assert loaded_session is None


def test_session_store_nonexistent():
    """Test loading a nonexistent session."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = SessionStore(Path(tmpdir) / "test.db")
        
        loaded_session = store.load_session("nonexistent-id")
        assert loaded_session is None


def test_session_store_with_history():
    """Test storing and loading session history."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = SessionStore(Path(tmpdir) / "test.db")
        
        # Create session with history
        session = StorySession(
            id="test-session-4",
            profile_name="TestUser"
        )
        session.history = [
            {"type": "decision", "direction": "left", "scene": "chapter_one.fork"},
            {"type": "decision", "direction": "right", "scene": "chapter_one.deeper"},
        ]
        
        store.save_session(session.id, session)
        loaded_session = store.load_session(session.id)
        
        assert loaded_session is not None
        assert len(loaded_session.history) == 2
        assert loaded_session.history[0]["direction"] == "left"


def test_session_store_with_flags():
    """Test storing and loading session flags."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = SessionStore(Path(tmpdir) / "test.db")
        
        # Create session with various flags
        session = StorySession(
            id="test-session-5",
            profile_name="TestUser"
        )
        session.pending_decision = True
        session.allow_registration = True
        session.story_complete = False
        
        store.save_session(session.id, session)
        loaded_session = store.load_session(session.id)
        
        assert loaded_session is not None
        assert loaded_session.pending_decision is True
        assert loaded_session.allow_registration is True
        assert loaded_session.story_complete is False


def test_session_store_migration():
    """Test migration from old 'payload' column to new 'data' column."""
    import sqlite3
    
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        
        # Create an old-style database with 'payload' column
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            """
            CREATE TABLE sessions (
                id TEXT PRIMARY KEY,
                payload TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "INSERT INTO sessions (id, payload) VALUES (?, ?)",
            ("test-session", '{"id": "test-session", "profile_name": "TestUser", "scene_id": "chapter_one.arrival", "emotional_track": "glitchy", "next_scene_id": null, "pending_decision": false, "allow_registration": false, "story_complete": false, "paragraphs": [], "history": []}')
        )
        conn.commit()
        conn.close()
        
        # Now initialize the store, which should trigger migration
        store = SessionStore(db_path)
        
        # Verify we can load the migrated data
        session = store.load_session("test-session")
        assert session is not None
        assert session.id == "test-session"
        assert session.profile_name == "TestUser"
