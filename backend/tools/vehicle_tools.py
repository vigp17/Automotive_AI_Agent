"""Tools over the vehicle signals (via the VehicleBus abstraction)."""

from __future__ import annotations

import json

from langchain_core.tools import tool

from simulator.bus import get_bus
from services.preferences import get_preferences, update_preferences


@tool
def get_soc() -> str:
    """Get the EV battery state of charge (percent) and estimated range in km."""
    bus = get_bus()
    return json.dumps(
        {
            "soc_percent": bus.read_signal("battery.soc"),
            "range_km": bus.read_signal("battery.range_km"),
        }
    )


@tool
def get_speed() -> str:
    """Get the current vehicle speed in km/h."""
    return json.dumps({"speed_kph": get_bus().read_signal("vehicle.speed_kph")})


@tool
def get_location() -> str:
    """Get the current vehicle GPS location (latitude/longitude)."""
    return json.dumps({"location": get_bus().read_signal("vehicle.location")})


@tool
def get_cabin_temperature() -> str:
    """Get the current cabin temperature and the HVAC target temperature in Celsius."""
    bus = get_bus()
    return json.dumps(
        {
            "cabin_temp_c": bus.read_signal("hvac.cabin_temp_c"),
            "target_temp_c": bus.read_signal("hvac.target_temp_c"),
        }
    )


@tool
def set_temperature(celsius: float) -> str:
    """Set the cabin HVAC target temperature in Celsius (16-30)."""
    applied = get_bus().write_signal("hvac.target_temp_c", celsius)
    return json.dumps({"target_temp_c": applied, "status": "ok"})


@tool
def apply_preferred_temperature() -> str:
    """Set the cabin to the driver's saved default temperature."""
    prefs = get_preferences()
    applied = get_bus().write_signal("hvac.target_temp_c", prefs.default_temp_c)
    return json.dumps({"target_temp_c": applied, "preferred": True})


@tool
def set_preferred_temperature(celsius: float) -> str:
    """Save and apply the driver's default cabin temperature (16-30 C)."""
    prefs = update_preferences(default_temp_c=celsius)
    applied = get_bus().write_signal("hvac.target_temp_c", prefs.default_temp_c)
    return json.dumps({"target_temp_c": applied, "saved": True})
