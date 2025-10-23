from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import requests
import streamlit as st

API_BASE = os.getenv('MAZE_API_BASE', 'http://127.0.0.1:8000')


def api_post(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
  response = requests.post(f'{API_BASE}{path}', json=payload, timeout=30)
  response.raise_for_status()
  return response.json()


def ensure_session(profile_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
  payload = st.session_state.get('maze_session')
  if not payload:
    try:
      payload = api_post('/api/session', {'profile_name': profile_name})
    except requests.RequestException as exc:  # pragma: no cover - UI safeguard
      st.error(f'Failed to start session: {exc}')
      return None
    st.session_state.maze_session = payload
  return payload


def refresh_session(session_id: Optional[str]) -> Optional[Dict[str, Any]]:
  if not session_id:
    st.error('No active session to refresh.')
    return None
  try:
    response = requests.get(f'{API_BASE}/api/session/{session_id}', timeout=30)
    response.raise_for_status()
  except requests.RequestException as exc:  # pragma: no cover - UI safeguard
    st.error(f'Failed to refresh session: {exc}')
    return None
  st.session_state.maze_session = response.json()
  return st.session_state.maze_session


def advance_session() -> Optional[Dict[str, Any]]:
  payload = st.session_state.get('maze_session')
  if not payload:
    st.error('No active session. Start a session first.')
    return None
  try:
    data = api_post(
      '/api/progress',
      {
        'session_id': payload['session_id'],
        'event': 'advance',
      },
    )
  except requests.RequestException as exc:  # pragma: no cover - UI safeguard
    st.error(f'Failed to advance the maze: {exc}')
    return None
  payload.update(data)
  st.session_state.maze_session = payload
  return payload


def decide(direction: str) -> Optional[Dict[str, Any]]:
  payload = st.session_state.get('maze_session')
  if not payload:
    st.error('No active session. Start a session first.')
    return None
  try:
    data = api_post(
      '/api/progress',
      {
        'session_id': payload['session_id'],
        'event': 'decision',
        'direction': direction,
        'via': 'streamlit',
      },
    )
  except requests.RequestException as exc:  # pragma: no cover - UI safeguard
    st.error(f'Failed to resolve decision: {exc}')
    return None
  payload.update(data)
  st.session_state.maze_session = payload
  return payload


def render_paragraphs(paragraphs: Optional[List[Dict[str, Any]]]) -> None:
  if not paragraphs:
    st.markdown('_The maze is quiet for now._')
    return
  for idx, paragraph in enumerate(paragraphs, start=1):
    st.markdown(f"**P{idx:02d}** — {paragraph.get('text', '')}")


def render_branch(branch: Dict[str, Any]) -> None:
  options = branch.get('options') or []
  if not options:
    st.warning('Branch data missing options.')
    return
  st.subheader('Choose a path')
  cols = st.columns(len(options))
  for col, option in zip(cols, options):
    if col.button(option['label'], use_container_width=True):
      decide(option['direction'])


def render_hud(payload: Optional[Dict[str, Any]]) -> None:
  if not payload:
    st.sidebar.warning('Session unavailable. Start a session to explore the maze.')
    return
  st.sidebar.markdown('### Maze Diagnostics')
  st.sidebar.write(f"Session: `{payload['session_id']}`")
  st.sidebar.write(f"Scene: `{payload.get('scene_id', 'unknown')}`")
  st.sidebar.write(f"Emotion track: `{payload.get('emotional_track', 'n/a')}`")
  st.sidebar.write(f"Theme: {payload.get('theme') or '—'}")
  st.sidebar.write(f"Pending decision: {payload.get('pending_decision')}" )
  st.sidebar.write(f"Registration unlocked: {payload.get('allow_registration')}")
  if payload.get('hud_message'):
    st.sidebar.info(payload['hud_message'])

  if payload.get('allow_registration'):
    with st.sidebar.expander('Register for Chapter Two'):
      name = st.text_input('Name', key='register_name')
      email = st.text_input('Email', key='register_email')
      if st.button('Submit Registration', type='primary'):
        api_post(
          '/api/register',
          {
            'name': name,
            'email': email,
            'session_id': payload['session_id'],
          },
        )
        st.success('The maze will reach out when the corridor stabilises.')


def main() -> None:
  st.set_page_config(page_title='Deadlight 2003 — Prototype', layout='wide')
  st.title('Deadlight 2003 — AI Labyrinth Prototype')
  st.caption('2003 terminal vibes, LangChain-driven narrative maze.')

  with st.sidebar.expander('Session Controls', expanded=True):
    profile_name = st.text_input('Protagonist name override', key='profile_name')
    if st.button('Start New Session', type='primary'):
      st.session_state.pop('maze_session', None)
      ensure_session(profile_name or None)
    if st.session_state.get('maze_session'):
      if st.button('Advance', key='advance_btn'):
        advance_session()
      if st.button('Reload Session Payload', key='reload_btn'):
        refresh_session(st.session_state['maze_session']['session_id'])

  payload = ensure_session(st.session_state.get('profile_name') or None)
  if not payload:
    st.stop()
  render_hud(payload)

  st.divider()
  render_paragraphs(payload.get('paragraphs', []))

  if payload.get('branch'):
    render_branch(payload['branch'])
  else:
    if st.button('Continue the corridor', disabled=payload.get('pending_decision')):
      updated = advance_session()
      if updated:
        payload = updated

  if payload.get('prompt_scroll_back'):
    st.toast('Scroll back—the maze may have changed what it just told you.', icon='🔁')

  if payload.get('story_complete'):
    st.success('Chapter one endpoint reached. Register to continue or restart for another path.')


if __name__ == '__main__':
  main()
