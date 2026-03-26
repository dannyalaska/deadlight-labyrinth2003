"use client";

import type { FormEvent, JSX } from "react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

const STORAGE_KEY = "deadlightProfile";
const API_BASE = process.env.NEXT_PUBLIC_MAZE_API_BASE ?? "";

type BranchOption = {
  direction: string;
  target_scene_id: string;
  target_scene_title: string;
  label: string;
};

type ScenePayload = {
  id: string;
  title: string;
  goal: string;
  body: string;
  style?: string | null;
  length?: string | null;
  theme?: string | null;
  requires_device_orientation: boolean;
};

type SessionSnapshot = {
  chapter_id: string;
  chapter_title: string;
  session_id: string;
  profile_name?: string | null;
  scene: ScenePayload;
  pending_branch: boolean;
  branching_paths: BranchOption[];
  story_complete: boolean;
  allow_registration: boolean;
  registered: boolean;
  history: Array<Record<string, unknown>>;
};

type ChapterMetadata = {
  chapter_id: string;
  title: string;
  theme?: string | null;
  global_mood?: string | null;
  entrypoint: string;
  scenes: Array<{
    id: string;
    title: string;
    has_branching: boolean;
    requires_device_orientation: boolean;
  }>;
};

type RegisterResponse = {
  status: string;
  session?: SessionSnapshot;
};

type StoredProfile = {
  name: string;
  email: string;
};

async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "GET",
    headers: {
      Accept: "application/json",
    },
  });
  if (!response.ok) {
    let detail: string | undefined;
    try {
      const body = (await response.json()) as { detail?: string; message?: string };
      detail = body?.detail ?? body?.message;
    } catch {
      detail = undefined;
    }
    throw new Error(detail ?? `Request failed with status ${response.status}`);
  }
  return (await response.json()) as T;
}

async function apiPost<T>(path: string, payload: unknown): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    let detail: string | undefined;
    try {
      const body = (await response.json()) as { detail?: string; message?: string };
      detail = body?.detail ?? body?.message;
    } catch {
      detail = undefined;
    }
    throw new Error(detail ?? `Request failed with status ${response.status}`);
  }
  return (await response.json()) as T;
}

function normaliseParagraphs(body?: string): string[] {
  if (!body) {
    return [];
  }
  const chunks = body.split(/\n{2,}/).map((chunk) => chunk.trim()).filter(Boolean);
  return chunks.length > 0 ? chunks : [body];
}

function combineMood(meta: ChapterMetadata | null): string {
  if (!meta) return "Synchronising memory...";
  const parts = [meta.theme, meta.global_mood].filter((part): part is string => Boolean(part));
  if (parts.length === 0) return "Synchronising memory...";
  return parts.join(" • ");
}

function resolveOrientationSupport(): {
  supported: boolean;
  requiresPermission: boolean;
} {
  if (typeof window === "undefined") {
    return { supported: false, requiresPermission: false };
  }

  const supported = "DeviceOrientationEvent" in window;
  const requiresPermission =
    supported &&
    typeof (window.DeviceOrientationEvent as typeof window.DeviceOrientationEvent & {
      requestPermission?: () => Promise<"granted" | "denied">;
    })?.requestPermission === "function";

  return { supported, requiresPermission };
}

function readStoredProfile(): StoredProfile {
  if (typeof window === "undefined") {
    return { name: "", email: "" };
  }
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return { name: "", email: "" };
    const parsed = JSON.parse(raw) as Partial<StoredProfile>;
    return {
      name: typeof parsed.name === "string" ? parsed.name : "",
      email: typeof parsed.email === "string" ? parsed.email : "",
    };
  } catch {
    window.localStorage.removeItem(STORAGE_KEY);
    return { name: "", email: "" };
  }
}

function storeProfile(profile: StoredProfile): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(profile));
}

export default function MazeConsole(): JSX.Element {
  const [status, setStatus] = useState("BOOTING");
  const [chapterMeta, setChapterMeta] = useState<ChapterMetadata | null>(null);
  const [session, setSession] = useState<SessionSnapshot | null>(null);
  const [profileDraft, setProfileDraft] = useState<StoredProfile>({ name: "", email: "" });
  const [snackbar, setSnackbar] = useState<string | null>(null);
  const [isOverlayOpen, setOverlayOpen] = useState(false);
  const [orientationInfo] = useState(() => resolveOrientationSupport());
  const orientationSupported = orientationInfo.supported;
  const tiltRequiresPermission = orientationInfo.requiresPermission;
  const [tiltPermissionGranted, setTiltPermissionGranted] = useState(
    () => !orientationInfo.requiresPermission,
  );
  const [tiltHeights, setTiltHeights] = useState({ left: 0, right: 0 });

  const initRef = useRef(false);
  const snackbarTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pendingRequestRef = useRef<Promise<SessionSnapshot> | null>(null);
  const branchOptionsRef = useRef<BranchOption[]>([]);
  const tiltActiveRef = useRef(false);

  const branchOptions = useMemo(
    () => (session?.pending_branch ? session.branching_paths : []),
    [session],
  );
  const showBranching = Boolean(session?.pending_branch);
  const showTiltWidget =
    showBranching && session?.scene.requires_device_orientation && orientationSupported;
  const showTiltPermissionButton = showTiltWidget && tiltRequiresPermission && !tiltPermissionGranted;
  const showAdvanceButton = !showBranching || Boolean(session?.story_complete);
  const showRegisterButton =
    Boolean(session?.allow_registration) && !session?.registered && Boolean(session);

  const moodText = useMemo(() => combineMood(chapterMeta), [chapterMeta]);
  const sceneParagraphs = useMemo(() => normaliseParagraphs(session?.scene.body), [session?.scene.body]);

  const showSnackbar = useCallback((message: string) => {
    setSnackbar(message);
  }, []);

  const applySession = useCallback((snapshot: SessionSnapshot) => {
    setSession(snapshot);
    branchOptionsRef.current = snapshot.pending_branch ? snapshot.branching_paths : [];
    setStatus("CONNECTED");
  }, []);

  const bootstrap = useCallback(async () => {
    setStatus("SYNCHRONISING");
    try {
      const meta = await apiGet<ChapterMetadata>("/api/chapter");
      setChapterMeta(meta);
      const stored = readStoredProfile();
      setProfileDraft(stored);
      const snapshot = await apiPost<SessionSnapshot>("/api/session", stored.name ? { profile_name: stored.name } : {});
      applySession(snapshot);
    } catch (error) {
      console.error("Failed to bootstrap app", error);
      setStatus("OFFLINE");
      showSnackbar("Failed to connect to the maze. Retry later.");
    }
  }, [applySession, showSnackbar]);

  const progressSession = useCallback(
    async (event: "advance" | "decision" | "cta", direction?: string) => {
      if (!session) {
        throw new Error("No active session. Start the maze first.");
      }
      if (pendingRequestRef.current) {
        return pendingRequestRef.current;
      }
      const payload: Record<string, unknown> = {
        session_id: session.session_id,
        event,
      };
      if (direction) {
        payload.direction = direction;
      }
      const request = apiPost<SessionSnapshot>("/api/progress", payload)
        .then((snapshot) => {
          applySession(snapshot);
          return snapshot;
        })
        .catch((error) => {
          throw error;
        })
        .finally(() => {
          pendingRequestRef.current = null;
        });
      pendingRequestRef.current = request;
      return request;
    },
    [applySession, session],
  );

  const restartSession = useCallback(async () => {
    const profileName = session?.profile_name ?? undefined;
    setStatus("SYNCHRONISING");
    try {
      const snapshot = await apiPost<SessionSnapshot>(
        "/api/session",
        profileName ? { profile_name: profileName } : {},
      );
      applySession(snapshot);
    } catch (error) {
      console.error("Failed to restart session", error);
      setStatus("OFFLINE");
      showSnackbar((error as Error).message ?? "Restart failed. Try again.");
    }
  }, [applySession, session, showSnackbar]);

  const handleAdvance = useCallback(async () => {
    if (!session) return;
    if (session.story_complete) {
      await restartSession();
      return;
    }
    try {
      await progressSession("advance");
    } catch (error) {
      console.error("Advance failed", error);
      showSnackbar((error as Error).message || "The maze stalls. Try again.");
    }
  }, [progressSession, restartSession, session, showSnackbar]);

  const handleBranchDecision = useCallback(
    async (direction: string) => {
      try {
        await progressSession("decision", direction);
      } catch (error) {
        console.error("Decision failed", error);
        showSnackbar((error as Error).message || "The corridor glitches. Try again.");
      }
    },
    [progressSession, showSnackbar],
  );

  const handleTiltPermission = useCallback(async () => {
    if (!orientationSupported) {
      return;
    }
    if (!tiltRequiresPermission) {
      setTiltPermissionGranted(true);
      return;
    }
    const deviceOrientation = window.DeviceOrientationEvent as typeof window.DeviceOrientationEvent & {
      requestPermission?: () => Promise<"granted" | "denied">;
    };
    if (typeof deviceOrientation?.requestPermission !== "function") {
      showSnackbar("Tilt unavailable on this device.");
      setTiltPermissionGranted(false);
      return;
    }
    try {
      const result = await deviceOrientation.requestPermission();
      const granted = result === "granted";
      setTiltPermissionGranted(granted);
      if (!granted) {
        showSnackbar("Tilt denied. Use onscreen choices.");
      }
    } catch (error) {
      console.error("Tilt permission failed", error);
      showSnackbar("Tilt unavailable on this device.");
      setTiltPermissionGranted(false);
    }
  }, [orientationSupported, showSnackbar, tiltRequiresPermission]);

  const handleRegistrationSubmit = useCallback(
    async (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      if (!profileDraft.name || !profileDraft.email) {
        showSnackbar("Name and email required.");
        return;
      }
      try {
        const payload = {
          name: profileDraft.name,
          email: profileDraft.email,
          session_id: session?.session_id,
        };
        const response = await apiPost<RegisterResponse>("/api/register", payload);
        storeProfile(profileDraft);
        setOverlayOpen(false);
        showSnackbar("We will wake you when the next chapter stabilises.");
        if (response.session) {
          applySession(response.session);
        }
      } catch (error) {
        console.error("Registration failed", error);
        showSnackbar("Registration failed. Try again soon.");
      }
    },
    [applySession, profileDraft, session, showSnackbar],
  );

  useEffect(() => {
    if (initRef.current) return;
    initRef.current = true;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- bootstrap seeds client state on first mount.
    void bootstrap();
  }, [bootstrap]);

  useEffect(() => {
    if (!snackbar) return;
    if (snackbarTimeout.current) {
      clearTimeout(snackbarTimeout.current);
    }
    snackbarTimeout.current = setTimeout(() => {
      setSnackbar(null);
    }, 3200);
    return () => {
      if (snackbarTimeout.current) {
        clearTimeout(snackbarTimeout.current);
        snackbarTimeout.current = null;
      }
    };
  }, [snackbar]);

  useEffect(() => {
    branchOptionsRef.current = branchOptions;
  }, [branchOptions]);

  useEffect(() => {
    if (!orientationSupported) {
      return;
    }
    const shouldArmTilt =
      showTiltWidget && (!tiltRequiresPermission || (tiltRequiresPermission && tiltPermissionGranted));
    if (!shouldArmTilt) {
      tiltActiveRef.current = false;
      return;
    }
    tiltActiveRef.current = true;

    const handler = (event: DeviceOrientationEvent) => {
      if (!tiltActiveRef.current || !branchOptionsRef.current.length) {
        return;
      }
      const gamma = event.gamma ?? 0;
      const maxTilt = 30;
      const clamped = Math.max(-maxTilt, Math.min(maxTilt, gamma));
      const leftPercent = ((-clamped + maxTilt) / (maxTilt * 2)) * 100;
      const rightPercent = ((clamped + maxTilt) / (maxTilt * 2)) * 100;
      setTiltHeights({
        left: Number(leftPercent.toFixed(1)),
        right: Number(rightPercent.toFixed(1)),
      });

      const threshold = 18;
      if (Math.abs(clamped) < threshold || pendingRequestRef.current) {
        return;
      }

      const hint = clamped < 0 ? "left" : "right";
      const option = branchOptionsRef.current.find((candidate) =>
        candidate.direction.toLowerCase().includes(hint),
      );
      if (!option) {
        return;
      }

      tiltActiveRef.current = false;
      void handleBranchDecision(option.direction);
    };

    window.addEventListener("deviceorientation", handler);
    return () => {
      window.removeEventListener("deviceorientation", handler);
      tiltActiveRef.current = false;
    };
  }, [
    handleBranchDecision,
    orientationSupported,
    showTiltWidget,
    tiltPermissionGranted,
    tiltRequiresPermission,
  ]);

  return (
    <>
      <div className="scanlines" aria-hidden="true" />
      <div className="app-shell">
        <header className="app-header">
          <div className="brand">
            <span className="cursor">%</span>
            <span className="label">DEADLIGHT_2003</span>
            <span className="divider">{"//"}</span>
            <span id="statusIndicator" className="status">
              {status}
            </span>
          </div>
          <div className="chapter-meta">
            <h1 id="chapterTitle">{chapterMeta?.title ?? "Deadlight 2003"}</h1>
            <p id="chapterMood" className="chapter-mood">
              {moodText}
            </p>
          </div>
        </header>

        <main className="layout">
          <section className="story-pane" aria-live="polite">
            <h2 id="sceneTitle" className="scene-title">
              {session?.scene.title ?? "..."}
            </h2>
            <p id="sceneGoal" className="scene-goal">
              {session?.scene.goal ?? ""}
            </p>
            <div id="sceneBody" className="scene-body">
              {sceneParagraphs.map((paragraph, index) => (
                <p key={`${session?.scene.id ?? "scene"}-${index}`}>{paragraph}</p>
              ))}
            </div>
          </section>

          <aside className="control-pane">
            <div
              id="branchContainer"
              className={`branch-container${showBranching ? "" : " hidden"}`}
              aria-live="polite"
            >
              <p className="branch-instruction">Tilt or select a path:</p>
              <div id="branchOptions" className="branch-options">
                {branchOptions.map((option) => (
                  <button
                    type="button"
                    className="btn-branch"
                    key={option.direction}
                    data-direction={option.direction}
                    onClick={() => handleBranchDecision(option.direction)}
                  >
                    <span className="branch-label">{option.label}</span>
                    <span className="branch-target">{option.target_scene_title}</span>
                  </button>
                ))}
              </div>
              <div
                id="tiltWidget"
                className={`tilt-widget${showTiltWidget ? "" : " hidden"}`}
                data-needs-permission={showTiltPermissionButton ? "1" : ""}
              >
                <div className="tilt-bars">
                  <div
                    className="tilt-bar left"
                    id="tiltLeft"
                    style={{ height: `${showTiltWidget ? tiltHeights.left : 0}%` }}
                  />
                  <div
                    className="tilt-bar right"
                    id="tiltRight"
                    style={{ height: `${showTiltWidget ? tiltHeights.right : 0}%` }}
                  />
                </div>
                {showTiltPermissionButton ? (
                  <button type="button" className="btn-ghost request-tilt" onClick={handleTiltPermission}>
                    Enable Tilt Controls
                  </button>
                ) : (
                  <p className="tilt-hint">Lean your device to decide.</p>
                )}
              </div>
            </div>

            <button
              id="advanceBtn"
              type="button"
              className={`btn-primary${showAdvanceButton ? "" : " hidden"}`}
              onClick={handleAdvance}
            >
              {session?.story_complete ? "Restart Chapter" : "Continue"}
            </button>

            <button
              id="registerBtn"
              type="button"
              className={`btn-secondary${showRegisterButton ? "" : " hidden"}`}
              onClick={() => setOverlayOpen(true)}
            >
              Register
            </button>
          </aside>
        </main>
      </div>

      <section
        id="registerOverlay"
        className={`overlay${isOverlayOpen ? "" : " hidden"}`}
        role="dialog"
        aria-modal="true"
      >
        <div className="overlay-content">
          <header className="overlay-header">
            <h3>Wake The Next Chapter</h3>
            <button type="button" className="btn-ghost" id="registerCloseBtn" onClick={() => setOverlayOpen(false)}>
              Not Yet
            </button>
          </header>
          <form id="registerForm" className="overlay-body" onSubmit={handleRegistrationSubmit}>
            <label htmlFor="registerName">
              Name
              <input
                type="text"
                id="registerName"
                name="name"
                required
                autoComplete="name"
                value={profileDraft.name}
                onChange={(event) =>
                  setProfileDraft((prev) => ({
                    ...prev,
                    name: event.target.value,
                  }))
                }
              />
            </label>
            <label htmlFor="registerEmail">
              Email
              <input
                type="email"
                id="registerEmail"
                name="email"
                required
                autoComplete="email"
                value={profileDraft.email}
                onChange={(event) =>
                  setProfileDraft((prev) => ({
                    ...prev,
                    email: event.target.value,
                  }))
                }
              />
            </label>
            <button type="submit" className="btn-primary">
              Save &amp; Wake Me
            </button>
            <p className="register-note">Stored locally. We&apos;ll contact you when the maze shifts.</p>
          </form>
        </div>
      </section>

      <div
        id="snackbar"
        className={`snackbar${snackbar ? " visible" : ""}`}
        role="status"
        aria-live="polite"
      >
        {snackbar}
      </div>
    </>
  );
}
