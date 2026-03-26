from __future__ import annotations

import os
from typing import Any, Dict, Optional

import requests
import streamlit as st

API_BASE = os.getenv("MAZE_API_BASE", "http://127.0.0.1:8000")
SESSION_KEY = "maze_session"


def api_get(path: str) -> Dict[str, Any]:
  response = requests.get(f"{API_BASE}{path}", timeout=15)
  response.raise_for_status()
  return response.json()


def api_post(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
  response = requests.post(f"{API_BASE}{path}", json=payload, timeout=15)
  response.raise_for_status()
  return response.json()


def init_session(profile_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
  if SESSION_KEY in st.session_state:
    return st.session_state[SESSION_KEY]

  payload = {"profile_name": profile_name} if profile_name else {}
  try:
    session = api_post("/api/session", payload)
  except requests.RequestException as err:
    st.error(f"Failed to start maze session: {err}")
    return None

  st.session_state[SESSION_KEY] = session
  return session


def update_session(data: Dict[str, Any]) -> None:
  st.session_state[SESSION_KEY] = data


def get_session() -> Optional[Dict[str, Any]]:
  return st.session_state.get(SESSION_KEY)


def send_progress(event: str, direction: Optional[str] = None) -> Optional[Dict[str, Any]]:
  session = get_session()
  if not session:
    st.error("No active session. Start the maze first.")
    return None

  payload: Dict[str, Any] = {"session_id": session["session_id"], "event": event}
  if direction:
    payload["direction"] = direction

  try:
    updated = api_post("/api/progress", payload)
  except requests.RequestException as err:
    st.error(f"Progress failed: {err}")
    return None

  update_session(updated)
  return updated


def register_reader(name: str, email: str) -> bool:
  if not name or not email:
    st.error("Name and email are required.")
    return False

  session = get_session()
  payload: Dict[str, Any] = {"name": name, "email": email}
  if session:
    payload["session_id"] = session["session_id"]

  try:
    response = api_post("/api/register", payload)
  except requests.RequestException as err:
    st.error(f"Registration failed: {err}")
    return False

  if session and response.get("session"):
    update_session(response["session"])
  return True


def render_story() -> None:
  st.set_page_config(page_title="Deadlight Maze", layout="centered")
  st.title("Deadlight 2003: Chapter One")

  session = get_session() or init_session()
  if not session:
    return

  scene = session["scene"]
  st.subheader(scene["title"])
  st.caption(scene["goal"])

  for block in scene["body"].split("\n\n"):
    if not block.strip():
      continue
    st.markdown(f"> {block.strip()}")

  if session["pending_branch"]:
    st.markdown("### Choose the corridor")
    for option in session["branching_paths"]:
      label = f"{option['label']} → {option['target_scene_title']}"
      if st.button(label, key=option["direction"]):
        send_progress("decision", direction=option["direction"])
        st.experimental_rerun()
        return
  elif not session["story_complete"]:
    if st.button("Continue deeper"):
      send_progress("advance")
      st.experimental_rerun()
      return
  else:
    st.success("Maze stabilised. Await further instructions.")

  if session["allow_registration"] and not session["registered"]:
    with st.form("registration"):
      name = st.text_input("Name")
      email = st.text_input("Email")
      submitted = st.form_submit_button("Register")
      if submitted:
        if register_reader(name, email):
          st.success("Registration saved.")
          st.experimental_rerun()
