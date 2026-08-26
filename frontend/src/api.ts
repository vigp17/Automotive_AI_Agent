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
  } | null;
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
  ws.onmessage = (event) => onState(JSON.parse(event.data));
  return ws;
}
