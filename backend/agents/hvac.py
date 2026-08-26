from agents.base import build_tool_agent
from agents.llm import get_chat_model
from tools.vehicle_tools import get_cabin_temperature, set_temperature

SYSTEM_PROMPT = (
    "You are the HVAC agent of an in-cabin copilot. You manage cabin comfort: "
    "reading and setting the cabin temperature (16-30 C). If the driver says "
    "they are cold, raise the target; if hot, lower it. Keep answers short and "
    "driver-friendly - one sentence, no markdown."
)


def build_hvac_agent():
    return build_tool_agent(get_chat_model(), [get_cabin_temperature, set_temperature], SYSTEM_PROMPT)
