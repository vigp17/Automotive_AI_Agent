"""Generic tool-calling agent graph (model -> tools -> model loop).

Hand-rolled instead of langgraph.prebuilt.create_react_agent to stay stable
across langgraph versions; the loop is the standard ReAct shape.
"""

from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import SystemMessage
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode


def build_tool_agent(llm: BaseChatModel, tools: list, system_prompt: str):
    model = llm.bind_tools(tools)
    tool_node = ToolNode(tools)

    def agent_node(state: MessagesState):
        messages = [SystemMessage(content=system_prompt)] + list(state["messages"])
        response = model.invoke(messages)
        return {"messages": [response]}

    def should_continue(state: MessagesState):
        last = state["messages"][-1]
        if getattr(last, "tool_calls", None):
            return "tools"
        return END

    graph = StateGraph(MessagesState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")
    return graph.compile()
