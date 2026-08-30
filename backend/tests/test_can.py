from simulator.bus import CanBus
from simulator.can_bridge import CanBridge
from simulator.can_codec import decode_signal, encode_signal
from simulator.vehicle import get_simulator


def test_codec_soc_roundtrip():
    arb_id, payload = encode_signal("battery.soc", 78.0)
    assert arb_id == 256
    assert decode_signal("battery.soc", payload) == 78.0


def test_codec_location_roundtrip():
    loc = {"lat": 47.6062, "lon": -122.3321}
    arb_id, payload = encode_signal("vehicle.location", loc)
    assert arb_id == 259
    decoded = decode_signal("vehicle.location", payload)
    assert decoded["lat"] == loc["lat"]
    assert decoded["lon"] == loc["lon"]


def test_codec_hvac_writable():
    from simulator.can_codec import is_writable

    assert is_writable("hvac.target_temp_c")
    assert not is_writable("battery.soc")


def test_virtual_can_hvac_write_updates_simulator():
    sim = get_simulator()
    bridge = CanBridge(sim=sim, channel="test-hvac")
    try:
        bus = CanBus(bridge)
        applied = bus.write_signal("hvac.target_temp_c", 22.0)
        assert applied == 22.0
        assert sim.target_temp_c == 22.0
    finally:
        bridge.close()


def test_virtual_can_read_after_publish():
    sim = get_simulator()
    sim.soc = 64.0
    bridge = CanBridge(sim=sim, channel="test-read")
    try:
        bus = CanBus(bridge)
        assert bus.read_signal("battery.soc") == 64.0
        loc = bus.read_signal("vehicle.location")
        assert loc["lat"] == sim.get_location()["lat"]
    finally:
        bridge.close()


def test_can_frames_logged():
    sim = get_simulator()
    bridge = CanBridge(sim=sim, channel="test-log")
    try:
        CanBus(bridge).write_signal("hvac.target_temp_c", 19.0)
        frames = bridge.recent_frames()
        assert any(f["signal"] == "hvac.target_temp_c" and f["arbitration_id"] == "0x3a1" for f in frames)
    finally:
        bridge.close()


def test_vehicle_can_endpoint_disabled_in_sim_mode(client):
    resp = client.get("/vehicle/can")
    assert resp.status_code == 200
    assert resp.json() == {"enabled": False, "frames": []}
