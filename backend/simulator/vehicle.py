"""Stateful vehicle simulator: battery, motion, climate and trip state.

This is the stand-in for real vehicle data (blueprint Phase 1). All signal
access from the rest of the app goes through this module (or the VehicleBus
wrapper in simulator/bus.py) so a CAN adapter can replace it later.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from threading import Lock

# Energy model constants
BATTERY_CAPACITY_KWH = 75.0
BASE_CONSUMPTION_KWH_PER_KM = 0.16
HVAC_LOAD_KW = 1.5  # extra draw while cabin temp is being pushed to target
SOC_RESERVE_PERCENT = 10.0  # never plan a trip below this

MIN_CABIN_TEMP = 16.0
MAX_CABIN_TEMP = 30.0

EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlam / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


@dataclass
class TripInfo:
    destination: str
    started_at: float
    start_odometer_km: float
    start_soc: float
    route: list[tuple[float, float]] = field(default_factory=list)
    route_index: int = 0
    eta_min: float | None = None
    distance_km: float | None = None
    traffic_delay_min: float | None = None


class VehicleSimulator:
    """Simple physics: cruise toward the next route point, drain SOC with
    distance plus HVAC load, and drift cabin temperature toward the target."""

    def __init__(self) -> None:
        self._lock = Lock()
        # Start parked in downtown Seattle
        self.lat = 47.6062
        self.lon = -122.3321
        self.soc = 78.0
        self.speed_kph = 0.0
        self.cruise_kph = 60.0
        self.cabin_temp_c = 21.0
        self.target_temp_c = 21.0
        self.outside_temp_c = 12.0
        self.odometer_km = 18452.0
        self.driving = False
        self.trip: TripInfo | None = None
        self._sim_time = time.time()

    # ------------------------------------------------------------------
    # Signal getters/setters (blueprint Phase 1 API surface)
    # ------------------------------------------------------------------
    def get_soc(self) -> float:
        return round(self.soc, 1)

    def get_speed(self) -> float:
        return round(self.speed_kph, 1)

    def get_location(self) -> dict:
        return {"lat": round(self.lat, 6), "lon": round(self.lon, 6)}

    def get_cabin_temperature(self) -> float:
        return round(self.cabin_temp_c, 1)

    def set_temperature(self, celsius: float) -> float:
        with self._lock:
            self.target_temp_c = max(MIN_CABIN_TEMP, min(MAX_CABIN_TEMP, float(celsius)))
            return self.target_temp_c

    def range_km(self) -> float:
        usable_kwh = max(self.soc - SOC_RESERVE_PERCENT, 0.0) / 100.0 * BATTERY_CAPACITY_KWH
        return round(usable_kwh / BASE_CONSUMPTION_KWH_PER_KM, 1)

    # ------------------------------------------------------------------
    # Trip control
    # ------------------------------------------------------------------
    def set_route(
        self,
        points: list[tuple[float, float]],
        destination: str,
        eta_min: float | None = None,
        distance_km: float | None = None,
        traffic_delay_min: float | None = None,
    ) -> None:
        with self._lock:
            self.trip = TripInfo(
                destination=destination,
                started_at=time.time(),
                start_odometer_km=self.odometer_km,
                start_soc=self.soc,
                route=list(points),
                eta_min=eta_min,
                distance_km=distance_km,
                traffic_delay_min=traffic_delay_min,
            )
            self.driving = True

    def stop_trip(self) -> None:
        with self._lock:
            self.driving = False
            self.speed_kph = 0.0

    def cancel_trip(self) -> dict:
        """Abort navigation: park immediately and clear the route."""
        with self._lock:
            destination = self.trip.destination if self.trip else None
            had_trip = self.trip is not None
            self.driving = False
            self.speed_kph = 0.0
            self.trip = None
            return {"cancelled": had_trip, "destination": destination}

    def trip_elapsed_min(self) -> float:
        if not self.trip:
            return 0.0
        return (time.time() - self.trip.started_at) / 60.0

    # ------------------------------------------------------------------
    # Physics tick
    # ------------------------------------------------------------------
    def tick(self, dt_s: float = 1.0) -> None:
        with self._lock:
            self._tick_climate(dt_s)
            if self.driving and self.trip and self.trip.route:
                self._tick_motion(dt_s)
            else:
                self.speed_kph = max(0.0, self.speed_kph - 20.0 * dt_s)

    def _tick_climate(self, dt_s: float) -> None:
        delta = self.target_temp_c - self.cabin_temp_c
        if abs(delta) > 0.05:
            # exponential approach, ~0.5 C per 10 s
            step = max(-0.06 * dt_s, min(0.06 * dt_s, delta * 0.02 * dt_s))
            # ensure some minimum progress so the cabin actually converges
            if abs(step) < 0.01 * dt_s:
                step = math.copysign(0.01 * dt_s, delta)
            self.cabin_temp_c += step
            hvac_kwh = HVAC_LOAD_KW * dt_s / 3600.0
            self.soc = max(0.0, self.soc - hvac_kwh / BATTERY_CAPACITY_KWH * 100.0)

    def _tick_motion(self, dt_s: float) -> None:
        assert self.trip is not None
        # accelerate toward cruise with a gentle oscillation for realism
        wobble = 5.0 * math.sin(time.time() / 20.0)
        target_speed = max(20.0, self.cruise_kph + wobble)
        if self.speed_kph < target_speed:
            self.speed_kph = min(target_speed, self.speed_kph + 8.0 * dt_s)
        else:
            self.speed_kph = max(target_speed, self.speed_kph - 8.0 * dt_s)

        remaining_km = self.speed_kph * dt_s / 3600.0
        while remaining_km > 0 and self.trip.route_index < len(self.trip.route):
            wp_lat, wp_lon = self.trip.route[self.trip.route_index]
            dist = haversine_km(self.lat, self.lon, wp_lat, wp_lon)
            if dist <= remaining_km or dist < 1e-4:
                self.lat, self.lon = wp_lat, wp_lon
                self.trip.route_index += 1
                travelled = dist
            else:
                frac = remaining_km / dist
                self.lat += (wp_lat - self.lat) * frac
                self.lon += (wp_lon - self.lon) * frac
                travelled = remaining_km
            remaining_km -= travelled
            self.odometer_km += travelled
            drain = travelled * BASE_CONSUMPTION_KWH_PER_KM / BATTERY_CAPACITY_KWH * 100.0
            self.soc = max(0.0, self.soc - drain)

        if self.trip.route_index >= len(self.trip.route):
            self.driving = False
            self.speed_kph = 0.0

    # ------------------------------------------------------------------
    def state(self) -> dict:
        trip = None
        if self.trip:
            trip = {
                "destination": self.trip.destination,
                "elapsed_min": round(self.trip_elapsed_min(), 1),
                "distance_km": self.trip.distance_km,
                "eta_min": self.trip.eta_min,
                "traffic_delay_min": self.trip.traffic_delay_min,
                "progress": (
                    round(self.trip.route_index / len(self.trip.route), 2)
                    if self.trip.route
                    else None
                ),
                "active": self.driving,
                # Waypoints for the dashboard map (routes are <= ~20 points)
                "route": [
                    [round(lat, 5), round(lon, 5)] for lat, lon in self.trip.route
                ],
            }
        return {
            "soc_percent": self.get_soc(),
            "range_km": self.range_km(),
            "speed_kph": self.get_speed(),
            "location": self.get_location(),
            "cabin_temp_c": self.get_cabin_temperature(),
            "target_temp_c": round(self.target_temp_c, 1),
            "outside_temp_c": round(self.outside_temp_c, 1),
            "odometer_km": round(self.odometer_km, 1),
            "driving": self.driving,
            "trip": trip,
        }


_simulator: VehicleSimulator | None = None


def get_simulator() -> VehicleSimulator:
    global _simulator
    if _simulator is None:
        _simulator = VehicleSimulator()
    return _simulator


def reset_simulator() -> VehicleSimulator:
    """Test helper: replace the singleton with a fresh instance."""
    global _simulator
    _simulator = VehicleSimulator()
    return _simulator
