from __future__ import annotations

import importlib
from types import SimpleNamespace

import pytest
import requests


def _fake_streamlit():
  class FakeSessionState(dict):
    def __getattr__(self, item):
      try:
        return self[item]
      except KeyError as exc:  # pragma: no cover - attribute missing
        raise AttributeError(item) from exc

    def __setattr__(self, key, value):
      self[key] = value

  return SimpleNamespace(
    session_state=FakeSessionState(),
    error=lambda *args, **kwargs: None,
  )


@pytest.fixture
def streamlit_app(monkeypatch):
  module = importlib.import_module("streamlit_app_v2")
  fake_st = _fake_streamlit()
  monkeypatch.setattr(module, "st", fake_st)
  return module, fake_st


def test_init_session_creates_session(monkeypatch, streamlit_app):
  module, fake_st = streamlit_app
  payload_data = {
    "session_id": "new",
    "scene": {"id": "boot_sequence", "title": "Boot"},
    "pending_branch": False,
  }
  monkeypatch.setattr(module, "api_post", lambda path, payload: payload_data)

  payload = module.init_session()

  assert payload == payload_data
  assert fake_st.session_state["maze_session"] == payload_data


def test_init_session_reuses_existing(monkeypatch, streamlit_app):
  module, fake_st = streamlit_app
  fake_st.session_state.maze_session = {"session_id": "existing"}

  def fail_api(*_args, **_kwargs):  # pragma: no cover - should not run
    raise AssertionError("api_post should not be called for existing session")

  monkeypatch.setattr(module, "api_post", fail_api)

  payload = module.init_session()

  assert payload["session_id"] == "existing"


def test_init_session_handles_api_failure(monkeypatch, streamlit_app):
  module, fake_st = streamlit_app
  captured_errors = []
  fake_st.error = lambda message: captured_errors.append(message)

  def failing_api(*_args, **_kwargs):
    raise requests.RequestException("boom")

  monkeypatch.setattr(module, "api_post", failing_api)

  payload = module.init_session()

  assert payload is None
  assert not fake_st.session_state
  assert captured_errors  # An error was reported to the UI


def test_send_progress_updates_session(monkeypatch, streamlit_app):
  module, fake_st = streamlit_app
  fake_st.session_state.maze_session = {"session_id": "abc", "scene": {"id": "boot_sequence"}}
  progress_payload = {"session_id": "abc", "scene": {"id": "login_prompt"}}

  def fake_post(path, payload):
    assert payload["event"] == "advance"
    return progress_payload

  monkeypatch.setattr(module, "api_post", fake_post)

  updated = module.send_progress("advance")

  assert updated == progress_payload
  assert fake_st.session_state.maze_session["scene"]["id"] == "login_prompt"


def test_register_reader_updates_session(monkeypatch, streamlit_app):
  module, fake_st = streamlit_app
  fake_st.session_state.maze_session = {
    "session_id": "abc",
    "scene": {"id": "black_terminal"},
    "allow_registration": True,
    "registered": False,
  }

  monkeypatch.setattr(
    module,
    "api_post",
    lambda path, payload: {"status": "registered", "session": {"session_id": "abc", "registered": True}},
  )

  success = module.register_reader("Test", "test@example.com")

  assert success is True
  assert fake_st.session_state.maze_session["registered"] is True
