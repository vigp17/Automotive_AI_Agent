# Architecture

Implements the "AI-Powered Intelligent Cabin Copilot for Software-Defined Vehicles"
blueprint: a voice-enabled multi-agent in-cabin assistant integrating navigation, EV
charging, calendar awareness, vehicle signals, climate control and driver wellness.

## Flow

```
Driver -> Speech-to-Text -> AI Orchestrator -> {Navigation, EV, HVAC, Calendar} agents
       -> Vehicle APIs -> Simulated vehicle data -> Text-to-Speech -> Driver
```

## Components

| Layer | Location | Notes |
| --- | --- | --- |
| FastAPI app | `backend/app/main.py` | `/chat`, `/voice`, `/vehicle/*`, `/navigate`, `/places/search`, `/preferences`, `/calendar/*`, `/maps/*`, `/alerts`, `/report`, websocket state feed |
| Orchestrator | `backend/agents/orchestrator.py` | LangGraph supervisor: classify intent -> route to agent -> wellness rules; SQLite checkpointer keyed by `session_id` |
| Domain agents | `backend/agents/{navigation,ev,hvac,calendar}.py` | Each is a small tool-calling loop (`agents/base.py`) with a domain prompt |
| Trip planner | `trip_planner_node` in orchestrator | Deterministic cross-agent workflow: next meeting -> route -> energy check -> charging stop -> arrival-time verdict |
| Tools | `backend/tools/` | LangChain tools over the simulator, maps client, charging dataset, calendar store |
| LLM factory | `backend/agents/llm.py` | AzureChatOpenAI in real mode; deterministic keyword-driven `MockChatModel` in `MOCK_MODE` (same tool-calling contract) |
| Vehicle simulator | `backend/simulator/vehicle.py` | SOC drain, motion along route waypoints, cabin-temp drift; 1 Hz tick loop |
| VehicleBus | `backend/simulator/bus.py` | `sim` (direct) or `can` (python-can virtual bus + `can_codec` / `can_bridge`) |
| Speech | `backend/speech/azure_speech.py` | Azure Speech REST STT/TTS + mocks |
| Maps | `backend/services/maps.py` | Pluggable geocode + route + traffic: `mock` (offline table), `osm` (Nominatim + OSRM, keyless), `tomtom`, `azure`; `auto` picks TomTom, then Azure Maps, then OSM |
| Calendar | `backend/services/{calendar_store,graph_calendar,graph_auth,demo_meetings}.py` | JSON seed calendar, or Outlook via Microsoft Graph (MSAL device-code login, seed fallback until connected) |
| Preferences | `backend/services/preferences.py` | Persisted home, work, driver name, and default cabin temperature |
| Alerts | `backend/services/alerts.py` | Proactive cockpit banners: leave-soon, low battery, cabin gap, long drive, late-night fatigue |
| Reports | `backend/reports/trip_report.py` | Markdown trip/wellness report |
| Frontend | `frontend/` | React + Vite dashboard: live widgets over websocket, Leaflet map (route, vehicle, destination, traffic overlay), chat, hold-to-talk mic, preferences and Outlook panels |

## Orchestration graph

```
START -> classify -> [trip_planning | navigation | ev | hvac | calendar | chat] -> wellness -> END
```

- Intent classification: keyword rules in mock mode, structured-output LLM call in real mode.
- Wellness node appends rule-based nudges (drive > 90 min, SOC < 15%, cabin temp gap,
  late-night driving) to any reply.
- Conversation memory: `SqliteSaver` checkpointer, one thread per `session_id`.

## Mock mode

`MOCK_MODE=true` (default) swaps three thin client wrappers - chat model, speech, maps -
for deterministic local implementations. The LangGraph graphs, tools, simulator and API
are identical in both modes, so tests exercise the real orchestration paths offline.

Two keyless paths sit between mock and full Azure: local Whisper STT (`LOCAL_STT=true`)
and OpenStreetMap routing (`MAPS_BACKEND=osm`, Nominatim + OSRM). Both hit the network
but need no credentials. Tests pin `MAPS_BACKEND=mock` and `LOCAL_STT=false` so the suite
stays fully offline.

## Configuration seams

| Setting | Values | Effect |
| --- | --- | --- |
| `MOCK_MODE` | `true` / `false` | Deterministic mock clients vs Azure OpenAI + Azure Speech |
| `MAPS_BACKEND` | `auto` / `mock` / `osm` / `tomtom` / `azure` | Geocoding, routing, and traffic provider |
| `CALENDAR_BACKEND` | `json` / `graph` | Seed calendar vs signed-in Outlook |
| `VEHICLE_BUS` | `sim` / `can` | In-process simulator vs python-can virtual bus |
| `LOCAL_STT` | `true` / `false` | Local Whisper vs mock transcriber |
| `CORS_ORIGINS` | comma-separated origins | Browser origins allowed to call the API cross-origin |
