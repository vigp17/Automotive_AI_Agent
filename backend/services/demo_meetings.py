"""Local sample meetings so the trip-planning demo works when Outlook is empty."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from app.config import DATA_DIR
from services.calendar_store import Meeting

DEMO_FILE = DATA_DIR / "demo_meetings.json"

_DEFAULT = {
    "title": "Design Review",
    "location": "Bellevue Office",
    "lat": 47.6101,
    "lon": -122.2015,
    "duration_min": 60,
    "offset_hours": 2,
}

_meetings: list[Meeting] | None = None


def reset_demo_meetings() -> None:
    global _meetings
    _meetings = None


def _parse_start(raw: str) -> datetime:
    return datetime.fromisoformat(raw)


def _load() -> list[Meeting]:
    global _meetings
    if _meetings is not None:
        return _meetings
    loaded: list[Meeting] = []
    path = Path(DEMO_FILE)
    if path.exists():
        raw = json.loads(path.read_text())
        for entry in raw:
            loaded.append(
                Meeting(
                    title=entry["title"],
                    location=entry["location"],
                    lat=float(entry["lat"]),
                    lon=float(entry["lon"]),
                    start=_parse_start(entry["start"]),
                    duration_min=int(entry.get("duration_min", 60)),
                )
            )
    _meetings = loaded
    return _meetings


def _save(meetings: list[Meeting]) -> None:
    Path(DEMO_FILE).write_text(
        json.dumps(
            [
                {
                    "title": meeting.title,
                    "location": meeting.location,
                    "lat": meeting.lat,
                    "lon": meeting.lon,
                    "start": meeting.start.isoformat(timespec="minutes"),
                    "duration_min": meeting.duration_min,
                }
                for meeting in meetings
            ],
            indent=2,
        )
        + "\n"
    )


def list_demo_meetings() -> list[Meeting]:
    now = datetime.now()
    return [meeting for meeting in _load() if meeting.start >= now]


def add_demo_meeting() -> Meeting:
    existing = list_demo_meetings()
    if existing:
        return existing[0]
    start = datetime.now().replace(second=0, microsecond=0) + timedelta(
        hours=_DEFAULT["offset_hours"]
    )
    meeting = Meeting(
        title=_DEFAULT["title"],
        location=_DEFAULT["location"],
        lat=_DEFAULT["lat"],
        lon=_DEFAULT["lon"],
        start=start,
        duration_min=_DEFAULT["duration_min"],
    )
    meetings = _load()
    meetings.append(meeting)
    global _meetings
    _meetings = meetings
    _save(meetings)
    return meeting


def clear_demo_meetings() -> None:
    path = Path(DEMO_FILE)
    if path.exists():
        path.unlink()
    reset_demo_meetings()


def merge_meetings(base: list[Meeting]) -> list[Meeting]:
    now = datetime.now()
    merged = [meeting for meeting in [*base, *list_demo_meetings()] if meeting.start >= now]
    merged.sort(key=lambda meeting: meeting.start)
    return merged
