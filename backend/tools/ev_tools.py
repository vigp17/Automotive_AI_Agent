"""EV tools: SOC analysis and charging-stop planning."""

from __future__ import annotations

import asyncio
import json

from langchain_core.tools import tool

from services.charging import charging_needed, nearest_station, station_near_route
from services.maps import get_maps_client
from simulator.vehicle import get_simulator


@tool
def get_battery_status() -> str:
    """Get battery state of charge, estimated range, and whether a charge is advisable."""
    sim = get_simulator()
    soc = sim.get_soc()
    return json.dumps(
        {
            "soc_percent": soc,
            "range_km": sim.range_km(),
            "low_battery": soc < 25.0,
        }
    )


@tool
def plan_charging_stop(destination: str = "") -> str:
    """Check whether the battery covers a trip and recommend a charging stop.
    If destination is empty, uses the active trip or the nearest station."""
    sim = get_simulator()
    soc = sim.get_soc()

    if destination:
        route = asyncio.run(get_maps_client().route((sim.lat, sim.lon), destination))
        points = route["points"]
        trip_km = route["distance_km"]
        target = route["destination"]
    elif sim.trip and sim.trip.route:
        points = sim.trip.route
        trip_km = sim.trip.distance_km or 0.0
        target = sim.trip.destination
    else:
        station = nearest_station(sim.lat, sim.lon)
        return json.dumps(
            {
                "soc_percent": soc,
                "charging_required": soc < 25.0,
                "nearest_station": station,
            }
        )

    analysis = charging_needed(soc, trip_km)
    result = {"soc_percent": soc, "destination": target, **analysis}
    if analysis["charging_required"]:
        result["recommended_station"] = station_near_route(points)
    return json.dumps(result)
