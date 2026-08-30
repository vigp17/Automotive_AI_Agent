# Portfolio demo script (~2–3 minutes)

Use this when recording a Loom/screen capture for LinkedIn, your resume, or interviews.
Run the app first (`README.md` quickstart), then open http://localhost:5173.

---

## 0:00 — Hook (15 sec)

> "This is an AI Cabin Copilot — a voice-enabled, multi-agent assistant for software-defined
> vehicles. It routes driver requests to specialized agents for navigation, EV charging,
> climate, and calendar — all over live vehicle signals."

*Show the dashboard: battery, speed, climate, trip widgets + chat panel.*

---

## 0:15 — Architecture (30 sec)

> "A LangGraph orchestrator classifies intent and delegates to domain agents. Each agent
> uses tool calling against a vehicle simulator today, with a VehicleBus interface designed
> for real CAN or automotive Ethernet on production hardware."

*Optional: briefly flash `docs/architecture.md` or the architecture diagram in README.*

---

## 0:45 — Cross-agent trip planning (45 sec)

Type or click: **"Get me to my next meeting"**

> "This single request chains three agents: Calendar finds the next meeting, Navigation
> computes route and ETA with traffic, and the EV agent checks whether battery covers the
> trip — adding a charging stop if SOC is too low. Navigation starts automatically."

*Point at: trip widget updating, SOC draining, intent tag `trip_planning`.*

---

## 1:30 — Voice + climate (30 sec)

Click mic, say: **"Set the temperature to 22 degrees"** (click mic again to stop)

> "Voice works without cloud keys — browser speech recognition or a local Whisper model
> on the backend. The HVAC agent sets cabin temperature through the vehicle API."

*Point at climate widget target changing.*

---

## 2:00 — EV + wellness (30 sec)

Type: **"Do I have enough battery for the airport?"**

> "The EV agent analyzes state of charge against trip distance and recommends charging
> stops from a station dataset. A wellness layer adds proactive nudges for long drives
> and low battery."

---

## 2:30 — Close (15 sec)

> "Built with Python, FastAPI, LangGraph, React, and Azure-ready integrations for OpenAI,
> Speech, and Maps. Twenty automated tests, Docker deployment, and a clean path to real
> vehicle HMI via WebView and the VehicleBus abstraction."

*Show GitHub repo URL on screen.*

---

## Tips for recording

- Use **1440p or 1080p** window, dark theme already looks good
- Hide browser bookmarks bar; zoom to 100%
- Pre-load the app so widgets show live data before you hit record
- Keep mouse movement slow and deliberate
- Export as MP4; upload to LinkedIn or embed in README once hosted
