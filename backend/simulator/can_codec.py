"""Encode/decode cabin signals as 8-byte CAN payloads (mini-DBC)."""

from __future__ import annotations

import json
import struct
from pathlib import Path

MAP_PATH = Path(__file__).resolve().parent / "can_map.json"


def load_can_map() -> dict:
    return json.loads(MAP_PATH.read_text())


def _spec(name: str) -> dict:
    signals = load_can_map()["signals"]
    if name not in signals:
        raise KeyError(f"Unknown CAN signal: {name}")
    return signals[name]


def encode_signal(name: str, value: float | dict) -> tuple[int, bytes]:
    spec = _spec(name)
    kind = spec["kind"]
    if kind == "float":
        raw = int(round(float(value) / spec["scale"]))
        payload = struct.pack("<h", max(-32768, min(32767, raw))) + bytes(6)
    elif kind == "latlon":
        loc = value if isinstance(value, dict) else {"lat": 0.0, "lon": 0.0}
        payload = struct.pack(
            "<ii",
            int(round(float(loc["lat"]) * 1_000_000)),
            int(round(float(loc["lon"]) * 1_000_000)),
        )
    else:
        raise ValueError(f"Unsupported kind: {kind}")
    return spec["id"], payload


def decode_signal(name: str, payload: bytes) -> float | dict:
    spec = _spec(name)
    kind = spec["kind"]
    if kind == "float":
        (raw,) = struct.unpack_from("<h", payload)
        return round(raw * spec["scale"], 1)
    if kind == "latlon":
        lat_raw, lon_raw = struct.unpack_from("<ii", payload)
        return {"lat": round(lat_raw / 1_000_000, 6), "lon": round(lon_raw / 1_000_000, 6)}
    raise ValueError(f"Unsupported kind: {kind}")


def signal_for_id(arbitration_id: int) -> str | None:
    for name, spec in load_can_map()["signals"].items():
        if spec["id"] == arbitration_id:
            return name
    return None


def is_writable(name: str) -> bool:
    return bool(_spec(name).get("writable"))
