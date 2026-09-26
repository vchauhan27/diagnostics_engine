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
from deepeval.metrics import DAGMetric
from deepeval.metrics.dag.graph import DeepAcyclicGraph
from deepeval.metrics.dag.nodes import BinaryJudgementNode


JUDGE_MODEL = cfg.get_judge_model()

# Tools that do NOT represent RAG evidence retrieval (the pgvector search
# over past defects / code changes). Adjust to match AIAgent/agent/tools.py
# if your tool names differ.
NON_RETRIEVAL_TOOLS = {"search_test_details_tool", "parse_failure_log", "ask_user_jira_approval"}

# ---------------------------------------------------------
# DAG metric
# ---------------------------------------------------------
# A deterministic rule tree instead of a single subjective judgement:
#   1. Does the answer reference retrieved evidence (past defects / code
#      changes) at all?
#      - No  -> nothing to hallucinate, automatic pass (score 1).
#      - Yes -> check node 2.
#   2. Is every evidence-based claim actually backed by the retrieved
#      context?
#      - No  -> hard fail (score 0), regardless of anything else.
#      - Yes -> pass (score 1).

grounded_node = BinaryJudgementNode(
    criteria=(
        "Is every claim in the actual output about past defects, code "
        "changes, or test history directly supported by the retrieval "
        "context?"
    ),
    evaluation_params=[
        SingleTurnParams.ACTUAL_OUTPUT,
        SingleTurnParams.RETRIEVAL_CONTEXT,
    ],
)
grounded_node.add_verdict(False, score=0)  # hallucinated evidence-based claim
grounded_node.add_verdict(True, score=1)

# Check retrieval_context directly (deterministic) instead of asking the judge
# to read the actual_output. This prevents false positives where the agent
# explicitly says "no related evidence was found" -- which mentions evidence
# in the output but means NO evidence-based claims were actually made.
uses_evidence_node = BinaryJudgementNode(
    criteria=(
        "Does the retrieval context contain actual retrieved evidence "
        "(i.e., it is NOT empty and does NOT consist solely of the string "
        "'No internal documents were retrieved.')?"
    ),
    evaluation_params=[SingleTurnParams.RETRIEVAL_CONTEXT],
)
uses_evidence_node.add_verdict(False, score=1)  # no evidence retrieval -> nothing to check
uses_evidence_node.add_verdict(True, then=grounded_node)

dag = DeepAcyclicGraph(root_nodes=[uses_evidence_node])

groundedness_gate_metric = DAGMetric(
    name="Evidence Groundedness Gate",
    dag=dag,
    threshold=0.5,
    model=JUDGE_MODEL,
    async_mode=False,
)


# ---------------------------------------------------------
# Run the agent and capture retrieval context
# ---------------------------------------------------------

QUESTIONS = [
    # Should trigger evidence retrieval -> exercises the grounded_node check.
    "Test TC-CAM-0142 failed on the Galaxy S24 Ultra with a "
    "NullPointerException in Night Mode. Are there similar past defects?",
    # Purely conversational, non-diagnostic (per about.md) -> should trigger
    # no retrieval, exercising the auto-pass branch.
    "Hi there! How do I use this tool?",
]


async def _ainvoke(question: str, thread_id: str):
    return await agent.ainvoke(
        AgentState(messages=[HumanMessage(content=question)]),
        config={"configurable": {"thread_id": thread_id}},
    )


async def arun_agent(question: str, thread_id: str):
    result = await _ainvoke(question, thread_id)
    messages = result["messages"] if isinstance(result, dict) else result.messages

    retrieval_context = [
        str(m.content) for m in messages
        if getattr(m, "name", None) and m.name not in NON_RETRIEVAL_TOOLS
    ]

    actual_output = messages[-1].content
    if isinstance(actual_output, list):
        actual_output = " ".join(b.get("text", "") for b in actual_output if isinstance(b, dict))

    return actual_output, retrieval_context


async def main():
    test_cases = []
    for i, question in enumerate(QUESTIONS):
        actual_output, retrieval_context = await arun_agent(question, thread_id=f"dag-eval-{i}")

        print(f"Q: {question}")
        print(f"Retrieved chunks: {len(retrieval_context)}\n")

        test_cases.append(
            LLMTestCase(
                input=question,
                actual_output=actual_output,
                retrieval_context=retrieval_context or ["No internal documents were retrieved."],  # type: ignore
            )
        )
    return test_cases

test_cases = asyncio.run(main())

evaluate(
    test_cases=test_cases,
    metrics=[groundedness_gate_metric],
    async_config=AsyncConfig(run_async=False, throttle_value=1, max_concurrent=1),
)
