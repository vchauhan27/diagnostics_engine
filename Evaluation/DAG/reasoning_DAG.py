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
from deepeval.test_case import LLMTestCase, SingleTurnParams, ToolCall
from deepeval.metrics import DAGMetric
from deepeval.metrics.dag.graph import DeepAcyclicGraph
from deepeval.metrics.dag.nodes import BinaryJudgementNode


JUDGE_MODEL = cfg.get_judge_model()

# Tools that do NOT represent RAG evidence retrieval. Adjust to match your
# actual AIAgent/agent/tools.py if names differ.
NON_RETRIEVAL_TOOLS = {"search_test_details_tool", "parse_failure_log", "ask_user_jira_approval"}

# ---------------------------------------------------------
# DAG metric
# ---------------------------------------------------------
# A deterministic two-step reasoning gate, tailored to what THIS agent
# actually does (test-detail lookup vs. evidence-gathering diagnosis):
#
#   1. Did the agent pick an appropriate set of tools for the question --
#      evidence-gathering tools not skipped when a diagnosis was needed,
#      and not called needlessly when the question only asked for test
#      details or was purely conversational?
#      - No  -> hard fail (score 0). A wrong tool choice makes any
#               downstream reasoning suspect regardless of fluency.
#      - Yes -> check node 2.
#   2. Does the final answer's conclusion actually follow from what those
#      tools returned, without unsupported leaps?
#      - No  -> hard fail (score 0).
#      - Yes -> pass (score 1).
#
# This traces WHICH reasoning step broke, unlike a single G-Eval float --
# useful for telling "bad tool choice" apart from "right tool, bad
# synthesis of the result."

answer_follows_node = BinaryJudgementNode(
    criteria=(
        "Does the actual_output's conclusion logically follow from the "
        "evidence in the retrieval context, without unsupported leaps or "
        "claims the retrieved evidence does not back up?"
    ),
    evaluation_params=[
        SingleTurnParams.ACTUAL_OUTPUT,
        SingleTurnParams.RETRIEVAL_CONTEXT,
    ],
)
answer_follows_node.add_verdict(False, score=0)  # conclusion doesn't follow from evidence
answer_follows_node.add_verdict(True, score=1)

tool_choice_node = BinaryJudgementNode(
    criteria=(
        "Given the input question, was the set of tools called an "
        "appropriate choice -- i.e. evidence-gathering tools (historical "
        "defect / code-change search) were not skipped when the question "
        "required diagnosing a failure, and were not called needlessly "
        "when the question only asked for test details or was purely "
        "conversational?"
    ),
    evaluation_params=[
        SingleTurnParams.INPUT,
        SingleTurnParams.TOOLS_CALLED,
    ],
)
tool_choice_node.add_verdict(False, score=0)  # wrong tool choice, downstream reasoning is moot
tool_choice_node.add_verdict(True, then=answer_follows_node)

dag = DeepAcyclicGraph(root_nodes=[tool_choice_node])

reasoning_validity_gate_metric = DAGMetric(
    name="Reasoning Validity Gate",
    dag=dag,
    threshold=0.5,
    model=JUDGE_MODEL,
    async_mode=False,
)


# ---------------------------------------------------------
# Run the agent and capture retrieval context + tools called
# ---------------------------------------------------------

QUESTIONS = [
    # Should call evidence-gathering tools -> exercises "not skipped when needed".
    "Test TC-CAM-0142 failed on the Galaxy S24 Ultra with a "
    "NullPointerException in Night Mode. Are there similar past defects?",
    # Should NOT need evidence-gathering tools -> exercises "not called needlessly".
    "Please fetch the test details for TC-SYS-0021.",
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

    # Every message carrying a tool "name" attribute represents a tool call
    # made along the way.
    tools_called = [ToolCall(name=m.name, input_parameters={}) for m in messages if getattr(m, "name", None)]

    actual_output = messages[-1].content
    if isinstance(actual_output, list):
        actual_output = " ".join(b.get("text", "") for b in actual_output if isinstance(b, dict))

    return actual_output, retrieval_context, tools_called


async def main():
    test_cases = []
    for i, question in enumerate(QUESTIONS):
        actual_output, retrieval_context, tools_called = await arun_agent(
            question, thread_id=f"reasoning-dag-eval-{i}"
        )

        print(f"Q: {question}")
        print(f"Tools called: {[t.name for t in tools_called]}")
        print(f"Retrieved chunks: {len(retrieval_context)}\n")

        test_cases.append(
            LLMTestCase(
                input=question,
                actual_output=actual_output,
                retrieval_context=retrieval_context or ["No internal documents were retrieved."],  # type: ignore
                tools_called=tools_called,
            )
        )
    return test_cases

test_cases = asyncio.run(main())

evaluate(
    test_cases=test_cases,
    metrics=[reasoning_validity_gate_metric],
    async_config=AsyncConfig(run_async=False, throttle_value=1, max_concurrent=1),
)
