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
| FastAPI app | `backend/app/main.py` | `/chat`, `/voice`, `/vehicle/*`, `/report`, websocket state feed |
| Orchestrator | `backend/agents/orchestrator.py` | LangGraph supervisor: classify intent -> route to agent -> wellness rules; SQLite checkpointer keyed by `session_id` |
| Domain agents | `backend/agents/{navigation,ev,hvac,calendar}.py` | Each is a small tool-calling loop (`agents/base.py`) with a domain prompt |
| Trip planner | `trip_planner_node` in orchestrator | Deterministic cross-agent workflow: next meeting -> route -> energy check -> charging stop -> arrival-time verdict |
| Tools | `backend/tools/` | LangChain tools over the simulator, maps client, charging dataset, calendar store |
| LLM factory | `backend/agents/llm.py` | AzureChatOpenAI in real mode; deterministic keyword-driven `MockChatModel` in `MOCK_MODE` (same tool-calling contract) |
| Vehicle simulator | `backend/simulator/vehicle.py` | SOC drain, motion along route waypoints, cabin-temp drift; 1 Hz tick loop |
| VehicleBus | `backend/simulator/bus.py` | Signal-level read/write seam for a future CAN adapter (blueprint Phase 5) |
| Speech | `backend/speech/azure_speech.py` | Azure Speech REST STT/TTS + mocks |
| Maps | `backend/services/maps.py` | Azure Maps geocode + route + traffic, deterministic mock geocoder for demo places |
| Reports | `backend/reports/trip_report.py` | Markdown trip/wellness report |
| Frontend | `frontend/` | React + Vite dashboard: live widgets over websocket, chat, MediaRecorder mic |

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
