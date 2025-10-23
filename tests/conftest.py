from __future__ import annotations

import os
import sys
from importlib import reload
from pathlib import Path
from typing import Generator

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path: Path, monkeypatch) -> Generator[TestClient, None, None]:
  """Provide a fresh API client with an isolated session store."""
  db_path = tmp_path / "maze.db"
  os.environ["LABYRINTH_DB_PATH"] = str(db_path)
  monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
  monkeypatch.setenv("LABYRINTH_LOG_LEVEL", "ERROR")

  # Ensure the module is reloaded with the new environment.
  if "labyrinth.server" in sys.modules:
    del sys.modules["labyrinth.server"]
  
  from labyrinth import server  # type: ignore
  
  # Re-add to sys.modules before reloading
  sys.modules["labyrinth.server"] = server
  reload(server)
  app = server.app
  test_client = TestClient(app)
  try:
    yield test_client
  finally:
    test_client.close()
    if "labyrinth.server" in sys.modules:
      del sys.modules["labyrinth.server"]
