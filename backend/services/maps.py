"""Azure Maps client wrapper plus a deterministic mock (MOCK_MODE)."""

from __future__ import annotations

import hashlib
import math
from urllib.parse import quote

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

# Real city coordinates so mock routing isn't "15 km from Seattle" for
# Detroit, Chicago, etc. Offline — no geocoding API required.
KNOWN_CITIES = {
    "detroit": (42.3314, -83.0458),
    "chicago": (41.8781, -87.6298),
    "new york": (40.7128, -74.0060),
    "nyc": (40.7128, -74.0060),
    "los angeles": (34.0522, -118.2437),
    "san francisco": (37.7749, -122.4194),
    "portland": (45.5152, -122.6784),
    "vancouver": (49.2827, -123.1207),
    "spokane": (47.6588, -117.4260),
    "boise": (43.6150, -116.2023),
    "denver": (39.7392, -104.9903),
    "austin": (30.2672, -97.7431),
    "boston": (42.3601, -71.0589),
    "miami": (25.7617, -80.1918),
}

ALL_PLACES = {**KNOWN_CITIES, **KNOWN_PLACES}


def lookup_place(query: str) -> tuple[float, float] | None:
    """Longest substring match against local POIs and known cities."""
    key = query.strip().lower()
    if not key:
        return None
    matches = [
        (name, coords)
        for name, coords in ALL_PLACES.items()
        if name == key or (len(name) >= 3 and (name in key or key in name))
    ]
    if not matches:
        return None
    matches.sort(key=lambda item: len(item[0]), reverse=True)
    return matches[0][1]


def _place_label(name: str) -> str:
    return " ".join(part.capitalize() for part in name.replace("-", " ").split())


def search_known_places(query: str, limit: int = 5) -> list[dict]:
    """Match the mock geocoder table, de-duplicated by coordinates."""
    key = query.strip().lower()
    if not key:
        return []
    seen: set[tuple[float, float]] = set()
    results: list[dict] = []
    for name, coords in ALL_PLACES.items():
        if key not in name and name not in key:
            continue
        if coords in seen:
            continue
        seen.add(coords)
        results.append({"label": _place_label(name), "lat": coords[0], "lon": coords[1]})
        if len(results) >= limit:
            break
    return results


def _interpolate(origin: tuple[float, float], dest: tuple[float, float], n: int = 8):
    return [
        (
            origin[0] + (dest[0] - origin[0]) * i / n,
            origin[1] + (dest[1] - origin[1]) * i / n,
        )
        for i in range(1, n + 1)
    ]


def _cruise_kph(distance_km: float) -> float:
    # Local streets vs highway — a 26-minute "Seattle to Detroit" was the
    # city-speed model applied to a fake nearby pin.
    return 90.0 if distance_km >= 150 else AVERAGE_SPEED_KPH


def _waypoint_count(distance_km: float) -> int:
    return max(8, min(20, int(distance_km / 200) + 8))


class MockMapsClient:
    """Deterministic routing: geocode from a known-places table (or a stable
    pseudo-random point ~15-25 km away for unknown names), straight-line route
    with a road-factor, traffic delay derived from the name hash."""

    async def geocode(self, query: str) -> tuple[float, float]:
        known = lookup_place(query)
        if known:
            return known
        digest = hashlib.sha256(query.strip().lower().encode()).digest()
        angle = digest[0] / 255.0 * 2 * math.pi
        dist_km = 15.0 + digest[1] / 255.0 * 10.0
        dlat = dist_km / 111.0 * math.cos(angle)
        dlon = dist_km / 78.0 * math.sin(angle)
        return (47.6062 + dlat, -122.3321 + dlon)

    async def search(self, query: str, limit: int = 5) -> list[dict]:
        """Typeahead suggestions for the HMI search box (parked only)."""
        hits = search_known_places(query, limit=limit)
        if hits:
            return hits
        lat, lon = await self.geocode(query)
        return [{"label": query.strip(), "lat": lat, "lon": lon}]

    async def route(self, origin: tuple[float, float], destination: str) -> dict:
        dest = await self.geocode(destination)
        return await self.route_to_coords(origin, dest, destination)

    async def route_to_coords(
        self, origin: tuple[float, float], dest: tuple[float, float], label: str
    ) -> dict:
        """Route to explicit coordinates (e.g. a map tap) without geocoding."""
        straight = haversine_km(origin[0], origin[1], dest[0], dest[1])
        distance_km = round(straight * 1.25, 1)  # road factor
        traffic_delay_min = hashlib.sha256(label.lower().encode()).digest()[2] % 9
        duration_min = round(distance_km / _cruise_kph(distance_km) * 60 + traffic_delay_min, 1)
        return {
            "destination": label,
            "dest_lat": dest[0],
            "dest_lon": dest[1],
            "distance_km": distance_km,
            "duration_min": duration_min,
            "traffic_delay_min": traffic_delay_min,
            "points": _interpolate(origin, dest, n=_waypoint_count(distance_km)),
        }


class OsmMapsClient:
    """Nominatim geocoding + OSRM road routing. No API key. Used when Azure
    Maps isn't configured so any city or address gets a real driving distance
    instead of a fake pin near Seattle."""

    NOMINATIM = "https://nominatim.openstreetmap.org"
    OSRM = "https://router.project-osrm.org"
    USER_AGENT = "AI-Cabin-Copilot/0.1 (https://github.com/vigp17/Automotive_AI_Agent)"

    def __init__(
        self,
        nominatim: str | None = None,
        osrm: str | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.nominatim = nominatim or self.NOMINATIM
        self.osrm = osrm or self.OSRM
        self.transport = transport

    def _headers(self) -> dict[str, str]:
        return {"User-Agent": self.USER_AGENT, "Accept": "application/json"}

    async def geocode(self, query: str) -> tuple[float, float]:
        known = lookup_place(query)
        if known:
            return known
        hits = await self.search(query, limit=1)
        if hits:
            return (hits[0]["lat"], hits[0]["lon"])
        raise ValueError(f"Could not geocode {query!r}")

    async def search(self, query: str, limit: int = 5) -> list[dict]:
        local = search_known_places(query, limit=limit)
        remaining = max(0, limit - len(local))
        if remaining == 0:
            return local
        try:
            async with httpx.AsyncClient(
                timeout=12, headers=self._headers(), transport=self.transport
            ) as client:
                resp = await client.get(
                    f"{self.nominatim}/search",
                    params={
                        "q": query,
                        "format": "json",
                        "limit": remaining,
                        "addressdetails": 0,
                    },
                )
                resp.raise_for_status()
                remote = []
                seen = {(round(p["lat"], 4), round(p["lon"], 4)) for p in local}
                for item in resp.json():
                    lat = float(item["lat"])
                    lon = float(item["lon"])
                    key = (round(lat, 4), round(lon, 4))
                    if key in seen:
                        continue
                    seen.add(key)
                    remote.append(
                        {
                            "label": item.get("display_name") or query,
                            "lat": lat,
                            "lon": lon,
                        }
                    )
                return local + remote
        except (httpx.HTTPError, ValueError, KeyError):
            return local

    async def route(self, origin: tuple[float, float], destination: str) -> dict:
        dest = await self.geocode(destination)
        return await self.route_to_coords(origin, dest, destination)

    async def route_to_coords(
        self, origin: tuple[float, float], dest: tuple[float, float], label: str
    ) -> dict:
        """Actual driving distance/ETA from OSRM; straight-line fallback."""
        try:
            async with httpx.AsyncClient(
                timeout=20, headers=self._headers(), transport=self.transport
            ) as client:
                coord = f"{origin[1]},{origin[0]};{dest[1]},{dest[0]}"
                resp = await client.get(
                    f"{self.osrm}/route/v1/driving/{coord}",
                    params={"overview": "simplified", "geometries": "geojson"},
                )
                resp.raise_for_status()
                route = resp.json()["routes"][0]
                coords = route.get("geometry", {}).get("coordinates") or []
                points = [(lat, lon) for lon, lat in coords]  # geojson is lon,lat
                if len(points) > 20:
                    step = max(1, len(points) // 20)
                    points = points[::step]
                if not points:
                    points = _interpolate(origin, dest, n=_waypoint_count(route["distance"] / 1000))
                return {
                    "destination": label,
                    "dest_lat": dest[0],
                    "dest_lon": dest[1],
                    "distance_km": round(route["distance"] / 1000, 1),
                    "duration_min": round(route["duration"] / 60, 1),
                    "traffic_delay_min": 0.0,
                    "points": points,
                }
        except (httpx.HTTPError, KeyError, IndexError, TypeError):
            return await MockMapsClient().route_to_coords(origin, dest, label)


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

    async def search(self, query: str, limit: int = 5) -> list[dict]:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{self.BASE}/search/fuzzy/json",
                params={
                    "api-version": "1.0",
                    "subscription-key": self.key,
                    "query": query,
                    "limit": limit,
                },
            )
            resp.raise_for_status()
            results = []
            for item in resp.json().get("results", [])[:limit]:
                pos = item.get("position") or {}
                if "lat" not in pos or "lon" not in pos:
                    continue
                poi = item.get("poi") or {}
                address = item.get("address") or {}
                label = poi.get("name") or address.get("freeformAddress") or query
                results.append({"label": label, "lat": pos["lat"], "lon": pos["lon"]})
            return results

    async def route(self, origin: tuple[float, float], destination: str) -> dict:
        dest = await self.geocode(destination)
        return await self.route_to_coords(origin, dest, destination)

    async def route_to_coords(
        self, origin: tuple[float, float], dest: tuple[float, float], label: str
    ) -> dict:
        async with httpx.AsyncClient(timeout=20) as client:
            try:
                resp = await client.get(
                    f"{self.BASE}/route/directions/json",
                    params={
                        "api-version": "1.0",
                        "subscription-key": self.key,
                        "query": f"{origin[0]},{origin[1]}:{dest[0]},{dest[1]}",
                        "traffic": "true",
                        "travelMode": "car",
                        "computeTravelTimeFor": "all",
                    },
                )
                resp.raise_for_status()
                summary = resp.json()["routes"][0]["summary"]
                points = [
                    (p["latitude"], p["longitude"])
                    for leg in resp.json()["routes"][0]["legs"]
                    for p in leg["points"]
                ]
            except (httpx.HTTPError, KeyError, IndexError, TypeError):
                return await OsmMapsClient().route_to_coords(origin, dest, label)
        return {
            "destination": label,
            "dest_lat": dest[0],
            "dest_lon": dest[1],
            "distance_km": round(summary["lengthInMeters"] / 1000, 1),
            "duration_min": round(summary["travelTimeInSeconds"] / 60, 1),
            "traffic_delay_min": round(summary.get("trafficDelayInSeconds", 0) / 60, 1),
            "points": points[:: max(1, len(points) // 20)] if points else [],
        }


class TomTomMapsClient:
    """TomTom Search + Routing with live traffic. Free developer key."""

    BASE = "https://api.tomtom.com"

    def __init__(self, key: str) -> None:
        self.key = key

    async def geocode(self, query: str) -> tuple[float, float]:
        known = lookup_place(query)
        if known:
            return known
        hits = await self.search(query, limit=1)
        if hits:
            return (hits[0]["lat"], hits[0]["lon"])
        raise ValueError(f"Could not geocode {query!r}")

    async def search(self, query: str, limit: int = 5) -> list[dict]:
        local = search_known_places(query, limit=limit)
        remaining = max(0, limit - len(local))
        if remaining == 0:
            return local
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"{self.BASE}/search/2/search/{quote(query)}.json",
                    params={"key": self.key, "limit": remaining},
                )
                resp.raise_for_status()
                remote = []
                seen = {(round(p["lat"], 4), round(p["lon"], 4)) for p in local}
                for item in resp.json().get("results", []):
                    pos = item.get("position") or {}
                    if "lat" not in pos or "lon" not in pos:
                        continue
                    key = (round(float(pos["lat"]), 4), round(float(pos["lon"]), 4))
                    if key in seen:
                        continue
                    seen.add(key)
                    poi = item.get("poi") or {}
                    address = item.get("address") or {}
                    label = poi.get("name") or address.get("freeformAddress") or query
                    remote.append({"label": label, "lat": float(pos["lat"]), "lon": float(pos["lon"])})
                    if len(local) + len(remote) >= limit:
                        break
                return local + remote
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            return local or []

    async def route(self, origin: tuple[float, float], destination: str) -> dict:
        dest = await self.geocode(destination)
        return await self.route_to_coords(origin, dest, destination)

    async def route_to_coords(
        self, origin: tuple[float, float], dest: tuple[float, float], label: str
    ) -> dict:
        path = f"{origin[0]},{origin[1]}:{dest[0]},{dest[1]}"
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.get(
                    f"{self.BASE}/routing/1/calculateRoute/{path}/json",
                    params={
                        "key": self.key,
                        "traffic": "true",
                        "travelMode": "car",
                        "computeTravelTimeFor": "all",
                    },
                )
                resp.raise_for_status()
                route = resp.json()["routes"][0]
                summary = route["summary"]
                points = [
                    (p["latitude"], p["longitude"])
                    for leg in route.get("legs") or []
                    for p in leg.get("points") or []
                ]
        except (httpx.HTTPError, KeyError, IndexError, TypeError):
            return await OsmMapsClient().route_to_coords(origin, dest, label)
        return {
            "destination": label,
            "dest_lat": dest[0],
            "dest_lon": dest[1],
            "distance_km": round(summary["lengthInMeters"] / 1000, 1),
            "duration_min": round(summary["travelTimeInSeconds"] / 60, 1),
            "traffic_delay_min": round(summary.get("trafficDelayInSeconds", 0) / 60, 1),
            "points": points[:: max(1, len(points) // 20)] if points else [],
        }


_client: MockMapsClient | OsmMapsClient | AzureMapsClient | TomTomMapsClient | None = None

AZURE_TRAFFIC_TILE = "https://atlas.microsoft.com/traffic/flow/tile/png"
TOMTOM_TRAFFIC_TILE = "https://api.tomtom.com/traffic/map/4/tile/flow/relative"


def reset_maps_client() -> None:
    global _client
    _client = None


def resolved_maps_backend() -> str:
    settings = get_settings()
    backend = settings.maps_backend.lower().strip()
    if backend == "auto":
        if settings.tomtom_api_key.strip():
            return "tomtom"
        if settings.azure_maps_key.strip():
            return "azure"
        return "osm"
    return backend


def maps_status() -> dict:
    backend = resolved_maps_backend()
    return {
        "backend": backend,
        "configured": backend in {"tomtom", "azure"},
        "traffic": backend in {"tomtom", "azure"},
    }


async def fetch_traffic_tile(z: int, x: int, y: int) -> bytes:
    """Traffic-flow tile from TomTom or Azure Maps. Key stays on the server."""
    settings = get_settings()
    backend = resolved_maps_backend()
    async with httpx.AsyncClient(timeout=15) as client:
        if backend == "tomtom" and settings.tomtom_api_key.strip():
            resp = await client.get(
                f"{TOMTOM_TRAFFIC_TILE}/{z}/{x}/{y}.png",
                params={"key": settings.tomtom_api_key.strip()},
            )
        elif backend == "azure" and settings.azure_maps_key.strip():
            resp = await client.get(
                AZURE_TRAFFIC_TILE,
                params={
                    "api-version": "1.0",
                    "style": "relative",
                    "zoom": z,
                    "x": x,
                    "y": y,
                    "subscription-key": settings.azure_maps_key.strip(),
                },
            )
        else:
            raise ValueError("Live traffic is not configured")
        resp.raise_for_status()
        return resp.content


def get_maps_client():
    global _client
    if _client is None:
        settings = get_settings()
        backend = resolved_maps_backend()
        if backend == "tomtom" and settings.tomtom_api_key.strip():
            _client = TomTomMapsClient(settings.tomtom_api_key.strip())
        elif backend == "azure" and settings.azure_maps_key.strip():
            _client = AzureMapsClient(settings.azure_maps_key.strip())
        elif backend == "mock":
            _client = MockMapsClient()
        else:
            _client = OsmMapsClient()
    return _client
