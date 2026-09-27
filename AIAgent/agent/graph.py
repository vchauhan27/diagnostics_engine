from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.store.memory import InMemoryStore
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.types import interrupt
from .state import AgentState

from .nodes import (
    agent_node,
    tools_node,
    query_enhancement_node,
    evidence_gathering_node,
    check_evidence_node,
    jira_ticket_node
)

async def jira_approval_node(state):
    """Pause and ask the human to approve or reject the Jira ticket before creation."""
    diagnosis = state.diagnosis
    # Build a clean approval payload shown in the UI interrupt card
    approval_payload = {
        "action": "approve_jira_ticket",
        "message": "The diagnosis is ready. Do you want to create a Jira ticket?",
        "diagnosis": {
            "root_cause": diagnosis.root_cause if diagnosis else "",
            "probable_cause": diagnosis.probable_cause if diagnosis else "",
            "severity": diagnosis.severity if diagnosis else "",
            "priority": diagnosis.priority if diagnosis else "",
            "suggested_fix": diagnosis.suggested_fix if diagnosis else "",
            "affected_component": diagnosis.affected_component if diagnosis else "",
        },
    }
    decision = interrupt(approval_payload)
    approved = decision.get("approved", False) if isinstance(decision, dict) else False
    notes = decision.get("notes", "") if isinstance(decision, dict) else ""
    return {
        "ticket_hitl_approved": approved,
        "ticket_hitl_notes": notes,
    }

def route_after_approval(state) -> str:
    if state.ticket_hitl_approved:
        return "jira_ticket"
    # Rejected — inject a ToolMessage so agent can respond with rejection context
    return "agent_node"

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
graph_builder.add_node("jira_approval", jira_approval_node)
graph_builder.add_node("jira_ticket", jira_ticket_node)

# -- Define edges --
graph_builder.add_edge(START, "agent_node")

graph_builder.add_conditional_edges(
    "agent_node",
    route_agent,
    {
        "tools_node": "tools_node",
        "query_enhancement": "query_enhancement",
        "jira_ticket": "jira_approval",   # route to approval gate first
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

graph_builder.add_conditional_edges(
    "jira_approval",
    route_after_approval,
    {"jira_ticket": "jira_ticket", "agent_node": "agent_node"}
)

graph_builder.add_edge("jira_ticket", "agent_node")

graph = graph_builder.compile()
