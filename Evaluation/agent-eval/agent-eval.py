import sys
import os
import asyncio
import time
from pathlib import Path

# psycopg's async connection pool requires a SelectorEventLoop; Windows
# defaults to ProactorEventLoop, so switch policy before any loop is created.
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    if hasattr(sys.stdout, 'reconfigure'):
        getattr(sys.stdout, 'reconfigure')(encoding='utf-8')

import nest_asyncio
nest_asyncio.apply()


# Give the judge-model LLM calls more time before DeepEval gives up.
# Must be set before any deepeval module is imported/used (settings are cached).
os.environ["DEEPEVAL_PER_TASK_TIMEOUT_SECONDS_OVERRIDE"] = "900"
os.environ["DEEPEVAL_PER_ATTEMPT_TIMEOUT_SECONDS_OVERRIDE"] = "300"

# Add the project root to sys.path so we can import Evaluation and AIAgent
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from Evaluation import config as cfg

from AIAgent.agent import graph as agent
from AIAgent.agent.state import AgentState
from langchain_core.messages import HumanMessage, AIMessage

# Follow AIAgent.md pattern: use @observe decorator instead of CallbackHandler
from deepeval.tracing import observe, update_current_span

from deepeval import evaluate
from deepeval.evaluate import AsyncConfig
from deepeval.dataset import EvaluationDataset, Golden
from deepeval.test_case import ToolCall, LLMTestCase
from deepeval.metrics import (
    TaskCompletionMetric,
    StepEfficiencyMetric,
    PlanAdherenceMetric,
    PlanQualityMetric,
    ToolCorrectnessMetric,
    ArgumentCorrectnessMetric,
)

# Judge model (provider configured in config.py — uses Gemini for structured JSON output)
JUDGE_MODEL = cfg.get_judge_model()

_loop = asyncio.get_event_loop()


@observe(type="agent")
async def run_agent(question: str, thread_id: str = "agent-eval"):
    """Invoke the agent once with tracing. Each golden gets a unique thread_id
    so the LangGraph checkpointer doesn't bleed history between test cases.

    FIX: update_current_span populates the span's input/output fields so that
    DeepEval trajectory metrics can read the final agent output from the trace
    (instead of seeing an empty span with no context).
    """
    result = await agent.ainvoke(
        AgentState(messages=[HumanMessage(content=question)]),
        config={
            "configurable": {"thread_id": thread_id},
        },
    )

    # Extract final agent output for the span — strip system_update messages first
    # so internal "[Tool Update] ..." messages don't appear as agent output in the trace.
    messages = result.get("messages", []) if isinstance(result, dict) else getattr(result, "messages", [])
    visible_messages = [m for m in messages if getattr(m, "name", None) != "system_update"]
    last = visible_messages[-1] if visible_messages else None
    final_content = last.content if last else ""
    if isinstance(final_content, list):
        final_content = " ".join(b.get("text", "") for b in final_content if isinstance(b, dict))

    update_current_span(
        input=question,
        output=str(final_content),
    )

    return result


# ---------------------------------------------------------------------------
# Two goldens matching the engine's two real capabilities (see about.md):
#   1. Fetch test details for a test case that exists in the seeded DB.
#   2. Send a raw failure log — agent should parse and call start_diagnosis.
#
# FIX: The second golden previously expected `parse_failure_log`, a tool that
# does not exist in the agent.  The agent's correct behaviour is to call
# `start_diagnosis` after parsing the log content from the user message.
# expected_tools is updated to reflect what the agent *actually does*.
# ---------------------------------------------------------------------------

sample_log_path = Path(project_root) / "indexer" / "data" / "sample.log"
try:
    sample_log_content = sample_log_path.read_text(encoding="utf-8").strip()
except Exception as e:
    raise SystemExit(f"Failed to read {sample_log_path}: {e}")

dataset = EvaluationDataset(
    goldens=[
        Golden(
            input="Please fetch the test details for TC-SYS-0021.",
            expected_tools=[
                ToolCall(name="search_test_details_tool", input_parameters={"test_case_id": "TC-SYS-0021"}),
            ], multimodal=False,
        ),
        Golden(
            input=sample_log_content,
            # FIX: was parse_failure_log (non-existent tool) — agent correctly calls start_diagnosis
            expected_tools=[
                ToolCall(name="start_diagnosis", input_parameters={}),
            ], multimodal=False,
        ),
    ]
)

# Run each metric individually with a 15-second sleep between them so the
# Gemini judge model doesn't hit the Google API rate limit.
_INTER_METRIC_SLEEP = 15

# Trajectory metrics — each gets its own evals_iterator pass so we can
# sleep between judge calls.  The agent is re-invoked per golden per metric.
traj_metric_classes = [
    ("Task Completion",  TaskCompletionMetric(threshold=0.7,  model=JUDGE_MODEL, async_mode=False)),
    ("Step Efficiency",  StepEfficiencyMetric(threshold=0.7,  model=JUDGE_MODEL, async_mode=False)),
    ("Plan Adherence",   PlanAdherenceMetric(threshold=0.7,   model=JUDGE_MODEL, async_mode=False)),
    ("Plan Quality",     PlanQualityMetric(threshold=0.7,     model=JUDGE_MODEL, async_mode=False)),
]

tool_metric_classes = [
    ("Tool Correctness",    ToolCorrectnessMetric(threshold=0.7,    model=JUDGE_MODEL, include_reason=True, async_mode=False)),
    ("Argument Correctness", ArgumentCorrectnessMetric(threshold=0.7, model=JUDGE_MODEL, include_reason=True, async_mode=False)),
]

print("=" * 70)
print("Diagnostics Engine: Agentic Evaluation (Trajectory)")
print("=" * 70)

# Guide pattern: call the agent synchronously inside evals_iterator so
# DeepEval can attach the LangGraph trace to each golden's evaluation.
# Each metric runs in its own pass; a sleep is inserted between metrics
# to stay within the Gemini API rate limit.
for idx, (metric_name, metric) in enumerate(traj_metric_classes):
    print(f"\n[{idx+1}/{len(traj_metric_classes)}] Running trajectory metric: {metric_name}")
    for i, golden in enumerate(dataset.evals_iterator(metrics=[metric])):
        _loop.run_until_complete(run_agent(golden.input, thread_id=f"traj-{idx}-eval-{i}"))
    if idx < len(traj_metric_classes) - 1:
        print(f"  Sleeping {_INTER_METRIC_SLEEP}s to avoid API rate limit...")
        time.sleep(_INTER_METRIC_SLEEP)

print("\n" + "=" * 70)
print("Diagnostics Engine: Tool-call-based agentic metrics")
print("=" * 70)

tool_test_cases = []


def get_tool_calls(question: str, thread_id: str):
    result = _loop.run_until_complete(run_agent(question, thread_id=thread_id))
    messages = result["messages"] if isinstance(result, dict) else getattr(result, "messages", [])

    # FIX: Filter out internal system_update messages before building the test
    # case.  These "[Tool Update] ..." AIMessages are injected by nodes.py for
    # UI progress reporting only — they must not appear as agent tool calls or
    # output content in the eval, as they inflate step counts and confuse
    # PlanAdherenceMetric into flagging them as extraneous actions.
    messages = [m for m in messages if getattr(m, "name", None) != "system_update"]

    tools_called = []
    for message in messages:
        for call in getattr(message, "tool_calls", None) or []:
            tools_called.append(ToolCall(name=call["name"], input_parameters=call.get("args", {})))

    final_content = messages[-1].content if messages else ""
    if isinstance(final_content, list):
        actual_output = " ".join(block.get("text", "") for block in final_content if isinstance(block, dict))
    else:
        actual_output = str(final_content)

    return actual_output, tools_called

for i, item in enumerate(dataset.goldens):
    if not isinstance(item, Golden):
        continue

    actual_output, tools_called = get_tool_calls(item.input, thread_id=f"tool-eval-{i}")

    tool_test_cases.append(
        LLMTestCase(
            input=item.input,
            actual_output=actual_output,
            tools_called=tools_called,
            expected_tools=item.expected_tools,
        )
    )

if tool_test_cases:
    # Sleep before starting tool metrics to give the API a breather after trajectory evals.
    print(f"\nSleeping {_INTER_METRIC_SLEEP}s before tool metrics...")
    time.sleep(_INTER_METRIC_SLEEP)

    for idx, (metric_name, metric) in enumerate(tool_metric_classes):
        print(f"\n[{idx+1}/{len(tool_metric_classes)}] Running tool metric: {metric_name}")
        evaluate(
            test_cases=tool_test_cases,
            metrics=[metric],
            async_config=AsyncConfig(run_async=False)
        )
        if idx < len(tool_metric_classes) - 1:
            print(f"  Sleeping {_INTER_METRIC_SLEEP}s to avoid API rate limit...")
            time.sleep(_INTER_METRIC_SLEEP)