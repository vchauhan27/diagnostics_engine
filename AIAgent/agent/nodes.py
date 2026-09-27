from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
import typing
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from guardrail import guardrails

from .config import llm
from .state import AgentState, JiraTicketInput, CheckDecision, DiagnosisReport, FailureInput
from .tools import (
    get_test_details,
    search_code_changes,
    search_historical_failures,
)

@tool
def search_test_details_tool(test_case_id: str) -> str:
    """Fetch details for a specific test case ID."""
    return ""

@tool
def start_diagnosis(
    test_case_id: str,
    error_type: str,
    error_message: str,
    component: str,
    build_version: str,
    environment: str,
    product_name: str,
    stack_trace: str = ""
) -> str:
    """Start the background research loop to gather evidence (historical failures, code changes) and diagnose the failure."""
    return ""

@tool
def submit_diagnosis(
    root_cause: str,
    probable_cause: str,
    affected_component: str,
    severity: str,
    priority: str,
    suggested_fix: str,
    evidence_summary: list[str]
) -> str:
    """Submit the final diagnosis to create a Jira ticket. Call this ONLY after you have gathered evidence and optionally checked with the user."""
    return ""

async def agent_node(state: AgentState, config: RunnableConfig) -> dict:
    last_msg = state.messages[-1] if state.messages else None

    # 1. Guard Input
    if last_msg and getattr(last_msg, "type", "") == "human":
        input_result = await guardrails.a_guard_input(str(last_msg.content))
        if input_result.breached:
            reasons = "\n".join([f"- {v.name} ({v.safety_level}): {v.reason}" for v in input_result.verdicts])
            return {"messages": [AIMessage(content=f"Your message was flagged by our safety system.\n\nDetails:\n{reasons}")]}

    system_prompt = SystemMessage(
        content=(
            "You are the central Brain of an AI Diagnostics Engine. "
            "Your job is to interact with the user, understand test failures, and route tasks.\n"
            "- If the user asks for test details, use the search_test_details_tool.\n"
            "- If the user wants to diagnose a failure, first ensure you have the required details (test case id, error message, etc.). Ask the user if missing.\n"
            "- Once you have the details, call start_diagnosis to launch the research loop.\n"
            "- When start_diagnosis returns evidence, analyze it and present a clear diagnosis summary to the user.\n"
            "- Then call submit_diagnosis to request Jira ticket creation — the user will be asked to approve or reject before the ticket is filed.\n"
            "- If the user has rejected the ticket (ticket_hitl_approved is False), acknowledge this gracefully and ask if they want to revise the diagnosis or take a different action."
        )
    )
    llm_with_tools = llm.bind_tools([search_test_details_tool, start_diagnosis, submit_diagnosis])
    filtered_messages = [m for m in state.messages if getattr(m, "name", None) != "system_update"]
    response = await llm_with_tools.ainvoke([system_prompt] + filtered_messages)

    # 2. Guard Output — runs on any textual content, including turns where tool calls are also present,
    # so hallucinations embedded inside submit_diagnosis arguments are caught.
    if last_msg and getattr(last_msg, "type", "") == "human" and response.content:
        output_result = await guardrails.a_guard_output(input=str(last_msg.content), output=str(response.content))
        if output_result.breached:
            return {"messages": [AIMessage(content="I'm unable to provide that information.")]}

    return {"messages": [response]}

async def tools_node(state: AgentState, config: RunnableConfig) -> dict:
    last_msg = state.messages[-1]
    msgs = []
    if isinstance(last_msg, AIMessage) and last_msg.tool_calls:
        for tc in last_msg.tool_calls:
            if tc["name"] == "search_test_details_tool":
                test_case_id = tc["args"].get("test_case_id")
                msgs.append(AIMessage(content=f"[Tool Update] Fetching test details for {test_case_id}...", name="system_update"))
                res = await get_test_details.ainvoke({"test_case_id": test_case_id})
                msgs.append(ToolMessage(content=str(res), tool_call_id=tc["id"]))
    return {"messages": msgs}

async def query_enhancement_node(state: AgentState, config: RunnableConfig) -> dict:
    failure_input = state.failure_input
    last_msg = state.messages[-1]
    if not failure_input and isinstance(last_msg, AIMessage) and last_msg.tool_calls:
        for tc in last_msg.tool_calls:
            if tc["name"] == "start_diagnosis":
                args = tc["args"]
                valid_args = {k: v for k, v in args.items() if k in FailureInput.__annotations__}
                failure_input = FailureInput(**valid_args)
                break
                
    if not failure_input:
        raise ValueError("query_enhancement_node: failure_input is missing.")
        
    prompt = f"""Enhance this test failure information into a better search query for retrieving historical failures and code changes:
Original Error: {failure_input.error_message}
Failure Details: {failure_input}

Return only the enhanced query string."""
    response = await llm.ainvoke([HumanMessage(content=prompt)])
    
    content_val = response.content
    if isinstance(content_val, list):
        content_val = " ".join(str(c.get("text", "")) for c in content_val if isinstance(c, dict) and c.get("type") == "text")
    
    query_str = str(content_val).strip()
    
    updates: dict[str, typing.Any] = {
        "enhanced_query": query_str,
        "messages": [AIMessage(content=f'[Tool Update] Enhanced query: {query_str}', name="system_update")]
    }
    if failure_input and not state.failure_input:
        updates["failure_input"] = failure_input
        
    return updates

async def evidence_gathering_node(state: AgentState, config: RunnableConfig) -> dict:
    if not state.failure_input:
        raise ValueError("evidence_gathering_node: failure_input is missing.")
    f = state.failure_input
    retrieved = dict(state.retrieved_evidence)
    
    msg_updates = []
    if not retrieved:
        # Initial retrieval
        search_query = state.enhanced_query or f.error_message
        
        msg_updates.append(AIMessage(content=f"[Tool Update] Fetching test details for {f.test_case_id}...", name="system_update"))
        retrieved["test_details"] = await get_test_details.ainvoke({"test_case_id": f.test_case_id})
        
        msg_updates.append(AIMessage(content=f"[Tool Update] Searching historical failures related to {f.component}...", name="system_update"))
        retrieved["historical_failures"] = await search_historical_failures.ainvoke({
            "error_type": f.error_type,
            "product_name": f.product_name,
            "error_message": search_query,
            "component": f.component,
            "environment": f.environment
        })
        
        msg_updates.append(AIMessage(content=f"[Tool Update] Searching code changes related to {f.component}...", name="system_update"))
        retrieved["code_changes"] = await search_code_changes.ainvoke({
            "error_message": search_query,
            "component": f.component,
            "product_name": f.product_name,
            "environment": f.environment
        })
    else:
        # Refinement retrieval based on feedback
        if state.retry_source == "historical_failures" and state.check_feedback:
            msg_updates.append(AIMessage(content=f"[Tool Update] Searching historical failures related to {f.component}...", name="system_update"))
            retrieved["historical_failures"] = await search_historical_failures.ainvoke({
                "error_type": f.error_type,
                "product_name": f.product_name,
                "error_message": state.check_feedback,
                "component": f.component,
                "environment": f.environment
            })
        elif state.retry_source == "code_changes" and state.check_feedback:
            msg_updates.append(AIMessage(content=f"[Tool Update] Searching code changes related to {f.component}...", name="system_update"))
            retrieved["code_changes"] = await search_code_changes.ainvoke({
                "error_message": state.check_feedback,
                "component": f.component,
                "product_name": f.product_name,
                "environment": f.environment
            })
    return {"retrieved_evidence": retrieved, "check_attempts": state.check_attempts + 1, "messages": msg_updates}

async def check_evidence_node(state: AgentState, config: RunnableConfig) -> dict:
    prompt = f"""Evaluate the retrieved evidence for this test failure:
Failure: {state.failure_input}
Evidence: {state.retrieved_evidence}

Is this sufficient to diagnose the root cause?
If not, provide feedback to refine the search and specify the retry_source (historical_failures or code_changes).
"""
    llm_with_struct = llm.with_structured_output(CheckDecision)
    decision = typing.cast(CheckDecision, await llm_with_struct.ainvoke([HumanMessage(content=prompt)]))
    
    updates = {
        "sufficient": decision.sufficient,
        "check_feedback": decision.feedback,
        "retry_source": decision.retry_source,
        "evidence_conflict": decision.conflict_detected,
        "evidence_conflict_reason": decision.conflict_reason
    }
    
    if decision.sufficient or state.check_attempts >= 3:
        tool_call_id = None
        for msg in reversed(state.messages):
            if isinstance(msg, AIMessage) and msg.tool_calls:
                for tc in msg.tool_calls:
                    if tc["name"] == "start_diagnosis":
                        tool_call_id = tc["id"]
                        break
            if tool_call_id:
                break
                
        if tool_call_id:
            evidence_str = str(state.retrieved_evidence)
            tool_msg = ToolMessage(content=f"Evidence gathered:\n{evidence_str}", tool_call_id=tool_call_id)
            updates["messages"] = [tool_msg]
            
    return updates

async def jira_ticket_node(state: AgentState, config: RunnableConfig) -> dict:
    last_msg = state.messages[-1]
    diagnosis = state.diagnosis
    tool_call_id = None
    
    if isinstance(last_msg, AIMessage) and last_msg.tool_calls:
        for tc in last_msg.tool_calls:
            if tc["name"] == "submit_diagnosis":
                tool_call_id = tc["id"]
                args = tc["args"]
                diagnosis = DiagnosisReport(
                    root_cause=args.get("root_cause", ""),
                    probable_cause=args.get("probable_cause", ""),
                    affected_component=args.get("affected_component", ""),
                    severity=args.get("severity", ""),
                    priority=args.get("priority", ""),
                    suggested_fix=args.get("suggested_fix", ""),
                    evidence_summary=args.get("evidence_summary", []),
                    root_cause_status="confirmed"
                )
                break
                
    if not diagnosis:
        raise ValueError("Cannot create Jira ticket: diagnosis is missing from state.")
    if not state.failure_input:
        raise ValueError("Cannot create Jira ticket: failure_input is missing from state.")

    ticket = JiraTicketInput(
        title=f"{diagnosis.root_cause} - {state.failure_input.test_case_id}",
        description=(
            f"Root Cause: {diagnosis.root_cause}\n"
            f"Probable Cause: {diagnosis.probable_cause}\n"
            f"Affected Component: {diagnosis.affected_component}\n\n"
            f"Evidence:\n" +
            "\n".join(diagnosis.evidence_summary) +
            f"\n\nSuggested Fix:\n{diagnosis.suggested_fix}"
        ),
        priority=diagnosis.priority,
        severity=diagnosis.severity,
        assignee="",
        components=[diagnosis.affected_component],
        labels=["AI-Diagnosed"],
    )

    updates = {
        "jira_ticket": ticket,
        "diagnosis": diagnosis,
        "idempotency_key": f"{state.failure_input.test_case_id}-{state.failure_input.build_version}",
        "idempotency_hit": False,
    }
    
    if tool_call_id:
        tool_msg = ToolMessage(content="Jira ticket created successfully.", tool_call_id=tool_call_id)
        updates["messages"] = [tool_msg]
        
    return updates
