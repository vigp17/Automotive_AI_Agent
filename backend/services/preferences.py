"""Persisted driver preferences: home, work, and default cabin temperature."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from app.config import DATA_DIR

DEFAULTS_FILE = DATA_DIR / "preferences.json"

_HOME_ALIASES = ("home", "house", "my place")
_WORK_ALIASES = ("work", "office")


@dataclass
class SavedPlace:
    label: str
    query: str


@dataclass
class DriverPreferences:
    driver_name: str
    default_temp_c: float
    home: SavedPlace
    work: SavedPlace

    def to_dict(self) -> dict:
        return asdict(self)


_path: Path = DEFAULTS_FILE
_store: DriverPreferences | None = None


def _defaults() -> DriverPreferences:
    return DriverPreferences(
        driver_name="Alex",
        default_temp_c=21.0,
        home=SavedPlace(label="Home", query="home"),
        work=SavedPlace(label="Work", query="office"),
    )


def _from_dict(raw: dict) -> DriverPreferences:
    home = raw.get("home") or {}
    work = raw.get("work") or {}
    return DriverPreferences(
        driver_name=str(raw.get("driver_name") or "Alex"),
        default_temp_c=float(raw.get("default_temp_c") or 21.0),
        home=SavedPlace(
            label=str(home.get("label") or "Home"),
            query=str(home.get("query") or "home"),
        ),
        work=SavedPlace(
            label=str(work.get("label") or "Work"),
            query=str(work.get("query") or "office"),
        ),
    )


def reset_preferences(path: Path | None = None) -> DriverPreferences:
    global _path, _store
    _path = path or DEFAULTS_FILE
    _store = None
    return get_preferences()


def get_preferences() -> DriverPreferences:
    global _store
    if _store is None:
        if _path.exists():
            _store = _from_dict(json.loads(_path.read_text()))
        else:
            _store = _defaults()
    return _store


def save_preferences(prefs: DriverPreferences) -> DriverPreferences:
    global _store
    _path.parent.mkdir(parents=True, exist_ok=True)
    _path.write_text(json.dumps(prefs.to_dict(), indent=2) + "\n")
    _store = prefs
    return prefs


def update_preferences(
    *,
    driver_name: str | None = None,
    default_temp_c: float | None = None,
    home_query: str | None = None,
    home_label: str | None = None,
    work_query: str | None = None,
    work_label: str | None = None,
) -> DriverPreferences:
    current = get_preferences()
    home = SavedPlace(
        label=(home_label or current.home.label).strip() or current.home.label,
        query=(home_query or current.home.query).strip() or current.home.query,
    )
    work = SavedPlace(
        label=(work_label or current.work.label).strip() or current.work.label,
        query=(work_query or current.work.query).strip() or current.work.query,
    )
    temp = current.default_temp_c if default_temp_c is None else float(default_temp_c)
    temp = max(16.0, min(30.0, temp))
    updated = DriverPreferences(
        driver_name=(driver_name if driver_name is not None else current.driver_name).strip()
        or current.driver_name,
        default_temp_c=temp,
        home=home,
        work=work,
    )
    return save_preferences(updated)


def resolve_place(destination: str) -> tuple[str, str]:
    """Map 'home' / 'work' to the saved geocode query and display label."""
    key = destination.strip().lower()
    prefs = get_preferences()
    if key in _HOME_ALIASES or key.startswith("my home"):
        return prefs.home.query, prefs.home.label
    if key in _WORK_ALIASES or key.startswith("my work"):
        return prefs.work.query, prefs.work.label
    return destination, destination
