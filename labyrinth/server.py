from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, EmailStr, Field

from .generate import generate_conversation_reply, generate_forum_posts, generate_prose
from .story_engine import (
    BranchRequired,
    InvalidProgress,
    SessionNotFound,
    StoryChapter,
    StoryEngine,
)

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

CHAPTER_FILE = BASE_DIR / "chapter_one_demo.json"
REGISTRATION_FILE = DATA_DIR / "registrations.json"
INDEX_FILE = BASE_DIR / "index.html"
SCRIPT_FILE = BASE_DIR / "script.js"
STYLES_FILE = BASE_DIR / "styles.css"


class SessionCreatePayload(BaseModel):
    profile_name: Optional[str] = Field(
        default=None,
        description="Preferred protagonist name used to personalise prompts.",
    )


class ProgressPayload(BaseModel):
    session_id: str = Field(..., description="Active story session identifier.")
    event: str = Field(
        ...,
        description="Progress event, e.g. 'advance', 'decision', 'cta', or 'link'.",
    )
    direction: Optional[str] = Field(
        default=None,
        description="Branch direction or target scene id for link events.",
    )


class IntakePayload(BaseModel):
    """Flexible intake — accepts any string key/value fields from the frontend."""

    session_id: str
    fields: Dict[str, str] = Field(
        default_factory=dict,
        description="Arbitrary key-value profile fields, e.g. {'player_name': 'vinyl_ghost'}",
    )


class ThreadReplyPayload(BaseModel):
    """Player reply in a multi-turn conversation thread."""

    session_id: str
    reply_text: str = Field(..., description="The text the player typed in the reply form.")


class RegistrationPayload(BaseModel):
    name: str
    email: EmailStr
    session_id: Optional[str] = None


# --------------------------------------------------------------------------- #
# Template helpers
# --------------------------------------------------------------------------- #

def _populate_templates(obj: Any, profile: Dict[str, str]) -> Any:
    """Recursively walk dicts/lists/strings and replace {{key}} placeholders."""
    if isinstance(obj, str):
        result = obj
        for key, value in profile.items():
            result = result.replace("{{" + key + "}}", str(value))
        return result
    if isinstance(obj, dict):
        return {k: _populate_templates(v, profile) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_populate_templates(item, profile) for item in obj]
    return obj


# --------------------------------------------------------------------------- #
# Engine
# --------------------------------------------------------------------------- #

def _load_engine() -> StoryEngine:
    chapter = StoryChapter.from_path(CHAPTER_FILE)
    return StoryEngine(chapter)


engine = _load_engine()

app = FastAPI(
    title="Deadlight 2003 API",
    version="0.4.0",
    description="Forum engine with Claude-powered post generation.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------------------------------- #
# Enrichment — dispatches by page_type
# --------------------------------------------------------------------------- #

def _attach_hook_post(
    thread_data: dict,
    scene_thread_data: dict,
    posts_list: list,
) -> None:
    """Either append hook_post to posts_list immediately, or stash it as
    delayed_hook_post (when hook_post.delay_ms is set) for the frontend timer."""
    hook_post = thread_data.get("hook_post")
    if not hook_post:
        return
    if hook_post.get("delay_ms"):
        # Frontend will inject this after delay_ms milliseconds
        scene_thread_data["delayed_hook_post"] = hook_post
    else:
        posts_list.append(hook_post)


def _enrich_snapshot(session_state, snapshot: dict) -> dict:
    """Enrich a snapshot based on the scene's page_type."""
    scene_dict = snapshot["scene"]
    page_type = scene_dict.get("page_type", "prose")
    profile = session_state.player_profile
    scene_id = scene_dict["id"]
    raw_scene = engine.chapter.get_raw_scene(scene_id)

    if page_type == "forum_index":
        # Static thread listing — just populate templates in forum_data
        if scene_dict.get("forum_data"):
            scene_dict["forum_data"] = _populate_templates(
                scene_dict["forum_data"], profile
            )

    elif page_type == "forum_thread":
        thread_data = scene_dict.get("thread_data")
        if thread_data:
            # Populate templates in all thread_data fields
            thread_data = _populate_templates(thread_data, profile)
            scene_dict["thread_data"] = thread_data

            if not raw_scene.get("static_content"):
                # Generate dynamic posts via Claude
                try:
                    generated_posts = generate_forum_posts(
                        thread_data=thread_data,
                        visit_count=session_state.visit_counts.get(scene_id, 1),
                        player_profile=profile,
                        story_bible=engine.chapter.story_bible,
                    )
                    # Merge: static_posts + generated + hook_post (unless delayed)
                    all_posts = list(thread_data.get("static_posts", []))
                    all_posts.extend(generated_posts)
                    _attach_hook_post(thread_data, scene_dict["thread_data"], all_posts)
                    scene_dict["thread_data"]["posts"] = all_posts
                except Exception as exc:
                    logger.error("Forum post generation failed for %s: %s", scene_id, exc)
                    # Fallback: just use static posts + hook
                    all_posts = list(thread_data.get("static_posts", []))
                    _attach_hook_post(thread_data, scene_dict["thread_data"], all_posts)
                    scene_dict["thread_data"]["posts"] = all_posts
            else:
                # Static thread — just combine existing posts
                all_posts = list(thread_data.get("static_posts", []))
                _attach_hook_post(thread_data, scene_dict["thread_data"], all_posts)
                scene_dict["thread_data"]["posts"] = all_posts

    elif page_type == "profile_page":
        # Populate templates in profile_data
        if scene_dict.get("profile_data"):
            scene_dict["profile_data"] = _populate_templates(
                scene_dict["profile_data"], profile
            )

    else:
        # Legacy prose page_type — keep old behaviour
        if raw_scene.get("static_content"):
            from .generate import _populate_templates as gen_populate
            raw_body = raw_scene.get("body") or raw_scene.get("prompt_seed", "")
            scene_dict["body"] = gen_populate(raw_body, profile)
        else:
            try:
                generated = generate_prose(
                    scene_data=raw_scene,
                    visit_count=session_state.visit_counts.get(scene_id, 1),
                    player_profile=profile,
                    story_bible=engine.chapter.story_bible,
                    history=session_state.history,
                )
                scene_dict["body"] = generated
            except Exception as exc:
                logger.error("Generation failed for scene %s: %s", scene_id, exc)

    return snapshot


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #

@app.get("/api/health")
def healthcheck() -> dict:
    return {"status": "ok"}


@app.get("/api/chapter")
def chapter_metadata() -> dict:
    chapter = engine.chapter
    return {
        "chapter_id": chapter.chapter_id,
        "title": chapter.title,
        "theme": chapter.theme,
        "global_mood": chapter.global_mood,
        "entrypoint": chapter.entrypoint,
        "scenes": [
            {
                "id": scene.id,
                "title": scene.title,
                "has_branching": bool(scene.branching_paths),
                "requires_device_orientation": scene.requires_device_orientation,
            }
            for scene in chapter.scenes
        ],
    }


@app.post("/api/session")
def start_session(payload: SessionCreatePayload) -> dict:
    session = engine.create_session(profile_name=payload.profile_name)
    snapshot = engine.snapshot(session)
    return _enrich_snapshot(session, snapshot)


@app.get("/api/session/{session_id}")
def get_session(session_id: str) -> dict:
    try:
        session = engine.get_session(session_id)
    except SessionNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    snapshot = engine.snapshot(session)
    return _enrich_snapshot(session, snapshot)


@app.post("/api/progress")
def progress(payload: ProgressPayload) -> dict:
    # Capture previous scene before progressing (for first-thread tracking)
    prev_scene_id = None
    try:
        prev_session = engine.get_session(payload.session_id)
        prev_scene_id = prev_session.current_scene_id
    except SessionNotFound:
        pass

    try:
        session = engine.progress(
            payload.session_id,
            payload.event,
            direction=payload.direction,
        )
    except SessionNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except BranchRequired as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except InvalidProgress as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Track which thread the player chose first from the forum index
    if (
        payload.event == "link"
        and prev_scene_id
        and prev_scene_id.startswith("forum_index")
        and "first_thread" not in session.player_profile
        and payload.direction
    ):
        session.player_profile["first_thread"] = payload.direction

    snapshot = engine.snapshot(session)
    return _enrich_snapshot(session, snapshot)


@app.post("/api/intake")
def intake(payload: IntakePayload) -> dict:
    """Store player profile data (flexible key-value fields)."""
    try:
        profile = {k: v for k, v in payload.fields.items() if v}
        engine.update_player_profile(payload.session_id, profile)
        return {"status": "accepted", "fields_stored": len(profile)}
    except SessionNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/thread_reply")
def thread_reply(payload: ThreadReplyPayload) -> dict:
    """Multi-turn conversation in a thread (e.g. still_here_03 reply loop)."""
    try:
        session = engine.get_session(payload.session_id)
    except SessionNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    # Append user's message to conversation log
    session.conversation_log.append({"role": "user", "text": payload.reply_text})

    # Read conversation config from the current scene
    raw_scene = engine.chapter.get_raw_scene(session.current_scene_id)
    thread_data = raw_scene.get("thread_data", {})
    live_reply = thread_data.get("live_reply", {})
    conversation_config = live_reply.get("conversation", {})

    # Store reply text as intake — use exchange-specific intake_key if configured
    exchange_number_so_far = len([m for m in session.conversation_log if m["role"] == "user"])
    exchanges = conversation_config.get("exchanges", [])
    intake_key = "player_post"
    if exchange_number_so_far <= len(exchanges):
        exchange_cfg = exchanges[exchange_number_so_far - 1]
        intake_key = exchange_cfg.get("intake_key", intake_key)
    engine.update_player_profile(payload.session_id, {intake_key: payload.reply_text})

    profile = session.player_profile
    max_exchanges = conversation_config.get("max_exchanges", 2)
    exchange_number = len([m for m in session.conversation_log if m["role"] == "user"])
    is_final = exchange_number >= max_exchanges

    # Generate still_here_03's response via Claude
    response_text = generate_conversation_reply(
        exchange_number=exchange_number,
        max_exchanges=max_exchanges,
        conversation_log=session.conversation_log,
        player_profile=profile,
        story_bible=engine.chapter.story_bible,
        conversation_config=_populate_templates(conversation_config, profile),
    )

    # Append NPC response to conversation log
    session.conversation_log.append({"role": "npc", "text": response_text})

    # Build the post
    post = {
        "author": "still_here_03",
        "author_data": {"joined": "Mar 2003", "posts": 2 + exchange_number},
        "date": "just now",
        "body": response_text,
    }

    # On final exchange, inject body_links and ensure link text is in body
    if is_final:
        final_links = conversation_config.get("final_body_links", [])
        if final_links:
            populated_links = _populate_templates(final_links, profile)
            post["body_links"] = populated_links
            # Ensure the link text appears in the body
            for link in populated_links:
                link_text = link.get("text", "")
                if link_text and link_text not in response_text:
                    post["body"] = response_text + f"\n\n{link_text}."

    return {
        "post": _populate_templates(post, profile),
        "exchange_count": exchange_number,
        "conversation_complete": is_final,
    }


@app.post("/api/register")
def register(payload: RegistrationPayload) -> dict:
    registration_record = {
        "name": payload.name,
        "email": payload.email,
        "session_id": payload.session_id,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }

    existing: list = []
    if REGISTRATION_FILE.exists():
        try:
            existing = json.loads(REGISTRATION_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = []
    existing.append(registration_record)
    REGISTRATION_FILE.write_text(json.dumps(existing, indent=2), encoding="utf-8")

    if payload.session_id:
        try:
            session = engine.mark_registered(payload.session_id)
        except SessionNotFound:
            session = None
    else:
        session = None

    response = {"status": "registered"}
    if session:
        snapshot = engine.snapshot(session)
        response["session"] = _enrich_snapshot(session, snapshot)
    return response


# --------------------------------------------------------------------------- #
# Static file serving
# --------------------------------------------------------------------------- #

@app.get("/", include_in_schema=False)
def serve_index() -> FileResponse:
    if not INDEX_FILE.exists():
        raise HTTPException(status_code=404, detail="index.html not found")
    return FileResponse(INDEX_FILE)


@app.get("/script.js", include_in_schema=False)
def serve_script() -> FileResponse:
    if not SCRIPT_FILE.exists():
        raise HTTPException(status_code=404, detail="script.js not found")
    return FileResponse(SCRIPT_FILE)


@app.get("/styles.css", include_in_schema=False)
def serve_styles() -> FileResponse:
    if not STYLES_FILE.exists():
        raise HTTPException(status_code=404, detail="styles.css not found")
    return FileResponse(STYLES_FILE)
