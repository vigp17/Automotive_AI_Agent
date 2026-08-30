"""VehicleBus abstraction (blueprint Phase 5 seam).

Signal-level read/write interface. `VEHICLE_BUS=sim` (default) reads the
in-process simulator. `VEHICLE_BUS=can` encodes those signals as CAN frames
on a python-can virtual bus — same agent tools, different transport.
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


class CanBus(VehicleBus):
    """Reads/writes via the virtual CAN bridge (encode → bus → decode)."""

    def __init__(self, bridge) -> None:
        self.bridge = bridge

    def read_signal(self, name: str) -> float | dict:
        if name not in self.bridge.cache:
            self.bridge.publish_state()
        return self.bridge.wait_for(name)

    def write_signal(self, name: str, value: float) -> float:
        from simulator.can_codec import decode_signal, encode_signal, is_writable

        if not is_writable(name):
            raise KeyError(f"Signal not writable: {name}")
        encoded = encode_signal(name, value)
        expected = decode_signal(name, encoded[1])
        self.bridge.send(name, value)
        decoded = self.bridge.wait_for(name, expected=expected)
        return float(decoded)


def can_mode() -> bool:
    from app.config import get_settings

    return get_settings().vehicle_bus.lower() == "can"


def get_bus() -> VehicleBus:
    if can_mode():
        from simulator.can_bridge import get_bridge

        return CanBus(get_bridge())
    return SimulatedBus(get_simulator())


def publish_vehicle_frames() -> None:
    if not can_mode():
        return
    from simulator.can_bridge import publish_vehicle_frames as _publish

    _publish()
