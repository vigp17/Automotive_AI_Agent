from agents.base import build_tool_agent
from agents.llm import get_chat_model
from tools.ev_tools import get_battery_status, plan_charging_stop

SYSTEM_PROMPT = (
    "You are the EV agent of an in-cabin copilot. You analyze battery state of "
    "charge and plan charging stops. Always ground answers in tool results. "
    "Keep answers short and driver-friendly - one or two sentences, no markdown."
)


def build_ev_agent():
    return build_tool_agent(get_chat_model(), [get_battery_status, plan_charging_stop], SYSTEM_PROMPT)
