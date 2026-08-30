# Demo script

Start the stack (mock mode, no keys needed):

```bash
cd backend && ../.venv/bin/python -m uvicorn app.main:app --port 8000   # terminal 1
cd frontend && npm run dev                                              # terminal 2
```

Open http://localhost:5173 and walk through:

1. **Vehicle signals (Phase 1)** - widgets show live SOC, speed, cabin temp, location,
   streamed over the websocket from the simulator. A **leave-soon** banner appears for
   the next calendar meeting (drive time + buffer). Click the action chip to start trip
   planning, or Dismiss. Raise the climate target by 5°C or drop SOC below 15% to see
   more alerts.
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
7. **Voice** - click the mic button, speak, click again to stop. Chrome/Edge/Safari
   use the browser's built-in speech recognition; other browsers upload the audio and a
   local Whisper model transcribes it on the backend (first use downloads the model,
   ~145 MB, so allow ~30 s once). Replies are spoken aloud either way. No Azure keys
   required; with keys and `MOCK_MODE=false` the `/voice` path uses Azure STT/TTS.
8. **Report** - `curl localhost:8000/report` returns the markdown trip report.
9. **Memory** - follow-ups share a session: the SQLite checkpointer keeps per-session
   conversation history across requests.
10. **Virtual CAN** - set `VEHICLE_BUS=can` in `.env` and restart the backend. Agent
    HVAC/battery reads now travel as CAN frames on a python-can virtual bus. Inspect
    recent frames: `curl localhost:8000/vehicle/can`. Default `VEHICLE_BUS=sim` is unchanged.
