"""Claude API generation for Deadlight 2003 — forum posts and legacy prose."""

from __future__ import annotations

import json
import os
import logging
import re
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_client = None


def _get_client():
    global _client
    if _client is None:
        try:
            from anthropic import Anthropic
            _client = Anthropic()
        except Exception as exc:
            logger.warning("Could not initialise Anthropic client: %s", exc)
            return None
    return _client


# --------------------------------------------------------------------------- #
# Template helpers
# --------------------------------------------------------------------------- #

def _populate_templates(text: str, profile: Dict[str, str]) -> str:
    """Replace {{key}} placeholders in a string."""
    result = text
    for key, value in profile.items():
        result = result.replace("{{" + key + "}}", str(value))
    return result


def _strip_json_fences(text: str) -> str:
    """Strip markdown code fences from Claude's response to get raw JSON."""
    text = text.strip()
    # Remove ```json ... ``` or ``` ... ```
    if text.startswith("```"):
        # Find end of opening fence line
        first_newline = text.index("\n") if "\n" in text else len(text)
        text = text[first_newline + 1:]
        if text.endswith("```"):
            text = text[:-3]
    return text.strip()


# --------------------------------------------------------------------------- #
# Forum post generation
# --------------------------------------------------------------------------- #

_FALLBACK_POSTS: List[dict] = [
    {
        "author": "sleeparchitect",
        "author_data": {"joined": "Nov 2002", "posts": 891},
        "date": "Nov 17, 2003 — 1:14am",
        "body": "anyone up",
    },
    {
        "author": "halflight_kid",
        "author_data": {"joined": "Oct 2002", "posts": 234},
        "date": "Nov 18, 2003 — 3:02am",
        "body": "yeah. this place feels weird at night. like it's holding its breath.",
    },
    {
        "author": "static_prayer",
        "author_data": {"joined": "Feb 2003", "posts": 445},
        "date": "Nov 19, 2003 — 2:45am",
        "body": "i keep coming back here even though i don't know why. i think we all do.",
    },
]


def generate_forum_posts(
    thread_data: dict,
    visit_count: int = 1,
    player_profile: Optional[Dict[str, str]] = None,
    story_bible: Optional[dict] = None,
) -> List[dict]:
    """Generate forum posts via Claude. Returns a list of post dicts.

    Falls back to placeholder posts on API failure.
    """
    profile = player_profile or {}
    bible = story_bible or {}

    client = _get_client()
    if client is None:
        logger.warning("No Anthropic client — using fallback posts")
        return _FALLBACK_POSTS[:]

    # Build system prompt from story bible
    system_prompt = bible.get("llm_system_prompt_base", "")
    if not system_prompt:
        system_prompt = (
            "You are generating forum posts for an early-2000s phpBB forum. "
            "Write like real people typed on forums at 2am in 2003. "
            "Return ONLY a JSON array of post objects."
        )
    system_prompt = _populate_templates(system_prompt, profile)

    # Build user prompt from thread_data's generation_prompt
    user_prompt = thread_data.get("generation_prompt", "")
    if not user_prompt:
        user_prompt = (
            f"Generate {thread_data.get('generated_post_count', 5)} forum posts "
            f"for the thread '{thread_data.get('thread_title', 'untitled')}'."
        )
    user_prompt = _populate_templates(user_prompt, profile)

    # Add visit context for regeneration variety
    if visit_count > 1:
        user_prompt += (
            f"\n\nThis is visit #{visit_count} to this thread. "
            "Generate DIFFERENT posts than you would otherwise — "
            "vary the songs, stories, and details. Keep the same usernames."
        )

    model = os.environ.get("DEADLIGHT_MODEL", "claude-sonnet-4-5-20241022")

    try:
        response = client.messages.create(
            model=model,
            max_tokens=2000,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        raw_text = response.content[0].text
        cleaned = _strip_json_fences(raw_text)
        posts = json.loads(cleaned)

        if not isinstance(posts, list):
            logger.error("Claude returned non-list JSON: %s", type(posts))
            return _FALLBACK_POSTS[:]

        return posts

    except json.JSONDecodeError as exc:
        logger.error("JSON parse error from Claude response: %s", exc)
        return _FALLBACK_POSTS[:]
    except Exception as exc:
        logger.error("Claude API error (forum posts): %s", exc)
        return _FALLBACK_POSTS[:]


# --------------------------------------------------------------------------- #
# Conversation reply generation (multi-turn still_here_03 thread)
# --------------------------------------------------------------------------- #

_FALLBACK_CONVERSATION_REPLIES = [
    "it's really you. i can't believe it. where are you even from. like originally. i always wondered.",
    "that's cool. what were you into back then. like what kept you up at 3am besides us.",
    "yeah. i remember. who did you think you were going to become. back when you still thought you could be anyone.",
    "you should look around. things have changed since you were last here.",
]


def generate_conversation_reply(
    exchange_number: int,
    max_exchanges: int,
    conversation_log: List[Dict[str, str]],
    player_profile: Optional[Dict[str, str]] = None,
    story_bible: Optional[dict] = None,
    conversation_config: Optional[dict] = None,
) -> str:
    """Generate still_here_03's response in a multi-turn reply conversation.

    Returns the plain text of the response (not JSON).
    Falls back to static responses on API failure.
    """
    profile = player_profile or {}
    config = conversation_config or {}
    fallback_idx = min(exchange_number - 1, len(_FALLBACK_CONVERSATION_REPLIES) - 1)

    client = _get_client()
    if client is None:
        logger.warning("No Anthropic client — using fallback conversation reply")
        return _FALLBACK_CONVERSATION_REPLIES[fallback_idx]

    # System prompt — from conversation config or default
    system_prompt = config.get("system_prompt", "")
    if not system_prompt:
        system_prompt = (
            "You are still_here_03, a presence on a dead phpBB forum called "
            "dreams_and_static. You posted 'we are so glad you're back' when "
            "the player returned. You are warm but something is slightly off. "
            "Respond in lowercase. 2-3 sentences max. No exclamation marks."
        )
    system_prompt = _populate_templates(system_prompt, profile)

    # Build user prompt with conversation history + exchange guidance
    exchanges = config.get("exchanges", [])
    exchange_guidance = ""
    if exchange_number <= len(exchanges):
        exchange_guidance = exchanges[exchange_number - 1].get("guidance", "")
    exchange_guidance = _populate_templates(exchange_guidance, profile)

    player_name = profile.get("player_name", "someone")

    user_prompt = "CONVERSATION SO FAR:\n"
    user_prompt += "[still_here_03]: we are so glad you're back\n"
    for msg in conversation_log:
        role_label = player_name if msg["role"] == "user" else "still_here_03"
        user_prompt += f"[{role_label}]: {msg['text']}\n"

    user_prompt += f"\nThis is exchange #{exchange_number} of {max_exchanges}.\n"
    if exchange_guidance:
        user_prompt += f"\nGUIDANCE FOR THIS EXCHANGE:\n{exchange_guidance}\n"
    user_prompt += (
        "\nRespond as still_here_03. Return ONLY the text of your response — "
        "no JSON, no formatting, no quotation marks. 2-3 sentences maximum."
    )

    model = os.environ.get("DEADLIGHT_MODEL", "claude-sonnet-4-5-20241022")

    try:
        response = client.messages.create(
            model=model,
            max_tokens=300,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        text = response.content[0].text.strip()
        # Strip any accidental quotes Claude might wrap it in
        if text.startswith('"') and text.endswith('"'):
            text = text[1:-1]
        return text
    except Exception as exc:
        logger.error("Conversation reply generation failed: %s", exc)
        return _FALLBACK_CONVERSATION_REPLIES[fallback_idx]


# --------------------------------------------------------------------------- #
# Legacy prose generation (kept for backward compatibility)
# --------------------------------------------------------------------------- #

def generate_prose(
    scene_data: dict,
    visit_count: int = 1,
    player_profile: Optional[Dict[str, str]] = None,
    story_bible: Optional[dict] = None,
    history: Optional[List[dict]] = None,
) -> str:
    """Generate scene prose via Claude. Falls back to prompt_seed on error."""
    profile = player_profile or {}
    bible = story_bible or {}
    hist = history or []

    # Static scenes bypass Claude entirely
    if scene_data.get("static_content"):
        return _populate_templates(scene_data.get("prompt_seed", ""), profile)

    client = _get_client()
    if client is None:
        return _populate_templates(scene_data.get("prompt_seed", ""), profile)

    system_prompt = _build_system_prompt(bible, profile)
    user_prompt = _build_scene_prompt(scene_data, visit_count, profile, hist)

    model = os.environ.get("DEADLIGHT_MODEL", "claude-sonnet-4-5-20241022")

    try:
        response = client.messages.create(
            model=model,
            max_tokens=800,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return response.content[0].text
    except Exception as exc:
        logger.error("Claude API error: %s", exc)
        return _populate_templates(scene_data.get("prompt_seed", ""), profile)


def _build_system_prompt(bible: dict, profile: Dict[str, str]) -> str:
    base = bible.get("llm_system_prompt_base", "")
    if not base:
        base = (
            "You are generating prose for DEADLIGHT, an interactive horror narrative. "
            "Write in second-person present tense. The horror is implication, not explanation. "
            "Output ONLY the scene prose — no metadata, no scene titles, no stage directions."
        )
    return _populate_templates(base, profile)


def _build_scene_prompt(
    scene: dict,
    visit_count: int,
    profile: Dict[str, str],
    history: List[dict],
) -> str:
    parts: list[str] = []

    parts.append("Generate the prose for this scene. Output ONLY the prose the reader will see — no titles, no labels, no markdown headers.")
    parts.append(f"Scene: {scene.get('title', scene.get('id', 'unknown'))}")
    parts.append(f"Visit count: {visit_count}")
    parts.append(f"Form level: {scene.get('form_level', 'subtle')}")

    if scene.get("length_guidance"):
        parts.append(f"Length: {scene['length_guidance']}")

    parts.append(f"\n--- SCENE SEED ---\n{scene.get('prompt_seed', '')}")

    if scene.get("narrative_beats"):
        parts.append("\n--- NARRATIVE BEATS (all must appear) ---")
        for i, beat in enumerate(scene["narrative_beats"], 1):
            parts.append(f"{i}. {beat}")

    if scene.get("atmosphere_cues"):
        cues = scene["atmosphere_cues"]
        parts.append("\n--- ATMOSPHERE (draw from these) ---")
        for category, items in cues.items():
            if isinstance(items, list):
                parts.append(f"{category}: {', '.join(items)}")

    if scene.get("forbidden"):
        parts.append("\n--- FORBIDDEN ---")
        for f in scene["forbidden"]:
            parts.append(f"- {f}")

    if visit_count > 1 and scene.get("mutation_rules"):
        rules = scene["mutation_rules"]
        key = f"visit_{min(visit_count, 3)}"
        if key in rules:
            parts.append(f"\n--- MUTATION (visit #{visit_count}) ---")
            parts.append(rules[key])

    if scene.get("personal_hook_active") and scene.get("personal_hook_instruction"):
        instruction = _populate_templates(scene["personal_hook_instruction"], profile)
        parts.append(f"\n--- PERSONAL HOOK ---\n{instruction}")

    form_level = scene.get("form_level", "subtle")
    if form_level == "moderate":
        parts.append("\n--- FORMATTING ---")
        parts.append("Include 1-2 researcher margin notes as [NOTE: ...] within the prose.")
    elif form_level == "full":
        parts.append("\n--- FORMATTING ---")
        parts.append("The prose IS the maze. Use structural tricks.")

    if scene.get("form_directives"):
        parts.append("Form directives: " + ", ".join(scene["form_directives"]))

    if history:
        recent = history[-5:]
        parts.append("\n--- RECENT HISTORY ---")
        for h in recent:
            parts.append(f"- {h.get('type', 'scene')}: {h.get('scene_id', '')} {h.get('title', '')}")

    return _populate_templates("\n".join(parts), profile)
