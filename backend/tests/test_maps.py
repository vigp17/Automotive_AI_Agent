import asyncio

from services.maps import MockMapsClient, lookup_place


def test_lookup_detroit_is_in_michigan():
    lat, lon = lookup_place("detroit")
    assert lat == 42.3314
    assert lon == -83.0458


def test_seattle_to_detroit_is_a_multi_day_drive():
    client = MockMapsClient()
    route = asyncio.run(client.route((47.6062, -122.3321), "Detroit"))
    assert route["distance_km"] > 2000
    assert route["duration_min"] > 20 * 60
    assert route["dest_lat"] == 42.3314


def test_local_airport_still_short():
    client = MockMapsClient()
    route = asyncio.run(client.route((47.6062, -122.3321), "airport"))
    assert route["distance_km"] < 50
    assert route["duration_min"] < 60
