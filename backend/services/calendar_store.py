"""JSON-backed calendar store, with an Outlook/Graph option.

Seed entries in data/calendar.json use offset_hours from process start so demo
meetings are always in the near future. Set CALENDAR_BACKEND=graph to read the
signed-in Outlook calendar (falls back to this seed until you connect).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.config import DATA_DIR

CALENDAR_FILE = DATA_DIR / "calendar.json"


@dataclass
class Meeting:
    title: str
    location: str
    lat: float
    lon: float
    start: datetime
    duration_min: int

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "location": self.location,
            "lat": self.lat,
            "lon": self.lon,
            "start": self.start.isoformat(timespec="minutes"),
            "start_display": self.start.strftime("%a %I:%M %p").replace(" 0", " "),
            "duration_min": self.duration_min,
        }


class CalendarStore:
    def __init__(self) -> None:
        self.meetings: list[Meeting] = []
        self._load()

    def _load(self) -> None:
        base = datetime.now().replace(second=0, microsecond=0)
        raw = json.loads(CALENDAR_FILE.read_text()) if CALENDAR_FILE.exists() else []
        for entry in raw:
            self.meetings.append(
                Meeting(
                    title=entry["title"],
                    location=entry["location"],
                    lat=entry["lat"],
                    lon=entry["lon"],
                    start=base + timedelta(hours=entry["offset_hours"]),
                    duration_min=entry.get("duration_min", 30),
                )
            )
        self.meetings.sort(key=lambda m: m.start)

    def next_meeting(self) -> Meeting | None:
        upcoming = self.list_meetings()
        return upcoming[0] if upcoming else None

    def list_meetings(self) -> list[Meeting]:
        from services.demo_meetings import merge_meetings

        return merge_meetings(self.meetings)


_store: CalendarStore | GraphCalendarStore | None = None


def reset_calendar_store() -> None:
    global _store
    _store = None


def get_calendar_store():
    """JSON seed, or Outlook via Graph when CALENDAR_BACKEND=graph."""
    global _store
    if _store is None:
        from app.config import get_settings

        if get_settings().calendar_backend.lower().strip() == "graph":
            from services.graph_calendar import GraphCalendarStore

            _store = GraphCalendarStore()
        else:
            _store = CalendarStore()
    return _store
