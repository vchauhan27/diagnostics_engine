import sys
import os
import asyncio
import time

from langchain_core.messages import ToolMessage

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


# Tools whose ToolMessage responses ARE RAG evidence (pgvector search results).
# Guide (rag.md): retrieval_context = the actual retrieved text chunks from the
# retriever. Only ToolMessages from search tools count — not control/status messages.
RETRIEVAL_TOOLS = {"search_historical_failures", "search_code_changes"}

# Kept for backward-compat (used in retrieval_context guard below).
NON_RETRIEVAL_TOOLS = {"search_test_details_tool", "parse_failure_log", "ask_user_jira_approval", "system_update"}


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

# 15-second sleep between each metric to avoid Gemini API rate limits.
_INTER_METRIC_SLEEP = 15

metrics = [
    ("Answer Relevancy",        AnswerRelevancyMetric(threshold=0.7, model=JUDGE_MODEL, include_reason=True, async_mode=False)),
    ("Faithfulness",            FaithfulnessMetric(threshold=0.7, model=JUDGE_MODEL, include_reason=True, async_mode=False)),
    ("Contextual Relevancy",    ContextualRelevancyMetric(threshold=0.7, model=JUDGE_MODEL, include_reason=True, async_mode=False)),
    ("Contextual Precision",    ContextualPrecisionMetric(threshold=0.7, model=JUDGE_MODEL, include_reason=True, async_mode=False)),
    ("Contextual Recall",       ContextualRecallMetric(threshold=0.7, model=JUDGE_MODEL, include_reason=True, async_mode=False)),
]

async def main():
    test_cases = []

    for i, item in enumerate(TEST_CASES):
        messages = await run_agent(item["input"], thread_id=f"rag-eval-{i}")

        # Guide (rag.md): retrieval_context is the list of text chunks the
        # retriever pulled. Only ToolMessage responses from the RAG search tools
        # count — not AIMessage system_update strings or test-detail lookups.
        retrieval_context = [
            str(m.content) for m in messages
            if isinstance(m, ToolMessage) and getattr(m, "name", None) in RETRIEVAL_TOOLS
        ]

        # Filter system_update progress messages before taking the final output
        # so [Tool Update] strings are never treated as the agent's answer.
        visible = [m for m in messages if getattr(m, "name", None) != "system_update"]
        actual_output = visible[-1].content if visible else ""
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
        # Run each metric individually with a sleep between them to avoid
        # hitting the Gemini API rate limit.
        for idx, (metric_name, metric) in enumerate(metrics):
            print(f"\n[{idx+1}/{len(metrics)}] Evaluating: {metric_name}")
            evaluate(
                test_cases=test_cases,
                metrics=[metric],
                async_config=AsyncConfig(run_async=False, throttle_value=1, max_concurrent=1),
            )
            if idx < len(metrics) - 1:
                print(f"  Sleeping {_INTER_METRIC_SLEEP}s to avoid API rate limit...")
                time.sleep(_INTER_METRIC_SLEEP)
    else:
        print("No test cases had retrieval context to evaluate against.")


asyncio.run(main())