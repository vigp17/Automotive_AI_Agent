# AI Cabin Copilot

A voice-enabled, multi-agent in-cabin assistant for software-defined vehicles. A LangGraph
orchestrator routes driver requests to Navigation, EV Charging, HVAC, and Calendar agents
operating over a simulated vehicle (battery, motion, climate), exposed through a FastAPI
backend and a React cabin-dashboard frontend.

Stack per the project blueprint: Python, LangGraph, Azure OpenAI, FastAPI, Azure Speech
Services, Azure Maps, Docker. See `docs/architecture.md` and `docs/demo.md`.

## Features

- **Voice assistant** - speech in/out via Azure Speech Services (`/voice`)
- **Navigation agent** - routing, ETA and traffic via Azure Maps
- **EV charging planner** - SOC analysis, charging-stop recommendations from a station dataset
- **Calendar integration** - JSON-backed local calendar, schedule-aware trips
- **Vehicle signal simulator** - `get_soc`, `get_speed`, `get_location`, `set_temperature`,
  live drive loop that drains the battery and moves the vehicle along routes
- **HVAC agent** - cabin comfort control
- **Driver wellness** - rule-based nudges (long drives, low battery, late-night fatigue)
- **Report generation** - markdown trip report (`/report`)
- **Cross-agent workflow** - "Get me to my next meeting" chains calendar, navigation and
  EV charging (adds a charging stop when SOC won't cover the trip) and checks arrival time

## Quickstart (no Azure keys needed)

Everything runs in **mock mode** by default: deterministic local stand-ins for Azure
OpenAI, Speech and Maps, so the full system works offline.

```bash
# Backend
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
cd backend && ../.venv/bin/python -m uvicorn app.main:app --port 8000

# Frontend (second terminal)
cd frontend
npm install
npm run dev   # http://localhost:5173
```

Try in the dashboard chat (or `POST /chat`):

- "Get me to my next meeting"
- "Do I have enough battery to reach the airport?"
- "Set temperature to 22"
- "What's on my calendar?"

### Docker

```bash
docker compose up --build
# frontend on http://localhost:3000, backend on http://localhost:8000
```

### Real Azure services

Copy `.env.example` to `.env`, set `MOCK_MODE=false` and fill in Azure OpenAI, Speech and
Maps credentials.

Voice input: the dashboard mic uses the browser's built-in Web Speech API when available
(Chrome, Edge, Safari - real transcription and spoken replies with no keys). Browsers
without it fall back to uploading audio to `/voice` (Azure Speech with keys, mock
otherwise). Note for the fallback with real Azure STT: the browser records WebM/Opus
while Azure short-form STT expects WAV/PCM.

## Architecture

```
Driver (voice/text)
   -> Azure Speech STT
   -> FastAPI (/chat, /voice)
   -> LangGraph orchestrator (intent classify -> route)
        -> Navigation agent -> Azure Maps + simulator
        -> EV agent         -> charging dataset + simulator
        -> HVAC agent       -> simulator (VehicleBus)
        -> Calendar agent   -> JSON calendar store
        -> Trip planner     -> calendar + maps + charging (cross-agent workflow)
        -> Wellness rules
   -> SQLite conversation memory (per session_id)
   -> Azure Speech TTS -> Driver
```

The simulator sits behind a `VehicleBus` interface (`backend/simulator/bus.py`) so a real
CAN adapter can replace it later without touching agents or tools (blueprint Phase 5).

## Project layout

```
backend/
  app/          FastAPI app + settings
  agents/       LLM factory (Azure/mock), orchestrator, domain agents
  tools/        LangChain tools over simulator and services
  services/     Azure Maps client, calendar store, charging lookup
  simulator/    vehicle physics + VehicleBus abstraction
  speech/       Azure Speech STT/TTS + mocks
  reports/      trip report generator
  data/         charging stations, calendar seed
  tests/        pytest suite (runs fully in mock mode)
frontend/       React + Vite cabin dashboard
docs/           architecture notes + demo script
```

## Tests

```bash
cd backend && ../.venv/bin/python -m pytest
```
