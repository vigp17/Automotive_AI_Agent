"""Virtual CAN bridge: publish simulator signals, apply HVAC writes.

Uses python-can's in-process `virtual` interface (no hardware, works on macOS).
A listener thread decodes incoming frames into a cache that CanBus reads.
"""

from __future__ import annotations

import threading
import time
from collections import deque

import can

from simulator.can_codec import (
    decode_signal,
    encode_signal,
    is_writable,
    load_can_map,
    signal_for_id,
)
from simulator.vehicle import VehicleSimulator, get_simulator

_CHANNEL = load_can_map()["channel"]
_INTERFACE = load_can_map()["interface"]


class CanBridge:
    def __init__(self, sim: VehicleSimulator | None = None, channel: str | None = None) -> None:
        self.sim = sim or get_simulator()
        self.channel = channel or _CHANNEL
        self.cache: dict[str, float | dict] = {}
        self.frames: deque[dict] = deque(maxlen=20)
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._tx = can.Bus(interface=_INTERFACE, channel=self.channel)
        self._rx = can.Bus(interface=_INTERFACE, channel=self.channel)
        self._thread = threading.Thread(target=self._listen, daemon=True, name="can-listener")
        self._thread.start()

    def close(self) -> None:
        self._stop.set()
        self._thread.join(timeout=1.0)
        self._tx.shutdown()
        self._rx.shutdown()

    def _listen(self) -> None:
        while not self._stop.is_set():
            msg = self._rx.recv(timeout=0.1)
            if msg is None:
                continue
            name = signal_for_id(msg.arbitration_id)
            if name is None:
                continue
            value = decode_signal(name, bytes(msg.data))
            with self._lock:
                self.cache[name] = value
                self.frames.append(
                    {
                        "ts": time.time(),
                        "arbitration_id": hex(msg.arbitration_id),
                        "data": bytes(msg.data).hex(),
                        "signal": name,
                    }
                )
            if is_writable(name) and name == "hvac.target_temp_c":
                self.sim.set_temperature(float(value))

    def send(self, name: str, value: float | dict) -> None:
        arb_id, payload = encode_signal(name, value)
        self._tx.send(can.Message(arbitration_id=arb_id, data=payload, is_extended_id=False))

    def publish_state(self) -> None:
        self.send("battery.soc", self.sim.get_soc())
        self.send("battery.range_km", self.sim.range_km())
        self.send("vehicle.speed_kph", self.sim.get_speed())
        self.send("vehicle.location", self.sim.get_location())
        self.send("hvac.cabin_temp_c", self.sim.get_cabin_temperature())
        self.send("hvac.target_temp_c", round(self.sim.target_temp_c, 1))

    def wait_for(self, name: str, timeout: float = 1.0, expected=None) -> float | dict:
        deadline = time.time() + timeout
        while time.time() < deadline:
            with self._lock:
                if name in self.cache and (expected is None or self.cache[name] == expected):
                    return self.cache[name]
            time.sleep(0.01)
        raise TimeoutError(f"No CAN frame for {name}")

    def recent_frames(self) -> list[dict]:
        with self._lock:
            return list(self.frames)


_bridge: CanBridge | None = None


def get_bridge() -> CanBridge:
    global _bridge
    if _bridge is None:
        _bridge = CanBridge()
    return _bridge


def start_bridge(sim: VehicleSimulator | None = None) -> CanBridge:
    global _bridge
    if _bridge is not None:
        _bridge.close()
    _bridge = CanBridge(sim=sim or get_simulator())
    return _bridge


def stop_bridge() -> None:
    global _bridge
    if _bridge is not None:
        _bridge.close()
        _bridge = None


def publish_vehicle_frames() -> None:
    if _bridge is not None:
        _bridge.publish_state()
