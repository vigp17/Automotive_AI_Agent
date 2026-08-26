"""Markdown trip/wellness report generator (blueprint 'Report generation')."""

from __future__ import annotations

from datetime import datetime

from services.calendar_store import get_calendar_store
from simulator.vehicle import get_simulator


def build_trip_report() -> str:
    sim = get_simulator()
    state = sim.state()
    lines = [
        "# Trip Report",
        "",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "## Vehicle status",
        "",
        "| Signal | Value |",
        "| --- | --- |",
        f"| Battery | {state['soc_percent']}% ({state['range_km']} km range) |",
        f"| Speed | {state['speed_kph']} km/h |",
        f"| Cabin temperature | {state['cabin_temp_c']} C (target {state['target_temp_c']} C) |",
        f"| Odometer | {state['odometer_km']} km |",
        f"| Location | {state['location']['lat']}, {state['location']['lon']} |",
    ]

    if sim.trip:
        soc_used = round(sim.trip.start_soc - sim.soc, 1)
        distance_done = round(sim.odometer_km - sim.trip.start_odometer_km, 1)
        lines += [
            "",
            "## Current trip",
            "",
            f"- Destination: {sim.trip.destination}",
            f"- Elapsed: {round(sim.trip_elapsed_min(), 1)} min",
            f"- Distance covered: {distance_done} km"
            + (f" of {sim.trip.distance_km} km" if sim.trip.distance_km else ""),
            f"- Battery used: {soc_used}%",
            f"- Status: {'driving' if sim.driving else 'arrived/paused'}",
        ]
    else:
        lines += ["", "## Current trip", "", "No active trip."]

    meetings = get_calendar_store().list_meetings()
    lines += ["", "## Upcoming meetings", ""]
    if meetings:
        lines += [
            f"- {m.title} - {m.start.strftime('%a %I:%M %p').replace(' 0', ' ')} at {m.location}"
            for m in meetings
        ]
    else:
        lines.append("Calendar is clear.")

    lines += ["", "## Wellness", ""]
    notes = []
    if sim.trip and sim.trip_elapsed_min() > 90:
        notes.append("- Long drive in progress: a break is recommended.")
    if state["soc_percent"] < 15:
        notes.append("- Battery low: plan a charging stop.")
    lines += notes or ["- No wellness concerns."]

    return "\n".join(lines)
