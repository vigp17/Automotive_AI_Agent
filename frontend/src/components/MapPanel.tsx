import { FormEvent, useEffect, useState } from "react";
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
import "leaflet/dist/leaflet.css";
import { navigateTo, PlaceSuggestion, searchPlaces, VehicleState } from "../api";

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
  const [query, setQuery] = useState("");
  const [suggestions, setSuggestions] = useState<PlaceSuggestion[]>([]);
  const [searching, setSearching] = useState(false);
  const parked = Boolean(state && !state.driving);

  useEffect(() => {
    if (!parked) {
      setQuery("");
      setSuggestions([]);
      setSearching(false);
    }
  }, [parked]);

  useEffect(() => {
    if (!parked) return;
    const q = query.trim();
    if (q.length < 2) {
      setSuggestions([]);
      setSearching(false);
      return;
    }
    let cancelled = false;
    setSearching(true);
    const timer = window.setTimeout(async () => {
      try {
        const results = await searchPlaces(q);
        if (!cancelled) setSuggestions(results);
      } catch {
        if (!cancelled) setSuggestions([]);
      } finally {
        if (!cancelled) setSearching(false);
      }
    }, 250);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [query, parked]);

  if (!state) {
    return <div className="map-panel loading">Loading map...</div>;
  }

  const { lat, lon } = state.location;
  const route = state.trip?.route ?? [];
  const fullPath: [number, number][] = route.length ? [[lat, lon], ...route] : [];
  const destination = route.length ? route[route.length - 1] : null;

  const driveTo = async (destLat: number, destLon: number, label: string) => {
    if (navBusy) return;
    setNavBusy(true);
    try {
      await navigateTo(destLat, destLon, label);
      setPin(null);
      setQuery("");
      setSuggestions([]);
    } catch {
      // keep the picker open so the user can retry
    } finally {
      setNavBusy(false);
    }
  };

  const onSearchSubmit = (event: FormEvent) => {
    event.preventDefault();
    if (!parked) return;
    if (suggestions[0]) {
      void driveTo(suggestions[0].lat, suggestions[0].lon, suggestions[0].label);
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
              <button
                className="pin-go"
                onClick={() => void driveTo(pin.lat, pin.lon, "Dropped pin")}
                disabled={navBusy}
              >
                {navBusy ? "Routing..." : "Drive here"}
              </button>
            </div>
          </Popup>
        )}
        <FollowVehicle lat={lat} lon={lon} driving={state.driving} />
        <FitRoute routeKey={state.trip?.destination ?? ""} route={route} />
      </MapContainer>
      <div className="map-search">
        <form className={`search-box ${parked ? "" : "locked"}`} onSubmit={onSearchSubmit}>
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={parked ? "Search destination..." : "Available in Park"}
            disabled={!parked}
            aria-label="Search destination"
          />
          <button type="submit" disabled={!parked || !suggestions[0] || navBusy}>
            Go
          </button>
        </form>
        {!parked && (
          <div className="search-lock">Keyboard search locked while driving — use voice or a favorite</div>
        )}
        {parked && (suggestions.length > 0 || searching) && (
          <ul className="search-results">
            {searching && suggestions.length === 0 && <li className="search-empty">Searching...</li>}
            {suggestions.map((place) => (
              <li key={`${place.label}-${place.lat}-${place.lon}`}>
                <button
                  type="button"
                  onClick={() => void driveTo(place.lat, place.lon, place.label)}
                  disabled={navBusy}
                >
                  {place.label}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
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
            : parked
              ? "Parked — search, tap the map, or pick a favorite"
              : "No active trip"}
      </div>
    </div>
  );
}
