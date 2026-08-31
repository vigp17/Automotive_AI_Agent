from agents.orchestrator import Orchestrator, classify_by_keywords
from simulator.vehicle import get_simulator


def test_keyword_classification():
    assert classify_by_keywords("Get me to my next meeting") == "trip_planning"
    assert classify_by_keywords("Set temperature to 21") == "hvac"
    assert classify_by_keywords("Do I have enough battery?") == "ev"
    assert classify_by_keywords("Navigate to the airport") == "navigation"
    assert classify_by_keywords("Cancel the trip") == "navigation"
    assert classify_by_keywords("What's on my calendar?") == "calendar"
    assert classify_by_keywords("Tell me a story") == "chat"


def make_orchestrator(tmp_path):
    return Orchestrator(db_path=str(tmp_path / "memory.sqlite"))


def test_trip_planning_with_sufficient_battery(tmp_path):
    sim = get_simulator()
    sim.soc = 90.0
    orch = make_orchestrator(tmp_path)
    result = orch.respond("Get me to my next meeting", session_id="t1")
    assert result["intent"] == "trip_planning"
    assert "Design Review" in result["reply"]
    assert "no charging stop" in result["reply"].lower()
    assert sim.driving


def test_trip_planning_adds_charging_stop_when_low(tmp_path):
    sim = get_simulator()
    sim.soc = 11.0  # barely above reserve: can't cover a cross-town trip
    orch = make_orchestrator(tmp_path)
    result = orch.respond("Get me to my next meeting", session_id="t2")
    assert result["intent"] == "trip_planning"
    assert "charging stop" in result["reply"].lower()


def test_wellness_note_on_low_battery(tmp_path):
    sim = get_simulator()
    sim.soc = 12.0
    orch = make_orchestrator(tmp_path)
    result = orch.respond("What's the cabin temperature?", session_id="t3")
    assert "wellness note" in result["reply"].lower()


def test_hvac_comfort_request(tmp_path):
    orch = make_orchestrator(tmp_path)
    result = orch.respond("I'm cold", session_id="t4")
    assert result["intent"] == "hvac"
    sim = get_simulator()
    assert sim.target_temp_c == 24.0


def test_calendar_agent(tmp_path):
    orch = make_orchestrator(tmp_path)
    result = orch.respond("When is my next meeting?", session_id="t5")
    assert result["intent"] == "calendar"
    assert "Design Review" in result["reply"]
