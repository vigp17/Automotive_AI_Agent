from simulator.bus import SimulatedBus
from simulator.vehicle import VehicleSimulator, haversine_km


def make_sim() -> VehicleSimulator:
    return VehicleSimulator()


def test_temperature_clamped():
    sim = make_sim()
    assert sim.set_temperature(50) == 30.0
    assert sim.set_temperature(5) == 16.0
    assert sim.set_temperature(21.5) == 21.5


def test_cabin_temp_drifts_toward_target():
    sim = make_sim()
    sim.cabin_temp_c = 18.0
    sim.set_temperature(24.0)
    for _ in range(60):
        sim.tick(1.0)
    assert sim.cabin_temp_c > 18.0


def test_driving_drains_soc_and_moves_vehicle():
    sim = make_sim()
    start_soc = sim.soc
    start = (sim.lat, sim.lon)
    dest = (sim.lat + 0.2, sim.lon + 0.2)
    sim.set_route([dest], destination="test", distance_km=30.0)
    for _ in range(600):
        sim.tick(1.0)
    assert sim.soc < start_soc
    assert haversine_km(start[0], start[1], sim.lat, sim.lon) > 0.5
    assert sim.odometer_km > 18452.0


def test_trip_completes_and_stops():
    sim = make_sim()
    dest = (sim.lat + 0.001, sim.lon)  # ~110 m away
    sim.set_route([dest], destination="close by")
    for _ in range(120):
        sim.tick(1.0)
    assert not sim.driving
    assert sim.speed_kph == 0.0


def test_range_reflects_soc():
    sim = make_sim()
    sim.soc = 100.0
    full = sim.range_km()
    sim.soc = 50.0
    assert sim.range_km() < full
    sim.soc = 5.0  # below reserve
    assert sim.range_km() == 0.0


def test_bus_signals():
    sim = make_sim()
    bus = SimulatedBus(sim)
    assert bus.read_signal("battery.soc") == sim.get_soc()
    assert bus.write_signal("hvac.target_temp_c", 25.0) == 25.0
    assert bus.read_signal("hvac.target_temp_c") == 25.0
