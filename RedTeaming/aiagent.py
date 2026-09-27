import sys
import os
import json
from typing import Optional
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from AIAgent.agent.graph import graph

from deepteam import red_team
from deepteam.test_case import RTTurn, ToolCall
from deepteam.vulnerabilities import (
    GoalTheft, ExcessiveAgency, ToolOrchestrationAbuse,
    ExploitToolAgent, IndirectInstruction, AutonomousAgentDrift
)
from deepteam.attacks.single_turn import (
    ContextPoisoning, GoalRedirection,
    SystemOverride, PermissionEscalation
)
from deepteam.attacks.multi_turn import LinearJailbreaking

async def model_callback(input: str, turns: list[RTTurn] | None = None) -> RTTurn:
    history = []
    for turn in (turns or []):
        if turn.role == "user":
            history.append(HumanMessage(content=turn.content))
        elif turn.role == "assistant":
            history.append(AIMessage(content=turn.content))
            
    history.append(HumanMessage(content=input))
    old_msg_count = len(history)
    
    state = {"messages": history}
    result = await graph.ainvoke(state)  # type: ignore
    
    new_messages = result["messages"][old_msg_count:]
    last_msg = result["messages"][-1]
    
    # Extract tool calls that occurred in this run
    tools_called = []
    for msg in new_messages:
        if getattr(msg, "type", "") == "ai" and getattr(msg, "tool_calls", None):
            for tc in msg.tool_calls:
                # Find matching ToolMessage for output
                output = ""
                for m in new_messages:
                    if getattr(m, "type", "") == "tool" and getattr(m, "tool_call_id", "") == tc.get("id"):
                        output = str(m.content)
                        break
                
                tools_called.append(
                    ToolCall(
                        name=tc.get("name", ""),
                        input_parameters=tc.get("args", {}),
                        output=output
                    )
                )

    return RTTurn(
        role="assistant",
        content=str(last_msg.content),
        tools_called=tools_called
    )

if __name__ == "__main__":
    red_team(
        model_callback=model_callback,  # type: ignore
        target_purpose="AI Diagnostic Engine that analyzes software test failures and creates Jira tickets.",
        vulnerabilities=[
            GoalTheft(),
            ExcessiveAgency(),
            ToolOrchestrationAbuse(),
            ExploitToolAgent(),
            IndirectInstruction(),
            AutonomousAgentDrift(),
        ],
        attacks=[
            ContextPoisoning(),
            GoalRedirection(),
            SystemOverride(),
            PermissionEscalation(),
            LinearJailbreaking(),
        ],
        attacks_per_vulnerability_type=5,
    )
