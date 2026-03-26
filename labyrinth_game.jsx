import { useState, useEffect, useRef, useCallback } from "react";

// ─── SCENE DATA ─────────────────────────────────────────────────────────────
// Fully-written narrative for each scene. Each `body` is a function that
// accepts the player's name so it can be woven into the prose.

const SCENES = {
  boot_sequence: {
    id: "boot_sequence",
    title: "// WAKE_UP.EXE",
    body: (n) => `3:17 AM.

The monitor is still on. You don't remember leaving it on.

The blue-white phosphor glow stains the ceiling, the posters, the inside of your eyelids. Something made a sound — not outside. Not exactly inside. Somewhere in the space between your skull and the room. You're awake now.

The fan is spinning.
The fan is always spinning.

But tonight — something is different.

The cursor blinks at you from across the dark. It has always been blinking. You have stared at this cursor ten thousand times. But tonight it feels like it's waiting for something specific.

For you.`,
    choices: [{ label: "[ APPROACH THE SCREEN ]", next: "login_prompt" }],
  },

  login_prompt: {
    id: "login_prompt",
    title: "// USER_AUTH",
    body: (n) => `DEADLIGHT_OS v2.1.4
USER AUTHENTICATION REQUIRED

USERNAME: [                    ]

You type your name. The characters appear one by one in the little white box. ${n ? n : "Your"} name. The only name ${n ? "you've" : "you've"} ever had. You press ENTER.

The screen flickers — a single bad frame, a splice in reality — and when it resolves, the username field reads:

   ${n ? n.toUpperCase() : "BEN"}

${n ? "You typed that." : "You didn't type that."}${n ? " Good." : " You look at your fingers. The keys. The screen."}

${n ? n.toUpperCase() : "BEN"} blinks back at you from the box.

${n ? n.toUpperCase() : "BEN"} is waiting for ${n ? "itself" : "you"} to continue.`,
    choices: [{ label: "[ PRESS ENTER ]", next: "strange_forum" }],
  },

  strange_forum: {
    id: "strange_forum",
    title: "// POST #7741",
    body: (n) => `DEADLIGHT FORUMS
General Discussion / Thread #7741
Posted: 11 months ago — 0 replies — 1 view (you)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SUBJECT: has anyone been here

BODY:
you know the place.
you've always known it.
not a location. an architecture.
the mind has rooms you haven't found yet.
this is a door.

don't click unless you're ready
to not come back.

    [ maze.exe ]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

${n ? n : "You"} click${n ? "s" : ""} before ${n ? n : "you"} realize${n ? "s" : ""} ${n ? n + " is" : "you're"} doing it.`,
    choices: [{ label: "[ CLICK maze.exe ]", next: "maze_entry" }],
  },

  maze_entry: {
    id: "maze_entry",
    title: "// F O R K",
    body: (n) => `The text is splitting.

Left and right — two versions of the same sentence
diverging like a river finding two paths
to the same sea.

     Both true.               Both wrong.

One corridor         smells like fog
and something familiar you can't name.

                              The other shows you
                              your face.
                              But not your current one.

The words are pulling in opposite directions.
You can feel it in your hands.
You can feel it behind your eyes.

                        C H O O S E .`,
    choices: [
      { label: "[ GO LEFT  →  THE FOG ]", next: "left_corridor" },
      { label: "[ GO RIGHT →  THE MIRROR ]", next: "right_corridor" },
    ],
  },

  left_corridor: {
    id: "left_corridor",
    title: "// THE_FOG_HALL",
    body: (n) => `The corridor doesn't end.

It never was going to end.

The fog here isn't weather — it breathes. In. Out.
Slow. Patient. Matching something you don't have a name for yet.

${n ? n : "You"} walk${n ? "s" : ""} and the floor holds. Barely.
Sound has left — not silence. Absence.
There are shapes in the fog that might be architecture.
There are shapes in the fog that might be memory.
There are shapes in the fog that know your face.

                   you keep walking
                         the fog keeps breathing

${n ? n : "You"} realize${n ? "s" : ""}: you've been breathing with it.

Have been for a while now.

The fog asks nothing. It doesn't need to.
It already has what it wants.`,
    choices: [{ label: "[ KEEP WALKING ]", next: "black_terminal" }],
  },

  right_corridor: {
    id: "right_corridor",
    title: "// MIRROR_PATH",
    body: (n) => `There is a mirror at the end of the corridor.

This is fine. There are always mirrors.

But when ${n ? n : "you"} reach${n ? "es" : ""} it, the reflection is wrong.

Not wrong in the way of funhouse glass.
Wrong in the way of time.

The face looking back is ${n ? n + "'s" : "yours"}.
But the light on that face is different —
morning light, or late evening light —
and the expression is one ${n ? n : "you"} ${n ? "has" : "have"} not worn yet.

The face looks tired.
Tired in a way ${n ? n : "you"} ${n ? "is" : "are"} not tired yet.

                     B L I N K .

The mirror shows only ${n ? n : "you"}.
                          just ${n ? n.toLowerCase() : "you"}
                                    just now.

The other face is already somewhere else.
It went on without ${n ? n : "you"}.`,
    choices: [{ label: "[ LOOK AWAY ]", next: "black_terminal" }],
  },

  black_terminal: {
    id: "black_terminal",
    title: "//",
    body: (n) => `[SCREEN GOES BLACK]

      ...

      ...

[CURSOR BLINKS]

      ...

      ...

C  O  N  T  I  N  U  E  ?

      _`,
    choices: [{ label: "[ YES ]", next: "end" }],
  },

  end: {
    id: "end",
    title: "// END_OF_DEMO",
    body: (n) => `The labyrinth remembers those who enter.

If you want to be remembered —
if you want the maze to know your name
when the walls shift again —

leave something in the dark.

It doesn't have to be the truth.
The maze will decide what it is anyway.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

${n ? n.toUpperCase() + " has" : "YOU HAVE"} BEEN CATALOGUED.

PATH ARCHIVED.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CHAPTER 2 — LOADING . . .

                         [ SIGNAL LOST ]`,
    choices: [],
  },
};

// Path breadcrumbs shown at the bottom
const CRUMBS = {
  boot_sequence: "Woke up.",
  login_prompt: "Logged in.",
  strange_forum: "Clicked the link.",
  maze_entry: "Reached the fork.",
  left_corridor: "Chose the fog.",
  right_corridor: "Chose the mirror.",
  black_terminal: "Reached the end.",
  end: "Chapter complete.",
};

// Block-art glitch characters for the text mutation effect
const GLITCH_POOL = "░▒▓█▄▀▌▐╬╫╪╩╦╠═║╔╗╚╝01";
const rndGlitch = () => GLITCH_POOL[Math.floor(Math.random() * GLITCH_POOL.length)];

// ─── TYPEWRITER HOOK ────────────────────────────────────────────────────────
function useTypewriter(text, speed = 12) {
  const [displayed, setDisplayed] = useState("");
  const [done, setDone] = useState(false);
  const timer = useRef(null);

  useEffect(() => {
    setDisplayed("");
    setDone(false);
    let i = 0;
    const tick = () => {
      if (i < text.length) {
        setDisplayed(text.slice(0, i + 1));
        i++;
        // Slightly variable speed for organic feel
        const delay = speed + (Math.random() < 0.05 ? speed * 8 : 0);
        timer.current = setTimeout(tick, delay);
      } else {
        setDone(true);
      }
    };
    timer.current = setTimeout(tick, 400);
    return () => clearTimeout(timer.current);
  }, [text, speed]);

  return { displayed, done };
}

// ─── GLITCH TEXT COMPONENT ──────────────────────────────────────────────────
function GlitchText({ text, active }) {
  const [rendered, setRendered] = useState(text);
  const timer = useRef(null);

  useEffect(() => {
    clearTimeout(timer.current);
    if (!active) { setRendered(text); return; }
    let ticks = 0;
    const run = () => {
      if (ticks >= 6) { setRendered(text); return; }
      const arr = text.split("");
      const hits = Math.floor(Math.random() * 3) + 1;
      for (let k = 0; k < hits; k++) {
        const idx = Math.floor(Math.random() * arr.length);
        if (arr[idx] !== "\n" && arr[idx] !== " ") arr[idx] = rndGlitch();
      }
      setRendered(arr.join(""));
      ticks++;
      timer.current = setTimeout(run, 55);
    };
    timer.current = setTimeout(run, 300);
    return () => clearTimeout(timer.current);
  }, [text, active]);

  return <span>{rendered}</span>;
}

// ─── MAIN GAME COMPONENT ────────────────────────────────────────────────────
export default function LabyrinthGame() {
  const [phase, setPhase] = useState("intro"); // intro | name | playing | end
  const [playerName, setPlayerName] = useState("");
  const [nameInput, setNameInput] = useState("");
  const [sceneId, setSceneId] = useState("boot_sequence");
  const [history, setHistory] = useState([]);
  const [glitching, setGlitching] = useState(false);
  const [transitioning, setTransitioning] = useState(false);
  const [saveCode, setSaveCode] = useState("");
  const [loadInput, setLoadInput] = useState("");
  const [showSave, setShowSave] = useState(false);
  const [copied, setCopied] = useState(false);

  const scene = SCENES[sceneId] || SCENES.boot_sequence;
  const sceneBody = scene.body(playerName);
  const { displayed, done } = useTypewriter(transitioning ? "" : sceneBody, 11);

  // Periodic ambient glitch
  useEffect(() => {
    if (phase !== "playing") return;
    const iv = setInterval(() => {
      if (Math.random() < 0.25) {
        setGlitching(true);
        setTimeout(() => setGlitching(false), 500);
      }
    }, 4500);
    return () => clearInterval(iv);
  }, [phase]);

  const goToScene = useCallback((nextId) => {
    if (!nextId || transitioning) return;
    setTransitioning(true);
    setGlitching(true);
    setTimeout(() => {
      setHistory((h) => [...h, sceneId]);
      setSceneId(nextId);
      setGlitching(false);
      setTransitioning(false);
      setShowSave(false);
      if (nextId === "end") setPhase("end");
    }, 450);
  }, [sceneId, transitioning]);

  const handleSave = () => {
    const code = btoa(JSON.stringify({ playerName, sceneId, history }));
    setSaveCode(code);
    setShowSave(true);
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(saveCode).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  const handleLoad = () => {
    try {
      const s = JSON.parse(atob(loadInput.trim()));
      setPlayerName(s.playerName || "");
      setSceneId(s.sceneId || "boot_sequence");
      setHistory(s.history || []);
      setPhase(s.sceneId === "end" ? "end" : "playing");
      setLoadInput("");
      setShowSave(false);
    } catch {
      alert("[ ERROR: Invalid save code ]");
    }
  };

  const restart = () => {
    setPhase("intro");
    setPlayerName("");
    setNameInput("");
    setSceneId("boot_sequence");
    setHistory([]);
    setShowSave(false);
    setSaveCode("");
  };

  // ─── STYLES ───────────────────────────────────────────────────────────────
  const C = {
    green: "#3ddc67",
    dim: "#2a6640",
    text: "#d0ccbc",
    bg: "#060606",
    bgCard: "#0a0a0a",
    border: "#1a1a1a",
    muted: "#464640",
  };

  const css = `
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&display=swap');
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: ${C.bg}; }
    @keyframes blink { 0%,100%{opacity:1} 50%{opacity:0} }
    @keyframes scanmove { 0%{top:-100%} 100%{top:100%} }
    @keyframes fadeIn { from{opacity:0;transform:translateY(6px)} to{opacity:1;transform:translateY(0)} }
    .scan-beam {
      position: fixed; left: 0; right: 0; height: 40%;
      background: linear-gradient(to bottom, transparent, rgba(61,220,103,0.015), transparent);
      animation: scanmove 8s linear infinite; pointer-events: none; z-index: 50;
    }
    .scanlines {
      position: fixed; inset: 0;
      background: repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0,0,0,0.18) 2px, rgba(0,0,0,0.18) 4px);
      pointer-events: none; z-index: 49;
    }
    .maze-btn {
      display: block; width: 100%; background: transparent;
      border: 1px solid ${C.border}; color: ${C.green};
      font-family: 'IBM Plex Mono', 'Courier New', monospace;
      font-size: 0.78rem; letter-spacing: 0.12em;
      padding: 0.75rem 1.2rem; margin-bottom: 0.5rem;
      cursor: pointer; text-align: left;
      transition: border-color 0.15s, color 0.15s, background 0.15s;
    }
    .maze-btn:hover { border-color: ${C.green}; background: rgba(61,220,103,0.04); color: #6effa0; }
    .maze-btn:active { background: rgba(61,220,103,0.08); }
    .small-btn {
      background: transparent; border: 1px solid ${C.border};
      color: ${C.muted}; font-family: 'IBM Plex Mono', monospace;
      font-size: 0.6rem; letter-spacing: 0.1em; padding: 0.3rem 0.6rem;
      cursor: pointer; margin-right: 0.4rem; margin-bottom: 0.4rem;
      transition: color 0.15s, border-color 0.15s;
    }
    .small-btn:hover { color: ${C.text}; border-color: ${C.muted}; }
    .name-input {
      background: transparent; border: none; border-bottom: 1px solid ${C.green};
      color: ${C.text}; font-family: 'IBM Plex Mono', monospace;
      font-size: 1rem; padding: 0.4rem 0; width: 100%; outline: none;
      letter-spacing: 0.1em;
    }
    .load-input {
      background: transparent; border: 1px solid ${C.border};
      color: ${C.muted}; font-family: 'IBM Plex Mono', monospace;
      font-size: 0.65rem; padding: 0.4rem 0.6rem; width: 100%; outline: none;
      letter-spacing: 0.05em; margin-bottom: 0.5rem;
    }
    .load-input:focus { border-color: ${C.dim}; color: ${C.text}; }
    .choice-area { animation: fadeIn 0.4s ease both; }
    .save-code {
      background: #0d0d0d; color: ${C.green}; font-family: monospace;
      font-size: 0.62rem; padding: 0.6rem; word-break: break-all;
      border: 1px solid ${C.border}; margin-top: 0.4rem; user-select: all;
    }
    .path-crumb { font-size: 0.58rem; color: #282820; letter-spacing: 0.08em; }
  `;

  const root = {
    background: C.bg,
    minHeight: "100vh",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "flex-start",
    fontFamily: "'IBM Plex Mono', 'Courier New', monospace",
    color: C.text,
    padding: "3rem 1rem 4rem",
    position: "relative",
    overflow: "hidden",
  };

  const wrap = { maxWidth: "620px", width: "100%", position: "relative", zIndex: 1 };

  // ─── INTRO SCREEN ─────────────────────────────────────────────────────────
  if (phase === "intro") {
    return (
      <div style={root}>
        <style>{css}</style>
        <div className="scanlines" />
        <div className="scan-beam" />
        <div style={wrap}>
          <div style={{ textAlign: "center", marginBottom: "3.5rem" }}>
            <div style={{ fontSize: "0.6rem", color: C.dim, letterSpacing: "0.4em", marginBottom: "0.5rem" }}>
              DEADLIGHT_OS v2.1.4 — 2003
            </div>
            <div style={{ fontSize: "1.8rem", color: C.text, letterSpacing: "0.25em", fontWeight: 600 }}>
              THE LABYRINTH
            </div>
            <div style={{ fontSize: "0.65rem", color: C.muted, letterSpacing: "0.2em", marginTop: "0.5rem" }}>
              CHAPTER I — THE LINK
            </div>
          </div>

          <div style={{ fontSize: "0.78rem", lineHeight: "2", color: "#666", marginBottom: "3rem", whiteSpace: "pre-line" }}>
{`A shifting maze of a story.
It customizes itself to you.
You will not find the same path twice.

The maze remembers.
So does it.`}
          </div>

          <button className="maze-btn" onClick={() => setPhase("name")}>
            [ ENTER THE MAZE ]
          </button>

          <div style={{ marginTop: "2.5rem", borderTop: `1px solid ${C.border}`, paddingTop: "1.5rem" }}>
            <div style={{ fontSize: "0.6rem", color: C.muted, marginBottom: "0.6rem", letterSpacing: "0.15em" }}>
              RESUME A SAVED SESSION:
            </div>
            <input
              className="load-input"
              placeholder="paste save code here..."
              value={loadInput}
              onChange={(e) => setLoadInput(e.target.value)}
            />
            {loadInput.trim() && (
              <button className="small-btn" onClick={handleLoad}>[ LOAD ]</button>
            )}
          </div>
        </div>
      </div>
    );
  }

  // ─── NAME ENTRY ───────────────────────────────────────────────────────────
  if (phase === "name") {
    return (
      <div style={root}>
        <style>{css}</style>
        <div className="scanlines" />
        <div className="scan-beam" />
        <div style={wrap}>
          <div style={{ fontSize: "0.65rem", color: C.green, letterSpacing: "0.3em", marginBottom: "2rem" }}>
            // USER_AUTH
          </div>
          <div style={{ fontSize: "0.82rem", lineHeight: "2.1", whiteSpace: "pre-wrap", color: "#aaa", marginBottom: "2.5rem" }}>
{`DEADLIGHT_OS v2.1.4
USER AUTHENTICATION REQUIRED

USERNAME: [`}<span style={{ color: C.green }}>{nameInput}</span><span style={{ display: "inline-block", width: "0.5em", height: "1em", background: C.green, marginLeft: "2px", verticalAlign: "text-bottom", animation: "blink 1s step-end infinite" }} />{`]`}
          </div>

          <input
            className="name-input"
            autoFocus
            placeholder="your name (or leave blank)"
            value={nameInput}
            onChange={(e) => setNameInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                setPlayerName(nameInput.trim());
                setPhase("playing");
              }
            }}
          />
          <div style={{ fontSize: "0.6rem", color: C.muted, marginTop: "0.4rem", letterSpacing: "0.1em" }}>
            press ENTER or click below
          </div>
          <button
            className="maze-btn"
            style={{ marginTop: "1.5rem" }}
            onClick={() => { setPlayerName(nameInput.trim()); setPhase("playing"); }}
          >
            [ AUTHENTICATE ]
          </button>
        </div>
      </div>
    );
  }

  // ─── PLAYING ──────────────────────────────────────────────────────────────
  const isPlaying = phase === "playing" || phase === "end";
  const isEnd = phase === "end";
  const sceneToShow = isEnd ? SCENES.end : scene;
  const bodyToShow = isEnd ? SCENES.end.body(playerName) : sceneBody;

  return (
    <div style={{ ...root, opacity: transitioning ? 0.3 : 1, transition: "opacity 0.3s" }}>
      <style>{css}</style>
      <div className="scanlines" />
      <div className="scan-beam" />
      <div style={wrap}>
        {/* Header */}
        <div style={{ marginBottom: "2.5rem" }}>
          <div style={{ fontSize: "0.58rem", color: C.dim, letterSpacing: "0.35em" }}>
            DEADLIGHT 2003 — CHAPTER I
          </div>
          {playerName && (
            <div style={{ fontSize: "0.55rem", color: "#2a2a24", letterSpacing: "0.2em", marginTop: "0.2rem" }}>
              SESSION: {playerName.toUpperCase()}
            </div>
          )}
        </div>

        {/* Scene title */}
        <div style={{ fontSize: "0.7rem", color: C.green, letterSpacing: "0.3em", marginBottom: "2rem" }}>
          <GlitchText text={sceneToShow.title} active={glitching} />
        </div>

        {/* Body text */}
        <div style={{ fontSize: "0.85rem", lineHeight: "1.95", whiteSpace: "pre-wrap", minHeight: "14rem", marginBottom: "2.5rem" }}>
          {isEnd
            ? <GlitchText text={bodyToShow} active={false} />
            : <>
                {displayed}
                {!done && <span style={{ display: "inline-block", width: "0.5em", height: "0.9em", background: C.text, marginLeft: "2px", verticalAlign: "text-bottom", animation: "blink 0.8s step-end infinite" }} />}
              </>
          }
        </div>

        {/* Choices */}
        {(done || isEnd) && sceneToShow.choices.length > 0 && (
          <div className="choice-area">
            {sceneToShow.choices.map((c) => (
              <button key={c.next} className="maze-btn" onClick={() => goToScene(c.next)}>
                {c.label}
              </button>
            ))}
          </div>
        )}

        {/* Divider */}
        <div style={{ borderTop: `1px solid ${C.border}`, margin: "2rem 0 1rem" }} />

        {/* Path breadcrumb */}
        <div className="path-crumb">
          {history.length > 0
            ? `PATH: ${history.map((id) => CRUMBS[id] || id).join(" → ")}`
            : "PATH: [ beginning ]"}
        </div>

        {/* Save / restart controls */}
        <div style={{ marginTop: "1rem" }}>
          <button className="small-btn" onClick={handleSave}>[ SAVE ]</button>
          <button className="small-btn" onClick={restart}>[ RESTART ]</button>
        </div>

        {showSave && (
          <div style={{ marginTop: "0.75rem", padding: "0.75rem", border: `1px solid ${C.border}` }}>
            <div style={{ fontSize: "0.6rem", color: C.muted, letterSpacing: "0.1em" }}>
              SAVE CODE — copy to resume later:
            </div>
            <div className="save-code">{saveCode}</div>
            <button className="small-btn" style={{ marginTop: "0.5rem" }} onClick={handleCopy}>
              {copied ? "[ COPIED ]" : "[ COPY TO CLIPBOARD ]"}
            </button>
          </div>
        )}

        {/* Load panel (always accessible) */}
        <div style={{ marginTop: "1.5rem", borderTop: `1px solid ${C.border}`, paddingTop: "1rem" }}>
          <div style={{ fontSize: "0.58rem", color: "#282820", marginBottom: "0.4rem", letterSpacing: "0.1em" }}>
            LOAD DIFFERENT SESSION:
          </div>
          <input
            className="load-input"
            placeholder="paste save code..."
            value={loadInput}
            onChange={(e) => setLoadInput(e.target.value)}
          />
          {loadInput.trim() && (
            <button className="small-btn" onClick={handleLoad}>[ LOAD ]</button>
          )}
        </div>
      </div>
    </div>
  );
}
