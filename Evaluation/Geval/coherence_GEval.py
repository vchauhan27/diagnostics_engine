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
# Checks a subjective quality that Format Adherence does NOT cover: does
# the *diagnosis itself* hold together logically -- no self-contradiction,
# no non-sequiturs, evidence that actually supports the stated root cause.
# An answer can be perfectly formatted and still incoherent.

coherence_metric = GEval(
    name="Coherence",
    evaluation_steps=[
        "Check whether the actual_output is logically organized and easy to "
        "follow from start to finish.",
        "Check for any self-contradiction within the actual_output (e.g. "
        "naming one root cause early on and an incompatible one later).",
        "Check whether the evidence cited (past defects, code changes, test "
        "history) actually supports the stated root cause / conclusion, "
        "rather than being disconnected from it.",
        "Penalize outputs that read as fragmented, jump between unrelated "
        "points, or draw a conclusion that does not follow from the "
        "evidence presented.",
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
    "NullPointerException in Night Mode. Diagnose the root cause.",
    "Compare the reboot time test (TC-SYS-0021) with the Night Mode "
    "camera test (TC-CAM-0142) -- what's different about how you'd "
    "diagnose a failure in each?",
]


async def _ainvoke(question: str, thread_id: str):
    return await agent.ainvoke(
        AgentState(messages=[HumanMessage(content=question)]),
        config={"configurable": {"thread_id": thread_id}},
    )


def run_agent(question: str, thread_id: str) -> str:
    result = asyncio.run(_ainvoke(question, thread_id))
    messages = result["messages"] if isinstance(result, dict) else result.messages
    final_content = messages[-1].content
    if isinstance(final_content, list):
        return " ".join(b.get("text", "") for b in final_content if isinstance(b, dict))
    return str(final_content)


test_cases = []

for i, question in enumerate(QUESTIONS):
    # Use a unique thread_id per question to prevent cross-contamination
    # from the checkpointer's conversation history.
    actual_output = run_agent(question, thread_id=f"coherence-eval-{i}")

    print(f"Q: {question}")
    print(f"A: {actual_output[:200]}...\n")

    test_cases.append(
        LLMTestCase(
            input=question,
            actual_output=actual_output,
        )
    )

evaluate(
    test_cases=test_cases,
    metrics=[coherence_metric],
    async_config=AsyncConfig(run_async=False, throttle_value=1, max_concurrent=1),
)
