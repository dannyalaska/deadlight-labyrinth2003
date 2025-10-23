from __future__ import annotations

"""
High-level scene scaffolding for AI Labyrinth.

This module defines the modular beats that shape each chapter. The backend
feeds these blueprints into the generation layer (Claude or static fallback)
to orchestrate emotional branches and maze mechanics.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


EMOTIONAL_TRACKS = ["seductive", "bureaucratic", "glitchy", "panicked"]


@dataclass(frozen=True)
class Decision:
  direction: str  # e.g. "left" / "right"
  label: str
  emotional_track: str
  next_scene: str
  summary: str


@dataclass(frozen=True)
class SceneBlueprint:
  scene_id: str
  scene_prompt: str
  theme: str
  emotional_default: str
  decisions: List[Decision] = field(default_factory=list)
  terminal: bool = False
  unlocks_registration: bool = False


SCENES: Dict[str, SceneBlueprint] = {
  "chapter_one.arrival": SceneBlueprint(
    scene_id="chapter_one.arrival",
    scene_prompt=(
      "Introduce {{protagonist}} in June 2003. He is recently laid off yet hopeful. "
      "He discovers a strange job offer in his old AOL inbox. Set the tone: early internet "
      "nostalgia mixed with unease. Use sensory detail, focus on isolation, and hint that the "
      "maze watches him even now."
    ),
    theme="paragraphs flicker when re-read; memory feels unreliable",
    emotional_default="lonely",
  ),
  "chapter_one.departure": SceneBlueprint(
    scene_id="chapter_one.departure",
    scene_prompt=(
      "Describe {{protagonist}} preparing for the trip north. He prints MapQuest directions, "
      "packs a ThinkPad, and hears from a coworker whose voice resembles his ex. "
      "The road should feel like a ritual, with radio static and empty rest stops."
    ),
    theme="scrolling back mutates travel details",
    emotional_default="nostalgic",
  ),
  "chapter_one.maze_edge": SceneBlueprint(
    scene_id="chapter_one.maze_edge",
    scene_prompt=(
      "He reaches the property line. The asphalt exhales as he turns into the trees. "
      "Describe the maze awakening, branches forming, copper wires or pale light luring him. "
      "It should feel like the forest is a computer circuit."
    ),
    theme="tilt choice determines the corridor mood",
    emotional_default="glitchy",
    decisions=[
      Decision(
        direction="left",
        label="Follow The Humming Wire",
        emotional_track="seductive",
        next_scene="chapter_one.maze_depth_a",
        summary="Copper guidance, alluring and dangerous.",
      ),
      Decision(
        direction="right",
        label="Chase The Pale Light",
        emotional_track="panicked",
        next_scene="chapter_one.maze_depth_a",
        summary="CRT glow that edits reality, unsettling clarity.",
      ),
    ],
  ),
  "chapter_one.maze_depth_a": SceneBlueprint(
    scene_id="chapter_one.maze_depth_a",
    scene_prompt=(
      "Layer the maze interior. Mix analog tech (CRTs, fax machines, copper wire) with forest, "
      "and adapt to the emotional track: seductive, bureaucratic, glitchy, or panicked. "
      "LiveJournal comments, AIM away messages, or corporate memos appear as the walls."
    ),
    theme="scroll back to see altered history; paragraphs mutate heavily",
    emotional_default="glitchy",
  ),
  "chapter_one.maze_depth_b": SceneBlueprint(
    scene_id="chapter_one.maze_depth_b",
    scene_prompt=(
      "Deepen the maze. Show time distortions, duplicate coworkers, and artifacts from the protagonist's past. "
      "Lean harder into the current emotional track (seductive vs bureaucratic vs glitchy vs panicked). "
      "End with the sense that an office door is close."
    ),
    theme="memory sync errors; paragraphs drift toward panic when reread",
    emotional_default="glitchy",
  ),
  "chapter_one.office_threshold": SceneBlueprint(
    scene_id="chapter_one.office_threshold",
    scene_prompt=(
      "He finds the prefab office pod hunched in the ferns. Through the glass he glimpses "
      "a coworker who mirrors him. The lock demands registration before the door opens. "
      "End on a cliffhanger, offering registration as next step."
    ),
    theme="memory checkpoints; door requires identity",
    emotional_default="bureaucratic",
    terminal=True,
    unlocks_registration=True,
  ),
}


def next_scene_after(current_scene: str) -> Optional[str]:
  """Return the default next scene if no explicit decision is required."""
  order = [
    "chapter_one.arrival",
    "chapter_one.departure",
    "chapter_one.maze_edge",
    "chapter_one.maze_depth_a",
    "chapter_one.maze_depth_b",
    "chapter_one.office_threshold",
  ]
  try:
    idx = order.index(current_scene)
  except ValueError:
    return None
  if idx + 1 < len(order):
    return order[idx + 1]
  return None
