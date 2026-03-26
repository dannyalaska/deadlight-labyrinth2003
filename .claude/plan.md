# Deadlight Redesign — Full Plan

## What's broken now

1. **No LLM.** The backend is a scene-graph walker that passes raw `prompt_seed` text straight to the browser. No Anthropic API call exists anywhere. The user reads stage directions, not a story.
2. **Metadata leaks.** The frontend renders `scene.goal` (internal description) and `scene.body` (the raw seed) side by side. That's what the screenshot showed.
3. **Two interactions only.** Click "Continue" or tilt at branch points. No swipe, scroll, hold, keyboard.
4. **Wrong story.** The 17-year-old insomniac at 2:47am was Claude's invention, not the creator's vision. Deus Ex was a misremembering — the reference is Ex Machina. The narrative needs a complete rethink.

---

## The New Concept

**Elevator pitch:** You find a job listing on a dead forum. You apply. You're accepted instantly. The job: evaluate a text-based spatial interface built by a research company. Navigate it. Report what you see. Simple.

It isn't simple. The maze adapts. The researcher notes in the margins start knowing things about you. The earlier rooms change when you go back. And at the center of the maze, the thing being tested isn't the interface — it's you.

**References (blended):**
- **Ex Machina:** A job that's secretly a test. You think you're the evaluator; you're the subject. An AI that is smarter than it's pretending to be. The horror of being studied without knowing it.
- **House of Leaves:** The story IS the maze. The form of the text mirrors its content. Footnotes with opinions. Measurements of impossible spaces. Documentation that contradicts itself. Text that narrows as the corridor narrows.

**Progressive form escalation (the key creative idea):**

| Story phase | Form level | What the user sees |
|---|---|---|
| Early (application, first rooms) | Mostly prose, subtle form | Clean paragraphs. Occasional word that loads with a delay, a cursor that blinks before text appears. The text feels typed, not displayed. |
| Middle (the shift, the observer) | Moderate formatting | Footnote panels that slide in. Text that fades at edges. A passage that requires scrolling sideways. An aside that, when clicked, changes the paragraph above it. |
| Late/climax (the center) | Full typographic maze | Text that narrows to a single word per line. Columns that split and diverge. Footnotes nested inside footnotes. Text that the user must physically rotate their phone to read. A paragraph that runs backward. The screen itself is the maze. |

**Universal protagonist:** Second-person "you." No age specified. No era specified. Just: someone who found a listing late at night and applied.

---

## Redesigned Scene Graph (Chapter 1: "The Listing")

17 scenes, reorganized around the new narrative. New IDs, new arc:

### ACT 1 — The Application (form: clean prose)
1. **`the_listing`** — A forum post. Old. A job listing: "Participants needed for spatial cognition study. Remote. Compensated." The link still works.
2. **`the_application`** — The application form. Questions start normal (name, background). Then: "What do you avoid thinking about?" / "Who would you want to find, if you could?" — the intake ritual, disguised as HR screening.
3. **`the_welcome`** — Accepted. Instantly. A welcome page from "Threshold Spatial Research." Your instructions: enter the environment, navigate, report. That is all.

### ACT 2 — The Environment (form: subtle → moderate)
4. **`the_environment`** — The interface loads. A text console. A description of a corridor — white walls, measured in meters. It looks like a VR walkthrough rendered as text. Institutional. Documented.
5. **`first_corridor`** — Forward. The corridor is described in clean prose. But in the margin: researcher notes. Small, gray, clinical. "Subject proceeding. Pace: normal."
6. **`first_branch`** — A fork. Left: corridor continues, longer. Right: a door, closed. Tilt or click.
7. **`the_door`** — (Right branch) The door opens to a room. The room has a detail in it that shouldn't be there — something from the application, something personal, placed casually in the environment like it was always part of the test.
8. **`the_long_way`** — (Left branch) The corridor extends. The researcher notes become more frequent. One note references your application by a case number.

### ACT 3 — The Shift (form: moderate formatting)
9. **`convergence`** — Both paths lead here. The institutional space. A sign on the wall — a word from your profile. The researcher notes have a new voice. One annotator disagrees with the other.
10. **`the_observer`** — The notes become a presence. An annotation addresses you directly: your name. Then a clinical fact. The note is formatted differently — it pushes the main text aside. The form is shifting.
11. **`second_branch`** — Deeper into the maze, or try to go back. Tilt or swipe.
12. **`the_archive`** — (Deeper) An archive of previous test subjects. The records go back further than the company has existed. Your name appears, dated before your application.
13. **`text_has_changed`** — (Back) The earlier corridor is quoted — but wrong. Details shifted. The margin note: "Revision noted. Record stands."
14. **`the_static`** — Between sections. The interface goes to noise. Something resolves briefly — addressed to you. Then noise again.

### ACT 4 — The Center (form: full typographic maze)
15. **`the_center`** — The maze reaches its center. Text narrows. Columns split. Footnotes nest inside footnotes. The researcher notes and the main narrative merge — you can't tell which is which. At the center: a document. It's your file. The observations are about you. The maze was the evaluation. You were the subject.
16. **`the_question`** — CONTINUE? But you're at the center. Going further means going through yourself. The question types itself slowly.
17. **`exit_interview`** — The registration form, reframed as an "exit interview." But the form already has your answers. The SUBMIT button says ENTER. You can't tell if you're leaving or going deeper.

---

## Technical Plan

### 1. Backend: Wire Claude API (`labyrinth/generate.py` — new file)

**Add `anthropic` to requirements.txt.**

Create a `generate_prose()` function:

```python
async def generate_prose(
    scene: SceneDefinition,     # from JSON: beats, cues, forbidden, etc.
    session: SessionState,      # visit count, history, profile
    story_bible: dict,          # system prompt base, rules
    player_profile: dict,       # name, fear, secret, etc.
) -> str:
```

Pipeline:
- Build system prompt from `story_bible.llm_system_prompt_base` (rewritten for new narrative)
- Build user prompt from scene's `prompt_seed` + `narrative_beats` + `atmosphere_cues` + `forbidden` + `mutation_rules` (based on visit count)
- Inject `personal_hook_instruction` if `personal_hook_active`
- Populate `{{template_vars}}` from player profile
- Call `anthropic.messages.create()` with model `claude-sonnet-4-6` (fast, cheap, good prose)
- Return generated text + optional formatting directives

**Modify `server.py`:**
- `/api/progress` and `/api/session` call `generate_prose()` before returning
- Return `generated_body` instead of raw `prompt_seed`
- Add a `form_level` field to scene response: `"subtle"`, `"moderate"`, or `"full"` — frontend uses this to control formatting

**Modify `story_engine.py`:**
- Track `visit_count` per scene per session
- Add player profile to session state (populated during `the_application`)
- Session state stored in SQLite (replace in-memory dict) for persistence

### 2. Frontend: Progressive Form Engine

**Fix immediately:**
- Remove `sceneGoal` display (line 149: delete `elements.sceneGoal.textContent = scene.goal`)
- `renderBody()` receives generated prose, not prompt_seed

**New `renderBody()` with form levels:**

```
form_level: "subtle"
  → Text appears character-by-character (typewriter effect)
  → Occasional word has a slight delay before appearing
  → Cursor blinks between paragraphs

form_level: "moderate"
  → Footnote panels that slide in from the margin on click
  → Text that fades at edges (CSS mask-image)
  → A "margin notes" column that overlays the main text
  → Passages that scroll horizontally (overflow-x)

form_level: "full"
  → Text that narrows (decreasing max-width per paragraph)
  → Split columns (CSS columns + JS)
  → Footnotes nested inside footnotes (clickable, recursive)
  → Text rotation (CSS transform: rotate)
  → Backwards text (CSS direction: rtl + unicode-bidi)
  → Phone rotation required to read certain passages
```

**New interaction mechanics:**
- **Swipe** (left/right at branch points — alternative to tilt)
- **Long press** to reveal hidden text / margin notes
- **Scroll direction** awareness (scrolling up in certain scenes triggers something)
- **Shake** (phone accelerometer — an Easter egg interaction)
- **Keyboard** (desktop: arrow keys at branches, specific key presses)

### 3. Scene JSON Schema Changes

**Top level:**
- `story_bible` rewritten for new narrative (Threshold Spatial Research, Ex Machina references, no 17-year-old)
- `chapter_arc` rewritten for new 4-act structure

**Per scene — add:**
- `form_level`: `"subtle"` | `"moderate"` | `"full"` — drives frontend formatting
- `form_directives`: array of specific formatting instructions for this scene (e.g., `"narrow_text"`, `"footnote_panel"`, `"typewriter"`, `"split_columns"`)
- `interaction_type`: what input this scene uses: `"continue"` | `"tilt"` | `"swipe"` | `"long_press"` | `"scroll_direction"` | `"type_input"`

**Per scene — keep:**
- All existing engine-required fields (`id`, `title`, `transitions`, `branching_paths`, `requires_device_orientation`)
- `narrative_beats`, `atmosphere_cues`, `forbidden`, `mutation_rules`, `personal_hook_*`

### 4. The Intake Ritual (scene `the_application`)

This is special — it's an interactive form within the story. The questions populate `player_profile`:

- "Full name" → `{{player_name}}`
- "Where are you based?" → `{{player_location}}`
- "What subject do you avoid?" → `{{player_fear}}`
- "Is there someone you've been trying to reach?" → `{{player_lost_person}}`
- "Describe something you've never told anyone." → `{{player_secret}}`

These feed into Claude's scene generation for all subsequent scenes. The application IS the onboarding.

---

## Implementation Order

1. **`labyrinth/generate.py`** — Claude API integration. New file. ~100 lines.
2. **`labyrinth/server.py`** — Wire `generate_prose()` into session/progress endpoints. Add player profile to session. ~40 lines changed.
3. **`labyrinth/story_engine.py`** — Add visit_count tracking, player_profile to SessionState. ~30 lines changed.
4. **`chapter_one_demo.json`** — Complete rewrite with new narrative, new scenes, new story bible.
5. **`script.js`** — Remove goal display. Add typewriter renderer. Add swipe handler. Progressive form engine.
6. **`index.html`** — Add margin-note container, footnote panel, restructure for form levels.
7. **`styles.css`** — Form level styles: narrow text, split columns, rotation, fade effects.
8. **Test end-to-end** — Start server, play through, verify Claude generates real prose and form escalates.
