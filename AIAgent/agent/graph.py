from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.store.memory import InMemoryStore
from langchain_core.messages import AIMessage

from .nodes import (
    agent_node,
    tools_node,
    query_enhancement_node,
    evidence_gathering_node,
    check_evidence_node,
    jira_ticket_node
)
from .state import AgentState

def route_agent(state: AgentState) -> str:
    last_msg = state.messages[-1]
    if isinstance(last_msg, AIMessage) and last_msg.tool_calls:
        tc = last_msg.tool_calls[0]["name"]
        if tc == "search_test_details_tool":
            return "tools_node"
        elif tc == "start_diagnosis":
            return "query_enhancement"
        elif tc == "submit_diagnosis":
            return "jira_ticket"
    return END

def check_evidence_route(state: AgentState) -> str:
    if state.sufficient:
        return "agent_node"
    if state.check_attempts >= 3:
        return "agent_node"
    return "query_enhancement"

graph_builder = StateGraph(AgentState)

# -- Register nodes --
graph_builder.add_node("agent_node", agent_node)
graph_builder.add_node("tools_node", tools_node)
graph_builder.add_node("query_enhancement", query_enhancement_node)
graph_builder.add_node("evidence_gathering", evidence_gathering_node)
graph_builder.add_node("check_evidence", check_evidence_node)
graph_builder.add_node("jira_ticket", jira_ticket_node)

# -- Define edges --
graph_builder.add_edge(START, "agent_node")

graph_builder.add_conditional_edges(
    "agent_node",
    route_agent,
    {
        "tools_node": "tools_node",
        "query_enhancement": "query_enhancement",
        "jira_ticket": "jira_ticket",
        END: END
    }
)

graph_builder.add_edge("tools_node", "agent_node")
graph_builder.add_edge("query_enhancement", "evidence_gathering")
graph_builder.add_edge("evidence_gathering", "check_evidence")

graph_builder.add_conditional_edges(
    "check_evidence",
    check_evidence_route,
    {"query_enhancement": "query_enhancement", "agent_node": "agent_node"}
)

graph_builder.add_edge("jira_ticket", END)

graph = graph_builder.compile()
