# Interview talking points

Use these when discussing the project in interviews or on your resume.

## One-liner

> Built a voice-enabled multi-agent in-cabin copilot for software-defined vehicles using LangGraph, FastAPI, and React — with cross-agent trip planning, live vehicle signal simulation, and a VehicleBus abstraction for production CAN integration.

## Resume bullets (pick 2–3)

- Designed a **LangGraph multi-agent orchestrator** that routes driver intent to Navigation, EV, HVAC, and Calendar agents with tool calling over live vehicle signals
- Implemented a **cross-agent workflow** ("get me to my next meeting") chaining calendar lookup, route/ETA computation, EV charging analysis, and automatic navigation start
- Built a **VehicleBus abstraction** separating agent logic from vehicle I/O, enabling future CAN/VSS/SOME-IP adapters without rewriting agents
- Delivered **keyless voice input** via browser Web Speech API and local Whisper STT fallback; Azure Speech integration for production
- Shipped **20 automated tests**, Docker Compose deployment, and GitHub CI covering backend pytest and frontend build

## "Tell me about a technical challenge"

**Challenge:** Voice had to work in demo mode without Azure keys, in browsers where Web Speech API isn't available, and with the browser recording WebM while Azure expects WAV.

**Solution:** Three-tier voice pipeline — browser STT first, local Whisper on the backend as fallback (decodes WebM via PyAV), Azure Speech when keys are configured. Fixed a state-race bug where failed recognition spawned duplicate recorders.

## "How would this go on a real vehicle?"

> The React UI embeds in an OEM HMI WebView. The Python agent runs as a localhost service on the cockpit ECU. The simulator is replaced by a VehicleBus adapter reading real signals from CAN, VSS, or Android CarPropertyManager. Voice goes through the vehicle mic array and automotive STT, not browser APIs.

## Skills demonstrated

| Category | Skills |
|---|---|
| AI/ML | LangGraph, LangChain, tool calling, intent classification, conversation memory |
| Backend | FastAPI, WebSockets, REST, pydantic-settings, pytest |
| Frontend | React, TypeScript, Vite, real-time dashboards, MediaRecorder |
| Cloud | Azure OpenAI, Azure Speech, Azure Maps (with mock/real switching) |
| Automotive | Vehicle signal modeling, SOC/range estimation, HMI integration path |
| DevOps | Docker Compose, GitHub Actions CI |

## Questions to ask them

- "What HMI stack do you use — Android Automotive, QNX, or WebView-based?"
- "How do IVI apps access vehicle signals — VSS, SOME/IP, or proprietary middleware?"
- "Is the assistant voice-first or touch-first in your product roadmap?"
