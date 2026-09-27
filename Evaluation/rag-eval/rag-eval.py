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
from deepeval.test_case import LLMTestCase
from deepeval.metrics import (
    AnswerRelevancyMetric,
    FaithfulnessMetric,
    ContextualRelevancyMetric,
    ContextualPrecisionMetric,
    ContextualRecallMetric,
)

JUDGE_MODEL = cfg.get_judge_model()


async def _ainvoke(question: str, thread_id: str):
    return await agent.ainvoke(
        AgentState(messages=[HumanMessage(content=question)]),
        config={"configurable": {"thread_id": thread_id}},
    )


async def run_agent(question: str, thread_id: str):
    result = await _ainvoke(question, thread_id)
    return result["messages"] if isinstance(result, dict) else result.messages


# Tools that do NOT represent RAG evidence retrieval (the pgvector search
# over past defects / code changes). Adjust these names to match
# AIAgent/agent/tools.py if they differ in your codebase.
NON_RETRIEVAL_TOOLS = {"search_test_details_tool", "parse_failure_log", "ask_user_jira_approval"}


# ---------------------------------------------------------
# Test case -- grounded in the seeded fake data (see about.md): TC-CAM-0142
# failing with a NullPointerException in Night Mode on the Galaxy S24
# Ultra, with two related seeded defects (BUG-101, BUG-102).
# ---------------------------------------------------------

TEST_CASES = [
    {
        "input": (
            "Test TC-CAM-0142 failed on the Galaxy S24 Ultra with a "
            "NullPointerException in SemMultiFrameFusionEngine.allocateBuffer() "
            "during Night Mode capture. Are there any similar past defects, "
            "and could a recent code change have caused this?"
        ),
        "expected_output": (
            "The failure is a NullPointerException thrown in "
            "SemMultiFrameFusionEngine.allocateBuffer() while running Night "
            "Mode on the Galaxy S24 Ultra. This is semantically similar to two "
            "seeded defects: BUG-101 (Camera App crashes on launch in Night "
            "Mode) and BUG-102 (Blurry images in Night Mode). The agent should "
            "also check for recent code changes to the camera/Night Mode "
            "component that could explain the regression."
        ),
    }
]


# ---------------------------------------------------------
# Metrics -- all share the same config, so build them in a loop
# ---------------------------------------------------------

metrics = [
    AnswerRelevancyMetric(threshold=0.7, model=JUDGE_MODEL, include_reason=True, async_mode=False),
    FaithfulnessMetric(threshold=0.7, model=JUDGE_MODEL, include_reason=True, async_mode=False),
    ContextualRelevancyMetric(threshold=0.7, model=JUDGE_MODEL, include_reason=True, async_mode=False),
    ContextualPrecisionMetric(threshold=0.7, model=JUDGE_MODEL, include_reason=True, async_mode=False),
    ContextualRecallMetric(threshold=0.7, model=JUDGE_MODEL, include_reason=True, async_mode=False),
]

async def main():
    test_cases = []

    for i, item in enumerate(TEST_CASES):
        messages = await run_agent(item["input"], thread_id=f"rag-eval-{i}")

        retrieval_context = [
            str(m.content) for m in messages
            if getattr(m, "name", None) and m.name not in NON_RETRIEVAL_TOOLS
        ]

        actual_output = messages[-1].content
        if isinstance(actual_output, list):
            actual_output = " ".join(b.get("text", "") for b in actual_output if isinstance(b, dict))

        print(f"Q: {item['input']}")
        print(f"Retrieved chunks: {len(retrieval_context)}\n")

        if not retrieval_context:
            print("  Skipping RAG-context metrics (no evidence retrieval occurred).\n")
            continue

        test_cases.append(
            LLMTestCase(
                input=item["input"],
                actual_output=actual_output,
                expected_output=item["expected_output"],
                retrieval_context=retrieval_context,  # type: ignore
            )
        )

    if test_cases:
        evaluate(
            test_cases=test_cases,
            metrics=metrics,
            async_config=AsyncConfig(run_async=False, throttle_value=1, max_concurrent=1),
        )
    else:
        print("No test cases had retrieval context to evaluate against.")


asyncio.run(main())