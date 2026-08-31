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
