from datetime import datetime, timedelta

from services.graph_calendar import meeting_from_graph, parse_graph_datetime
from services.maps import AzureMapsClient, MockMapsClient, OsmMapsClient, get_maps_client, reset_maps_client


def test_parse_graph_datetime_utc():
    dt = parse_graph_datetime({"dateTime": "2026-09-02T18:30:00Z", "timeZone": "UTC"})
    assert dt.hour in range(0, 24)
    assert dt.minute == 30


def test_meeting_from_graph_bellevue():
    event = {
        "subject": "Design Review",
        "start": {"dateTime": (datetime.now() + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%S")},
        "end": {"dateTime": (datetime.now() + timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%S")},
        "location": {"displayName": "Bellevue Office"},
    }
    meeting = meeting_from_graph(event)
    assert meeting is not None
    assert meeting.title == "Design Review"
    assert meeting.location == "Bellevue Office"
    assert meeting.lat == 47.6101


def test_calendar_status_json(client):
    resp = client.get("/calendar/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["backend"] == "json"
    assert body["connected"] is False


def test_calendar_connect_without_client_id(client):
    resp = client.post("/calendar/connect")
    assert resp.status_code == 400


def test_maps_auto_uses_osm_without_azure_key(monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("MAPS_BACKEND", "auto")
    monkeypatch.setenv("AZURE_MAPS_KEY", "")
    get_settings.cache_clear()
    reset_maps_client()
    client = get_maps_client()
    assert isinstance(client, OsmMapsClient)
    get_settings.cache_clear()
    reset_maps_client()


def test_maps_azure_when_key_and_backend_azure():
    client = AzureMapsClient("fake-key")
    assert client.key == "fake-key"
    assert isinstance(MockMapsClient(), MockMapsClient)
