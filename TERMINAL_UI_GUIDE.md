# 🌲 Deadlight 2003 — Terminal UI Mode

## What Changed

Your Streamlit app has been completely redesigned with an **eerie 2003 console/terminal aesthetic** to match your HTML version, optimized for **mobile scroll-based reading** instead of button clicks.

---

## ✨ New Features

### 1. **2003 Terminal Aesthetic**
- **CRT scanline effects** that animate across the screen
- **Phosphor-green monospace text** (#00ff41) on pure black background
- **Screen flicker animation** simulating old monitors
- **Terminal-style header** with command prompt and status
- **Glowing text shadows** for that authentic CRT glow
- **Custom styling** that completely hides Streamlit's default UI

### 2. **Scroll-Based Navigation (Mobile-Optimized)**
- Stories **accumulate in an infinite feed** as you scroll
- **No more button clicking** required (though manual advance button is available)
- Each paragraph **appears and stays** on screen
- **Smooth scroll indicator** prompts you to "descend deeper"
- Branch decisions are the only time you need to tap

### 3. **Longer, Literary Narrative**
The AI prompt has been completely rewritten to generate:
- **3-6 sentence paragraphs** of dense, literary prose
- **NOT bullet points** — full immersive novel-style writing
- Rich sensory details and psychological depth
- Influenced by Stephen King + House of Leaves + tech horror
- Proper 2003 cultural references (AIM, LiveJournal, MapQuest, CRTs)

### 4. **Story Feed System**
- Paragraphs accumulate in `st.session_state.story_feed`
- Each item is timestamped and typed (paragraph vs. branch)
- Creates an **endless scroll experience** like a Twitter/Tumblr feed
- Past content remains visible (unlike the old app that replaced everything)

---

## 🚀 How to Use

### Start the Terminal UI
```bash
./start_terminal_ui.sh
```

### Access on Mobile (Same WiFi)
Open on your phone:
```
http://192.168.1.230:8501
```

### Stop the Maze
```bash
./stop_maze.sh
```

### Switch Back to Old UI (If Needed)
```bash
./start_labyrinth.sh  # Uses streamlit_app.py instead
```

---

## 📱 Mobile Experience

### Reading Flow:
1. **Open the URL** on your phone
2. **Scroll down** to read the story
3. **Keep scrolling** — new content will load automatically
4. When you hit a **FORK IN THE MAZE**, tap a choice button
5. **Continue scrolling** deeper into the narrative

### No Sidebar
The sidebar is completely hidden for immersive, distraction-free reading.

---

## 🎨 Visual Design Details

### Color Palette
- **Background**: Pure black `#000000`
- **Primary text**: Phosphor green `#00ff41`
- **Accent**: Cyan `#55f5ff` (for prompts and choices)
- **Muted**: Dark gray `#4a4a4a` (for metadata)
- **Warning**: Pink `#ff6b8b` (for registration)
- **Glitch**: Yellow `#ffec99` (for mutated paragraphs)

### Typography
- **Font**: IBM Plex Mono, Courier Prime, Courier New
- **Letter spacing**: 0.02em–0.3em (depending on element)
- **Line height**: 1.9 for readability
- **Font size**: 1.1rem base (responsive)

### Effects
- **Scanlines**: Horizontal lines that scroll vertically
- **CRT flicker**: Subtle opacity animation
- **Text glow**: Green shadow around text
- **Hover effects**: Text brightens and shifts
- **Glitch animation**: Horizontal jitter for mutated text

---

## 🔧 Technical Details

### File Structure
```
streamlit_app.py        # Original Streamlit app (still works)
streamlit_app_v2.py     # NEW: Terminal UI version
start_labyrinth.sh      # Original startup (uses v1)
start_terminal_ui.sh    # NEW: Starts Terminal UI (v2)
stop_maze.sh            # NEW: Universal stop script
```

### Key Changes in `streamlit_app_v2.py`

1. **Custom CSS Injection** (~300 lines of terminal styling)
2. **Story Feed System** (accumulating paragraphs instead of replacing)
3. **No Sidebar** (hidden for immersion)
4. **Terminal Header** (shows status, scene, session ID)
5. **Scroll Indicator** (prompts to continue)
6. **Auto-advance on scroll** (commented out — use manual button for now)

### Server-Side Improvements

**`labyrinth/server.py`** — Updated Claude prompts:
- System prompt emphasizes **literary quality** over game-like brevity
- Explicit instruction to write **3-6 sentence paragraphs**
- User prompt reinforces "generative novel" framing
- Expanded tone/voice/era guidance

---

## 📝 Content Length Improvements

### Before (Bullet Point Style)
```
"PO1 — Copper vines guide your steps."
"PO2 — Signal bars flicker as corridors shift."
```

### After (Literary Paragraphs)
```
[001] > The copper wire doesn't just lie across the path—it moves. Not like a snake, but like something trying to remember how a snake moves. Each strand catches the last of the daylight filtering through the pine canopy, throwing off that dull orange glow you associate with cheap ethernet cables from the Staples clearance bin. When you step near it, the hum changes pitch. Not louder, just... aware. It knows you're here, and it's been waiting long enough that it doesn't mind letting you know.

[002] > The trees around you aren't trees anymore, or they are, but they're also server racks wrapped in bark. Ferns grow between rack mounts. A squirrel pauses on a branch that doubles as a conduit, its tail flicking in time with the pulse of data you can't see but somehow feel in your teeth. The forest breathes in packets. The canopy drops shadows that look like terminal windows, black text on black background, waiting for input you don't have...
```

---

## 🎯 Next Steps / TODO

### Immediate Improvements
- [ ] **Auto-advance on scroll** — Currently using manual button; can implement scroll detection with JavaScript
- [ ] **Paragraph mutations** — When user scrolls back up, paragraphs should occasionally change
- [ ] **Mobile tilt controls** — Integrate device orientation for branch choices
- [ ] **Sound effects** — Add subtle 2003 computer sounds (modem, hard drive clicks)
- [ ] **Session persistence** — Save story feed to localStorage for returning users

### Content Improvements
- [ ] **Expand scene blueprints** with more detailed prompts
- [ ] **Add more decision points** (currently only one in Chapter One)
- [ ] **Tune mutation logic** — More interesting paragraph variants
- [ ] **Test with Claude** — Verify the new prompts generate longer content

### UX Polish
- [ ] **Loading states** — Show "LOADING..." when generating
- [ ] **Progress indicator** — Show scene depth (1/6, 2/6, etc.)
- [ ] **Back button** — Allow revisiting previous sections
- [ ] **Share session** — Generate shareable links for specific story states

---

## 🐛 Known Issues

1. **Auto-scroll not implemented** — Currently uses manual "Continue" button
2. **No localStorage** — Refresh loses your story progress
3. **Sidebar override incomplete** — Some Streamlit elements may still leak through
4. **Mobile testing needed** — Visual tweaks likely needed for different screen sizes
5. **Paragraph mutations not live** — Currently static after generation

---

## 💡 Design Philosophy

This redesign transforms your app from a **Streamlit demo** into an **immersive reading experience**:

- **No UI chrome** — Pure content focus
- **Scroll as narrative progression** — Natural mobile gesture
- **Accumulating content** — Like reading a feed or chat log
- **Terminal aesthetics** — Matches your vision document
- **Literary quality** — GenAI book, not a game

The goal is to make it feel like **discovering a cursed Tumblr blog from 2003** that you can't stop scrolling through.

---

## 📚 References

Your existing `styles.css` and `index.html` provided the visual direction. The new Streamlit app replicates those aesthetics while maintaining Streamlit's architecture for rapid development.

---

## 🎮 Quick Start Commands

```bash
# Stop any running maze
./stop_maze.sh

# Start Terminal UI mode
./start_terminal_ui.sh

# Check logs
tail -f logs/api.log
tail -f logs/streamlit_v2.log

# Access on desktop
open http://localhost:8501

# Access on mobile (same WiFi)
# Use: http://192.168.1.230:8501
```

---

**You're now running a generative horror novel with 2003 terminal vibes!** 🌲⚡📟
