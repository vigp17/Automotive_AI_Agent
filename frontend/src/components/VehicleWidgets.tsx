import { useState } from "react";
import { setTemperature, VehicleState } from "../api";

function BatteryWidget({ state }: { state: VehicleState }) {
  const soc = state.soc_percent;
  const level = soc < 15 ? "low" : soc < 40 ? "mid" : "high";
  return (
    <div className="widget">
      <div className="widget-title">Battery</div>
      <div className="widget-value">
        {soc.toFixed(0)}<span className="unit">%</span>
      </div>
      <div className="battery-bar">
        <div className={`battery-fill ${level}`} style={{ width: `${soc}%` }} />
      </div>
      <div className="widget-sub">{state.range_km.toFixed(0)} km range</div>
    </div>
  );
}

function SpeedWidget({ state }: { state: VehicleState }) {
  return (
    <div className="widget">
      <div className="widget-title">Speed</div>
      <div className="widget-value">
        {state.speed_kph.toFixed(0)}
        <span className="unit">km/h</span>
      </div>
      <div className="widget-sub">
        {state.driving ? "driving" : "parked"} - odo {state.odometer_km.toFixed(0)} km
      </div>
    </div>
  );
}

function ClimateWidget({ state }: { state: VehicleState }) {
  const [pending, setPending] = useState<number | null>(null);
  const target = pending ?? state.target_temp_c;

  const adjust = async (delta: number) => {
    const next = Math.min(30, Math.max(16, target + delta));
    setPending(next);
    await setTemperature(next);
    setTimeout(() => setPending(null), 1500);
  };

  return (
    <div className="widget">
      <div className="widget-title">Climate</div>
      <div className="climate-row">
        <button className="temp-btn" onClick={() => adjust(-1)} aria-label="cooler">
          -
        </button>
        <div className="widget-value">
          {state.cabin_temp_c.toFixed(1)}
          <span className="unit">°C</span>
        </div>
        <button className="temp-btn" onClick={() => adjust(1)} aria-label="warmer">
          +
        </button>
      </div>
      <div className="widget-sub">
        target {target.toFixed(1)}°C - outside {state.outside_temp_c.toFixed(0)}°C
      </div>
    </div>
  );
}

function TripWidget({ state }: { state: VehicleState }) {
  const trip = state.trip;
  return (
    <div className="widget">
      <div className="widget-title">Trip</div>
      {trip ? (
        <>
          <div className="trip-dest">{trip.destination}</div>
          {trip.progress !== null && (
            <div className="battery-bar">
              <div className="battery-fill high" style={{ width: `${trip.progress * 100}%` }} />
            </div>
          )}
          <div className="widget-sub">
            {trip.distance_km ? `${trip.distance_km} km` : ""}
            {trip.eta_min ? ` - ETA ${Math.round(trip.eta_min)} min` : ""}
            {trip.traffic_delay_min
              ? ` - ${trip.traffic_delay_min} min traffic`
              : ""}
            {` - ${trip.active ? "en route" : "arrived"}`}
          </div>
        </>
      ) : (
        <div className="widget-sub">
          No active trip. Try "navigate to the airport".
        </div>
      )}
      <div className="widget-sub dim">
        {state.location.lat.toFixed(4)}, {state.location.lon.toFixed(4)}
      </div>
    </div>
  );
}

export default function VehicleWidgets({ state }: { state: VehicleState | null }) {
  if (!state) {
    return <div className="widgets loading">Connecting to vehicle...</div>;
  }
  return (
    <div className="widgets">
      <BatteryWidget state={state} />
      <SpeedWidget state={state} />
      <ClimateWidget state={state} />
      <TripWidget state={state} />
    </div>
  );
}
