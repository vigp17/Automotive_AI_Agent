import os
import sys
from pathlib import Path

# Force mock mode for the whole test run, regardless of any local .env.
# LOCAL_STT=false keeps the deterministic mock transcriber (no Whisper model
# download in tests).
os.environ["MOCK_MODE"] = "true"
os.environ["LOCAL_STT"] = "false"
os.environ["VEHICLE_BUS"] = "sim"
os.environ["MAPS_BACKEND"] = "mock"

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.config import DATA_DIR, get_settings
from services.maps import reset_maps_client
from services.preferences import reset_preferences

get_settings.cache_clear()
reset_maps_client()

import pytest

from simulator import vehicle


@pytest.fixture(autouse=True)
def isolated_prefs(tmp_path):
    dest = tmp_path / "preferences.json"
    dest.write_text((DATA_DIR / "preferences.json").read_text())
    reset_preferences(dest)
    yield dest
    reset_preferences()


@pytest.fixture(autouse=True)
def fresh_simulator():
    yield vehicle.reset_simulator()
    vehicle.reset_simulator()


@pytest.fixture
def client(tmp_path):
    """TestClient with an isolated per-test memory database."""
    from fastapi.testclient import TestClient

    from agents.orchestrator import Orchestrator
    from app.main import app

    with TestClient(app) as test_client:
        app.state.orchestrator = Orchestrator(db_path=str(tmp_path / "memory.sqlite"))
        yield test_client
