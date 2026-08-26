from simulator.vehicle import get_simulator


def test_vehicle_state(client):
    resp = client.get("/vehicle/state")
    assert resp.status_code == 200
    state = resp.json()
    assert 0 <= state["soc_percent"] <= 100
    assert "location" in state and "cabin_temp_c" in state


def test_set_temperature_endpoint(client):
    resp = client.post("/vehicle/temperature", json={"celsius": 23.0})
    assert resp.status_code == 200
    assert resp.json()["target_temp_c"] == 23.0
    assert get_simulator().target_temp_c == 23.0


def test_chat_battery(client):
    resp = client.post("/chat", json={"message": "What's my battery level?"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["intent"] == "ev"
    assert "%" in body["reply"]


def test_chat_set_temperature(client):
    resp = client.post("/chat", json={"message": "Set the temperature to 22 degrees"})
    body = resp.json()
    assert body["intent"] == "hvac"
    assert "22" in body["reply"]
    assert get_simulator().target_temp_c == 22.0


def test_chat_navigation_starts_trip(client):
    resp = client.post("/chat", json={"message": "Navigate to the airport"})
    body = resp.json()
    assert body["intent"] == "navigation"
    assert "ETA" in body["reply"] or "eta" in body["reply"].lower()
    sim = get_simulator()
    assert sim.driving and sim.trip is not None


def test_chat_memory_is_per_session(client):
    client.post("/chat", json={"message": "hello", "session_id": "a"})
    resp = client.post("/chat", json={"message": "hello", "session_id": "b"})
    assert resp.status_code == 200


def test_report_endpoint(client):
    resp = client.get("/report")
    assert resp.status_code == 200
    markdown = resp.json()["markdown"]
    assert "# Trip Report" in markdown
    assert "Battery" in markdown


def test_voice_endpoint(client):
    resp = client.post(
        "/voice",
        files={"file": ("speech.wav", b"fake-audio-bytes", "audio/wav")},
        data={"session_id": "voice-test"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["transcript"] == "What's my battery level?"
    assert "%" in body["reply"]
    assert len(body["audio_base64"]) > 0
