"""Navigation tools: routing, ETA and traffic via the maps client."""

from __future__ import annotations

import asyncio
import json

from langchain_core.tools import tool

from services.maps import get_maps_client
from services.preferences import resolve_place
from simulator.vehicle import get_simulator


def _route_sync(destination: str) -> dict:
    sim = get_simulator()
    origin = (sim.lat, sim.lon)
    query, label = resolve_place(destination)
    route = asyncio.run(get_maps_client().route(origin, query))
    route["destination"] = label
    return route


@tool
def get_route(destination: str) -> str:
    """Plan a route from the vehicle's current location to a destination.
    Returns distance, ETA, traffic delay, and starts driving there."""
    route = _route_sync(destination)
    sim = get_simulator()
    sim.set_route(
        route["points"],
        destination=route["destination"],
        eta_min=route["duration_min"],
        distance_km=route["distance_km"],
        traffic_delay_min=route["traffic_delay_min"],
    )
    return json.dumps(
        {
            "destination": route["destination"],
            "distance_km": route["distance_km"],
            "eta_min": route["duration_min"],
            "traffic_delay_min": route["traffic_delay_min"],
            "navigation_started": True,
        }
    )


@tool
def cancel_navigation() -> str:
    """Cancel the current trip. Stops the vehicle and clears the route.
    Use when the driver says cancel, abort, stop navigation, or end the trip."""
    sim = get_simulator()
    result = sim.cancel_trip()
    return json.dumps(result)


@tool
def set_saved_place(slot: str, query: str) -> str:
    """Save the driver's home or work destination. slot must be 'home' or 'work'.
    query is an address or place name used for routing (e.g. 'Ballard Seattle')."""
    from services.preferences import update_preferences

    key = slot.strip().lower()
    place = query.strip()
    if key not in ("home", "work"):
        return json.dumps({"error": "slot must be home or work"})
    if not place:
        return json.dumps({"error": "query is required"})
    if key == "home":
        prefs = update_preferences(home_query=place, home_label="Home")
        saved = prefs.home
    else:
        prefs = update_preferences(work_query=place, work_label="Work")
        saved = prefs.work
    return json.dumps({"slot": key, "label": saved.label, "query": saved.query})
