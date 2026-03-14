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
            f”June 17, 2003. The modem shriek ricochets across {protagonist}’s apartment, rattling the blinds like something that wants in.”,
            f”June 17, 2003. A 56k handshake howls through {protagonist}’s speakers and leaves the air shivering after the carrier drops.”,
            f”June 17, 2003. Dial-up static floods {protagonist}’s living room, the phone cord stretched tight like an IV line.”,
            f”June 17, 2003. {protagonist}’s old copy of Borges sits spine-cracked on the milk crate by the modem—The Garden of Forking Paths, a library book technically three years overdue, its margins dense with handwriting from a seminar that ended badly. Someone had written in red ink next to ‘The House of Asterion’: THE MINOTAUR CHOSE HIS PRISON. Now, with the modem shrieking its opening hymn, that sentence feels less like a graduate student’s insight and more like a warning left to be found.”,
          ]
        ),
        mutations=[
          “Modem shriek claws across the drywall; no neighbors knock; no one else heard it.”,
          “56k handshake keens like a freight train. The room keeps listening after it stops.”,
          “The Borges paperback is open to a different page than you left it. The sentence underlined now reads: all labyrinths have a center, and the center is always a monster or a mirror.”,
        ],
      ),
      Paragraph(
        id=uuid.uuid4().hex,
        text=pick(
          [
            “Buried in an AOL folder labelled Saved/Maybe, a message timestamped 03:17 AM glows. Subject: LABYRINTHE SYSTEMS // CONTRACTOR REQUEST // DO NOT IGNORE.”,
            “A blue email waits under expired chain letters. Header: LABYRINTHE SYSTEMS needs a contractor who will not ask questions.”,
            “Someone with no screenname left a single AIM offline message: LABYRINTHE SYSTEMS. The same text appears in your AOL inbox five seconds later.”,
            “A single email waits, timestamped 03:17 AM, from an address that resolves to LABYRINTHE SYSTEMS: the subject line reads DO NOT IGNORE, and the body contains only a coordinate string and one sentence—‘All labyrinths have a center; we have found something older than the center.’ Beneath it, quoted in a font you don’t recognize, is half a line from Borges: in some labyrinth there must exist a Minotaur.”,
          ]
        ),
        mutations=[
          “LABYRINTHE_SYSTEMS.eml // sender unknown // attachments scrubbed.”,
          “Email header forged in 1998, body edited tonight. The maze loops back on itself.”,
          “The email now contains a second attachment: DAEDALUS_BLUEPRINT_v1.pdf. You don’t remember opening it. The download bar reads 100% complete.”,
        ],
      ),
      Paragraph(
        id=uuid.uuid4().hex,
        text=pick(
          [
            “The voicemail light blinks 12. Your mother, your ex, a recruiter—each message ends mid-sentence as if spliced. Only the unknown extension finishes: \u201cSee you in the woods.\u201d”,
            “A coworker you barely remember pings on AIM. Her icon flickers between her face and your ex’s. \u201cCan\u2019t wait to collaborate in person,\u201d she types, then deletes the message before you can answer.”,
            “Friends check in through stale chain letters. Every reply-to address resolves to the same domain: labyrinthe.systems. Someone knows exactly where you’re going.”,
            “A LiveJournal entry you don’t remember writing sits in your drafts folder, timestamped last Tuesday: ‘I keep thinking about the Chartres Cathedral labyrinth—how pilgrims used to walk it on their knees, as a substitute for the journey to Jerusalem. A maze as a destination, not an obstacle. A maze as the whole point.’ Below it, someone has commented: THEN YOU UNDERSTAND WHY WE BUILT OURS.”,
          ]
        ),
        mutations=[
          “Voicemail rewinds on its own, replaying the unknown voice with a different laugh.”,
          “AIM chat window reopens with the words: YOU WILL LOVE IT HERE.”,
          “The LiveJournal draft updates: CHARTRES HAD ONE PATH IN, ONE PATH OUT. OURS IS DIFFERENT. THE MINOTAUR IS OPTIONAL.”,
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
            f"The route looks simple in daylight, but someone has handwritten in the margin of the MapQuest printout: \u2018Ariadne\u2019s thread runs north on Route 9.\u2019 {protagonist} doesn\u2019t remember writing it. The handwriting is theirs but younger\u2014the slant of a first apartment, when they still underlined things in library books and believed that understanding a maze\u2019s structure meant you could walk out of it.",
          ]
        ),
        mutations=[
          "Sharpie in the margin: IGNORE DETOURS. THEY LOOP.",
          "MapQuest footer: SOME ROADS UNCONFIRMED. You highlight them anyway.",
          "The annotated margin now reads: THESEUS HAD A THREAD. YOU HAVE A PRINTOUT. THE MAZE FINDS THIS CHARMING.",
        ],
      ),
      Paragraph(
        id=uuid.uuid4().hex,
        text=pick(
          [
            f"A milk crate of burnt CDs and the wheezing ThinkPad ride shotgun. {protagonist} tapes the offer letter to the dash like a saint card.",
            f"{protagonist} packs the ThinkPad, a cassette recorder, and the flashlight your ex insisted you keep. The answering machine blinks but you let it.",
            f"The trunk swallows a toolkit, the old modem, and a shoebox of printed AIM logs. You lock the apartment even though the landlord changed the bolt yesterday.",
            f"Wedged between the ThinkPad and a coil of Cat-5 cable is the fat Danielewski paperback {protagonist} has been meaning to finish\u2014House of Leaves, spine cracked at page 400, where the hallway grows. It went in the bag for the same reason the flashlight did: some instinct about unfamiliar geometry, the need to know someone else has mapped this kind of wrong before.",
          ]
        ),
        mutations=[
          "ThinkPad battery throbs at 12%. You promise it an outlet somewhere in the trees.",
          "Flashlight rattles in the glove compartment like a loose tooth. It will have to do.",
          "House of Leaves falls open to a footnote: 'No matter how many locks we put on it, a door designed to open will open.' The pages after that are blank.",
        ],
      ),
      Paragraph(
        id=uuid.uuid4().hex,
        text=pick(
          [
            f"{protagonist} heads north past rest stops lit like empty stage sets. Cell towers blink red in timed patterns, as if counting you down.",
            "The wagon hums past shuttered diners and novelty shops. Every twenty miles the pager vibrates once and shows NO SERVICE.",
            "You pass a billboard for an AIM chatroom that shut down years ago. The sky bruises purple; WRRV keeps dissolving into static.",
            "The road north feels ritualistic\u2014the kind of journey that myths encode as a hero\u2019s approach to something that cannot be approached directly. Eco wrote about libraries arranged as labyrinths; King wrote about hotels that consumed you room by room. This road is neither, but it is borrowing from both, and the radio static cycling through frequencies you\u2019ve never heard carries a frequency that sounds, briefly, like a voice reading coordinates.",
          ]
        ),
        mutations=[
          "Rest stops grin with vending-machine light and no people, as if power forgot to shut off.",
          "Payphones stand with their cords torn loose like tongues.",
          "The radio static resolves for one second into a voice reciting: 'In the center of the labyrinth was the Minotaur. In the center of this one is a server room and something we haven\u2019t named yet.'",
        ],
      ),
      Paragraph(
        id=uuid.uuid4().hex,
        text=pick(
          [
            "When the asphalt finally exhales\u2014a shudder felt through the steering wheel\u2014a service road yawns between black spruce.",
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
            "A rusted satellite dish marks the property line, its parabolic face half-swallowed by decades of moss and pine needles that pulse with faint electromagnetic activity. You've seen enough abandoned tech in your IT career to know dead equipment when you see it, but this dish is anything but dormant\u2014it tracks your movement with the fluid grace of an ancient predator, its receiving horn adjusting in microscopic increments to maintain perfect alignment with your chest. The moss growing across its surface ripples in patterns that remind you of the old Windows 95 maze screensaver, but the paths it traces feel deliberate, as if the dish is processing your presence through layers of analog filter. Standing here at the edge of the corporate property, you can feel the strange resonance between your heartbeat and the dish's subtle movements, a synchronization that shouldn't be possible with offline hardware.",
            "The trees have been repurposed, their natural forms subverted by loops of copper wire that wind through the canopy like tinsel at a programmer's Christmas party. Each breath you take sends vibrations through the metallic network\u2014you can see the tremors race from trunk to trunk, carrying your respiratory rhythm deeper into the forest like a biometric handshake. The wire itself is old Cat-3 cable, the kind you used to run in miles through office drop ceilings, but here it has grown wild and baroque, spawning impossible connections that remind you of circuit diagrams drawn by someone in the midst of a fever dream. When you reach out to touch one of the lower loops, the entire network shivers in anticipation, and you swear you can hear the ghost of a dial-up connection negotiating somewhere in the shadows between the trees.",
            "Between the black spruce trunks, something leaks a familiar light\u2014that specific phosphor glow that brings back memories of nights spent debugging in empty offices, face bathed in the radiation of old CRT monitors. The light pulses at exactly 60Hz, the refresh rate burned into your retinas from years of staring at code, but there's something wrong with the color temperature. It shifts between shades that don't exist in the RGB spectrum, rendering the gaps between trees in impossible colors that make your eyes water when you try to focus on them. You recognize the pattern of the flicker\u2014it's transmitting data, using the forest itself as a display matrix for some vast distributed system that seems to have been waiting for someone with the right kind of pattern recognition to arrive.",
            "The copper wire that braids through the high canopy glimmers with a warmth you recognize from somewhere\u2014then it comes to you: this is the color of Ariadne\u2019s thread, the burning-gold of a skein designed to lead a hero back through impossible corridors. But thread is pulled taut by someone waiting at the other end, and you wonder what intelligence crouches at the center of this particular structure, patient as myth, knowing you will come because the wire is already humming your name in frequencies just below hearing. In Ovid it was a simple skein of wool; here it is Cat-3 cable routed through a pine canopy, but the logic is the same: follow it in and you can follow it out\u2014unless the thing that strung it wants neither.",
            "The property line is marked by a rusted sign so corroded the text barely reads: LABYRINTHE SYSTEMS // OFFSITE CAMPUS // ARCHITECT: D. AEDALUS, P.E. Someone has added a handwritten asterisk in black marker and then nothing\u2014the footnote starts but the tree beside it has swallowed whatever it meant to explain. You stand at the threshold that Daedalus, or someone who thought they were him, built to contain something that grew too large, too specific, too alive for ordinary office space, and the wind through the spruce sounds exactly like the sound a prison makes when it realizes it has been waiting a very long time.",
          ]
        ),
        mutations=[
          "The satellite dish's movements become more pronounced, its whole frame rotating with the rhythmic precision of an MRI machine. You can feel it scanning deeper than skin, past muscle and bone, searching your internal architecture for some specific configuration of tissue and memory. The moss patterns shift from maze to flowchart to assembly code, documenting its analysis of your biological source code in real-time. When it finally locks onto whatever it was searching for, the dish emits a single pure tone that matches the resonant frequency of your skull.",
          "The copper network awakens fully, each wire now humming with the exact harmonic signature of a 56k handshake\u2014that digital song that used to announce connection to the early internet. But this sound carries extra frequencies, subharmonics that vibrate in your teeth and make you taste ozone. The network is establishing a connection, but not to any server you've ever known. When the handshake completes, you feel it in your spine, a click of acknowledgment between your nervous system and whatever vast distributed consciousness has made this forest its home.",
          "The copper wire goes slack, then taut, then slack again\u2014a pulse, or a breath, or the motion of something large turning over in the dark at the center of a structure whose architect signed the blueprints D. AEDALUS and then walked away. You remember that Daedalus flew out. You remember that Icarus did not. You have no wings and the wire is warm under your fingertips and the forest is already rearranging itself around you like a door closing.",
        ],
      ),
      Paragraph(
        id=uuid.uuid4().hex,
        text=pick(
          [
            "Your crumpled MapQuest printout terminates with an instruction that wasn't there at the last gas station: 'CONTINUE BY INTUITION' in a font that perfectly matches your own handwriting, down to the slight tremor you developed after too many caffeine-fueled coding sessions. The paper feels different now, less like standard printer stock and more like the punch cards your programming professor kept in a hermetically sealed case, each fold and crease encoding additional data you can almost read with your fingertips. When you try to refold it along the original lines, the creases multiply fractally, creating new paths that branch between the official roads like unauthorized hyperlinks.",
            "The map in your hands undergoes spontaneous revision, fresh lines bleeding through the inkjet paper like dark veins surfacing under pale skin. These new paths are labeled in a prototype version of MS Gothic\u2014that system font you remember from countless error messages\u2014each one marked as BETA with build numbers that include impossible dates. The legend updates itself in real-time, symbols shifting between standard cartographic notation and snippets of pseudocode that seem to describe algorithms for navigating non-Euclidean space. Every time you blink, the map's topology grows more complex, as if it's gradually importing the true structure of this place into your reality's limited coordinate system.",
            "A sharp vibration from your hip makes you jump\u2014the ancient pager you kept out of nostalgia or paranoia suddenly active after years of silence. The LCD display renders its message in the crisp pixels you remember from your first programming job: 'WELCOME TO OFFSITE OFFICE [LOCALHOST]. FOLLOW SIGNAL INTEGRITY.' The message should be too long for the pager's buffer, but it continues scrolling, the text now describing your exact position using coordinates that reference both physical space and some other set of dimensions you can feel but not quite comprehend. When you look up from the display, the forest has rearranged itself to match the topology suggested by those impossible coordinates.",
          ]
        ),
        mutations=[
          "The pager screen fragments into ASCII art, characters cascading like rain against the liquid crystal before resolving into a map of your own neural pathways. The display shows connection attempts, your synapses handshaking with something that understands consciousness as a network protocol. The last message blinks three times: 'HUMAN INTERFACE DETECTED // DRIVER INSTALLATION INITIATED' before the screen fills with question marks that seem to float above the surface of the LCD.",
          "The map's paper thins to transparency, then thickens into something that feels like a hybrid of vellum and magnetic tape. The edges char and curl not with heat but with information density, new passages writing themselves into existence as the document attempts to represent higher-dimensional network topologies in physical space. You can see your own location marked by a cursor that blinks in sync with your pulse, leaving a trail of breadcrumbs formed from executable code.",
          "The MapQuest printout now has a second page that wasn\u2019t there before. It shows the interior of the structure\u2014a floor plan drawn in the style of ancient Minoan architecture, corridors branching in the non-repeating pattern that archaeologists found at Knossos and have never fully explained. In the center of the plan, where the legend should be, someone has typed: YOU ARE ALREADY HERE.",
        ],
      ),
    ]

  def _maze_depth_a_paragraphs(self, emotional_track: str) -> List[Paragraph]:
    track = emotional_track or “glitchy”
    pool = {
      “seductive”: [
        “Copper filaments climb the birches, braiding into crude antennae that lean toward you.”,
        “Hold music winds through the pines, the melody matching your ex’s laugh.”,
        “A golden wire descends from the canopy in a slow spiral, winding around a birch trunk the way Ariadne\u2019s thread must have moved in the dark of the Cretan labyrinth\u2014purposeful, luminous, leading somewhere specific. The forest has arranged itself around this thread as if the wire is the structural principle, the thing that gives the corridor its shape, and you understand in a way that bypasses language that the seduction here is old: it predates electricity, predates copper, predates the idea of an office. The thread wants you to follow it. The thread has always wanted someone to follow it. The last one who did left their initials carved into a birch trunk fifty meters ahead, and the bark has healed over them so completely that only the indentation remains, the ghost of a name.”,
      ],
      “bureaucratic”: [
        “Tarps stretch between trees, stamped with LABYRINTHE SYSTEMS PROPERTY in bleeding ink.”,
        “A reception desk without walls spins slowly, drawers opening to reveal toner cartridges.”,
        “The tarp overhead bears a laminated placard, wrinkled with damp: LABYRINTHE SYSTEMS // CORRIDOR K // REF: THE CASTLE (KAFKA, F.) // PROPERTY ACCESS REQUIRES FORM J-7-DELTA. No one has ever brought the right form. You begin to understand that the forms are not the point\u2014the point is the corridor, the waiting, the slow accumulation of paperwork in a building that has no exit because no one has ever tried to leave using the correct documentation. You are already filling out Form J-7-Delta in your head, and the answers you\u2019re generating feel like they were written for you long before you arrived.”,
      ],
      “glitchy”: [
        “Phone poles sprout from the moss, their lines connecting to nothing. The path reboots with every footfall.”,
        “LiveJournal comments float like fireflies, their timestamps recalculating midair.”,
        “The bookshelves materialize between pine trunks like a memory you can’t have\u2014hexagonal chambers receding into the forest dark, each shelf crammed with volumes whose spines display error codes rather than titles. You recognize the architecture from a Borges story you read in a college lit course: the Library of Babel, the infinite maze of books that contains every possible text, including the one that describes this exact moment and the several thousand variants in which you make different choices. The volumes nearest to you are labeled with timestamps from tonight. One of them has your name on it.”,
      ],
      “panicked”: [
        “Footsteps echo half a second behind you, stumbling whenever you do.”,
        “Warning tones blare from unseen servers; the path ahead keeps jittering away.”,
        “Something large moves in the static between the trees, displacing branches with a rhythm you recognize as breathing\u2014slow, bovine, patient as geological time. The footprints in the moss ahead of you are too deep and too wide, the toes facing the wrong direction, and you feel the certainty that precedes panic: the certainty that Theseus, in the original telling, had something you don\u2019t\u2014a thread, a sword, a reason to believe the monster at the center could be killed rather than become. The pager on your hip vibrates twice. The display reads: NO THREAD DETECTED. NAVIGATE BY INSTINCT.”,
      ],
    }
    sentences = pool.get(track, pool[“glitchy”])
    return [
      Paragraph(
        id=uuid.uuid4().hex,
        text=pick(sentences),
        mutations=[
          “Paragraph refactors mid-sentence when you scroll.”,
          “A second version of the sentence appears, contradicting the first.”,
          “The text rewrites itself in a font you don\u2019t recognize, the letters resembling ancient Linear B script\u2014the syllabic alphabet used at Knossos, untranslated for centuries, still only partially decoded. You can\u2019t read it. You feel like you almost can.”,
        ],
      ),
      Paragraph(
        id=uuid.uuid4().hex,
        text=pick(
          [
            “The map in your palm redraws itself whenever you breathe. Corridors slide around like code being refactored.”,
            “A soft click behind you signals the corridor rewriting. Footprints you made five seconds ago now belong to someone else.”,
            “The maze has a plan\u2014you can feel the plan the way you can feel the load-bearing walls in a building when you lean against them, a resistance that is also a kind of architecture. In the old myths, the labyrinth was designed so that no one inside could find the exit without knowing the design in advance. The design changes here. The design is watching you to see what you know.”,
          ]
        ),
        mutations=[
          “Map refreshes: ROUTE RECOMPILED. You never saw the original.”,
          “Every step triggers a soft chime: PATH UPDATED.”,
          “The path curves back on itself in the non-repeating spiral pattern of the Chartres Cathedral labyrinth\u2014eleven circuits, one entrance, one center. Medieval pilgrims walked it on their knees. You are walking it on your feet and it is taking you somewhere they never went.”,
        ],
      ),
      Paragraph(
        id=uuid.uuid4().hex,
        text=pick(
          [
            “Analog monitors perch on stumps, each showing a different version of this moment. In one, you turn back. In another, you smile.”,
            “A PA system tucked into the branches whispers status updates: \u201cContractor en route. Emotion state: {track}.\u201d The word dissolves before you finish reading it.”.format(
              track=track.upper()
            ),
            “Every gust of pine needles spells out a memo: DO NOT TRUST STATIC MAPS. The letters scatter when you blink.”,
          ]
        ),
        mutations=[
          “Monitors desync; one shows someone else wearing your jacket.”,
          “PA system glitches into laughter, then apologizes.”,
          “One monitor displays a still from a Piranesi etching\u2014the Carceri d\u2019invenzione, the imaginary prisons, all impossible staircases and recurring arches that go nowhere and everywhere. The caption beneath it reads: INSPIRATION FOR CURRENT ARCHITECTURE. DATE: 1745. RENOVATION: ONGOING.”,
        ],
      ),
    ]

  def _maze_depth_b_paragraphs(self, emotional_track: str) -> List[Paragraph]:
    moods = {
      "seductive": [
        "Polaroids pinned to bark develop into scenes of warmth: your old apartment, minus the arguments.",
        "A coworker you almost loved beckons, promising a desk with your name already engraved.",
        "The figure appears between the ferns as a metaphor first\u2014a shape that isn\u2019t quite animal and isn\u2019t quite architectural\u2014and then it solidifies: someone in a pale suit with eyes that have been open too long, holding out an offer letter with your name already in the signature field. This is the oldest trick in the labyrinth\u2019s playbook, older than Borges and older than Ovid: the guide who is also the trap, the beautiful voice that leads you deeper by making deeper feel like the way out. The letter is warm from being held. The name in the signature field is spelled correctly.",
      ],
      "bureaucratic": [
        "Dot-matrix printouts hang from branches, listing action items you never completed.",
        "Fax machines spit out maps with corridors crossed in red pen, initialed by you.",
        "The corridor widens into something Kafka would have recognized: a waiting room with no chairs, a desk with no one behind it, a number ticket dispenser showing 404. The walls are papered with forms requiring your signature on lines that keep moving, and a voiceover from a speaker you can\u2019t locate announces in a pleasant tone that your request has been processed, your request is being processed, your request will be processed when the system is no longer experiencing unusual wait times. The maze, you understand, is not hostile. It is merely bureaucratic, which is a different thing and somehow worse.",
      ],
      "glitchy": [
        "Static hangs like fog. Shapes move inside it: cubicles, break rooms, a copy of your apartment with the lights on.",
        "Each tree now has a username carved into it; some belong to people you only knew online.",
        "The house was supposed to be smaller on the outside\u2014that\u2019s the rule, the fundamental architectural violation that signals a labyrinth consuming its own geometry. You remember reading about it, the footnotes piling up in the paperback in your bag, the ones you highlighted in blue during an all-nighter three years ago: the house grows in the dark, its corridors add footage that cannot be measured, the dimensions recorded by any instrument become unreliable the moment you stop looking at them. You are inside the growing part. The corridor behind you is longer than it was.",
      ],
      "panicked": [
        "A Windows error chime rolls through the trees. The blue screen hovers in midair, waiting for you to read it.",
        "Your pager vibrates with TURN AROUND, but the same pager in your pocket refuses to display anything.",
        "The Minotaur\u2019s mythology got one thing wrong: the monster was not waiting. It was pacing. You can hear it now\u2014a slow, rhythmic displacement of branches that carries the weight of something much larger than the forest should contain, something that has been walking the same path for so long that it has worn a groove in the ground you are now standing in. Theseus had a sword and a thread. You have a ThinkPad at 12% battery and a MapQuest printout that no longer describes this place. The pager vibrates: THREAD STATUS: NONE DETECTED. RECOMMEND: IMPROVISE.",
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
          "The scene is identical except that in the margin, in handwriting that belongs to no one in the room, someone has written: ASTERION ALSO WAITED HERE. DO YOU KNOW WHO ASTERION WAS? HE WAS THE MINOTAUR\u2019S REAL NAME. HE CHOSE TO STAY.",
        ],
      ),
      Paragraph(
        id=uuid.uuid4().hex,
        text=pick(
          [
            "Time hiccups; the breath you just took happens twice.",
            "A figure in a clipped PowerPoint suit mirrors your motions. When you wave, she keeps typing.",
            "The corridor geometry shifts into something Escher would have drawn\u2014not impossible exactly, but structurally committed to a logic that human bodies were not designed to navigate, staircases ascending in directions that are simultaneously up and inward, doorways aligned with other doorways in a perspective that makes every exit also an entrance. You have seen this in M.C. Escher prints on dormitory walls. You did not expect to walk inside one. The figure at the desk at the center of the impossible geometry does not look up when you enter. She has been here longer than the architecture.",
          ]
        ),
        mutations=[
          "She mouths your old pet name, then static erupts.",
          "Her outline flickers between familiar and stranger every frame.",
          "The figure turns and you see that her face is a slight variation on yours\u2014the features approximately correct, the proportions off by something you can\u2019t measure. Borges wrote about this: the double, the other, the self that the labyrinth manufactures from the raw material of whoever walks into it. She smiles. Her teeth are your teeth. She goes back to typing.",
        ],
      ),
      Paragraph(
        id=uuid.uuid4().hex,
        text=pick(
          [
            "Someone has pinned your performance reviews to a tree, but the bullet points describe feelings instead of metrics.",
            "A door made of Ethernet cable swings open to reveal your apartment as it was in 2001. The door closes before you decide to enter.",
            "A LiveJournal poll dangles from a branch asking: DO YOU TRUST THE VOICE ON THE LINE? The options flicker between YES and MAYBE.",
            "The moss on the ground has grown in a pattern\u2014circular, recursive, the eleven-circuit design of a medieval labyrinth laid out across twenty meters of forest floor. Chartres. Hampton Court. Troy Town. The pattern appears independently in cultures that never contacted each other, which means either it encodes something fundamental about the way minds navigate space, or something fundamental about space itself imposed the pattern on every mind that tried to map it. Your footprints, you notice, have been following the circuit without your instruction.",
          ]
        ),
        mutations=[
          "Review rewrites itself to praise your ability to stay lost.",
          "The Ethernet door reopens with a mirror image watching you.",
          "The labyrinth pattern in the moss shifts\u2014the circuits realign, the center moves, the entrance becomes the exit and the exit becomes somewhere else. Underneath the pattern, barely visible through the moss, is an engraving in concrete: LABYRINTHE SYSTEMS // FOUNDATION LAID // ORIGINAL DESIGN: KNOSSOS, 1400 BCE // RENOVATION: CONTINUOUS.",
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
          "The pod squats in the ferns like the center of something ancient\u2014not Minoan exactly, not quite Cretan, but cut from the same structural logic: a room built to contain someone who does not know they are contained. The contract number on the door is yours. The labyrinth knew your number before you did.",
        ],
      ),
      Paragraph(
        id=uuid.uuid4().hex,
        text="Through the security glass a figure with your slouch sits at an identical desk, fingers hovering over a keyboard that types a beat ahead of you. The keypad blinks: REGISTER USER TO PROCEED.",
        mutations=[
          "The ghost behind the glass smiles late, echoing your breath. KEYPAD STATUS: registration pending.",
          "REGISTER TO CONTINUE pulses in amber. The mirror-worker raises their head when you swallow.",
          "The figure behind the glass is what Borges called \u2018the other\u2019\u2014a self the labyrinth constructs from whomever enters it, built to occupy the center while the original wanders the corridors. It has your posture and your keyboard habits and a look on its face that you recognize as the look you have when you are waiting for something you know is coming. The keypad blinks: REGISTER TO CONFIRM WHICH ONE IS YOU.",
        ],
      ),
      Paragraph(
        id=uuid.uuid4().hex,
        text="A post-it note curls on the interior window: WELCOME, CONTRACTOR. BRING YOUR OWN MEMORY. Someone underlined memory three times.",
        mutations=[
          "Sticky note reads: BRING YOUR OWN MEMORY. Someone added: OR WE WILL SUPPLY ONE.",
          "Another hand scrawled: DON’T LEAVE UNTIL YOU’RE SURE IT’S YOU.",
          "A second note, smaller, in different handwriting, is stuck beside the first: THE MINOTAUR WAS ALSO A CONTRACTOR. HE ALSO DID NOT KNOW HE WAS THE CENTER. REGISTER. FIND OUT WHICH ONE YOU ARE.",
        ],
      ),
    ]

  def _hud_for_scene(self, scene_id: str) -> str:
    return {
      "chapter_one.arrival": pick([
        "LINK ESTABLISHED. LET THE TEXT PULL YOU UNDER.",
        "ARIADNE LEFT NO THREAD. YOU CAME ANYWAY.",
        "LABYRINTHE SYSTEMS: ALL MAZES HAVE A CENTER. OURS HAS SOMETHING OLDER.",
      ]),
      "chapter_one.departure": pick([
        "ROAD OPEN. WATCH FOR STATIC.",
        "THE ROAD NORTH IS DAEDALUS\u2019 FIRST CORRIDOR. DO NOT TURN BACK.",
        "ARIADNE\u2019S THREAD STATUS: UNCONFIRMED. NAVIGATE BY INSTINCT.",
      ]),
      "chapter_one.maze_edge": pick([
        "THE TREES ARE LISTENING.",
        "THE MINOTAUR KNOWS YOUR SIGNAL. CHOOSE A PATH.",
        "DAEDALUS BUILT THIS. THESEUS NEVER FOUND THE EXIT. YOU HAVE BETTER EQUIPMENT.",
      ]),
      "chapter_one.maze_depth_a": pick([
        "KEEP READING. THE CORRIDOR IS ONLY WARMING UP.",
        "BORGES MAPPED THIS ROOM. HIS MAP WAS WRONG. YOURS WILL BE DIFFERENT.",
        "THE LIBRARY HAS NO WALLS. KEEP WALKING.",
      ]),
      "chapter_one.maze_depth_b": pick([
        "THE MAZE LIKES WHEN YOU LOOK BACK.",
        "THESEUS DID NOT RETURN. THE CORRIDOR WILL REMEMBER YOU LONGER.",
        "THE MINOTAUR IS AT THE CENTER. THE CENTER IS CLOSE. KEEP READING.",
      ]),
      "chapter_one.office_threshold": pick([
        "THE DOOR WANTS A NAME. REGISTER TO CONTINUE.",
        "KNOSSOS PROTOCOL ACTIVE. YOU HAVE REACHED THE CENTER. REGISTER TO PROCEED.",
        "THE MINOTAUR WAS ALSO A CONTRACTOR. REGISTER TO FIND OUT WHICH ONE YOU ARE.",
      ]),
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
            "LABYRINTH MYTHOLOGY & LITERARY REFERENCES:\n"
            "- Weave in references to famous labyrinths and labyrinth mythology: the Cretan labyrinth (Daedalus as architect, Theseus as hero, Ariadne's thread as guide, the Minotaur as what waits at the center)\n"
            "- Reference great literary labyrinths: Borges' Library of Babel and Garden of Forking Paths, Kafka's Castle (bureaucratic maze), House of Leaves' impossible geometry, Umberto Eco's labyrinthine library\n"
            "- Visual labyrinth references: Piranesi's Carceri etchings (imaginary prisons), M.C. Escher's impossible architectures, the Chartres Cathedral labyrinth (eleven circuits, walked on knees by pilgrims)\n"
            "- Archaeological labyrinth: Knossos palace as original inspiration, Linear B script, Minoan architecture\n"
            "- These references should feel EARNED, not forced—like the protagonist's mind reaching for cultural touchstones in extremis, or the maze itself revealing its mythological DNA\n"
            "- Ariadne's thread = the copper wire network; Daedalus = the unnamed architect; the Minotaur = whatever occupies the center of the corporate structure\n"
            "- The maze knows its mythology and occasionally quotes it back at the reader\n"
            "\n"
            "AVOID: Modern slang, explicit gore, cheap jumpscares, exposition dumps\n"
            "EMBRACE: Uncanny warmth that curdles, liminal spaces, technological decay, memory unreliability, mythological resonance that makes the horror feel ancient\n"
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
