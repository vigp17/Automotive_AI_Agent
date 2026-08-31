import asyncio

import httpx

from services.maps import MockMapsClient, OsmMapsClient, lookup_place


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


def test_osrm_returns_road_distance_for_any_city():
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "/search" in url:
            return httpx.Response(
                200,
                json=[
                    {
                        "lat": "41.4993",
                        "lon": "-81.6944",
                        "display_name": "Cleveland, Cuyahoga County, Ohio, United States",
                    }
                ],
            )
        if "/route/v1/driving" in url:
            return httpx.Response(
                200,
                json={
                    "code": "Ok",
                    "routes": [
                        {
                            "distance": 3_900_000.0,
                            "duration": 140_400.0,
                            "geometry": {
                                "type": "LineString",
                                "coordinates": [[-122.33, 47.60], [-81.69, 41.50]],
                            },
                        }
                    ],
                },
            )
        return httpx.Response(404)

    client = OsmMapsClient(transport=httpx.MockTransport(handler))
    route = asyncio.run(client.route((47.6062, -122.3321), "Cleveland"))
    assert route["distance_km"] == 3900.0
    assert route["duration_min"] == 2340.0
    assert route["dest_lat"] == 41.4993



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
