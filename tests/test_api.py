from __future__ import annotations

from fastapi.testclient import TestClient


def test_healthcheck(client: TestClient) -> None:
  response = client.get("/api/health")
  assert response.status_code == 200
  assert response.json() == {"status": "ok"}


def test_session_branching_flow(client: TestClient) -> None:
  # create session
  response = client.post("/api/session", json={})
  assert response.status_code == 200
  payload = response.json()
  session_id = payload["session_id"]

  assert payload["scene_id"] == "chapter_one.arrival"
  assert payload["pending_decision"] is False

  # advance through arrival -> departure -> maze edge
  response = client.post(
    "/api/progress",
    json={"session_id": session_id, "event": "advance"},
  )
  assert response.status_code == 200
  payload = response.json()
  assert payload["scene_id"] == "chapter_one.departure"

  response = client.post(
    "/api/progress",
    json={"session_id": session_id, "event": "advance"},
  )
  assert response.status_code == 200
  payload = response.json()
  assert payload["scene_id"] == "chapter_one.maze_edge"
  assert payload["pending_decision"] is True
  assert payload.get("branch")

  # choose a direction
  response = client.post(
    "/api/progress",
    json={
      "session_id": session_id,
      "event": "decision",
      "direction": "left",
      "via": "pytest",
    },
  )
  assert response.status_code == 200
  payload = response.json()
  assert payload["pending_decision"] is False

  # continue deeper into the maze
  response = client.post(
    "/api/progress",
    json={"session_id": session_id, "event": "advance"},
  )
  assert response.status_code == 200
  payload = response.json()
  assert payload["scene_id"] in {
    "chapter_one.maze_depth_a",
    "chapter_one.maze_depth_b",
    "chapter_one.office_threshold",
  }

  # fetch snapshot
  response = client.get(f"/api/session/{session_id}")
  assert response.status_code == 200
  snapshot = response.json()
  assert snapshot["scene_id"] == payload["scene_id"]
  assert snapshot["session_id"] == session_id
