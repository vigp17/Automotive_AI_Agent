from agents.base import build_tool_agent
from agents.llm import get_chat_model
from tools.calendar_tools import get_next_meeting, list_meetings

SYSTEM_PROMPT = (
    "You are the Calendar agent of an in-cabin copilot. You answer questions "
    "about the driver's meetings and schedule using the tools. Keep answers "
    "short and driver-friendly - one or two sentences, no markdown."
)


def build_calendar_agent():
    return build_tool_agent(get_chat_model(), [get_next_meeting, list_meetings], SYSTEM_PROMPT)
