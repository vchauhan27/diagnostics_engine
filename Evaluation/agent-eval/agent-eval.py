import sys
import os
import asyncio
from pathlib import Path

# psycopg's async connection pool requires a SelectorEventLoop; Windows
# defaults to ProactorEventLoop, so switch policy before any loop is created.
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

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
from langchain_core.messages import HumanMessage

# DeepEval's LangGraph tracing hook -- required so agentic metrics have a
# trace to read from. See: https://deepeval.com/docs/evaluation-llm-tracing
from deepeval.integrations.langchain import CallbackHandler

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

# Judge model (provider configured in config.py)
JUDGE_MODEL = cfg.get_judge_model()


async def run_agent(question: str):
    """Invoke the agent once, with tracing enabled via CallbackHandler."""
    return await agent.ainvoke(
        AgentState(messages=[HumanMessage(content=question)]),
        config={
            "configurable": {"thread_id": "agent-eval"},
            "callbacks": [CallbackHandler()],
        },
    )


# ---------------------------------------------------------------------------
# Two goldens, matching the engine's two real capabilities (see about.md):
#   1. Fetch test details for a test case that exists in the seeded DB.
#   2. Upload the seeded failure log and let the engine diagnose it.
# expected_tools lets ToolCorrectnessMetric / ArgumentCorrectnessMetric
# check tool selection off the same trace as the trajectory metrics below.
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
            expected_tools=[
                ToolCall(name="parse_failure_log", input_parameters={}),
            ], multimodal=False,
        ),
    ]
)

trajectory_metrics = [
    TaskCompletionMetric(threshold=0.7, model=JUDGE_MODEL, async_mode=False),
    StepEfficiencyMetric(threshold=0.7, model=JUDGE_MODEL, async_mode=False),
    PlanAdherenceMetric(threshold=0.7, model=JUDGE_MODEL, async_mode=False),
    PlanQualityMetric(threshold=0.7, model=JUDGE_MODEL, async_mode=False),
]

tool_metrics = [
    ToolCorrectnessMetric(threshold=0.7, model=JUDGE_MODEL, include_reason=True, async_mode=False),
    ArgumentCorrectnessMetric(threshold=0.7, model=JUDGE_MODEL, include_reason=True, async_mode=False),
]

print("=" * 70)
print("Diagnostics Engine: Agentic Evaluation (Trajectory)")
print("=" * 70)

for golden in dataset.evals_iterator(metrics=trajectory_metrics):
    task = asyncio.create_task(run_agent(golden.input))
    dataset.evaluate(task)

print("\n" + "=" * 70)
print("Diagnostics Engine: Tool-call-based agentic metrics")
print("=" * 70)

tool_test_cases = []

_global_loop = asyncio.new_event_loop()
asyncio.set_event_loop(_global_loop)

def get_tool_calls(question: str):
    result = _global_loop.run_until_complete(run_agent(question))
    messages = result["messages"] if isinstance(result, dict) else getattr(result, "messages", [])
    
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

for item in dataset.goldens:
    if not isinstance(item, Golden):
        continue
    
    actual_output, tools_called = get_tool_calls(item.input)
    
    tool_test_cases.append(
        LLMTestCase(
            input=item.input,
            actual_output=actual_output,
            tools_called=tools_called,
            expected_tools=item.expected_tools,
        )
    )

if tool_test_cases:
    evaluate(
        test_cases=tool_test_cases,
        metrics=tool_metrics,
        async_config=AsyncConfig(run_async=False)
    )