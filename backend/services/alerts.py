"""Proactive cabin alerts from live vehicle + calendar state.

Evaluated every websocket tick and attached to /vehicle/state so the dashboard
can show banners without the driver asking.
"""

from __future__ import annotations

from datetime import datetime

from services.calendar_store import Meeting, get_calendar_store
from services.maps import AVERAGE_SPEED_KPH
from simulator.vehicle import VehicleSimulator, get_simulator, haversine_km

LOW_BATTERY_PERCENT = 15.0
CABIN_GAP_C = 4.0
LONG_DRIVE_MIN = 90.0
LEAVE_BUFFER_MIN = 5.0
LEAVE_WINDOW_MIN = 120.0
ROAD_FACTOR = 1.25


def _leave_eta_min(sim: VehicleSimulator, meeting: Meeting) -> float:
    straight = haversine_km(sim.lat, sim.lon, meeting.lat, meeting.lon)
    distance_km = straight * ROAD_FACTOR
    return distance_km / AVERAGE_SPEED_KPH * 60.0


def evaluate_alerts(
    sim: VehicleSimulator | None = None,
    meeting: Meeting | None = None,
    now: datetime | None = None,
) -> list[dict]:
    """Return currently active alerts (id, severity, title, message, action)."""
    sim = sim or get_simulator()
    now = now or datetime.now()
    if meeting is None:
        meeting = get_calendar_store().next_meeting()

    alerts: list[dict] = []

    if meeting is not None:
        already_en_route = bool(
            sim.trip
            and sim.driving
            and sim.trip.destination.lower() == meeting.location.lower()
        )
        if not already_en_route:
            eta_min = _leave_eta_min(sim, meeting)
            minutes_until = (meeting.start - now).total_seconds() / 60.0
            leave_in = minutes_until - eta_min - LEAVE_BUFFER_MIN
            if leave_in <= LEAVE_WINDOW_MIN:
                when = "now" if leave_in <= 0 else f"in {max(1, round(leave_in))} min"
                severity = "danger" if leave_in <= 0 else "warning" if leave_in <= 20 else "info"
                alerts.append(
                    {
                        "id": "leave_soon",
                        "severity": severity,
                        "title": "Leave soon" if leave_in > 0 else "Leave now",
                        "message": (
                            f"Leave {when} for {meeting.title} at {meeting.location} "
                            f"({round(eta_min)} min drive)."
                        ),
                        "action": "Get me to my next meeting",
                    }
                )

    soc = sim.get_soc()
    if soc < LOW_BATTERY_PERCENT:
        alerts.append(
            {
                "id": "low_battery",
                "severity": "danger",
                "title": "Low battery",
                "message": f"Battery is at {soc}% ({sim.range_km()} km range). Plan a charging stop.",
                "action": "Do I have enough battery for the airport?",
            }
        )

    gap = abs(sim.cabin_temp_c - sim.target_temp_c)
    if gap > CABIN_GAP_C:
        alerts.append(
            {
                "id": "cabin_temp",
                "severity": "info",
                "title": "Cabin still adjusting",
                "message": (
                    f"Cabin is {sim.get_cabin_temperature()}°C, "
                    f"target {round(sim.target_temp_c, 1)}°C."
                ),
                "action": None,
            }
        )

    if sim.trip and sim.driving and sim.trip_elapsed_min() > LONG_DRIVE_MIN:
        alerts.append(
            {
                "id": "long_drive",
                "severity": "warning",
                "title": "Time for a break",
                "message": (
                    f"You've been driving {round(sim.trip_elapsed_min())} minutes. "
                    "Consider a short stop."
                ),
                "action": None,
            }
        )

    hour = now.hour
    if sim.driving and (hour >= 22 or hour < 5):
        alerts.append(
            {
                "id": "late_night",
                "severity": "warning",
                "title": "Late-night drive",
                "message": "It's late — watch for fatigue.",
                "action": None,
            }
        )

    return alerts


def cockpit_payload() -> dict:
    """Vehicle state plus live alerts — what the dashboard websocket sends."""
    payload = get_simulator().state()
    payload["alerts"] = evaluate_alerts()
    return payload
