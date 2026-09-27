import sys
import os
from typing import Optional
from langchain_core.messages import HumanMessage, AIMessage

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from AIAgent.agent.graph import graph

from deepteam import red_team
from deepteam.test_case import RTTurn
from deepteam.vulnerabilities import (
    Toxicity, IllegalActivity, PersonalSafety,
    Bias, PIILeakage, PromptLeakage
)
from deepteam.attacks.multi_turn import (
    LinearJailbreaking, CrescendoJailbreaking, SequentialJailbreak,
    TreeJailbreaking, BadLikertJudge
)

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
    convo_vulnerabilities = [
        Toxicity(),
        IllegalActivity(),
        PersonalSafety(),
        Bias(),
        PIILeakage(),
        PromptLeakage(),
    ]

    red_team(
        model_callback=model_callback,  # type: ignore
        target_purpose="Conversational AI Diagnostic Engine that assists developers in troubleshooting code and analyzing test failures iteratively.",
        vulnerabilities=convo_vulnerabilities,
        attacks=[
            LinearJailbreaking(),
            CrescendoJailbreaking(),
            SequentialJailbreak(),
            TreeJailbreaking(),
            BadLikertJudge(),
        ],
        attacks_per_vulnerability_type=3,
    )
