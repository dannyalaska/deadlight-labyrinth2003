````markdown
# 🧠 AI Labyrinth – Story App Architecture Guide

## 🎯 Project Vision
Create a generative, interactive horror story that adapts to each reader. Every session is different. The maze changes. The protagonist changes. The text itself rewrites when you look back. It starts like a story. Then it becomes an experience. Then it becomes *you*.

---

## 🧱 1. Break Free of Single-LLM Limits

**Goal:** Make the story feel alive, not pre-baked.

### 🔧 Architecture:
Use **LangChain** or **LangGraph** to orchestrate modular agents:
- **Narrative Agent** → Expands prompts into vivid scenes.
- **Twist Agent** → Injects surreal logic or emotional shifts.
- **Meta Agent** → Watches user behavior and feeds it into the story.
- **Style Agent** → Alters tone/grammar/genre based on emotional or narrative "path."

> Bonus: Add **prompt mixing + memory** to allow callbacks, déjà vu, false memories, etc.

---

## ⚙️ 2. Event-Driven Engine (Scene-Based)

**Goal:** Modular chapters that behave differently every read.

### 🗂 Scene Structure:
Each scene is a JSON block:

```json
{
  "id": "forest_office",
  "goal": "Get user disoriented and curious",
  "entry_conditions": ["user_has_seen_intro"],
  "path_choices": {
    "left": "foggy_field",
    "right": "mirror_corridor"
  },
  "prompt_seed": "Ben approaches the office path. The woods are thicker today.",
  "mood": "haunted curiosity",
  "generation_rules": {
    "length": "short",
    "style": "fragmented"
  }
}
````

Scene transitions driven by:

* User phone tilt
* Inactivity
* Reading pace
* Prior path history

> Use SQLite (long-term) + Redis (short-term) to manage session state + flash memory.

---

## ⚡ 3. Fast + Reactive UX

**Goal:** Readers feel like they're in control, not waiting.

### 💡 Frontend Stack:

* **Next.js** (React + SSR) for performance + routing
* **Tailwind CSS** or **CSS-in-JS** for UI styling
* **Framer Motion** or custom Canvas code for:

  * Tilt-based branching
  * Floating, fading text
  * Subtle animation of scenes
  * Cursor blinking, loading trails

> Visual tone = *early 2000s command line*, not “retro-futurism”

---

## 🔮 4. Generative Creative Story Engine

**Goal:** Let the AI *surprise even the writer*.

### 🧬 Techniques:

* Use **Claude Sonnet or Haiku** for scene generation
* Prime each scene with:

  * Scene JSON block
  * Global story themes + tonal guide
  * Prior choices
  * Character state
  * User-specific memory (optional)

#### 🛠️ Sample System Prompt:

> *“This is a generative techno-horror about losing identity in a digital labyrinth. The story should feel intimate, disorienting, and a little too real. Be poetic, cinematic, and nonlinear.”*

* Add a **weirdness slider** (invisible to user) to toggle creative chaos.
* Let *contextual memory* distort. Generate false memories.

---

## 🔐 5. Optional Features

* **User login / chapter tracker**: Use Supabase or Firebase.
* **Analytics engine**: Track paths, scrolls, tilts. Use to shape future chapters.
* **Phone tilt input (JS only)**:

  * Activate only during maze scenes
  * Text splits subtly left and right
  * Tilt determines which side grows, which one fades
  * Use **DeviceOrientation API**

> Example: At the fork in the story, two paths begin. Tilt left and that text continues. Tilt right and *another* text unrolls. The other fades like fog.

---

## 🧰 Recommended Stack

| Layer        | Tool                        | Purpose                               |
| ------------ | --------------------------- | ------------------------------------- |
| Frontend     | Next.js + Tailwind + Framer | Tilt-reactive UI, fast SSR rendering  |
| Backend      | FastAPI / Node              | Scene serving, auth, API coordination |
| Story Engine | LangGraph / LangChain       | Modular LLM agents + routing          |
| LLM          | Claude Sonnet + Haiku       | Scene + prompt generation             |
| DB           | Supabase / SQLite + Redis   | User save + session + scene memory    |
| Hosting      | Vercel + Fly.io             | Global, scalable                      |

---

## 💡 Deployment Strategy

* **Today**: Teaser chapter (1–2 scenes), public web demo with tilt
* **This Week**: Add login + scene tracker, full Chapter 1
* **Later**: Publish to iOS App Store with deeper hardware hooks

---

## 🌀 Experience Design

* Black screen, white monospace text
* Cursor blinking
* Text occasionally shifts subtly as if it's not quite stable
* Only 1 paragraph visible at a time
* Scrolling is locked or lags
* Look back? Text *slightly* changed

> It’s not about gameplay. It’s about psychological pull.

---

## 🚪 Chapter 1: The Hook

Set in 2003. No smartphones. Forums, AOL, shadows in CRT glow.
Ben (or the user’s name, blurred and changed) discovers a link.
The labyrinth begins. And *you’re still in it*.

---
