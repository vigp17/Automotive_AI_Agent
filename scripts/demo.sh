#!/usr/bin/env bash
#
# Demo pre-flight: force a known-good state, prove the demo prompts actually
# work, then leave the app running and ready to record.
#
# The failure this exists to prevent: recording the headline prompt ("Get me to
# my next meeting") against an empty Outlook calendar, where the copilot answers
# "Your calendar is clear" instead of planning a trip.
#
#   scripts/demo.sh              seed calendar, start both servers, verify, hold
#   scripts/demo.sh --check-only verify against a backend this script starts, then exit
#   scripts/demo.sh --graph      keep CALENDAR_BACKEND=graph (to demo Outlook)
#   scripts/demo.sh --mock-maps  force the offline map backend (no network)
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
BASE="http://127.0.0.1:${BACKEND_PORT}"
LOG_DIR="${TMPDIR:-/tmp}"; LOG_DIR="${LOG_DIR%/}/cabin-copilot-demo"

CHECK_ONLY=false
USE_GRAPH=false
MOCK_MAPS=false
for arg in "$@"; do
  case "$arg" in
    --check-only) CHECK_ONLY=true ;;
    --graph) USE_GRAPH=true ;;
    --mock-maps) MOCK_MAPS=true ;;
    -h|--help) sed -n '3,14p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown option: $arg (try --help)" >&2; exit 2 ;;
  esac
done

if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
  GREEN=$'\033[32m'; RED=$'\033[31m'; YELLOW=$'\033[33m'; BOLD=$'\033[1m'; OFF=$'\033[0m'
else
  GREEN=""; RED=""; YELLOW=""; BOLD=""; OFF=""
fi

FAILURES=0
ok()   { printf "  %sok%s    %s\n" "$GREEN" "$OFF" "$1"; }
warn() { printf "  %swarn%s  %s\n" "$YELLOW" "$OFF" "$1"; }
bad()  { printf "  %sFAIL%s  %s\n" "$RED" "$OFF" "$1"; FAILURES=$((FAILURES + 1)); }
step() { printf "\n%s%s%s\n" "$BOLD" "$1" "$OFF"; }

BACKEND_PID=""
FRONTEND_PID=""
DEMO_MEETINGS="$ROOT/backend/data/demo_meetings.json"
DEMO_MEETINGS_STASH=""
cleanup() {
  [ -n "$FRONTEND_PID" ] && kill "$FRONTEND_PID" 2>/dev/null || true
  [ -n "$BACKEND_PID" ] && kill "$BACKEND_PID" 2>/dev/null || true
  # Put any previously saved sample meetings back exactly as they were.
  if [ -n "$DEMO_MEETINGS_STASH" ] && [ -f "$DEMO_MEETINGS_STASH" ]; then
    mv -f "$DEMO_MEETINGS_STASH" "$DEMO_MEETINGS"
  fi
}
trap cleanup EXIT INT TERM

# Read one dotted key out of a JSON body on stdin; prints "" when absent.
json_field() {
  python3 -c '
import json, sys
data = json.load(sys.stdin)
for part in sys.argv[1].split("."):
    data = data.get(part) if isinstance(data, dict) else None
print("" if data is None else data)
' "$1"
}

# Ask the copilot something. Uses its own session so nothing from the
# pre-flight shows up in the chat panel you record.
chat() {
  local payload
  payload="$(python3 -c 'import json,sys; print(json.dumps({"message": sys.argv[1], "session_id": "preflight"}))' "$1")"
  curl -s -X POST "$BASE/chat" -H 'content-type: application/json' --data "$payload"
}

step "Environment"

[ -x "$ROOT/.venv/bin/python" ] || { bad "no .venv — see the README quickstart"; exit 1; }
ok "python venv"

if ! "$ROOT/.venv/bin/python" -c "import uvicorn" 2>/dev/null; then
  bad "backend deps missing — .venv/bin/pip install -r backend/requirements.txt"
  exit 1
fi
ok "backend dependencies"

if [ "$CHECK_ONLY" = false ] && [ ! -d "$ROOT/frontend/node_modules" ]; then
  bad "frontend deps missing — cd frontend && npm ci"
  exit 1
fi

for port in "$BACKEND_PORT" "$FRONTEND_PORT"; do
  if lsof -ti :"$port" >/dev/null 2>&1; then
    bad "port $port is already in use — stop the other process first"
    exit 1
  fi
done
ok "ports $BACKEND_PORT and $FRONTEND_PORT are free"

# Demo state, kept separate from whatever is in .env:
#   MOCK_MODE     deterministic replies, no Azure spend mid-recording
#   CALENDAR      json seed always has a meeting a couple of hours out
#   MEMORY_DB     scratch file, so the chat history starts empty every run
mkdir -p "$LOG_DIR"
export MOCK_MODE=true
export MEMORY_DB_PATH="$LOG_DIR/demo-memory.sqlite"
rm -f "$MEMORY_DB_PATH" "$MEMORY_DB_PATH"-wal "$MEMORY_DB_PATH"-shm
if [ "$USE_GRAPH" = true ]; then
  export CALENDAR_BACKEND=graph
else
  export CALENDAR_BACKEND=json
fi
[ "$MOCK_MAPS" = true ] && export MAPS_BACKEND=mock
ok "demo env (MOCK_MODE=true, CALENDAR_BACKEND=$CALENDAR_BACKEND, scratch memory db)"

# Sample meetings accumulate across runs and show up as duplicate entries in the
# calendar list. Set them aside for the recording and restore them on exit.
if [ -f "$DEMO_MEETINGS" ]; then
  DEMO_MEETINGS_STASH="$LOG_DIR/demo_meetings.stashed.json"
  mv "$DEMO_MEETINGS" "$DEMO_MEETINGS_STASH"
  ok "existing sample meetings set aside (restored when this script exits)"
fi

step "Backend"

(cd "$ROOT/backend" && exec "$ROOT/.venv/bin/python" -m uvicorn app.main:app --port "$BACKEND_PORT") \
  > "$LOG_DIR/backend.log" 2>&1 &
BACKEND_PID=$!

for _ in $(seq 1 60); do
  curl -sf "$BASE/healthz" >/dev/null 2>&1 && break
  kill -0 "$BACKEND_PID" 2>/dev/null || { bad "backend exited — see $LOG_DIR/backend.log"; exit 1; }
  sleep 0.5
done
curl -sf "$BASE/healthz" >/dev/null 2>&1 || { bad "backend never became healthy"; exit 1; }
ok "listening on $BASE"

state="$(curl -s "$BASE/vehicle/state")"
soc="$(echo "$state" | json_field soc_percent)"
ok "vehicle online (battery ${soc}%)"

maps="$(curl -s "$BASE/maps/status")"
maps_backend="$(echo "$maps" | json_field backend)"
if [ "$maps_backend" = "mock" ]; then
  ok "maps: mock (offline, deterministic)"
else
  ok "maps: $maps_backend (traffic: $(echo "$maps" | json_field traffic))"
fi

step "Calendar"

cal="$(curl -s "$BASE/calendar/status")"
count="$(echo "$cal" | json_field meeting_count)"
if [ "${count:-0}" -eq 0 ]; then
  warn "no upcoming meetings — adding the sample meeting"
  curl -s -X POST "$BASE/calendar/demo-meeting" >/dev/null
  cal="$(curl -s "$BASE/calendar/status")"
  count="$(echo "$cal" | json_field meeting_count)"
fi
if [ "${count:-0}" -eq 0 ]; then
  bad "still no meetings — 'Get me to my next meeting' will answer 'your calendar is clear'"
else
  ok "$count upcoming meeting(s); next: $(echo "$cal" | json_field next_meeting.title) at $(echo "$cal" | json_field next_meeting.start_display)"
fi

step "Demo prompts"

reply="$(chat "Get me to my next meeting")"
intent="$(echo "$reply" | json_field intent)"
text="$(echo "$reply" | json_field reply)"
if [ "$intent" = "trip_planning" ] && [ "${text#*calendar is clear}" = "$text" ]; then
  ok "\"Get me to my next meeting\" -> ${text:0:72}..."
else
  bad "\"Get me to my next meeting\" -> $text"
fi

# That started navigation. Park again so the recording begins from a clean slate.
curl -s -X POST "$BASE/navigate/cancel" >/dev/null
driving="$(curl -s "$BASE/vehicle/state" | json_field driving)"
if [ "$driving" = "False" ]; then
  ok "trip cancelled, vehicle parked"
else
  bad "vehicle still driving after cancel"
fi

# Verify HVAC with a value you would not use on camera, then put the cabin back
# to the driver's saved default so the on-camera "set temperature to 22" visibly
# changes something.
reply="$(chat "Set temperature to 20")"
if [ "$(echo "$reply" | json_field intent)" = "hvac" ]; then
  ok "\"Set temperature to 20\" -> $(echo "$reply" | json_field reply)"
else
  bad "HVAC prompt returned intent $(echo "$reply" | json_field intent)"
fi

default_temp="$(curl -s "$BASE/preferences" | json_field default_temp_c)"
curl -s -X POST "$BASE/vehicle/temperature" -H 'content-type: application/json' \
  --data "{\"celsius\": ${default_temp:-21}}" >/dev/null
ok "cabin reset to the saved default (${default_temp:-21}C)"

reply="$(chat "Do I have enough battery for the airport?")"
if [ "$(echo "$reply" | json_field intent)" = "ev" ]; then
  ok "\"Do I have enough battery for the airport?\" -> $(echo "$reply" | json_field reply)"
else
  bad "EV prompt returned intent $(echo "$reply" | json_field intent)"
fi

if [ "$FAILURES" -gt 0 ]; then
  printf "\n%s%s pre-flight check(s) failed — not starting the dashboard.%s\n" "$RED" "$FAILURES" "$OFF"
  printf "Backend log: %s\n" "$LOG_DIR/backend.log"
  exit 1
fi

if [ "$CHECK_ONLY" = true ]; then
  printf "\n%sPre-flight passed.%s Re-run without --check-only to hold the app open.\n" "$GREEN" "$OFF"
  exit 0
fi

step "Dashboard"

(cd "$ROOT/frontend" && exec npm run dev -- --port "$FRONTEND_PORT" --strictPort) \
  > "$LOG_DIR/frontend.log" 2>&1 &
FRONTEND_PID=$!

# Probe via localhost, not 127.0.0.1: Vite binds ::1 only, so the IPv4
# literal never connects even once the dev server is up.
for _ in $(seq 1 60); do
  curl -sf "http://localhost:$FRONTEND_PORT" >/dev/null 2>&1 && break
  kill -0 "$FRONTEND_PID" 2>/dev/null || { bad "frontend exited — see $LOG_DIR/frontend.log"; exit 1; }
  sleep 0.5
done
curl -sf "http://localhost:$FRONTEND_PORT" >/dev/null 2>&1 \
  || { bad "dashboard never came up — see $LOG_DIR/frontend.log"; exit 1; }
ok "dashboard on http://localhost:$FRONTEND_PORT"

cat <<EOF

${GREEN}${BOLD}Ready to record.${OFF}  http://localhost:$FRONTEND_PORT

  Prompts, in order:
    1. Get me to my next meeting
    2. Set temperature to 22          <- mic, if you are demoing voice
    3. Do I have enough battery for the airport?

  Before you hit record: 100% zoom, bookmarks bar hidden, chat panel empty.
  Logs: $LOG_DIR
  Ctrl-C stops both servers.

EOF

wait "$BACKEND_PID" "$FRONTEND_PID"
