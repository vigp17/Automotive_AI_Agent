import { useState } from "react";
import {
  CircleMarker,
  MapContainer,
  Polyline,
  Popup,
  TileLayer,
  Tooltip,
  useMap,
  useMapEvents,
} from "react-leaflet";
import { useEffect } from "react";
import "leaflet/dist/leaflet.css";
import { navigateTo, VehicleState } from "../api";

// OpenStreetMap tiles (keyless); a CSS invert filter (.dark-tiles) restyles
// them to match the dark cockpit theme. CARTO basemaps now watermark
// "API KEY REQUIRED" on keyless requests, so we avoid them.
const TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
const TILE_ATTRIBUTION =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';

// Quick destinations known to the geocoder (see backend KNOWN_PLACES).
const FAVORITES = ["Home", "Office", "Airport"];

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

/** Drops a pin where the user taps so they can confirm "Drive here". */
function TapPin({ onPin }: { onPin: (lat: number, lon: number) => void }) {
  useMapEvents({
    click: (e) => onPin(e.latlng.lat, e.latlng.lng),
  });
  return null;
}

export default function MapPanel({
  state,
  onPrompt,
}: {
  state: VehicleState | null;
  onPrompt?: (prompt: string) => void;
}) {
  const [pin, setPin] = useState<{ lat: number; lon: number } | null>(null);
  const [navBusy, setNavBusy] = useState(false);

  if (!state) {
    return <div className="map-panel loading">Loading map...</div>;
  }

  const { lat, lon } = state.location;
  const route = state.trip?.route ?? [];
  const fullPath: [number, number][] = route.length ? [[lat, lon], ...route] : [];
  const destination = route.length ? route[route.length - 1] : null;

  const driveToPin = async () => {
    if (!pin || navBusy) return;
    setNavBusy(true);
    try {
      await navigateTo(pin.lat, pin.lon, "Dropped pin");
      setPin(null);
    } catch {
      // keep the popup open so the user can retry
    } finally {
      setNavBusy(false);
    }
  };

  return (
    <div className="map-panel">
      <MapContainer
        center={[lat, lon]}
        zoom={12}
        className="map-container"
        zoomControl={false}
        attributionControl={false}
      >
        <TileLayer url={TILE_URL} attribution={TILE_ATTRIBUTION} className="dark-tiles" />
        <TapPin onPin={(plat, plon) => setPin({ lat: plat, lon: plon })} />
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
        {pin && (
          <Popup position={[pin.lat, pin.lon]} eventHandlers={{ remove: () => setPin(null) }}>
            <div className="pin-popup">
              <div className="pin-coords">
                {pin.lat.toFixed(4)}, {pin.lon.toFixed(4)}
              </div>
              <button className="pin-go" onClick={() => void driveToPin()} disabled={navBusy}>
                {navBusy ? "Routing..." : "Drive here"}
              </button>
            </div>
          </Popup>
        )}
        <FollowVehicle lat={lat} lon={lon} driving={state.driving} />
        <FitRoute routeKey={state.trip?.destination ?? ""} route={route} />
      </MapContainer>
      <div className="map-favorites">
        {FAVORITES.map((name) => (
          <button
            key={name}
            className="fav-chip"
            onClick={() => onPrompt?.(`Navigate to ${name.toLowerCase()}`)}
          >
            {name}
          </button>
        ))}
      </div>
      <div className="map-overlay">
        {state.trip?.active
          ? `En route to ${state.trip.destination}`
          : state.trip
            ? `Arrived - ${state.trip.destination}`
            : "No active trip - tap the map to drive somewhere"}
      </div>
    </div>
  );
}
