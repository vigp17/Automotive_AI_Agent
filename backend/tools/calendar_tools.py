"""Calendar tools over the JSON-backed local store."""

from __future__ import annotations

import json

from langchain_core.tools import tool

from services.calendar_store import get_calendar_store


@tool
def get_next_meeting() -> str:
    """Get the driver's next upcoming meeting (title, time, location)."""
    meeting = get_calendar_store().next_meeting()
    if meeting is None:
        return json.dumps({"next_meeting": None})
    return json.dumps({"next_meeting": meeting.to_dict()})


@tool
def list_meetings() -> str:
    """List all upcoming meetings on the driver's calendar."""
    meetings = [m.to_dict() for m in get_calendar_store().list_meetings()]
    return json.dumps({"meetings": meetings, "count": len(meetings)})
