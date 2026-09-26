import sys
import os
import asyncio

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

os.environ.setdefault("DEEPEVAL_PER_TASK_TIMEOUT_SECONDS_OVERRIDE", "180")
os.environ.setdefault("DEEPEVAL_PER_ATTEMPT_TIMEOUT_SECONDS_OVERRIDE", "90")

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from Evaluation import config as cfg

from AIAgent.agent import graph as agent
from AIAgent.agent.state import AgentState
from langchain_core.messages import HumanMessage

from deepeval import evaluate
from deepeval.evaluate import AsyncConfig
from deepeval.test_case import LLMTestCase, SingleTurnParams
from deepeval.metrics import GEval


JUDGE_MODEL = cfg.get_judge_model()

# ---------------------------------------------------------
# G-Eval metric
# ---------------------------------------------------------
# Checks a subjective quality that Coherence does NOT cover: does the
# diagnosis follow the expected report structure (Root Cause / Probable
# Cause, Suggested Fix, evidence clearly summarized) described in about.md?

format_adherence_metric = GEval(
    name="Format Adherence",
    evaluation_steps=[
        "Check whether the diagnosis clearly states a Root Cause (or "
        "Probable Cause when the evidence is inconclusive).",
        "Check whether a Suggested Fix is included after the root cause.",
        "Check whether the evidence used (past defects, code changes, test "
        "history) is clearly summarized and distinguished from the agent's "
        "own reasoning.",
        "Penalize heavily if the diagnosis is missing a clear root cause, "
        "a suggested fix, or fails to separate evidence from reasoning.",
    ],
    evaluation_params=[
        SingleTurnParams.INPUT,
        SingleTurnParams.ACTUAL_OUTPUT,
    ],
    threshold=0.7,
    model=JUDGE_MODEL,
    async_mode=False,
)


# ---------------------------------------------------------
# Test cases
# ---------------------------------------------------------

QUESTIONS = [
    "Test TC-CAM-0142 failed on the Galaxy S24 Ultra with a "
    "NullPointerException in Night Mode. Diagnose the root cause and "
    "suggest a fix.",
    "TC-SYS-0021 (Reboot Time) is failing intermittently. Investigate and "
    "give me a full diagnosis.",
]


async def _ainvoke(question: str, thread_id: str):
    return await agent.ainvoke(
        AgentState(messages=[HumanMessage(content=question)]),
        config={"configurable": {"thread_id": thread_id}},
    )


async def arun_agent(question: str, thread_id: str) -> str:
    result = await _ainvoke(question, thread_id)
    messages = result["messages"] if isinstance(result, dict) else result.messages
    final_content = messages[-1].content
    if isinstance(final_content, list):
        return " ".join(b.get("text", "") for b in final_content if isinstance(b, dict))
    return str(final_content)


async def main():
    test_cases = []
    for i, question in enumerate(QUESTIONS):
        # Use a unique thread_id per question to prevent cross-contamination
        # from the checkpointer's conversation history.
        actual_output = await arun_agent(question, thread_id=f"geval-eval-{i}")

        print(f"Q: {question}")
        print(f"A: {actual_output[:200]}...\n")

        test_cases.append(
            LLMTestCase(
                input=question,
                actual_output=actual_output,
            )
        )
    return test_cases

test_cases = asyncio.run(main())

evaluate(
    test_cases=test_cases,
    metrics=[format_adherence_metric],
    async_config=AsyncConfig(run_async=False, throttle_value=1, max_concurrent=1),
)
