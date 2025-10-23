from __future__ import annotations

import importlib
from contextlib import nullcontext
from types import SimpleNamespace

import pytest
import requests


def _fake_streamlit_state():
  class FakeSessionState(dict):
    def __getattr__(self, item):
      try:
        return self[item]
      except KeyError as exc:  # pragma: no cover - attribute missing
        raise AttributeError(item) from exc

    def __setattr__(self, key, value):
      self[key] = value

  sidebar = SimpleNamespace(
    warning=lambda *args, **kwargs: None,
    markdown=lambda *args, **kwargs: None,
    write=lambda *args, **kwargs: None,
    info=lambda *args, **kwargs: None,
    expander=lambda *args, **kwargs: nullcontext(),
  )

  return SimpleNamespace(
    session_state=FakeSessionState(),
    sidebar=sidebar,
    error=lambda *args, **kwargs: None,
    toast=lambda *args, **kwargs: None,
    set_page_config=lambda *args, **kwargs: None,
    title=lambda *args, **kwargs: None,
    caption=lambda *args, **kwargs: None,
    markdown=lambda *args, **kwargs: None,
    subheader=lambda *args, **kwargs: None,
    columns=lambda n: [SimpleNamespace(button=lambda *args, **kwargs: False) for _ in range(n)],
    button=lambda *args, **kwargs: False,
    text_input=lambda *args, **kwargs: "",
    success=lambda *args, **kwargs: None,
    stop=lambda: None,
  )


@pytest.fixture
def streamlit_app(monkeypatch):
  module = importlib.import_module('streamlit_app')
  fake_st = _fake_streamlit_state()
  monkeypatch.setattr(module, 'st', fake_st)
  return module, fake_st


def test_ensure_session_creates_session(monkeypatch, streamlit_app):
  module, fake_st = streamlit_app

  monkeypatch.setattr(module, 'api_post', lambda path, payload: {'session_id': 'new'})

  payload = module.ensure_session()

  assert payload['session_id'] == 'new'
  assert fake_st.session_state['maze_session']['session_id'] == 'new'


def test_ensure_session_reuses_existing(monkeypatch, streamlit_app):
  module, fake_st = streamlit_app
  fake_st.session_state.maze_session = {'session_id': 'existing'}

  def fail_api(*args, **kwargs):  # pragma: no cover - should not be called
    raise AssertionError('api_post should not be invoked when session exists')

  monkeypatch.setattr(module, 'api_post', fail_api)

  payload = module.ensure_session()

  assert payload['session_id'] == 'existing'


def test_ensure_session_handles_api_failure(monkeypatch, streamlit_app):
  module, fake_st = streamlit_app
  errors = []
  fake_st.error = lambda message: errors.append(message)

  def failing_api(*args, **kwargs):
    raise requests.RequestException('boom')

  monkeypatch.setattr(module, 'api_post', failing_api)

  payload = module.ensure_session()

  assert payload is None
  assert not fake_st.session_state.get('maze_session')
  assert errors  # error message recorded
