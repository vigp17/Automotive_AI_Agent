"""LangGraph supervisor: intent routing, domain agents, cross-agent trip
planning workflow, wellness rules, and SQLite-backed conversation memory."""

from __future__ import annotations

import asyncio
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, MessagesState, StateGraph
from pydantic import BaseModel

from agents.calendar import build_calendar_agent
from agents.ev import build_ev_agent
from agents.hvac import build_hvac_agent
from agents.llm import get_chat_model
from agents.navigation import build_navigation_agent
from app.config import get_settings
from services.calendar_store import get_calendar_store
from services.charging import charging_needed, station_near_route
from services.maps import get_maps_client
from simulator.vehicle import get_simulator

INTENTS = ("trip_planning", "navigation", "ev", "hvac", "calendar", "chat")


class CabinState(MessagesState):
    intent: str
    reply: str


class RouteDecision(BaseModel):
    intent: Literal["trip_planning", "navigation", "ev", "hvac", "calendar", "chat"]


# ---------------------------------------------------------------------------
# Intent classification
# ---------------------------------------------------------------------------
_MOVEMENT_WORDS = ("get me to", "take me", "drive", "head to", "make it", "leave for", "go to")
_MEETING_WORDS = ("meeting", "appointment", "calendar")


def classify_by_keywords(text: str) -> str:
    t = text.lower()
    if any(m in t for m in _MEETING_WORDS) and (
        any(w in t for w in _MOVEMENT_WORDS) or "on time" in t or "route" in t
    ):
        return "trip_planning"
    if any(w in t for w in ("set home", "set work", "home is", "work is")):
        return "navigation"
    if any(w in t for w in ("temp", "degrees", "climate", "cold", "hot", "warmer", "cooler", "ac ", "heat", "usual")):
        return "hvac"
    if any(w in t for w in ("battery", "soc", "charging", "charger", "charge", "range")):
        return "ev"
    if any(
        w in t
        for w in (
            "cancel",
            "abort",
            "end trip",
            "stop the trip",
            "stop navigation",
            "navigate",
            "route",
            "take me",
            "drive",
            "directions",
            "eta",
            "traffic",
            "where am i",
            "how long",
            "speed",
        )
    ):
        return "navigation"
    if any(w in t for w in _MEETING_WORDS) or "schedule" in t:
        return "calendar"
    return "chat"


def classify_intent(text: str) -> str:
    settings = get_settings()
    if settings.mock_mode or not settings.azure_openai_api_key:
        return classify_by_keywords(text)
    llm = get_chat_model().with_structured_output(RouteDecision)
    decision = llm.invoke(
        "Classify this in-car driver request into one intent.\n"
        "- trip_planning: getting to a calendar meeting (combines calendar + navigation + charging)\n"
        "- navigation: routes, ETA, traffic\n"
        "- ev: battery, range, charging\n"
        "- hvac: cabin temperature, climate comfort\n"
        "- calendar: meetings and schedule questions\n"
        "- chat: anything else\n\n"
        f"Request: {text}"
    )
    return decision.intent


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

def _last_user_text(state: CabinState) -> str:
    for message in reversed(state["messages"]):
        if isinstance(message, HumanMessage):
            return str(message.content)
    return ""


def classify_node(state: CabinState):
    return {"intent": classify_intent(_last_user_text(state))}


def _agent_node(agent):
    def node(state: CabinState):
        result = agent.invoke({"messages": list(state["messages"])})
        final = result["messages"][-1]
        return {"messages": [final], "reply": str(final.content)}

    return node


def trip_planner_node(state: CabinState):
    """Deterministic cross-agent workflow: calendar -> navigation -> EV."""
    sim = get_simulator()
    meeting = get_calendar_store().next_meeting()
    if meeting is None:
        reply = "Your calendar is clear - no upcoming meetings to drive to."
        return {"messages": [AIMessage(content=reply)], "reply": reply}

    route = asyncio.run(get_maps_client().route((sim.lat, sim.lon), meeting.location))
    analysis = charging_needed(sim.get_soc(), route["distance_km"])

    parts = [
        f"Your next meeting is {meeting.title} at {meeting.start.strftime('%I:%M %p').lstrip('0')} "
        f"at {meeting.location}.",
        f"It's {route['distance_km']} km away, about {route['duration_min']} minutes with "
        f"{route['traffic_delay_min']} minutes of traffic delay.",
    ]

    total_min = route["duration_min"]
    if analysis["charging_required"]:
        station = station_near_route(route["points"])
        charge_min = analysis["recommended_charge_minutes"]
        total_min += charge_min
        parts.append(
            f"Battery is at {sim.get_soc()}% which won't cover the trip, so I've added a "
            f"charging stop at {station['name']} ({station['power_kw']} kW, ~{charge_min} min)."
        )
    else:
        parts.append(f"Battery is at {sim.get_soc()}% - no charging stop needed.")

    arrival = datetime.now() + timedelta(minutes=total_min)
    if arrival <= meeting.start:
        slack = int((meeting.start - arrival).total_seconds() // 60)
        parts.append(f"Leaving now you'd arrive around {arrival.strftime('%I:%M %p').lstrip('0')}, "
                     f"{slack} minutes early. Starting navigation.")
    else:
        late = int((arrival - meeting.start).total_seconds() // 60)
        parts.append(f"Heads up: leaving now you'd be about {late} minutes late "
                     f"(arriving {arrival.strftime('%I:%M %p').lstrip('0')}). Starting navigation.")

    sim.set_route(
        route["points"],
        destination=meeting.location,
        eta_min=route["duration_min"],
        distance_km=route["distance_km"],
        traffic_delay_min=route["traffic_delay_min"],
    )
    reply = " ".join(parts)
    return {"messages": [AIMessage(content=reply)], "reply": reply}


def chat_node(state: CabinState):
    response = get_chat_model().invoke(list(state["messages"]))
    return {"messages": [response], "reply": str(response.content)}


def wellness_node(state: CabinState):
    """Rule-based driver wellness nudges appended to the reply."""
    sim = get_simulator()
    notes: list[str] = []
    if sim.trip and sim.driving and sim.trip_elapsed_min() > 90:
        notes.append("you've been driving for over 90 minutes - consider a short break")
    if sim.get_soc() < 15:
        notes.append("battery is below 15%, I can plan a charging stop")
    if abs(sim.cabin_temp_c - sim.target_temp_c) > 4:
        notes.append("the cabin is still adjusting to your target temperature")
    hour = datetime.now().hour
    if sim.driving and (hour >= 22 or hour < 5):
        notes.append("it's late, watch for fatigue")

    if not notes:
        return {}
    note_text = "Wellness note: " + "; ".join(notes) + "."
    return {"reply": state.get("reply", "") + "\n\n" + note_text}


# ---------------------------------------------------------------------------
# Graph assembly
# ---------------------------------------------------------------------------

def build_orchestrator(checkpointer=None):
    graph = StateGraph(CabinState)
    graph.add_node("classify", classify_node)
    graph.add_node("navigation", _agent_node(build_navigation_agent()))
    graph.add_node("ev", _agent_node(build_ev_agent()))
    graph.add_node("hvac", _agent_node(build_hvac_agent()))
    graph.add_node("calendar", _agent_node(build_calendar_agent()))
    graph.add_node("trip_planning", trip_planner_node)
    graph.add_node("chat", chat_node)
    graph.add_node("wellness", wellness_node)

    graph.add_edge(START, "classify")
    graph.add_conditional_edges(
        "classify",
        lambda state: state["intent"],
        {intent: intent for intent in INTENTS},
    )
    for intent in INTENTS:
        graph.add_edge(intent, "wellness")
    graph.add_edge("wellness", END)
    return graph.compile(checkpointer=checkpointer)


class Orchestrator:
    """Facade owning the compiled graph and its SQLite conversation memory."""

    def __init__(self, db_path: str | None = None) -> None:
        settings = get_settings()
        path = db_path or settings.memory_db_path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path, check_same_thread=False)
        self.checkpointer = SqliteSaver(conn)
        self.graph = build_orchestrator(self.checkpointer)

    def respond(self, message: str, session_id: str = "default") -> dict:
        result = self.graph.invoke(
            {"messages": [HumanMessage(content=message)], "reply": ""},
            config={"configurable": {"thread_id": session_id}},
        )
        return {"reply": result.get("reply", ""), "intent": result.get("intent", "chat")}
