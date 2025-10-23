from __future__ import annotations

import json
import logging
import os
import random
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from langgraph.graph import StateGraph, END
from langchain_anthropic import ChatAnthropic
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig

try:
  from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional dependency handled via requirements
  def load_dotenv(*_args, **_kwargs):
    return False

from .story_blueprint import (
  Decision,
  SceneBlueprint,
  SCENES,
  EMOTIONAL_TRACKS,
  next_scene_after,
)
from .state_store import SessionStore

logger = logging.getLogger("deadlight.server")

BASE_DIR = Path(__file__).resolve().parent.parent
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

# Set up session logging with simplified format
session_logger = logging.getLogger("deadlight.session")
session_handler = logging.FileHandler(LOGS_DIR / "sessions.log")
session_handler.setFormatter(
    logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
)
session_logger.addHandler(session_handler)
session_logger.setLevel(logging.INFO)

load_dotenv(dotenv_path=BASE_DIR / ".env")

logging.basicConfig(
    level=os.getenv("LABYRINTH_LOG_LEVEL", "INFO"),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

if os.getenv("LANGSMITH_TRACING", "0") == "1":
    os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
    os.environ.setdefault("LANGCHAIN_PROJECT", "deadlight-2003")

REGISTRATION_FILE = BASE_DIR / "registrations.json"
PROTAGONIST_FALLBACK = "Ben"


@dataclass
class Paragraph:
  id: str
  text: str
  mutations: List[str] = field(default_factory=list)


@dataclass
class BranchOption:
  direction: str
  label: str
  body: str


@dataclass
class Branch:
  id: str
  instruction: Optional[str]
  options: List[BranchOption]


@dataclass
class GenerationResult:
  paragraphs: List[Paragraph] = field(default_factory=list)
  branch: Optional[Branch] = None
  hud_message: Optional[str] = None
  prompt_scroll_back: bool = False
  unlock_registration: bool = False
  story_complete: bool = False


@dataclass
class StorySession:
  id: str
  profile_name: Optional[str]
  scene_id: str = "chapter_one.arrival"
  emotional_track: str = "glitchy"
  next_scene_id: Optional[str] = None
  history: List[Dict] = field(default_factory=list)
  paragraphs: List[Paragraph] = field(default_factory=list)
  paragraph_map: Dict[str, Paragraph] = field(default_factory=dict)
  pending_decision: bool = False
  allow_registration: bool = False
  story_complete: bool = False

  def protagonist(self) -> str:
    return self.profile_name or PROTAGONIST_FALLBACK

  def add_paragraphs(self, paragraphs: List[Paragraph]) -> None:
    for paragraph in paragraphs:
      self.paragraphs.append(paragraph)
      self.paragraph_map[paragraph.id] = paragraph

  def summary(self, max_entries: int = 6) -> str:
    corpus = []
    for item in self.paragraphs[-max_entries:]:
      corpus.append(item.text.strip())
    for entry in self.history[-max_entries:]:
      if entry.get("type") == "decision":
        corpus.append(
          f"[decision] {entry.get('direction')} ({entry.get('scene')})"
        )
    return "\n".join(corpus)


class StoryStartPayload(BaseModel):
  profile_name: Optional[str] = Field(
    default=None, description="Preferred protagonist name."
  )


class ProgressPayload(BaseModel):
  session_id: str
  event: str
  direction: Optional[str] = None
  confidence: Optional[float] = None
  via: Optional[str] = None


class MutationPayload(BaseModel):
  session_id: str
  paragraph_id: str


class RegistrationPayload(BaseModel):
  name: str
  email: str
  session_id: Optional[str] = None


class StoryGenerator:
  def __init__(self) -> None:
    self._scene_runner = self._compile_scene_graph()
    self._decision_runner = self._compile_decision_graph()

  def _compile_scene_graph(self):
    graph = StateGraph(dict)

    def render(state: Dict) -> Dict:
      session: StorySession = state["session"]
      blueprint: SceneBlueprint = state["blueprint"]
      is_new = state.get("is_new_session", False)
      state["result"] = self._render_scene_impl(
        session, blueprint, is_new_session=is_new
      )
      return state

    graph.add_node("render", render)
    graph.set_entry_point("render")
    graph.add_edge("render", END)
    return graph.compile()

  def _compile_decision_graph(self):
    graph = StateGraph(dict)

    def decide(state: Dict) -> Dict:
      session: StorySession = state["session"]
      blueprint: SceneBlueprint = state["blueprint"]
      decision: Decision = state["decision"]
      meta: Dict = state.get("meta", {})
      state["result"] = self._handle_decision_impl(session, blueprint, decision, meta)
      return state

    graph.add_node("decide", decide)
    graph.set_entry_point("decide")
    graph.add_edge("decide", END)
    return graph.compile()

  def render_scene(
    self,
    session: StorySession,
    blueprint: SceneBlueprint,
    *,
    is_new_session: bool = False,
  ) -> GenerationResult:
    output = self._scene_runner.invoke(
      {
        "session": session,
        "blueprint": blueprint,
        "is_new_session": is_new_session,
      }
    )
    return output["result"]

  def handle_decision(
    self,
    session: StorySession,
    blueprint: SceneBlueprint,
    decision: Decision,
    meta: Dict,
  ) -> GenerationResult:
    output = self._decision_runner.invoke(
      {
        "session": session,
        "blueprint": blueprint,
        "decision": decision,
        "meta": meta,
      }
    )
    return output["result"]

  def _render_scene_impl(
    self,
    session: StorySession,
    blueprint: SceneBlueprint,
    *,
    is_new_session: bool = False,
  ) -> GenerationResult:  # pragma: no cover - interface
    raise NotImplementedError

  def _handle_decision_impl(
    self,
    session: StorySession,
    blueprint: SceneBlueprint,
    decision: Decision,
    meta: Dict,
  ) -> GenerationResult:  # pragma: no cover - interface
    raise NotImplementedError

  def mutate_paragraph(self, session: StorySession, paragraph: Paragraph) -> str:  # pragma: no cover
    raise NotImplementedError


def glitch_text(text: str) -> str:
  fragments = text.split(" ")
  if not fragments:
    return text
  idx = random.randrange(len(fragments))
  target = fragments[idx]
  if len(target) > 3:
    target = "".join(random.choice([ch.upper(), ch.lower(), "#", "~"]) for ch in target)
  fragments[idx] = target
  return " ".join(fragments)


def pick(options: List[str]) -> str:
  return random.choice(options)


class StaticStoryGenerator(StoryGenerator):
  def __init__(self) -> None:
    super().__init__()

  def _render_scene_impl(
    self,
    session: StorySession,
    blueprint: SceneBlueprint,
    *,
    is_new_session: bool = False,
  ) -> GenerationResult:
    protagonist = session.protagonist()
    branch = None
    hud = None
    prompt_scroll = False
    unlock_registration = blueprint.unlocks_registration
    story_complete = blueprint.terminal

    paragraphs = self._paragraphs_for_scene(
      blueprint.scene_id,
      protagonist=protagonist,
      emotional_track=session.emotional_track,
    )

    if blueprint.decisions:
      branch = Branch(
        id=f"{blueprint.scene_id}::branch",
        instruction="The maze is listening. Lean or click when a path calls.",
        options=[
          BranchOption(
            direction=decision.direction,
            label=decision.label,
            body=decision.summary,
          )
          for decision in blueprint.decisions
        ],
      )
      hud = "THE CORRIDOR WAITS. TILT OR CLICK TO CHOOSE."
    else:
      hud = self._hud_for_scene(blueprint.scene_id)

    if blueprint.scene_id in {"chapter_one.maze_depth_a", "chapter_one.maze_depth_b"}:
      prompt_scroll = True

    return GenerationResult(
      paragraphs=paragraphs,
      branch=branch,
      hud_message=hud,
      prompt_scroll_back=prompt_scroll,
      unlock_registration=unlock_registration,
      story_complete=story_complete,
    )

  def _handle_decision_impl(
    self,
    session: StorySession,
    blueprint: SceneBlueprint,
    decision: Decision,
    meta: Dict,
  ) -> GenerationResult:
    if decision.direction not in {"left", "right"}:
      raise HTTPException(status_code=400, detail="Unknown direction.")
    if decision.direction == "left":
      paragraphs = [
        Paragraph(
          id=uuid.uuid4().hex,
          text=pick(
            [
              "Copper vines snake along the ground, guiding each step. The trees whisper modem noise, syllables you almost remember.",
              "Bundles of coax crawl over your boots, nudging you forward with a low, coaxing hum.",
              "Wire wrapped around dried pine cones glows with modem light, pulsing whenever you hesitate.",
            ]
          ),
          mutations=[
            "Wire choir sings 56k hymns; you hum along without meaning to.",
            "Copper threads bite your boots, tugging you toward a dial tone.",
          ],
        ),
        Paragraph(
          id=uuid.uuid4().hex,
          text=pick(
            [
              "Signal strength jitters. Each tilt of your body redraws the map, corridors shuffling like frustrated code.",
              "Every sway of your shoulders reroutes the corridor. Bars of signal bloom and vanish in the corner of your eye.",
              "The path recalculates with a soft chime, as though you clicked recenter on a map you can’t see.",
            ]
          ),
          mutations=[
            "Signal bars blink amber; corridors recalc with every sway.",
            "Maze walls refactor themselves whenever you breathe unevenly.",
          ],
        ),
        Paragraph(
          id=uuid.uuid4().hex,
          text=pick(
            [
              "Somewhere overhead, lines snap taut; a voice filtered through static promises they have been expecting you.",
              "The hum resolves into an old hold-music melody, the same track your ex’s office used to play after midnight.",
              "Copper beads into droplets that fall like rain, sizzling when they touch the path you didn’t take.",
            ]
          ),
          mutations=[
            "Hold music mutates into your name spelled in tones.",
            "Copper rain leaves scorch marks that fade the second you blink.",
          ],
        ),
      ]
      hud = "WIRE HUM CONFIRMED. PATH REALIGNING."
    else:
      paragraphs = [
        Paragraph(
          id=uuid.uuid4().hex,
          text=pick(
            [
              "You angle toward the pale light. It flickers in CRT refresh rates, blinding and familiar. Every blink edits the footprints behind you.",
              "The glow washes over you in horizontal lines, repainting your outline with each pass.",
              "Phosphor light clings to your skin; when it lets go, your shadow lags a beat behind.",
            ]
          ),
          mutations=[
            "Light pulses 60Hz. Your footprints disappear between frames.",
            "Phosphor glow chews at your outline. The path you took keeps rewriting.",
          ],
        ),
        Paragraph(
          id=uuid.uuid4().hex,
          text=pick(
            [
              "Some lines of text rearrange themselves as you pass. The maze wants you to notice. Maybe it prefers you lost.",
              "AIM chat transcripts curl in the air, reshuffling their timestamps whenever you blink.",
              "Every tree becomes a monitor for one frame, displaying a status message you wrote years ago.",
            ]
          ),
          mutations=[
            "Text crawls backward over itself. The maze likes it when you doubt.",
            "Sentences rewrite mid-air. You are not the only reader.",
          ],
        ),
        Paragraph(
          id=uuid.uuid4().hex,
          text=pick(
            [
              "The light hums like a CRT a minute before it dies. Somewhere beyond it, a keyboard clicks in triplets.",
              "You taste dust and ozone; the glow smells like a computer lab sealed in 1999.",
              "A silhouette shaped like a co-worker-of-memory beckons. When you focus, it dissolves into refresh lines.",
            ]
          ),
          mutations=[
            "Keyboard clicks sync with your heartbeat, then race ahead.",
            "Glow sharpens into a doorway outline labelled LOGIN.",
          ],
        ),
      ]
      hud = "GLOW ACCEPTED. THE WALLS ARE SHIFTING."

    return GenerationResult(
      paragraphs=paragraphs,
      hud_message=hud,
      prompt_scroll_back=True,
    )

  def mutate_paragraph(self, session: StorySession, paragraph: Paragraph) -> str:
    if paragraph.mutations:
      return paragraph.mutations.pop(0)
    return glitch_text(paragraph.text)

  def _paragraphs_for_scene(
    self,
    scene_id: str,
    *,
    protagonist: str,
    emotional_track: str,
  ) -> List[Paragraph]:
    if scene_id == "chapter_one.arrival":
      return self._arrival_paragraphs(protagonist)
    if scene_id == "chapter_one.departure":
      return self._departure_paragraphs(protagonist)
    if scene_id == "chapter_one.maze_edge":
      return self._maze_edge_paragraphs()
    if scene_id == "chapter_one.maze_depth_a":
      return self._maze_depth_a_paragraphs(emotional_track)
    if scene_id == "chapter_one.maze_depth_b":
      return self._maze_depth_b_paragraphs(emotional_track)
    if scene_id == "chapter_one.office_threshold":
      return self._office_threshold_paragraphs()
    return [
      Paragraph(
        id=uuid.uuid4().hex,
        text="The maze glitches politely, asking for a prompt it can trust.",
        mutations=["Maze waits. Maybe give it a better prompt."],
      )
    ]

  def _arrival_paragraphs(self, protagonist: str) -> List[Paragraph]:
    return [
      Paragraph(
        id=uuid.uuid4().hex,
        text=pick(
          [
            f"June 17, 2003. The modem shriek ricochets across {protagonist}'s apartment, rattling the blinds like something that wants in.",
            f"June 17, 2003. A 56k handshake howls through {protagonist}'s speakers and leaves the air shivering after the carrier drops.",
            f"June 17, 2003. Dial-up static floods {protagonist}'s living room, the phone cord stretched tight like an IV line.",
          ]
        ),
        mutations=[
          "Modem shriek claws across the drywall; no neighbors knock; no one else heard it.",
          "56k handshake keens like a freight train. The room keeps listening after it stops.",
        ],
      ),
      Paragraph(
        id=uuid.uuid4().hex,
        text=pick(
          [
            "Buried in an AOL folder labelled Saved/Maybe, a message timestamped 03:17 AM glows. Subject: LABYRINTHE SYSTEMS // CONTRACTOR REQUEST // DO NOT IGNORE.",
            "A blue email waits under expired chain letters. Header: LABYRINTHE SYSTEMS needs a contractor who will not ask questions.",
            "Someone with no screenname left a single AIM offline message: LABYRINTHE SYSTEMS. The same text appears in your AOL inbox five seconds later.",
          ]
        ),
        mutations=[
          "LABYRINTHE_SYSTEMS.eml // sender unknown // attachments scrubbed.",
          "Email header forged in 1998, body edited tonight. The maze loops back on itself.",
        ],
      ),
      Paragraph(
        id=uuid.uuid4().hex,
        text=pick(
          [
            "The voicemail light blinks 12. Your mother, your ex, a recruiter—each message ends mid-sentence as if spliced. Only the unknown extension finishes: “See you in the woods.”",
            "A coworker you barely remember pings on AIM. Her icon flickers between her face and your ex’s. “Can’t wait to collaborate in person,” she types, then deletes the message before you can answer.",
            "Friends check in through stale chain letters. Every reply-to address resolves to the same domain: labyrinthe.systems. Someone knows exactly where you’re going.",
          ]
        ),
        mutations=[
          "Voicemail rewinds on its own, replaying the unknown voice with a different laugh.",
          "AIM chat window reopens with the words: YOU WILL LOVE IT HERE.",
        ],
      ),
    ]

  def _departure_paragraphs(self, protagonist: str) -> List[Paragraph]:
    return [
      Paragraph(
        id=uuid.uuid4().hex,
        text=pick(
          [
            f"{protagonist} prints the MapQuest directions twice; the ink beads where the site warns Data Unverified.",
            f"Someone annotated the MapQuest route in a hand that is almost yours. {protagonist} circles the note that reads: TURN WHEN THE ASPHALT SIGHS.",
            f"{protagonist} feeds coordinates into a beige Garmin that promptly loses signal north of Albany, so the crinkled MapQuest sheet becomes gospel again.",
          ]
        ),
        mutations=[
          "Sharpie in the margin: IGNORE DETOURS. THEY LOOP.",
          "MapQuest footer: SOME ROADS UNCONFIRMED. You highlight them anyway.",
        ],
      ),
      Paragraph(
        id=uuid.uuid4().hex,
        text=pick(
          [
            f"A milk crate of burnt CDs and the wheezing ThinkPad ride shotgun. {protagonist} tapes the offer letter to the dash like a saint card.",
            f"{protagonist} packs the ThinkPad, a cassette recorder, and the flashlight your ex insisted you keep. The answering machine blinks but you let it.",
            f"The trunk swallows a toolkit, the old modem, and a shoebox of printed AIM logs. You lock the apartment even though the landlord changed the bolt yesterday.",
          ]
        ),
        mutations=[
          "ThinkPad battery throbs at 12%. You promise it an outlet somewhere in the trees.",
          "Flashlight rattles in the glove compartment like a loose tooth. It will have to do.",
        ],
      ),
      Paragraph(
        id=uuid.uuid4().hex,
        text=pick(
          [
            f"{protagonist} heads north past rest stops lit like empty stage sets. Cell towers blink red in timed patterns, as if counting you down.",
            "The wagon hums past shuttered diners and novelty shops. Every twenty miles the pager vibrates once and shows NO SERVICE.",
            "You pass a billboard for an AIM chatroom that shut down years ago. The sky bruises purple; WRRV keeps dissolving into static.",
          ]
        ),
        mutations=[
          "Rest stops grin with vending-machine light and no people, as if power forgot to shut off.",
          "Payphones stand with their cords torn loose like tongues.",
        ],
      ),
      Paragraph(
        id=uuid.uuid4().hex,
        text=pick(
          [
            "When the asphalt finally exhales—a shudder felt through the steering wheel—a service road yawns between black spruce.",
            "A melted mailbox marks the turn. The main road seems relieved when you leave it for pine needles and dirt.",
            "The dash spits out a dot-matrix strip: TAKE THE SERVICE ROAD NOW. The asphalt groans as you obey.",
          ]
        ),
        mutations=[
          "A payphone rings once as you swing into the trees, even though its cord dangles.",
          "The asphalt trembles like it was holding its breath until you were gone.",
        ],
      ),
    ]

  def _maze_edge_paragraphs(self) -> List[Paragraph]:
    return [
      Paragraph(
        id=uuid.uuid4().hex,
        text=pick(
          [
            "A rusted satellite dish marks the property line, its parabolic face half-swallowed by decades of moss and pine needles that pulse with faint electromagnetic activity. You've seen enough abandoned tech in your IT career to know dead equipment when you see it, but this dish is anything but dormant—it tracks your movement with the fluid grace of an ancient predator, its receiving horn adjusting in microscopic increments to maintain perfect alignment with your chest. The moss growing across its surface ripples in patterns that remind you of the old Windows 95 maze screensaver, but the paths it traces feel deliberate, as if the dish is processing your presence through layers of analog filter. Standing here at the edge of the corporate property, you can feel the strange resonance between your heartbeat and the dish's subtle movements, a synchronization that shouldn't be possible with offline hardware.",
            "The trees have been repurposed, their natural forms subverted by loops of copper wire that wind through the canopy like tinsel at a programmer's Christmas party. Each breath you take sends vibrations through the metallic network—you can see the tremors race from trunk to trunk, carrying your respiratory rhythm deeper into the forest like a biometric handshake. The wire itself is old Cat-3 cable, the kind you used to run in miles through office drop ceilings, but here it has grown wild and baroque, spawning impossible connections that remind you of circuit diagrams drawn by someone in the midst of a fever dream. When you reach out to touch one of the lower loops, the entire network shivers in anticipation, and you swear you can hear the ghost of a dial-up connection negotiating somewhere in the shadows between the trees.",
            "Between the black spruce trunks, something leaks a familiar light—that specific phosphor glow that brings back memories of nights spent debugging in empty offices, face bathed in the radiation of old CRT monitors. The light pulses at exactly 60Hz, the refresh rate burned into your retinas from years of staring at code, but there's something wrong with the color temperature. It shifts between shades that don't exist in the RGB spectrum, rendering the gaps between trees in impossible colors that make your eyes water when you try to focus on them. You recognize the pattern of the flicker—it's transmitting data, using the forest itself as a display matrix for some vast distributed system that seems to have been waiting for someone with the right kind of pattern recognition to arrive.",
          ]
        ),
        mutations=[
          "The satellite dish's movements become more pronounced, its whole frame rotating with the rhythmic precision of an MRI machine. You can feel it scanning deeper than skin, past muscle and bone, searching your internal architecture for some specific configuration of tissue and memory. The moss patterns shift from maze to flowchart to assembly code, documenting its analysis of your biological source code in real-time. When it finally locks onto whatever it was searching for, the dish emits a single pure tone that matches the resonant frequency of your skull.",
          "The copper network awakens fully, each wire now humming with the exact harmonic signature of a 56k handshake—that digital song that used to announce connection to the early internet. But this sound carries extra frequencies, subharmonics that vibrate in your teeth and make you taste ozone. The network is establishing a connection, but not to any server you've ever known. When the handshake completes, you feel it in your spine, a click of acknowledgment between your nervous system and whatever vast distributed consciousness has made this forest its home.",
        ],
      ),
      Paragraph(
        id=uuid.uuid4().hex,
        text=pick(
          [
            "Your crumpled MapQuest printout terminates with an instruction that wasn't there at the last gas station: 'CONTINUE BY INTUITION' in a font that perfectly matches your own handwriting, down to the slight tremor you developed after too many caffeine-fueled coding sessions. The paper feels different now, less like standard printer stock and more like the punch cards your programming professor kept in a hermetically sealed case, each fold and crease encoding additional data you can almost read with your fingertips. When you try to refold it along the original lines, the creases multiply fractally, creating new paths that branch between the official roads like unauthorized hyperlinks.",
            "The map in your hands undergoes spontaneous revision, fresh lines bleeding through the inkjet paper like dark veins surfacing under pale skin. These new paths are labeled in a prototype version of MS Gothic—that system font you remember from countless error messages—each one marked as BETA with build numbers that include impossible dates. The legend updates itself in real-time, symbols shifting between standard cartographic notation and snippets of pseudocode that seem to describe algorithms for navigating non-Euclidean space. Every time you blink, the map's topology grows more complex, as if it's gradually importing the true structure of this place into your reality's limited coordinate system.",
            "A sharp vibration from your hip makes you jump—the ancient pager you kept out of nostalgia or paranoia suddenly active after years of silence. The LCD display renders its message in the crisp pixels you remember from your first programming job: 'WELCOME TO OFFSITE OFFICE [LOCALHOST]. FOLLOW SIGNAL INTEGRITY.' The message should be too long for the pager's buffer, but it continues scrolling, the text now describing your exact position using coordinates that reference both physical space and some other set of dimensions you can feel but not quite comprehend. When you look up from the display, the forest has rearranged itself to match the topology suggested by those impossible coordinates.",
          ]
        ),
        mutations=[
          "The pager screen fragments into ASCII art, characters cascading like rain against the liquid crystal before resolving into a map of your own neural pathways. The display shows connection attempts, your synapses handshaking with something that understands consciousness as a network protocol. The last message blinks three times: 'HUMAN INTERFACE DETECTED // DRIVER INSTALLATION INITIATED' before the screen fills with question marks that seem to float above the surface of the LCD.",
          "The map's paper thinns to transparency, then thickens into something that feels like a hybrid of vellum and magnetic tape. The edges char and curl not with heat but with information density, new passages writing themselves into existence as the document attempts to represent higher-dimensional network topologies in physical space. You can see your own location marked by a cursor that blinks in sync with your pulse, leaving a trail of breadcrumbs formed from executable code.",
        ],
      ),
    ]

  def _maze_depth_a_paragraphs(self, emotional_track: str) -> List[Paragraph]:
    track = emotional_track or "glitchy"
    pool = {
      "seductive": [
        "Copper filaments climb the birches, braiding into crude antennae that lean toward you.",
        "Hold music winds through the pines, the melody matching your ex’s laugh.",
      ],
      "bureaucratic": [
        "Tarps stretch between trees, stamped with LABYRINTHE SYSTEMS PROPERTY in bleeding ink.",
        "A reception desk without walls spins slowly, drawers opening to reveal toner cartridges.",
      ],
      "glitchy": [
        "Phone poles sprout from the moss, their lines connecting to nothing. The path reboots with every footfall.",
        "LiveJournal comments float like fireflies, their timestamps recalculating midair.",
      ],
      "panicked": [
        "Footsteps echo half a second behind you, stumbling whenever you do.",
        "Warning tones blare from unseen servers; the path ahead keeps jittering away.",
      ],
    }
    sentences = pool.get(track, pool["glitchy"])
    return [
      Paragraph(
        id=uuid.uuid4().hex,
        text=pick(sentences),
        mutations=[
          "Paragraph refactors mid-sentence when you scroll.",
          "A second version of the sentence appears, contradicting the first.",
        ],
      ),
      Paragraph(
        id=uuid.uuid4().hex,
        text=pick(
          [
            "The map in your palm redraws itself whenever you breathe. Corridors slide around like code being refactored.",
            "A soft click behind you signals the corridor rewriting. Footprints you made five seconds ago now belong to someone else.",
          ]
        ),
        mutations=[
          "Map refreshes: ROUTE RECOMPILED. You never saw the original.",
          "Every step triggers a soft chime: PATH UPDATED.",
        ],
      ),
      Paragraph(
        id=uuid.uuid4().hex,
        text=pick(
          [
            "Analog monitors perch on stumps, each showing a different version of this moment. In one, you turn back. In another, you smile.",
            "A PA system tucked into the branches whispers status updates: “Contractor en route. Emotion state: {track}.” The word dissolves before you finish reading it.".format(
              track=track.upper()
            ),
            "Every gust of pine needles spells out a memo: DO NOT TRUST STATIC MAPS. The letters scatter when you blink.",
          ]
        ),
        mutations=[
          "Monitors desync; one shows someone else wearing your jacket.",
          "PA system glitches into laughter, then apologizes.",
        ],
      ),
    ]

  def _maze_depth_b_paragraphs(self, emotional_track: str) -> List[Paragraph]:
    moods = {
      "seductive": [
        "Polaroids pinned to bark develop into scenes of warmth: your old apartment, minus the arguments.",
        "A coworker you almost loved beckons, promising a desk with your name already engraved.",
      ],
      "bureaucratic": [
        "Dot-matrix printouts hang from branches, listing action items you never completed.",
        "Fax machines spit out maps with corridors crossed in red pen, initialed by you.",
      ],
      "glitchy": [
        "Static hangs like fog. Shapes move inside it: cubicles, break rooms, a copy of your apartment with the lights on.",
        "Each tree now has a username carved into it; some belong to people you only knew online.",
      ],
      "panicked": [
        "A Windows error chime rolls through the trees. The blue screen hovers in midair, waiting for you to read it.",
        "Your pager vibrates with TURN AROUND, but the same pager in your pocket refuses to display anything.",
      ],
    }
    selected = moods.get(emotional_track, moods["glitchy"])
    return [
      Paragraph(
        id=uuid.uuid4().hex,
        text=pick(selected),
        mutations=[
          "The scene replays with a slightly different ending each time you scroll.",
          "Another version of you walks through the background, then fades.",
        ],
      ),
      Paragraph(
        id=uuid.uuid4().hex,
        text=pick(
          [
            "Time hiccups; the breath you just took happens twice.",
            "A figure in a clipped PowerPoint suit mirrors your motions. When you wave, she keeps typing.",
          ]
        ),
        mutations=[
          "She mouths your old pet name, then static erupts.",
          "Her outline flickers between familiar and stranger every frame.",
        ],
      ),
      Paragraph(
        id=uuid.uuid4().hex,
        text=pick(
          [
            "Someone has pinned your performance reviews to a tree, but the bullet points describe feelings instead of metrics.",
            "A door made of Ethernet cable swings open to reveal your apartment as it was in 2001. The door closes before you decide to enter.",
            "A LiveJournal poll dangles from a branch asking: DO YOU TRUST THE VOICE ON THE LINE? The options flicker between YES and MAYBE.",
          ]
        ),
        mutations=[
          "Review rewrites itself to praise your ability to stay lost.",
          "The Ethernet door reopens with a mirror image watching you.",
        ],
      ),
    ]

  def _office_threshold_paragraphs(self) -> List[Paragraph]:
    return [
      Paragraph(
        id=uuid.uuid4().hex,
        text="A prefab office pod squats in the ferns like a forgotten FEMA shelter. Your contract number is bolted to the door along with a stenciled warning: THIS CORRIDOR REMEMBERS.",
        mutations=[
          "Steel panels sweat. Contract number riveted over a spray-painted tag: CORRIDOR NEVER FORGETS.",
          "Fern fronds kiss the threshold. The badge reads your number, the graffiti replies: THIS HALLWAY WATCHES.",
        ],
      ),
      Paragraph(
        id=uuid.uuid4().hex,
        text="Through the security glass a figure with your slouch sits at an identical desk, fingers hovering over a keyboard that types a beat ahead of you. The keypad blinks: REGISTER USER TO PROCEED.",
        mutations=[
          "The ghost behind the glass smiles late, echoing your breath. KEYPAD STATUS: registration pending.",
          "REGISTER TO CONTINUE pulses in amber. The mirror-worker raises their head when you swallow.",
        ],
      ),
      Paragraph(
        id=uuid.uuid4().hex,
        text="A post-it note curls on the interior window: WELCOME, CONTRACTOR. BRING YOUR OWN MEMORY. Someone underlined memory three times.",
        mutations=[
          "Sticky note reads: BRING YOUR OWN MEMORY. Someone added: OR WE WILL SUPPLY ONE.",
          "Another hand scrawled: DON’T LEAVE UNTIL YOU’RE SURE IT’S YOU.",
        ],
      ),
    ]

  def _hud_for_scene(self, scene_id: str) -> str:
    return {
      "chapter_one.arrival": "LINK ESTABLISHED. LET THE TEXT PULL YOU UNDER.",
      "chapter_one.departure": "ROAD OPEN. WATCH FOR STATIC.",
      "chapter_one.maze_edge": "THE TREES ARE LISTENING.",
      "chapter_one.maze_depth_a": "KEEP READING. THE CORRIDOR IS ONLY WARMING UP.",
      "chapter_one.maze_depth_b": "THE MAZE LIKES WHEN YOU LOOK BACK.",
      "chapter_one.office_threshold": "THE DOOR WANTS A NAME. REGISTER TO CONTINUE.",
    }.get(scene_id, "THE MAZE IS QUIET FOR NOW.")


class ClaudeStoryGenerator(StaticStoryGenerator):
  def __init__(self, api_key: str, model: str = "claude-3-haiku-20240307"):
    super().__init__()
    self.llm = ChatAnthropic(model=model, api_key=api_key)
    self.parser = JsonOutputParser()
    self.prompt = ChatPromptTemplate.from_messages(
      [
        (
          "system",
          (
            "You are the MAZE ENGINE for Deadlight 2003, a generative literary horror experience. "
            "This is NOT a chatbot or game—it's an evolving novel that changes with each read. "
            "\n\n"
            "TONE & VOICE:\n"
            "- Late-90s/early-2000s Stephen King road-horror meets House of Leaves meets a self-aware AI narrator\n"
            "- Write like a literary novel: rich sensory detail, psychological depth, atmospheric dread\n"
            "- The maze speaks in second-person but thinks like an anxious novelist\n"
            "- Tactile, conversational, intimate—the reader should FEEL every detail\n"
            "\n"
            "ERA ACCURACY (2003):\n"
            "- AIM, LiveJournal, DSL modems, CRT monitors, MapQuest, ThinkPads, AOL, dial-up sounds\n"
            "- Pre-smartphone, pre-social media, pre-WiFi ubiquity\n"
            "- The internet feels new, unstable, liminal\n"
            "\n"
            "PARAGRAPH STRUCTURE:\n"
            "- Each paragraph should be 3-6 sentences of dense, literary prose\n"
            "- Not bullet points—full narrative immersion\n"
            "- Layer sensory details: sight, sound, smell, touch, psychological state\n"
            "- Build atmosphere slowly, let dread accumulate\n"
            "- Use concrete details from 2003: brand names, tech specs, cultural references\n"
            "\n"
            "NARRATIVE MECHANICS:\n"
            "- Paragraphs can mutate when re-read (provide mutation variants)\n"
            "- The maze is unreliable, self-editing, alive\n"
            "- Mix technology and nature: circuits in trees, CRTs in clearings, copper wire vines\n"
            "- Emotional tracks shape tone: seductive, bureaucratic, glitchy, panicked\n"
            "\n"
            "AVOID: Modern slang, explicit gore, cheap jumpscares, exposition dumps\n"
            "EMBRACE: Uncanny warmth that curdles, liminal spaces, technological decay, memory unreliability\n"
            "\n"
            "{format_instructions}"
          ),
        ),
        (
          "user",
          (
            "Generate narrative content for this scene. Follow the scene prompt closely, weaving in the theme and emotional track. "
            "\n\n"
            "CRITICAL NARRATIVE CONSTRAINTS:\\n"
            "1. Each paragraph MUST be 4-6 sentences minimum. Short, punchy sentences are not allowed.\\n"
            "2. Each paragraph must contain:\\n"
            "   - Physical/sensory details (what protagonist sees, hears, feels)\\n"
            "   - Internal state (thoughts, emotions, memories)\\n"
            "   - Environmental details (the maze/forest/technology)\\n"
            "   - Subtle horror elements (uncanny, not gore)\\n"
            "3. Write as if Stephen King and Mark Danielewski collaborated on a literary novel.\\n"
            "4. NO game-like elements, single-line statements, or exposition dumps.\\n"
            "\n\n"
            "Build atmosphere through specific, tactile details. Show the protagonist's psychological state through environment and sensation. "
            "If this scene has previous context (previous_transcript), reference it subtly to maintain narrative continuity. "
            "\n\n"
            "Scene data:\n"
            "{scene_payload}"
          ),
        ),
      ]
    ).partial(format_instructions=self.parser.get_format_instructions())
    self.chain = self.prompt | self.llm | self.parser
    self.langsmith_config = RunnableConfig(run_name="maze-scene", tags=["deadlight-2003"])

  def render_scene(
    self,
    session: StorySession,
    blueprint: SceneBlueprint,
    *,
    is_new_session: bool = False,
  ) -> GenerationResult:
    fallback = super().render_scene(session, blueprint, is_new_session=is_new_session)
    return self._maybe_generate(session, blueprint, fallback, decision=None)

  def handle_decision(
    self,
    session: StorySession,
    blueprint: SceneBlueprint,
    decision: Decision,
    meta: Dict,
  ) -> GenerationResult:
    fallback = super().handle_decision(session, blueprint, decision, meta)
    return self._maybe_generate(session, blueprint, fallback, decision=decision)

  def mutate_paragraph(self, session: StorySession, paragraph: Paragraph) -> str:
    return super().mutate_paragraph(session, paragraph)

  def _maybe_generate(
    self,
    session: StorySession,
    blueprint: SceneBlueprint,
    fallback: GenerationResult,
    decision: Optional[Decision],
  ) -> GenerationResult:
    try:
      payload = self._request_generation(session, blueprint, decision)
    except Exception as exc:  # pragma: no cover - defensive
      logger.warning("Claude generation failed (%s); using fallback.", exc)
      return fallback
    if not payload:
      return fallback
    return self._convert_payload(payload, fallback)

  def _request_generation(
    self,
    session: StorySession,
    blueprint: SceneBlueprint,
    decision: Optional[Decision],
  ) -> Optional[Dict]:
    request_payload = {
      "protagonist": session.protagonist(),
      "scene_id": blueprint.scene_id,
      "scene_prompt": blueprint.scene_prompt,
      "theme": blueprint.theme,
      "emotional_track": session.emotional_track,
      "previous_transcript": session.summary(),
      "decision": {
        "direction": decision.direction,
        "label": decision.label,
        "summary": decision.summary,
      }
      if decision
      else None,
      "allow_registration": session.allow_registration,
    }
    return self.chain.invoke(
      {
        "scene_payload": json.dumps(request_payload, indent=2),
      },
      config=self.langsmith_config,
    )

  def _convert_payload(self, payload: Dict, fallback: GenerationResult) -> GenerationResult:
    paragraphs_payload = payload.get("paragraphs") or []
    paragraphs = []
    for item in paragraphs_payload:
      text = item.get("text")
      if not text:
        continue
      mutations = item.get("mutations") or []
      paragraphs.append(
        Paragraph(
          id=uuid.uuid4().hex,
          text=text,
          mutations=mutations if isinstance(mutations, list) else [],
        )
      )

    branch_payload = payload.get("branch")
    branch = None
    if branch_payload:
      options_payload = branch_payload.get("options") or []
      options = []
      for option in options_payload:
        direction = option.get("direction")
        label = option.get("label")
        body = option.get("body")
        if direction and label and body:
          options.append(BranchOption(direction=direction, label=label, body=body))
      if options:
        branch = Branch(
          id=branch_payload.get("id", uuid.uuid4().hex),
          instruction=branch_payload.get("instruction"),
          options=options,
        )

    if not paragraphs and not branch:
      return fallback

    return GenerationResult(
      paragraphs=paragraphs if paragraphs else fallback.paragraphs,
      branch=branch if branch else fallback.branch,
      hud_message=payload.get("hud_message", fallback.hud_message),
      prompt_scroll_back=payload.get("prompt_scroll_back", fallback.prompt_scroll_back),
      unlock_registration=payload.get("unlock_registration", fallback.unlock_registration),
      story_complete=payload.get("story_complete", fallback.story_complete),
    )


class SessionManager:
  def __init__(self, generator: StoryGenerator, store: SessionStore):
    self.generator = generator
    self.store = store
    self.sessions: Dict[str, StorySession] = {}

  def create_session(self, profile_name: Optional[str]) -> StorySession:
    session_id = uuid.uuid4().hex
    scene_id = "chapter_one.arrival"
    blueprint = SCENES[scene_id]
    emotional_track = blueprint.emotional_default or random.choice(EMOTIONAL_TRACKS)
    session = StorySession(
      id=session_id,
      profile_name=profile_name,
      scene_id=scene_id,
      emotional_track=emotional_track,
    )
    result = self.generator.render_scene(session, blueprint, is_new_session=True)
    session.add_paragraphs(result.paragraphs)
    session.pending_decision = bool(result.branch)
    if session.pending_decision:
      session.next_scene_id = None
    else:
      session.next_scene_id = next_scene_after(scene_id)
    if result.unlock_registration:
      session.allow_registration = True
    if result.story_complete:
      session.story_complete = True
    self.sessions[session_id] = session
    self.store.save_session(session.id, session)
    return session, result

  def get_session(self, session_id: str) -> StorySession:
    session = self.sessions.get(session_id)
    if not session:
      session = self.store.load_session(session_id)
      if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
      self.sessions[session_id] = session
    return session

  def advance(self, session_id: str) -> GenerationResult:
    session = self.get_session(session_id)
    if session.pending_decision:
      return GenerationResult(hud_message="THE MAZE WAITS FOR YOUR CHOICE.")
    if session.story_complete:
      return GenerationResult(
        hud_message="THE MAZE REMEMBERS YOU. REGISTER OR REFRESH TO START OVER.",
        unlock_registration=session.allow_registration,
        story_complete=True,
      )

    next_scene_id = session.next_scene_id or next_scene_after(session.scene_id)
    if not next_scene_id:
      session.story_complete = True
      session.allow_registration = True
      session.next_scene_id = None
      return GenerationResult(
        hud_message="THE CORRIDOR FALLS SILENT.",
        unlock_registration=True,
        story_complete=True,
      )

    if next_scene_id not in SCENES:
      raise HTTPException(status_code=500, detail=f"Unknown scene: {next_scene_id}")

    blueprint = SCENES[next_scene_id]
    if not next_scene_id.startswith("chapter_one.maze_depth"):
      session.emotional_track = blueprint.emotional_default or session.emotional_track

    result = self.generator.render_scene(session, blueprint)
    session.add_paragraphs(result.paragraphs)
    session.pending_decision = bool(result.branch)
    session.scene_id = next_scene_id
    session.next_scene_id = None if session.pending_decision else next_scene_after(next_scene_id)
    if result.unlock_registration:
      session.allow_registration = True
    if result.story_complete:
      session.story_complete = True
    self.store.save_session(session.id, session)
    return result

  def decide(self, session_id: str, direction: str, meta: Dict) -> GenerationResult:
    session = self.get_session(session_id)
    if not session.pending_decision:
      raise HTTPException(status_code=400, detail="No decision required right now.")

    blueprint = SCENES.get(session.scene_id)
    if not blueprint:
      raise HTTPException(status_code=500, detail=f"Unknown scene {session.scene_id}")

    choice = next((d for d in blueprint.decisions if d.direction == direction), None)
    if not choice:
      raise HTTPException(status_code=400, detail="Invalid direction.")
    if choice.next_scene not in SCENES:
      raise HTTPException(status_code=500, detail=f"Unknown scene {choice.next_scene}")

    result = self.generator.handle_decision(session, blueprint, choice, meta)
    session.add_paragraphs(result.paragraphs)
    session.pending_decision = False
    session.emotional_track = choice.emotional_track or session.emotional_track
    session.next_scene_id = choice.next_scene
    session.history.append(
      {
        "type": "decision",
        "scene": blueprint.scene_id,
        "direction": direction,
        "via": meta.get("via"),
        "confidence": meta.get("confidence"),
        "emotional_track": session.emotional_track,
        "timestamp": datetime.utcnow().isoformat() + "Z",
      }
    )
    if result.unlock_registration:
      session.allow_registration = True
    if result.story_complete:
      session.story_complete = True
    self.store.save_session(session.id, session)
    return result

  def mutate(self, session_id: str, paragraph_id: str) -> str:
    session = self.get_session(session_id)
    paragraph = session.paragraph_map.get(paragraph_id)
    if not paragraph:
      raise HTTPException(status_code=404, detail="Paragraph not found.")
    new_text = self.generator.mutate_paragraph(session, paragraph)
    paragraph.text = new_text
    self.store.save_session(session.id, session)
    return new_text


def build_generator() -> StoryGenerator:
  api_key = os.environ.get("ANTHROPIC_API_KEY")
  if api_key:
    try:
      return ClaudeStoryGenerator(api_key=api_key)
    except Exception:  # pragma: no cover - fallback
      logger.warning("Falling back to static generator (Claude unavailable).")
      return StaticStoryGenerator()
  return StaticStoryGenerator()


app = FastAPI(title="Deadlight 2003 Teaser")
store_path = Path(os.environ.get("LABYRINTH_DB_PATH", BASE_DIR / "data" / "maze_state.db"))
store_path.parent.mkdir(parents=True, exist_ok=True)
store = SessionStore(store_path)
session_manager = SessionManager(build_generator(), store)


def serialize_result(session: StorySession, result: GenerationResult) -> Dict:
  blueprint = SCENES.get(session.scene_id)
  return {
    "session_id": session.id,
    "scene_id": session.scene_id,
    "emotional_track": session.emotional_track,
    "theme": blueprint.theme if blueprint else None,
    "pending_decision": session.pending_decision,
    "allow_registration": session.allow_registration,
    "paragraphs": [
      {
        "id": paragraph.id,
        "text": paragraph.text,
        "mutations": paragraph.mutations,
      }
      for paragraph in result.paragraphs
    ],
    "branch": serialize_branch(result.branch) if result.branch else None,
    "hud_message": result.hud_message,
    "prompt_scroll_back": result.prompt_scroll_back,
    "unlock_registration": session.allow_registration or result.unlock_registration,
    "story_complete": session.story_complete or result.story_complete,
  }


def serialize_branch(branch: Branch) -> Dict:
  if not branch:
    return {}
  return {
    "id": branch.id,
    "instruction": branch.instruction,
    "options": [
      {
        "direction": option.direction,
        "label": option.label,
        "body": option.body,
      }
      for option in branch.options
    ],
  }


@app.get("/", response_class=FileResponse)
def read_index():
  return FileResponse(BASE_DIR / "index.html")


@app.get("/styles.css", response_class=FileResponse)
def read_styles():
  return FileResponse(BASE_DIR / "styles.css")


@app.get("/script.js", response_class=FileResponse)
def read_script():
  return FileResponse(BASE_DIR / "script.js")


@app.post("/api/session")
def start_session(payload: StoryStartPayload):
  session, result = session_manager.create_session(payload.profile_name)
  return serialize_result(session, result)


@app.get("/api/session/{session_id}")
def fetch_session(session_id: str):
  session = session_manager.get_session(session_id)
  return serialize_result(
    session,
    GenerationResult(
      paragraphs=session.paragraphs,
      hud_message="SESSION SNAPSHOT",
      prompt_scroll_back=False,
      unlock_registration=session.allow_registration,
      story_complete=session.story_complete,
    ),
  )


@app.post("/api/progress")
def progress(payload: ProgressPayload):
  if payload.event not in {"advance", "decision"}:
    raise HTTPException(status_code=400, detail="Unknown event.")
  if payload.event == "advance":
    result = session_manager.advance(payload.session_id)
  else:
    if not payload.direction:
      raise HTTPException(status_code=400, detail="Direction required.")
    meta = {
      "via": payload.via,
      "confidence": payload.confidence,
    }
    result = session_manager.decide(payload.session_id, payload.direction, meta)
  session = session_manager.get_session(payload.session_id)
  return serialize_result(session, result)


@app.post("/api/paragraph/mutate")
def mutate_paragraph(payload: MutationPayload):
  new_text = session_manager.mutate(payload.session_id, payload.paragraph_id)
  return {"text": new_text}


def record_registration(entry: Dict) -> None:
  entries: List[Dict]
  if REGISTRATION_FILE.exists():
    try:
      entries = json.loads(REGISTRATION_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
      entries = []
  else:
    entries = []
  entries.append(entry)
  REGISTRATION_FILE.write_text(json.dumps(entries, indent=2), encoding="utf-8")


@app.post("/api/register")
def register_user(payload: RegistrationPayload):
  record = {
    "name": payload.name,
    "email": payload.email,
    "session_id": payload.session_id,
    "stored_at": datetime.utcnow().isoformat() + "Z",
  }
  try:
    record_registration(record)
  except OSError as exc:  # pragma: no cover - file I/O failure
    raise HTTPException(status_code=500, detail="Could not store registration.") from exc
  return {"status": "ok"}


@app.get("/api/health")
def healthcheck():
  return {"status": "ok"}
