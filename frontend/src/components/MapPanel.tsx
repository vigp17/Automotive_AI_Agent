import { useEffect } from "react";
import { CircleMarker, MapContainer, Polyline, TileLayer, Tooltip, useMap } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import { VehicleState } from "../api";

// Free dark basemap (no API key), matches the cockpit theme.
const TILE_URL = "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png";
const TILE_ATTRIBUTION =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>';

/** Keeps the vehicle in view as it moves without fighting the user's zoom. */
function FollowVehicle({ lat, lon, driving }: { lat: number; lon: number; driving: boolean }) {
  const map = useMap();
  useEffect(() => {
    if (!driving) return;
    if (!map.getBounds().pad(-0.2).contains([lat, lon])) {
      map.panTo([lat, lon], { animate: true });
    }
  }, [map, lat, lon, driving]);
  return null;
}

/** Zooms to fit the route once when a new trip starts. */
function FitRoute({ routeKey, route }: { routeKey: string; route: [number, number][] }) {
  const map = useMap();
  useEffect(() => {
    if (route.length > 1) {
      map.fitBounds(route, { padding: [40, 40] });
    }
  }, [map, routeKey]);
  return null;
}

export default function MapPanel({ state }: { state: VehicleState | null }) {
  if (!state) {
    return <div className="map-panel loading">Loading map...</div>;
  }

  const { lat, lon } = state.location;
  const route = state.trip?.route ?? [];
  const fullPath: [number, number][] = route.length ? [[lat, lon], ...route] : [];
  const destination = route.length ? route[route.length - 1] : null;

  return (
    <div className="map-panel">
      <MapContainer
        center={[lat, lon]}
        zoom={12}
        className="map-container"
        zoomControl={false}
        attributionControl={false}
      >
        <TileLayer url={TILE_URL} attribution={TILE_ATTRIBUTION} />
        {fullPath.length > 1 && (
          <Polyline
            positions={fullPath}
            pathOptions={{ color: "#4fc3f7", weight: 4, opacity: 0.85, dashArray: "1 8", lineCap: "round" }}
          />
        )}
        {destination && state.trip && (
          <CircleMarker
            center={destination}
            radius={8}
            pathOptions={{ color: "#7c6cf7", fillColor: "#7c6cf7", fillOpacity: 0.9 }}
          >
            <Tooltip direction="top" offset={[0, -8]} permanent>
              {state.trip.destination}
            </Tooltip>
          </CircleMarker>
        )}
        <CircleMarker
          center={[lat, lon]}
          radius={9}
          pathOptions={{ color: "#38d39f", fillColor: "#38d39f", fillOpacity: 1, weight: 6, opacity: 0.25 }}
        >
          <Tooltip direction="top" offset={[0, -8]}>
            {state.driving ? `${state.speed_kph.toFixed(0)} km/h` : "Parked"}
          </Tooltip>
        </CircleMarker>
        <FollowVehicle lat={lat} lon={lon} driving={state.driving} />
        <FitRoute routeKey={state.trip?.destination ?? ""} route={route} />
      </MapContainer>
      <div className="map-overlay">
        {state.trip?.active
          ? `En route to ${state.trip.destination}`
          : state.trip
            ? `Arrived - ${state.trip.destination}`
            : "No active trip"}
      </div>
    </div>
  );
}
