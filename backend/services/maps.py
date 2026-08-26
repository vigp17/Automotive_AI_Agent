"""Azure Maps client wrapper plus a deterministic mock (MOCK_MODE)."""

from __future__ import annotations

import hashlib
import math

import httpx

from app.config import get_settings
from simulator.vehicle import haversine_km

AVERAGE_SPEED_KPH = 55.0

# Known demo destinations around Seattle for the mock geocoder
KNOWN_PLACES = {
    "bellevue office": (47.6101, -122.2015),
    "bellevue": (47.6144, -122.1923),
    "hq - south lake union": (47.6235, -122.336),
    "hq": (47.6235, -122.336),
    "office": (47.6101, -122.2015),
    "airport": (47.4502, -122.3088),
    "seatac": (47.4502, -122.3088),
    "downtown": (47.6062, -122.3321),
    "redmond campus": (47.674, -122.1215),
    "redmond": (47.674, -122.1215),
    "tacoma": (47.2529, -122.4443),
    "home": (47.6802, -122.355),
}


def _interpolate(origin: tuple[float, float], dest: tuple[float, float], n: int = 8):
    return [
        (
            origin[0] + (dest[0] - origin[0]) * i / n,
            origin[1] + (dest[1] - origin[1]) * i / n,
        )
        for i in range(1, n + 1)
    ]


class MockMapsClient:
    """Deterministic routing: geocode from a known-places table (or a stable
    pseudo-random point ~15-25 km away for unknown names), straight-line route
    with a road-factor, traffic delay derived from the name hash."""

    async def geocode(self, query: str) -> tuple[float, float]:
        key = query.strip().lower()
        for name, coords in KNOWN_PLACES.items():
            if name in key:
                return coords
        digest = hashlib.sha256(key.encode()).digest()
        angle = digest[0] / 255.0 * 2 * math.pi
        dist_km = 15.0 + digest[1] / 255.0 * 10.0
        dlat = dist_km / 111.0 * math.cos(angle)
        dlon = dist_km / 78.0 * math.sin(angle)
        return (47.6062 + dlat, -122.3321 + dlon)

    async def route(self, origin: tuple[float, float], destination: str) -> dict:
        dest = await self.geocode(destination)
        straight = haversine_km(origin[0], origin[1], dest[0], dest[1])
        distance_km = round(straight * 1.25, 1)  # road factor
        traffic_delay_min = hashlib.sha256(destination.lower().encode()).digest()[2] % 9
        duration_min = round(distance_km / AVERAGE_SPEED_KPH * 60 + traffic_delay_min, 1)
        return {
            "destination": destination,
            "dest_lat": dest[0],
            "dest_lon": dest[1],
            "distance_km": distance_km,
            "duration_min": duration_min,
            "traffic_delay_min": traffic_delay_min,
            "points": _interpolate(origin, dest),
        }


class AzureMapsClient:
    """Thin wrapper over Azure Maps Search + Route Directions REST APIs."""

    BASE = "https://atlas.microsoft.com"

    def __init__(self, key: str) -> None:
        self.key = key

    async def geocode(self, query: str) -> tuple[float, float]:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{self.BASE}/search/address/json",
                params={"api-version": "1.0", "subscription-key": self.key, "query": query},
            )
            resp.raise_for_status()
            pos = resp.json()["results"][0]["position"]
            return (pos["lat"], pos["lon"])

    async def route(self, origin: tuple[float, float], destination: str) -> dict:
        dest = await self.geocode(destination)
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                f"{self.BASE}/route/directions/json",
                params={
                    "api-version": "1.0",
                    "subscription-key": self.key,
                    "query": f"{origin[0]},{origin[1]}:{dest[0]},{dest[1]}",
                    "traffic": "true",
                },
            )
            resp.raise_for_status()
            summary = resp.json()["routes"][0]["summary"]
            points = [
                (p["latitude"], p["longitude"])
                for leg in resp.json()["routes"][0]["legs"]
                for p in leg["points"]
            ]
        return {
            "destination": destination,
            "dest_lat": dest[0],
            "dest_lon": dest[1],
            "distance_km": round(summary["lengthInMeters"] / 1000, 1),
            "duration_min": round(summary["travelTimeInSeconds"] / 60, 1),
            "traffic_delay_min": round(summary.get("trafficDelayInSeconds", 0) / 60, 1),
            "points": points[:: max(1, len(points) // 20)] if points else [],
        }


_client: MockMapsClient | AzureMapsClient | None = None


def get_maps_client():
    global _client
    if _client is None:
        settings = get_settings()
        if settings.mock_mode or not settings.azure_maps_key:
            _client = MockMapsClient()
        else:
            _client = AzureMapsClient(settings.azure_maps_key)
    return _client
