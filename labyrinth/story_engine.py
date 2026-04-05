from __future__ import annotations

import json
import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional


class SessionNotFound(RuntimeError):
    """Raised when a requested session does not exist."""


class InvalidProgress(RuntimeError):
    """Raised when an invalid progress event is submitted."""


class BranchRequired(RuntimeError):
    """Raised when a scene expects a branch decision before advancing."""


@dataclass(frozen=True)
class SceneDefinition:
    """Immutable representation of a scene loaded from chapter JSON."""

    id: str
    title: str
    goal: str
    prompt_seed: str
    style: Optional[str] = None
    length: Optional[str] = None
    theme: Optional[str] = None
    transitions: Dict[str, str] = field(default_factory=dict)
    branching_paths: Dict[str, str] = field(default_factory=dict)
    requires_device_orientation: bool = False
    form_level: str = "subtle"
    interaction_type: str = "continue"
    static_content: bool = False
    page_type: str = "prose"

    def is_terminal(self) -> bool:
        """True when the scene has no exits or decisions."""
        return not self.transitions and not self.branching_paths


@dataclass
class SessionState:
    """Live session state tracked entirely in memory."""

    id: str
    profile_name: Optional[str]
    current_scene_id: str
    history: List[Dict[str, str]] = field(default_factory=list)
    pending_branch: bool = False
    story_complete: bool = False
    allow_registration: bool = False
    registered: bool = False
    visit_counts: Dict[str, int] = field(default_factory=dict)
    player_profile: Dict[str, str] = field(default_factory=dict)
    conversation_log: List[Dict[str, str]] = field(default_factory=list)


class StoryChapter:
    """A chapter composed of scene definitions."""

    def __init__(self, chapter_data: Dict):
        self.chapter_id: str = chapter_data["chapter_id"]
        self.title: str = chapter_data.get("title", "")
        self.theme: str = chapter_data.get("theme", "")
        self.global_mood: Optional[str] = chapter_data.get("global_mood")
        self.entrypoint: str = chapter_data["entrypoint"]
        self._scenes: Dict[str, SceneDefinition] = {}
        self._raw_scenes: Dict[str, dict] = {}
        self._raw_data: dict = chapter_data

        for scene_data in chapter_data.get("scenes", []):
            scene = SceneDefinition(
                id=scene_data["id"],
                title=scene_data.get("title", scene_data["id"]),
                goal=scene_data.get("goal", ""),
                prompt_seed=scene_data.get("prompt_seed", ""),
                style=scene_data.get("style"),
                length=scene_data.get("length"),
                theme=scene_data.get("theme"),
                transitions=scene_data.get("transitions", {}),
                branching_paths=scene_data.get("branching_paths", {}),
                requires_device_orientation=scene_data.get("requires_device_orientation", False),
                form_level=scene_data.get("form_level", "subtle"),
                interaction_type=scene_data.get("interaction_type", "continue"),
                static_content=scene_data.get("static_content", False),
                page_type=scene_data.get("page_type", "prose"),
            )
            self._scenes[scene.id] = scene
            self._raw_scenes[scene.id] = scene_data

    @classmethod
    def from_path(cls, path: Path | str) -> "StoryChapter":
        with Path(path).open("r", encoding="utf-8") as handle:
            raw_data = json.load(handle)
        return cls(raw_data)

    def get_scene(self, scene_id: str) -> SceneDefinition:
        try:
            return self._scenes[scene_id]
        except KeyError as exc:
            raise InvalidProgress(f"Unknown scene id '{scene_id}'") from exc

    def get_raw_scene(self, scene_id: str) -> dict:
        """Return the full JSON dict for a scene (used by generate.py)."""
        return self._raw_scenes.get(scene_id, {})

    @property
    def story_bible(self) -> dict:
        return self._raw_data.get("story_bible", {})

    @property
    def scenes(self) -> Iterable[SceneDefinition]:
        return self._scenes.values()


def _personalise_prompt(text: str, profile_name: Optional[str]) -> str:
    """Swap default protagonist with provided profile name."""
    if not profile_name:
        return text
    replacements = {
        "Ben": profile_name,
        "BEN": profile_name.upper(),
        "ben": profile_name.lower(),
    }
    result = text
    for needle, replacement in replacements.items():
        result = result.replace(needle, replacement)
    return result


class StoryEngine:
    """In-memory scene engine that follows the architecture guide."""

    def __init__(self, chapter: StoryChapter):
        self._chapter = chapter
        self._sessions: Dict[str, SessionState] = {}
        self._lock = threading.Lock()

    @property
    def chapter(self) -> StoryChapter:
        return self._chapter

    # ----------------------------------------------------------------------- #
    # Session lifecycle
    # ----------------------------------------------------------------------- #
    def create_session(self, profile_name: Optional[str] = None) -> SessionState:
        session_id = uuid.uuid4().hex
        session = SessionState(
            id=session_id,
            profile_name=profile_name,
            current_scene_id=self._chapter.entrypoint,
        )
        self._enter_scene(session, self._chapter.entrypoint, is_new=True)
        with self._lock:
            self._sessions[session_id] = session
        return session

    def restore_session(self, saved: Dict) -> SessionState:
        """Recreate a SessionState from a dict previously returned by to_dict()."""
        session = SessionState(
            id=saved["story_session_id"],
            profile_name=saved.get("player_profile", {}).get("player_name"),
            current_scene_id=saved["scene_id"],
            history=saved.get("history", []),
            player_profile=saved.get("player_profile", {}),
            conversation_log=saved.get("conversation_log", []),
            visit_counts=saved.get("visit_counts", {}),
            story_complete=saved.get("story_complete", False),
        )
        with self._lock:
            self._sessions[session.id] = session
        return session

    def session_to_dict(self, session: SessionState) -> Dict:
        """Serialise a SessionState to a plain dict for persistence."""
        return {
            "story_session_id": session.id,
            "scene_id": session.current_scene_id,
            "player_profile": session.player_profile,
            "conversation_log": session.conversation_log,
            "history": session.history,
            "visit_counts": session.visit_counts,
            "story_complete": session.story_complete,
        }

    def get_session(self, session_id: str) -> SessionState:
        with self._lock:
            session = self._sessions.get(session_id)
        if not session:
            raise SessionNotFound(f"No session with id '{session_id}'")
        return session

    def progress(self, session_id: str, event: str, *, direction: Optional[str] = None) -> SessionState:
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                raise SessionNotFound(f"No session with id '{session_id}'")
            scene = self._chapter.get_scene(session.current_scene_id)

            if event == "advance":
                if session.pending_branch:
                    raise BranchRequired(f"Scene '{scene.id}' expects a branch decision.")
                target = scene.transitions.get("default")
                if not target:
                    session.story_complete = True
                    return session
                self._enter_scene(session, target)
                return session

            if event == "decision":
                if not scene.branching_paths:
                    raise InvalidProgress(f"Scene '{scene.id}' does not offer branching paths.")
                if not direction:
                    raise InvalidProgress("A direction is required for decision events.")
                target = scene.branching_paths.get(direction)
                if not target:
                    raise InvalidProgress(f"Unknown branch direction '{direction}' for scene '{scene.id}'.")
                session.history.append(
                    {
                        "type": "decision",
                        "scene_id": scene.id,
                        "direction": direction,
                    }
                )
                self._enter_scene(session, target)
                return session

            if event == "cta":
                target = scene.transitions.get("cta")
                if target:
                    self._enter_scene(session, target)
                else:
                    session.story_complete = True
                return session

            if event == "link":
                if not direction:
                    raise InvalidProgress("A target scene is required for link events.")
                self._chapter.get_scene(direction)  # validates scene exists
                self._enter_scene(session, direction)
                return session

            raise InvalidProgress(f"Unsupported progress event '{event}'.")

    def update_player_profile(self, session_id: str, profile: Dict[str, str]) -> SessionState:
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                raise SessionNotFound(f"No session with id '{session_id}'")
            session.player_profile.update(profile)
            if profile.get("player_name"):
                session.profile_name = profile["player_name"]
            return session

    def mark_registered(self, session_id: str) -> SessionState:
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                raise SessionNotFound(f"No session with id '{session_id}'")
            session.registered = True
            return session

    # ----------------------------------------------------------------------- #
    # Serialisation helpers
    # ----------------------------------------------------------------------- #
    def snapshot(self, session: SessionState) -> Dict:
        scene = self._chapter.get_scene(session.current_scene_id)
        body = _personalise_prompt(scene.prompt_seed, session.profile_name)
        branch_options = []
        for direction, target_scene in scene.branching_paths.items():
            try:
                target_scene_title = self._chapter.get_scene(target_scene).title
            except InvalidProgress:
                target_scene_title = target_scene
            branch_options.append(
                {
                    "direction": direction,
                    "target_scene_id": target_scene,
                    "target_scene_title": target_scene_title,
                    "label": direction.replace("_", " ").upper(),
                }
            )

        # Get raw scene data for intake fields
        raw = self._chapter.get_raw_scene(session.current_scene_id)

        payload = {
            "chapter_id": self._chapter.chapter_id,
            "chapter_title": self._chapter.title,
            "session_id": session.id,
            "profile_name": session.profile_name,
            "scene": {
                "id": scene.id,
                "title": scene.title,
                "body": body,
                "style": scene.style,
                "form_level": scene.form_level,
                "form_directives": raw.get("form_directives", []),
                "interaction_type": scene.interaction_type,
                "requires_device_orientation": scene.requires_device_orientation,
                "static_content": scene.static_content,
                "page_type": scene.page_type,
                "intake_fields": raw.get("intake_fields"),
                "forum_data": raw.get("forum_data"),
                "thread_data": raw.get("thread_data"),
                "profile_data": raw.get("profile_data"),
                "body_links": raw.get("body_links"),
            },
            "pending_branch": session.pending_branch,
            "branching_paths": branch_options,
            "story_complete": session.story_complete,
            "allow_registration": session.allow_registration,
            "registered": session.registered,
            "history": session.history,
            "visit_count": session.visit_counts.get(session.current_scene_id, 1),
        }
        return payload

    # ----------------------------------------------------------------------- #
    # Internal helpers
    # ----------------------------------------------------------------------- #
    def _enter_scene(self, session: SessionState, scene_id: str, *, is_new: bool = False) -> None:
        scene = self._chapter.get_scene(scene_id)
        session.current_scene_id = scene.id
        session.pending_branch = bool(scene.branching_paths)
        session.allow_registration = "cta" in scene.transitions
        session.story_complete = scene.is_terminal() and not session.pending_branch

        # Track visit count
        session.visit_counts[scene_id] = session.visit_counts.get(scene_id, 0) + 1

        # Avoid duplicating entry in history when resuming the very first scene.
        if not session.history or session.history[-1].get("scene_id") != scene.id:
            session.history.append(
                {
                    "type": "scene",
                    "scene_id": scene.id,
                    "title": scene.title,
                }
            )

        if is_new:
            session.history[-1]["is_entrypoint"] = True
