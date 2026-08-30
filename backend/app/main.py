"""FastAPI backend for the AI Cabin Copilot."""

from __future__ import annotations

import asyncio
import base64
import contextlib
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, Form, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from agents.orchestrator import Orchestrator
from reports.trip_report import build_trip_report
from services.alerts import cockpit_payload, evaluate_alerts
from simulator.vehicle import get_simulator
from speech.azure_speech import get_speech_client

TICK_SECONDS = 1.0


async def _sim_loop() -> None:
    sim = get_simulator()
    while True:
        await asyncio.sleep(TICK_SECONDS)
        sim.tick(TICK_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.orchestrator = Orchestrator()
    task = asyncio.create_task(_sim_loop())
    yield
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task


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


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/vehicle/state")
def vehicle_state():
    return cockpit_payload()


@app.get("/alerts")
def alerts():
    return {"alerts": evaluate_alerts()}


@app.post("/vehicle/temperature")
def vehicle_temperature(req: TemperatureRequest):
    applied = get_simulator().set_temperature(req.celsius)
    return {"target_temp_c": applied}


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
