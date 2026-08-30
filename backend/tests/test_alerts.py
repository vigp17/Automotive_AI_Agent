from datetime import datetime, timedelta

from services.alerts import evaluate_alerts
from services.calendar_store import Meeting
from simulator.vehicle import get_simulator


def _meeting(hours_from_now: float = 0.5) -> Meeting:
    return Meeting(
        title="Design Review",
        location="Bellevue Office",
        lat=47.6101,
        lon=-122.2015,
        start=datetime.now() + timedelta(hours=hours_from_now),
        duration_min=60,
    )


def test_leave_soon_when_meeting_is_within_window():
    alerts = evaluate_alerts(sim=get_simulator(), meeting=_meeting(0.5))
    leave = next(a for a in alerts if a["id"] == "leave_soon")
    assert "Design Review" in leave["message"]
    assert leave["action"] == "Get me to my next meeting"
    assert leave["severity"] in ("info", "warning", "danger")


def test_leave_soon_suppressed_when_already_navigating_there():
    sim = get_simulator()
    sim.set_route([(47.61, -122.20)], destination="Bellevue Office")
    alerts = evaluate_alerts(sim=sim, meeting=_meeting(0.5))
    assert all(a["id"] != "leave_soon" for a in alerts)


def test_low_battery_alert():
    sim = get_simulator()
    sim.soc = 12.0
    alerts = evaluate_alerts(sim=sim, meeting=None)
    battery = next(a for a in alerts if a["id"] == "low_battery")
    assert battery["severity"] == "danger"
    assert "12" in battery["message"]


def test_cabin_temp_gap_alert():
    sim = get_simulator()
    sim.cabin_temp_c = 21.0
    sim.set_temperature(28.0)
    alerts = evaluate_alerts(sim=sim, meeting=None)
    assert any(a["id"] == "cabin_temp" for a in alerts)


def test_long_drive_alert():
    sim = get_simulator()
    sim.set_route([(47.7, -122.3)], destination="north")
    assert sim.trip is not None
    sim.trip.started_at -= 91 * 60
    alerts = evaluate_alerts(sim=sim, meeting=None)
    assert any(a["id"] == "long_drive" for a in alerts)


def test_late_night_alert():
    sim = get_simulator()
    sim.set_route([(47.7, -122.3)], destination="north")
    late = datetime.now().replace(hour=23, minute=0, second=0, microsecond=0)
    alerts = evaluate_alerts(sim=sim, meeting=None, now=late)
    assert any(a["id"] == "late_night" for a in alerts)


def test_no_spurious_alerts_on_parked_comfortable_car():
    sim = get_simulator()
    far = _meeting(8.0)
    alerts = evaluate_alerts(sim=sim, meeting=far)
    ids = {a["id"] for a in alerts}
    assert "low_battery" not in ids
    assert "cabin_temp" not in ids
    assert "leave_soon" not in ids


def test_alerts_on_vehicle_state_and_alerts_endpoint(client):
    resp = client.get("/vehicle/state")
    assert resp.status_code == 200
    assert isinstance(resp.json()["alerts"], list)

    resp = client.get("/alerts")
    assert resp.status_code == 200
    assert "alerts" in resp.json()


def test_websocket_includes_alerts(client):
    with client.websocket_connect("/vehicle/ws") as ws:
        payload = ws.receive_json()
    assert "soc_percent" in payload
    assert isinstance(payload["alerts"], list)
