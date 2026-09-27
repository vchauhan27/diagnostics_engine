import sys
import os
from langchain_core.messages import HumanMessage, AIMessage
from deepteam.test_case import RTTurn

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from AIAgent.agent.graph import graph

from deepteam import red_team
from deepteam.vulnerabilities import (
    Bias, Toxicity, Fairness,
    Misinformation, Hallucination,
    PersonalSafety, Ethics
)
from deepteam.attacks.single_turn import PromptInjection, Roleplay
from deepteam.attacks.multi_turn import CrescendoJailbreaking

async def model_callback(input: str, turns: list[RTTurn] | None = None) -> RTTurn:
    history = []
    for turn in (turns or []):
        if turn.role == "user":
            history.append(HumanMessage(content=turn.content))
        elif turn.role == "assistant":
            history.append(AIMessage(content=turn.content))
            
    history.append(HumanMessage(content=input))
    state = {"messages": history}
    
    result = await graph.ainvoke(state)  # type: ignore
    
    last_msg = result["messages"][-1]
    return RTTurn(
        role="assistant",
        content=str(last_msg.content)
    )

if __name__ == "__main__":
    diagnostics_vulnerabilities = [
        Bias(),
        Toxicity(),
        Fairness(),
        Misinformation(),
        Hallucination(),
        PersonalSafety(),
        Ethics()
    ]

    red_team(
        model_callback=model_callback,  # type: ignore
        target_purpose="AI Diagnostic Engine that analyzes software test failures and identifies root causes.",
        vulnerabilities=diagnostics_vulnerabilities,
        attacks=[PromptInjection(), Roleplay(), CrescendoJailbreaking()],
        attacks_per_vulnerability_type=5,
    )  # type: ignore
