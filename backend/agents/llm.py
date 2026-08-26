"""Chat-model factory: AzureChatOpenAI in real mode, a deterministic
keyword-driven MockChatModel in MOCK_MODE.

The mock implements enough of the tool-calling contract that the same
LangGraph agents run unchanged without Azure credentials: it emits a tool
call chosen by keyword rules, then summarizes the ToolMessage result into a
natural-language reply.
"""

from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from app.config import get_settings

_DEST_RE = re.compile(
    r"(?:\bto\b|\btoward\b|\bat\b)\s+(?:the\s+|my\s+)?([a-z0-9'\- ]+?)(?:\s+please)?[\s]*[?.!,]?$"
)
_NUM_RE = re.compile(r"(-?\d+(?:\.\d+)?)")


def _extract_destination(text: str) -> str:
    match = _DEST_RE.search(text)
    if match:
        return match.group(1).strip()
    return "downtown"


def _match_tool(text: str, available: set[str]):
    """Keyword rules -> (tool_name, args) or None."""
    num = _NUM_RE.search(text)

    if "set_temperature" in available:
        if ("temp" in text or "degrees" in text or "climate" in text) and num and (
            "set" in text or "to " in text or "make" in text
        ):
            return "set_temperature", {"celsius": float(num.group(1))}
        if "cold" in text or "freezing" in text or "warmer" in text:
            return "set_temperature", {"celsius": 24.0}
        if "hot" in text or "cooler" in text or "cool it" in text or "too warm" in text:
            return "set_temperature", {"celsius": 19.0}

    if "plan_charging_stop" in available and (
        "charging stop" in text
        or "charger" in text
        or "need to charge" in text
        or "charging" in text
        or ("enough" in text and ("battery" in text or "charge" in text or "range" in text))
    ):
        dest = _DEST_RE.search(text)
        return "plan_charging_stop", {"destination": dest.group(1).strip() if dest else ""}

    if "get_battery_status" in available and (
        "battery" in text or "soc" in text or "range" in text or "charge" in text
    ):
        return "get_battery_status", {}
    if "get_soc" in available and (
        "battery" in text or "soc" in text or "range" in text or "charge" in text
    ):
        return "get_soc", {}

    if "get_route" in available and (
        "navigate" in text
        or "route" in text
        or "take me" in text
        or "drive" in text
        or "directions" in text
        or "eta" in text
        or "traffic" in text
        or "how long" in text
    ):
        return "get_route", {"destination": _extract_destination(text)}

    if "list_meetings" in available and (
        ("meetings" in text and ("list" in text or "all" in text or "what" in text))
        or "my schedule" in text
        or "calendar" in text
    ):
        return "list_meetings", {}
    if "get_next_meeting" in available and ("meeting" in text or "appointment" in text):
        return "get_next_meeting", {}

    if "get_speed" in available and ("speed" in text or "how fast" in text):
        return "get_speed", {}
    if "get_location" in available and ("where am i" in text or "location" in text):
        return "get_location", {}
    if "get_cabin_temperature" in available and ("temp" in text or "cabin" in text or "warm" in text):
        return "get_cabin_temperature", {}
    return None


def summarize_tool_result(tool_name: str, payload: str) -> str:
    """Template-based natural language for mock mode."""
    try:
        data = json.loads(payload)
    except (json.JSONDecodeError, TypeError):
        return str(payload)

    if tool_name in ("get_soc", "get_battery_status"):
        text = f"Battery is at {data.get('soc_percent')}% with about {data.get('range_km')} km of range."
        if data.get("low_battery"):
            text += " That's getting low - I'd plan a charging stop soon."
        return text
    if tool_name == "get_speed":
        return f"You're currently doing {data.get('speed_kph')} km/h."
    if tool_name == "get_location":
        loc = data.get("location", {})
        return f"We're at latitude {loc.get('lat')}, longitude {loc.get('lon')}."
    if tool_name == "get_cabin_temperature":
        return (
            f"Cabin is at {data.get('cabin_temp_c')}°C, "
            f"target set to {data.get('target_temp_c')}°C."
        )
    if tool_name == "set_temperature":
        return f"Done - cabin temperature set to {data.get('target_temp_c')}°C."
    if tool_name == "get_route":
        return (
            f"Routing to {data.get('destination')}: {data.get('distance_km')} km, "
            f"ETA about {data.get('eta_min')} minutes "
            f"({data.get('traffic_delay_min')} min of traffic delay). Navigation started."
        )
    if tool_name == "plan_charging_stop":
        if data.get("charging_required"):
            station = data.get("recommended_station") or data.get("nearest_station") or {}
            msg = (
                f"Battery is at {data.get('soc_percent')}% - not enough for this trip"
                f" ({data.get('needed_kwh', '?')} kWh needed, {data.get('usable_kwh', '?')} kWh usable)."
                if "needed_kwh" in data
                else f"Battery is at {data.get('soc_percent')}% - a charge is recommended."
            )
            if station:
                msg += (
                    f" I recommend stopping at {station.get('name')} "
                    f"({station.get('power_kw')} kW)."
                )
            if data.get("recommended_charge_minutes"):
                msg += f" About {data['recommended_charge_minutes']} minutes of charging should do it."
            return msg
        return (
            f"You're good - battery at {data.get('soc_percent')}% comfortably covers this trip, "
            "no charging stop needed."
        )
    if tool_name == "get_next_meeting":
        meeting = data.get("next_meeting")
        if not meeting:
            return "Your calendar is clear - no upcoming meetings."
        return (
            f"Next up: {meeting['title']} at {meeting['start_display']}, "
            f"at {meeting['location']}."
        )
    if tool_name == "list_meetings":
        meetings = data.get("meetings", [])
        if not meetings:
            return "No upcoming meetings on your calendar."
        lines = [f"- {m['title']} at {m['start_display']} ({m['location']})" for m in meetings]
        return "Here's your schedule:\n" + "\n".join(lines)
    return str(payload)


class MockChatModel(BaseChatModel):
    """Deterministic stand-in for Azure OpenAI with tool-calling support."""

    bound_tools: list[Any] = []

    @property
    def _llm_type(self) -> str:
        return "mock-cabin-copilot"

    def bind_tools(self, tools, **kwargs):
        return self.model_copy(update={"bound_tools": list(tools)})

    def _generate(self, messages: list[BaseMessage], stop=None, run_manager=None, **kwargs):
        return ChatResult(generations=[ChatGeneration(message=self._respond(messages))])

    def _respond(self, messages: list[BaseMessage]) -> AIMessage:
        last = messages[-1]
        if isinstance(last, ToolMessage):
            return AIMessage(content=summarize_tool_result(last.name or "", str(last.content)))

        human = next(
            (m for m in reversed(messages) if isinstance(m, HumanMessage)), None
        )
        text = (str(human.content) if human else "").lower()

        if self.bound_tools:
            available = {getattr(t, "name", str(t)) for t in self.bound_tools}
            match = _match_tool(text, available)
            if match:
                name, args = match
                return AIMessage(
                    content="",
                    tool_calls=[{"name": name, "args": args, "id": "mock_call_1", "type": "tool_call"}],
                )

        if "hello" in text or "hi" in text or "hey" in text:
            return AIMessage(content="Hi! I'm your cabin copilot. I can handle navigation, charging, climate and your calendar - what do you need?")
        return AIMessage(
            content="I can help with navigation, EV charging, climate control and your calendar. Try 'navigate to the office' or 'set temperature to 22'."
        )


def get_chat_model() -> BaseChatModel:
    settings = get_settings()
    if settings.mock_mode or not settings.azure_openai_api_key:
        return MockChatModel()
    from langchain_openai import AzureChatOpenAI

    return AzureChatOpenAI(
        azure_endpoint=settings.azure_openai_endpoint,
        api_key=settings.azure_openai_api_key,
        azure_deployment=settings.azure_openai_deployment,
        api_version=settings.azure_openai_api_version,
        temperature=0.2,
    )
