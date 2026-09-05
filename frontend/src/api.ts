export interface CabinAlert {
  id: string;
  severity: "info" | "warning" | "danger";
  title: string;
  message: string;
  action: string | null;
}

export interface VehicleState {
  soc_percent: number;
  range_km: number;
  speed_kph: number;
  location: { lat: number; lon: number };
  cabin_temp_c: number;
  target_temp_c: number;
  outside_temp_c: number;
  odometer_km: number;
  driving: boolean;
  trip: {
    destination: string;
    elapsed_min: number;
    distance_km: number | null;
    eta_min: number | null;
    traffic_delay_min: number | null;
    progress: number | null;
    active: boolean;
    route: [number, number][];
  } | null;
  alerts: CabinAlert[];
}

export interface ChatResponse {
  reply: string;
  intent: string;
}

export async function sendChat(message: string, sessionId: string): Promise<ChatResponse> {
  const resp = await fetch("/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, session_id: sessionId }),
  });
  if (!resp.ok) throw new Error(`chat failed: ${resp.status}`);
  return resp.json();
}

export interface VoiceResponse extends ChatResponse {
  transcript: string;
  audio_base64: string;
}

export async function sendVoice(audio: Blob, sessionId: string): Promise<VoiceResponse> {
  const form = new FormData();
  form.append("file", audio, "speech.webm");
  form.append("session_id", sessionId);
  const resp = await fetch("/voice", { method: "POST", body: form });
  if (!resp.ok) throw new Error(`voice failed: ${resp.status}`);
  return resp.json();
}

export interface NavigateResponse {
  destination: string;
  distance_km: number;
  eta_min: number;
  traffic_delay_min: number;
}

export interface PlaceSuggestion {
  label: string;
  lat: number;
  lon: number;
}

export async function searchPlaces(query: string): Promise<PlaceSuggestion[]> {
  const resp = await fetch(`/places/search?q=${encodeURIComponent(query)}`);
  if (resp.status === 409) {
    throw new Error("search locked");
  }
  if (!resp.ok) throw new Error(`search failed: ${resp.status}`);
  const body = await resp.json();
  return body.results ?? [];
}

export async function navigateTo(
  lat: number,
  lon: number,
  label = "Dropped pin",
): Promise<NavigateResponse> {
  const resp = await fetch("/navigate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ lat, lon, label }),
  });
  if (!resp.ok) throw new Error(`navigate failed: ${resp.status}`);
  return resp.json();
}

export async function cancelTrip(): Promise<{ cancelled: boolean; destination: string | null }> {
  const resp = await fetch("/navigate/cancel", { method: "POST" });
  if (!resp.ok) throw new Error(`cancel failed: ${resp.status}`);
  return resp.json();
}

export interface SavedPlace {
  label: string;
  query: string;
}

export interface DriverPreferences {
  driver_name: string;
  default_temp_c: number;
  home: SavedPlace;
  work: SavedPlace;
}

export async function fetchPreferences(): Promise<DriverPreferences> {
  const resp = await fetch("/preferences");
  if (!resp.ok) throw new Error(`preferences failed: ${resp.status}`);
  return resp.json();
}

export async function savePreferences(
  update: Partial<{
    driver_name: string;
    default_temp_c: number;
    home_query: string;
    home_label: string;
    work_query: string;
    work_label: string;
  }>,
): Promise<DriverPreferences> {
  const resp = await fetch("/preferences", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(update),
  });
  if (!resp.ok) throw new Error(`save preferences failed: ${resp.status}`);
  return resp.json();
}

export interface CalendarMeeting {
  title: string;
  location: string;
  start: string;
  start_display: string;
  duration_min: number;
}

export interface CalendarStatus {
  backend: string;
  configured: boolean;
  connected: boolean;
  pending: { user_code: string; verification_uri: string; message: string } | null;
  error: string | null;
  meeting_count: number;
  next_meeting: CalendarMeeting | null;
}

export async function fetchCalendarStatus(): Promise<CalendarStatus> {
  const resp = await fetch("/calendar/status");
  if (!resp.ok) throw new Error(`calendar status failed: ${resp.status}`);
  return resp.json();
}

export async function connectOutlook(): Promise<{
  user_code: string;
  verification_uri: string;
  message: string;
  expires_in: number;
}> {
  const resp = await fetch("/calendar/connect", { method: "POST" });
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw new Error(body.detail || `connect failed: ${resp.status}`);
  }
  return resp.json();
}

export async function logoutOutlook(): Promise<void> {
  await fetch("/calendar/logout", { method: "POST" });
}

export interface MapsStatus {
  backend: string;
  configured: boolean;
  traffic: boolean;
}

export async function fetchMapsStatus(): Promise<MapsStatus> {
  const resp = await fetch("/maps/status");
  if (!resp.ok) throw new Error(`maps status failed: ${resp.status}`);
  return resp.json();
}

export async function addDemoMeeting(): Promise<CalendarMeeting> {
  const resp = await fetch("/calendar/demo-meeting", { method: "POST" });
  if (!resp.ok) throw new Error(`demo meeting failed: ${resp.status}`);
  const body = await resp.json();
  return body.meeting;
}

export async function setTemperature(celsius: number): Promise<void> {
  await fetch("/vehicle/temperature", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ celsius }),
  });
}

export function openStateSocket(onState: (state: VehicleState) => void): WebSocket {
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${window.location.host}/vehicle/ws`);
  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    onState({ ...data, alerts: data.alerts ?? [] });
  };
  return ws;
}
