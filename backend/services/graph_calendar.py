"""Outlook calendar via Microsoft Graph, falling back to the JSON seed."""

from __future__ import annotations

from datetime import datetime, timedelta

import httpx

from services.calendar_store import CalendarStore, Meeting
from services.graph_auth import get_graph_token
from services.maps import lookup_place

GRAPH = "https://graph.microsoft.com/v1.0"


def parse_graph_datetime(block: dict) -> datetime:
    raw = str(block.get("dateTime") or "")
    raw = raw.replace("Z", "+00:00")
    if raw.endswith("0000000") and "." in raw:
        raw = raw.split(".")[0]
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is not None:
        dt = dt.astimezone().replace(tzinfo=None)
    return dt


def meeting_from_graph(event: dict) -> Meeting | None:
    subject = (event.get("subject") or "Meeting").strip()
    start_block = event.get("start") or {}
    end_block = event.get("end") or {}
    try:
        start = parse_graph_datetime(start_block)
        end = parse_graph_datetime(end_block) if end_block.get("dateTime") else start + timedelta(minutes=30)
    except ValueError:
        return None
    loc = event.get("location") or {}
    location = (loc.get("displayName") or loc.get("locationUri") or "Teams").strip() or "Teams"
    coords = lookup_place(location) or (47.6062, -122.3321)
    duration = max(15, int((end - start).total_seconds() // 60) or 30)
    return Meeting(
        title=subject,
        location=location,
        lat=coords[0],
        lon=coords[1],
        start=start,
        duration_min=duration,
    )


class GraphCalendarStore:
    """Reads the signed-in user's Outlook calendar. Falls back to JSON seed
    when no Graph token is present so the demo still has meetings."""

    def __init__(self) -> None:
        self._fallback = CalendarStore()

    def list_meetings(self) -> list[Meeting]:
        token = get_graph_token()
        if not token:
            return self._fallback.list_meetings()
        now = datetime.now().replace(microsecond=0)
        end = now + timedelta(days=7)
        try:
            with httpx.Client(timeout=15) as client:
                resp = client.get(
                    f"{GRAPH}/me/calendarView",
                    headers={"Authorization": f"Bearer {token}", "Prefer": 'outlook.timezone="UTC"'},
                    params={
                        "startDateTime": now.isoformat(),
                        "endDateTime": end.isoformat(),
                        "$select": "subject,start,end,location",
                        "$orderby": "start/dateTime",
                        "$top": 20,
                    },
                )
                resp.raise_for_status()
        except httpx.HTTPError:
            return self._fallback.list_meetings()
        meetings = []
        for event in resp.json().get("value") or []:
            meeting = meeting_from_graph(event)
            if meeting and meeting.start >= now:
                meetings.append(meeting)
        return meetings

    def next_meeting(self) -> Meeting | None:
        upcoming = self.list_meetings()
        return upcoming[0] if upcoming else None
