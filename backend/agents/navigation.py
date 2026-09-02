from agents.base import build_tool_agent
from agents.llm import get_chat_model
from tools.navigation_tools import cancel_navigation, get_route, set_saved_place
from tools.vehicle_tools import get_location, get_speed

SYSTEM_PROMPT = (
    "You are the Navigation agent of an in-cabin copilot. You handle routing, "
    "ETA, traffic, cancelling a trip, and saving home/work. Use get_route for "
    "'take me home' / 'take me to work' (pass destination home or work). Use "
    "set_saved_place when the driver updates home or work. Keep answers short "
    "and driver-friendly - one or two sentences, no markdown."
)


def build_navigation_agent():
    return build_tool_agent(
        get_chat_model(),
        [get_route, cancel_navigation, set_saved_place, get_location, get_speed],
        SYSTEM_PROMPT,
    )
