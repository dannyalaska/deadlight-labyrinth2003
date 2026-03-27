from __future__ import annotations

from fastapi.testclient import TestClient


def test_healthcheck(client: TestClient) -> None:
  response = client.get("/api/health")
  assert response.status_code == 200
  assert response.json() == {"status": "ok"}

def test_frontend_assets_served(client: TestClient) -> None:
  index_response = client.get("/")
  assert index_response.status_code == 200
  assert "text/html" in index_response.headers["content-type"]

  css_response = client.get("/styles.css")
  assert css_response.status_code == 200
  assert "text/css" in css_response.headers["content-type"]

  js_response = client.get("/script.js")
  assert js_response.status_code == 200
  assert "javascript" in js_response.headers["content-type"]


def test_chapter_metadata(client: TestClient) -> None:
  response = client.get("/api/chapter")
  assert response.status_code == 200
  data = response.json()
  assert data["entrypoint"] == "boot_sequence"
  assert any(scene["requires_device_orientation"] for scene in data["scenes"])


def test_branching_story_flow(client: TestClient) -> None:
  start_response = client.post("/api/session", json={})
  assert start_response.status_code == 200
  session = start_response.json()
  session_id = session["session_id"]

  assert session["scene"]["id"] == "boot_sequence"
  assert session["pending_branch"] is False

  # Advance to the maze entry where a branch is required.
  for expected in ["login_prompt", "strange_forum", "maze_entry"]:
    advance_response = client.post(
      "/api/progress",
      json={"session_id": session_id, "event": "advance"},
    )
    assert advance_response.status_code == 200
    session = advance_response.json()
    assert session["scene"]["id"] == expected

  assert session["pending_branch"] is True
  assert session["scene"]["requires_device_orientation"] is True
  branch_options = session["branching_paths"]
  assert len(branch_options) == 2

  # Choose the left corridor.
  decision_response = client.post(
    "/api/progress",
    json={
      "session_id": session_id,
      "event": "decision",
      "direction": branch_options[0]["direction"],
    },
  )
  assert decision_response.status_code == 200
  session = decision_response.json()
  assert session["scene"]["id"] == branch_options[0]["target_scene_id"]
  assert session["pending_branch"] is False

  # Advance to the terminal scene.
  advance_response = client.post(
    "/api/progress",
    json={"session_id": session_id, "event": "advance"},
  )
  assert advance_response.status_code == 200
  session = advance_response.json()
  assert session["scene"]["id"] == "black_terminal"
  assert session["allow_registration"] is True

  # Trigger CTA to reach the signup screen.
  cta_response = client.post(
    "/api/progress",
    json={"session_id": session_id, "event": "cta"},
  )
  assert cta_response.status_code == 200
  session = cta_response.json()
  assert session["scene"]["id"] == "signup_screen"
  assert session["story_complete"] is True

  # Register and ensure the session flips to registered.
  register_response = client.post(
    "/api/register",
    json={
      "name": "Test User",
      "email": "test@example.com",
      "session_id": session_id,
    },
  )
  assert register_response.status_code == 200
  register_payload = register_response.json()
  assert register_payload["status"] == "registered"
  assert register_payload["session"]["registered"] is True
