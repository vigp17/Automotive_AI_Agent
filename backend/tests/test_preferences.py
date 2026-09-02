from services.preferences import get_preferences, resolve_place, update_preferences
from simulator.vehicle import get_simulator


def test_resolve_home_and_work():
    query, label = resolve_place("home")
    assert query == "home" and label == "Home"
    query, label = resolve_place("work")
    assert query == "office" and label == "Work"


def test_update_home_changes_resolution():
    update_preferences(home_query="Ballard Seattle", home_label="Home")
    query, label = resolve_place("take me home".split()[-1])
    assert query == "Ballard Seattle"
    assert label == "Home"


def test_preferences_endpoints(client):
    resp = client.get("/preferences")
    assert resp.status_code == 200
    body = resp.json()
    assert body["home"]["query"] == "home"
    resp = client.put(
        "/preferences",
        json={"home_query": "Redmond", "default_temp_c": 22.0},
    )
    assert resp.status_code == 200
    assert resp.json()["home"]["query"] == "Redmond"
    assert resp.json()["default_temp_c"] == 22.0
    assert get_simulator().target_temp_c == 22.0


def test_take_me_home_starts_navigation(client):
    resp = client.post("/chat", json={"message": "Take me home"})
    body = resp.json()
    assert body["intent"] == "navigation"
    assert get_simulator().driving
    assert get_simulator().trip is not None
    assert get_simulator().trip.destination == "Home"


def test_usual_temperature(client):
    update_preferences(default_temp_c=23.0)
    resp = client.post("/chat", json={"message": "Set my usual temperature"})
    assert resp.json()["intent"] == "hvac"
    assert get_simulator().target_temp_c == 23.0


def test_set_home_by_voice(client):
    resp = client.post("/chat", json={"message": "Set home to Portland"})
    assert resp.json()["intent"] == "navigation"
    assert get_preferences().home.query.lower() == "portland"
