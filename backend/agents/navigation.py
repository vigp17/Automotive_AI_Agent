from agents.base import build_tool_agent
from agents.llm import get_chat_model
from tools.navigation_tools import cancel_navigation, get_route
from tools.vehicle_tools import get_location, get_speed

SYSTEM_PROMPT = (
    "You are the Navigation agent of an in-cabin copilot. You handle routing, "
    "ETA, traffic, and cancelling an active trip. Use get_route to start "
    "navigation and cancel_navigation when the driver wants to abort. Keep "
    "answers short and driver-friendly - one or two sentences, no markdown."
)


def build_navigation_agent():
    return build_tool_agent(
        get_chat_model(),
        [get_route, cancel_navigation, get_location, get_speed],
        SYSTEM_PROMPT,
    )
