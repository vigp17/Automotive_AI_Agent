"""FastAPI backend for the AI Cabin Copilot."""

from __future__ import annotations

import asyncio
import base64
import contextlib
import html
import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from agents.orchestrator import Orchestrator
from reports.trip_report import build_trip_report
from services.alerts import cockpit_payload, evaluate_alerts
from simulator.bus import get_bus, publish_vehicle_frames
from simulator.vehicle import get_simulator
from speech.azure_speech import get_speech_client

TICK_SECONDS = 1.0


def _as_page(request: Request, title: str, data: dict):
    """Browsers get a readable HTML page; API clients still get JSON."""
    if "text/html" not in request.headers.get("accept", ""):
        return data
    pretty = html.escape(json.dumps(data, indent=2))
    return HTMLResponse(
        f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>{html.escape(title)}</title>
<style>
  body {{ font-family: ui-monospace, Menlo, monospace; background: #0d1117; color: #e6edf3;
         margin: 0; padding: 24px; }}
  a {{ color: #4fc3f7; }}
  pre {{ background: #161c26; border: 1px solid #2a3444; border-radius: 12px;
        padding: 16px; overflow: auto; white-space: pre-wrap; }}
</style></head>
<body>
  <p><a href="/">← API home</a> · <a href="http://localhost:5173">Dashboard</a></p>
  <h1>{html.escape(title)}</h1>
  <pre>{pretty}</pre>
</body></html>"""
    )


async def _sim_loop() -> None:
    sim = get_simulator()
    while True:
        await asyncio.sleep(TICK_SECONDS)
        sim.tick(TICK_SECONDS)
        publish_vehicle_frames()


@asynccontextmanager
async def lifespan(app: FastAPI):
    from simulator.bus import can_mode
    from simulator.can_bridge import start_bridge, stop_bridge

    app.state.orchestrator = Orchestrator()
    from services.preferences import get_preferences

    get_simulator().set_temperature(get_preferences().default_temp_c)
    if can_mode():
        start_bridge()
        publish_vehicle_frames()
    task = asyncio.create_task(_sim_loop())
    yield
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task
    stop_bridge()


app = FastAPI(title="AI Cabin Copilot", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    session_id: str = "default"


class TemperatureRequest(BaseModel):
    celsius: float


class NavigateRequest(BaseModel):
    """Destination picked on the map (coordinates, no geocoding needed)."""

    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    label: str = "Dropped pin"


class PreferencesUpdate(BaseModel):
    driver_name: str | None = None
    default_temp_c: float | None = Field(default=None, ge=16, le=30)
    home_query: str | None = None
    home_label: str | None = None
    work_query: str | None = None
    work_label: str | None = None


@app.get("/", response_class=HTMLResponse)
def root():
    return """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>AI Cabin Copilot API</title>
<style>
  body { font-family: system-ui, sans-serif; background: #0d1117; color: #e6edf3;
         max-width: 640px; margin: 48px auto; padding: 0 20px; }
  a { color: #4fc3f7; }
  .btn { display: inline-block; margin: 16px 12px 16px 0; padding: 12px 18px;
         background: #2563eb; color: white; text-decoration: none; border-radius: 10px;
         font-weight: 600; }
  li { margin: 8px 0; }
</style></head>
<body>
  <h1>AI Cabin Copilot API</h1>
  <p>This is the backend. The dashboard is a separate app.</p>
  <p><a class="btn" href="http://localhost:5173">Open cabin dashboard</a>
     <a class="btn" href="/docs">API docs</a></p>
  <ul>
    <li><a href="/vehicle/state">/vehicle/state</a> — live vehicle JSON</li>
    <li><a href="/vehicle/can">/vehicle/can</a> — recent CAN frames</li>
    <li><a href="/alerts">/alerts</a> — proactive alerts</li>
    <li><a href="/preferences">/preferences</a> — driver home, work, default temp</li>
    <li><a href="/healthz">/healthz</a> — health check</li>
  </ul>
  <p>Do not open <code>/vehicle/ws</code> in the browser — that is a WebSocket and will look blank.</p>
</body></html>
"""


@app.get("/healthz")
def healthz(request: Request):
    return _as_page(request, "healthz", {"status": "ok"})


@app.get("/vehicle")
def vehicle_index(request: Request):
    return _as_page(
        request,
        "vehicle",
        {
            "dashboard": "http://localhost:5173",
            "state": "/vehicle/state",
            "can": "/vehicle/can",
            "ws": "/vehicle/ws (WebSocket only — not a web page)",
        },
    )


@app.get("/vehicle/state")
def vehicle_state(request: Request):
    return _as_page(request, "vehicle/state", cockpit_payload())


@app.get("/alerts")
def alerts(request: Request):
    return _as_page(request, "alerts", {"alerts": evaluate_alerts()})


@app.post("/vehicle/temperature")
def vehicle_temperature(req: TemperatureRequest):
    applied = get_bus().write_signal("hvac.target_temp_c", req.celsius)
    return {"target_temp_c": applied}


@app.get("/places/search")
async def places_search(q: str = ""):
    """Typeahead destination search. Locked while the vehicle is moving,
    matching production HMI policy (keyboard entry only in Park). Voice
    and one-tap favorites stay available while driving."""
    from services.maps import get_maps_client

    query = q.strip()
    if not query:
        raise HTTPException(status_code=400, detail="q is required")
    if get_simulator().driving:
        raise HTTPException(
            status_code=409,
            detail="Destination search is available only when parked",
        )
    results = await get_maps_client().search(query)
    return {"query": query, "results": results}


@app.post("/navigate")
async def navigate(req: NavigateRequest):
    """Start navigation to a point tapped on the dashboard map."""
    from services.maps import get_maps_client

    sim = get_simulator()
    route = await get_maps_client().route_to_coords(
        (sim.lat, sim.lon), (req.lat, req.lon), req.label
    )
    sim.set_route(
        route["points"],
        destination=req.label,
        eta_min=route["duration_min"],
        distance_km=route["distance_km"],
    )
    return {
        "destination": req.label,
        "distance_km": route["distance_km"],
        "eta_min": route["duration_min"],
        "traffic_delay_min": route["traffic_delay_min"],
    }


@app.post("/navigate/cancel")
def cancel_navigation_endpoint():
    """Abort the current trip: park and clear the route."""
    result = get_simulator().cancel_trip()
    if not result["cancelled"]:
        return {"cancelled": False, "destination": None}
    return result


@app.get("/preferences")
def get_prefs(request: Request):
    from services.preferences import get_preferences

    return _as_page(request, "preferences", get_preferences().to_dict())


@app.put("/preferences")
def put_prefs(req: PreferencesUpdate):
    from services.preferences import update_preferences

    prefs = update_preferences(
        driver_name=req.driver_name,
        default_temp_c=req.default_temp_c,
        home_query=req.home_query,
        home_label=req.home_label,
        work_query=req.work_query,
        work_label=req.work_label,
    )
    if req.default_temp_c is not None:
        get_simulator().set_temperature(prefs.default_temp_c)
    return prefs.to_dict()


@app.get("/vehicle/can")
def vehicle_can(request: Request):
    """Last virtual CAN frames (empty when VEHICLE_BUS=sim)."""
    from simulator.bus import can_mode
    from simulator.can_bridge import get_bridge

    if not can_mode():
        payload = {"enabled": False, "frames": []}
    else:
        payload = {"enabled": True, "frames": get_bridge().recent_frames()}
    return _as_page(request, "vehicle/can", payload)


@app.websocket("/vehicle/ws")
async def vehicle_ws(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            await websocket.send_json(cockpit_payload())
            await asyncio.sleep(1.0)
    except WebSocketDisconnect:
        pass


@app.post("/chat")
async def chat(req: ChatRequest):
    result = await run_in_threadpool(
        app.state.orchestrator.respond, req.message, req.session_id
    )
    return result


@app.post("/voice")
async def voice(file: UploadFile = File(...), session_id: str = Form("default")):
    speech = get_speech_client()
    audio = await file.read()
    transcript = await speech.transcribe(audio, file.content_type or "audio/wav")
    if not transcript.strip():
        return {"transcript": "", "reply": "Sorry, I didn't catch that.", "audio_base64": ""}
    result = await run_in_threadpool(
        app.state.orchestrator.respond, transcript, session_id
    )
    reply_audio = await speech.synthesize(result["reply"])
    return {
        "transcript": transcript,
        "reply": result["reply"],
        "intent": result["intent"],
        "audio_base64": base64.b64encode(reply_audio).decode(),
    }


@app.get("/report")
def report():
    return {"markdown": build_trip_report()}
