# Demo script

Start the stack (mock mode, no keys needed):

```bash
cd backend && ../.venv/bin/python -m uvicorn app.main:app --port 8000   # terminal 1
cd frontend && npm run dev                                              # terminal 2
```

Open http://localhost:5173 and walk through:

1. **Vehicle signals (Phase 1)** - widgets show live SOC, speed, cabin temp, location,
   streamed over the websocket from the simulator.
2. **Climate (HVAC agent)** - type "Set temperature to 22" or "I'm cold". Watch the
   Climate widget target change and the cabin temp drift toward it.
3. **Battery (EV agent)** - "Do I have enough battery for the airport?" gives an SOC
   analysis with a charging-stop recommendation when needed.
4. **Navigation agent** - "Navigate to the airport" returns distance/ETA/traffic and the
   vehicle starts driving: speed rises, SOC drains, trip progress fills.
5. **Calendar agent** - "What's on my calendar?" lists the seeded meetings.
6. **Cross-agent trip planning** - "Get me to my next meeting" chains calendar ->
   route -> energy check -> arrival verdict, and starts navigation. To force a charging
   stop first ask a few questions with battery drained low (or edit `soc` in
   `backend/simulator/vehicle.py`).
7. **Voice** - click the mic button, speak, click stop. In Chrome/Edge/Safari the
   browser's built-in speech recognition transcribes your words (no keys needed) and the
   reply is spoken aloud. In browsers without speech recognition the audio is sent to
   the backend `/voice` pipeline instead: real Azure STT/TTS with keys, or the fixed
   mock transcript "What's my battery level?" in mock mode.
8. **Report** - `curl localhost:8000/report` returns the markdown trip report.
9. **Memory** - follow-ups share a session: the SQLite checkpointer keeps per-session
   conversation history across requests.
