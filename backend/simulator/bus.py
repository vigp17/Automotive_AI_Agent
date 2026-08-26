"""VehicleBus abstraction (blueprint Phase 5 seam).

Signal-level read/write interface so a real CAN adapter (python-can, someday
actual vehicle hardware) can replace the simulator without touching agents or
tools. Tools read/write named signals; richer trip operations stay on the
simulator itself.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from simulator.vehicle import VehicleSimulator, get_simulator


class VehicleBus(ABC):
    @abstractmethod
    def read_signal(self, name: str) -> float | dict:
        ...

    @abstractmethod
    def write_signal(self, name: str, value: float) -> float:
        ...


class SimulatedBus(VehicleBus):
    """Maps canonical signal names onto the in-process simulator."""

    def __init__(self, sim: VehicleSimulator) -> None:
        self.sim = sim

    def read_signal(self, name: str) -> float | dict:
        readers = {
            "battery.soc": self.sim.get_soc,
            "battery.range_km": self.sim.range_km,
            "vehicle.speed_kph": self.sim.get_speed,
            "vehicle.location": self.sim.get_location,
            "hvac.cabin_temp_c": self.sim.get_cabin_temperature,
            "hvac.target_temp_c": lambda: round(self.sim.target_temp_c, 1),
        }
        if name not in readers:
            raise KeyError(f"Unknown signal: {name}")
        return readers[name]()

    def write_signal(self, name: str, value: float) -> float:
        if name == "hvac.target_temp_c":
            return self.sim.set_temperature(value)
        raise KeyError(f"Signal not writable: {name}")


def get_bus() -> VehicleBus:
    # Constructed on demand so it always wraps the current simulator instance
    # (the simulator singleton can be replaced, e.g. in tests).
    return SimulatedBus(get_simulator())
