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
      "He discovers a strange job offer in his old AOL inbox from LABYRINTHE SYSTEMS. "
      "Set the tone: early internet nostalgia mixed with unease. Use sensory detail, focus on isolation, "
      "and hint that the maze watches him even now. "
      "Optionally reference Borges ('The House of Asterion', 'The Garden of Forking Paths') "
      "as a book the protagonist owns, or Ariadne's thread as an absent comfort, or the Chartres labyrinth "
      "as something he read about—let the mythological resonance feel like the protagonist's own frame of reference."
    ),
    theme="paragraphs flicker when re-read; memory feels unreliable; the labyrinth's mythology hums beneath the 2003 surface",
    emotional_default="lonely",
  ),
  "chapter_one.departure": SceneBlueprint(
    scene_id="chapter_one.departure",
    scene_prompt=(
      "Describe {{protagonist}} preparing for the trip north. He prints MapQuest directions, "
      "packs a ThinkPad, and hears from a coworker whose voice resembles his ex. "
      "The road should feel like a ritual, with radio static and empty rest stops. "
      "Reference Ariadne's thread as something absent—no thread to follow back out. "
      "The protagonist may pack House of Leaves or a Borges paperback alongside the laptop. "
      "The drive north should feel like a hero's approach to something that cannot be approached directly."
    ),
    theme="scrolling back mutates travel details; the road encodes ancient journey-toward-labyrinth mythology",
    emotional_default="nostalgic",
  ),
  "chapter_one.maze_edge": SceneBlueprint(
    scene_id="chapter_one.maze_edge",
    scene_prompt=(
      "He reaches the property line. The asphalt exhales as he turns into the trees. "
      "Describe the maze awakening, branches forming, copper wires or pale light luring him. "
      "It should feel like the forest is a computer circuit—and also like the entrance to Knossos. "
      "The copper wire IS Ariadne's thread, digitized. "
      "A rusted sign may credit the architect as D. AEDALUS. "
      "The pale CRT light flickers at the frequency of something much older than electricity."
    ),
    theme="tilt choice determines the corridor mood; the wire is Ariadne's thread; Daedalus is the unnamed architect",
    emotional_default="glitchy",
    decisions=[
      Decision(
        direction="left",
        label="Follow The Humming Wire",
        emotional_track="seductive",
        next_scene="chapter_one.maze_depth_a",
        summary="Copper guidance, alluring and dangerous—Ariadne's thread gone electric.",
      ),
      Decision(
        direction="right",
        label="Chase The Pale Light",
        emotional_track="panicked",
        next_scene="chapter_one.maze_depth_a",
        summary="CRT glow that edits reality, unsettling clarity—the phosphor eye of the labyrinth.",
      ),
    ],
  ),
  "chapter_one.maze_depth_a": SceneBlueprint(
    scene_id="chapter_one.maze_depth_a",
    scene_prompt=(
      "Layer the maze interior. Mix analog tech (CRTs, fax machines, copper wire) with forest, "
      "and adapt to the emotional track: seductive, bureaucratic, glitchy, or panicked. "
      "LiveJournal comments, AIM away messages, or corporate memos appear as the walls. "
      "For seductive: the Ariadne thread as golden wire, ancient allure. "
      "For bureaucratic: Kafka's Castle as the structural model—forms that can never be completed. "
      "For glitchy: Borges' Library of Babel materialized in the forest—hexagonal chambers, infinite texts. "
      "For panicked: the Minotaur's presence as sound and displacement—Theseus without his thread."
    ),
    theme="scroll back to see altered history; paragraphs mutate heavily; mythology bleeds through the 2003 aesthetic",
    emotional_default="glitchy",
  ),
  "chapter_one.maze_depth_b": SceneBlueprint(
    scene_id="chapter_one.maze_depth_b",
    scene_prompt=(
      "Deepen the maze. Show time distortions, duplicate coworkers, and artifacts from the protagonist's past. "
      "Lean harder into the current emotional track (seductive vs bureaucratic vs glitchy vs panicked). "
      "End with the sense that an office door is close. "
      "The Minotaur is at the center—something large, patient, waiting. "
      "The maze may reveal its own mythology: Piranesi's impossible prison architecture, "
      "Escher's impossible staircases, the double as a labyrinthine trap (Borges). "
      "The protagonist may find the eleven-circuit Chartres pattern in the moss underfoot."
    ),
    theme="memory sync errors; paragraphs drift toward panic when reread; the center is close and the center contains something",
    emotional_default="glitchy",
  ),
  "chapter_one.office_threshold": SceneBlueprint(
    scene_id="chapter_one.office_threshold",
    scene_prompt=(
      "He finds the prefab office pod hunched in the ferns—the center of the labyrinth, Knossos reimagined as corporate architecture. "
      "Through the glass he glimpses a coworker who mirrors him—Borges' double, the self the labyrinth manufactures. "
      "The lock demands registration before the door opens. "
      "The post-it note may reference the Minotaur (also a contractor; also did not know he was the center). "
      "End on a cliffhanger, offering registration as the final threshold."
    ),
    theme="memory checkpoints; door requires identity; the center of the labyrinth demands you name yourself",
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
