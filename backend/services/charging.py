"""Charging-station lookup over the bundled static dataset."""

from __future__ import annotations

import json

from app.config import DATA_DIR
from simulator.vehicle import (
    BASE_CONSUMPTION_KWH_PER_KM,
    BATTERY_CAPACITY_KWH,
    SOC_RESERVE_PERCENT,
    haversine_km,
)

STATIONS_FILE = DATA_DIR / "charging_stations.json"


def load_stations() -> list[dict]:
    return json.loads(STATIONS_FILE.read_text())


def nearest_station(lat: float, lon: float) -> dict:
    stations = load_stations()
    best = min(stations, key=lambda s: haversine_km(lat, lon, s["lat"], s["lon"]))
    best = dict(best)
    best["distance_km"] = round(haversine_km(lat, lon, best["lat"], best["lon"]), 1)
    return best


def station_near_route(points: list[tuple[float, float]]) -> dict:
    """Pick the station with the smallest detour from any route point."""
    stations = load_stations()

    def detour(station: dict) -> float:
        return min(haversine_km(p[0], p[1], station["lat"], station["lon"]) for p in points)

    best = min(stations, key=detour)
    best = dict(best)
    best["detour_km"] = round(detour(best), 1)
    return best


def charging_needed(soc_percent: float, trip_km: float) -> dict:
    """Energy math for a trip: does the current SOC cover it with reserve?"""
    needed_kwh = trip_km * BASE_CONSUMPTION_KWH_PER_KM
    usable_kwh = max(soc_percent - SOC_RESERVE_PERCENT, 0.0) / 100.0 * BATTERY_CAPACITY_KWH
    shortfall_kwh = max(0.0, needed_kwh - usable_kwh)
    return {
        "trip_km": round(trip_km, 1),
        "needed_kwh": round(needed_kwh, 1),
        "usable_kwh": round(usable_kwh, 1),
        "charging_required": shortfall_kwh > 0,
        "shortfall_kwh": round(shortfall_kwh, 1),
        "recommended_charge_minutes": round(shortfall_kwh / 100.0 * 60 + 5) if shortfall_kwh else 0,
    }
