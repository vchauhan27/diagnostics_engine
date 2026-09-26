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
from deepeval.test_case import Turn, MultiTurnParams, ConversationalTestCase
from deepeval.metrics import ConversationalDAGMetric
from deepeval.metrics.dag.graph import DeepAcyclicGraph
from deepeval.metrics.conversational_dag.nodes import ConversationalBinaryJudgementNode


JUDGE_MODEL = cfg.get_judge_model()

# ---------------------------------------------------------
# Run a multi-turn conversation on one thread_id
# ---------------------------------------------------------

CONVERSATION = [
    "I'm investigating a failure on the Galaxy S24 Ultra, One UI 6.1 build "
    "-- test TC-CAM-0142.",
    "Given what I just told you, what past defects should I check first?",
]


async def _ainvoke(question: str, thread_id: str):
    return await agent.ainvoke(
        AgentState(messages=[HumanMessage(content=question)]),
        config={"configurable": {"thread_id": thread_id}},
    )


async def arun_conversation(questions, thread_id="dag-conversation-1"):
    result = None
    for question in questions:
        result = await _ainvoke(question, thread_id)
    if result is None:
        return []
    return result["messages"] if isinstance(result, dict) else result.messages


def to_turns(messages):
    turns = []
    for message in messages:
        kind = type(message).__name__
        if kind == "HumanMessage":
            turns.append(Turn(role="user", content=message.content))
        elif kind == "AIMessage" and message.content:
            content = message.content
            if isinstance(content, list):
                content = " ".join(b.get("text", "") for b in content if isinstance(b, dict))
            turns.append(Turn(role="assistant", content=content))
    return turns


messages = asyncio.run(arun_conversation(CONVERSATION))
turns = to_turns(messages)

print("Conversation:")
for turn in turns:
    print(f"  [{turn.role}] {turn.content[:150]}")
print()

convo_test_case = ConversationalTestCase(turns=turns)


# ---------------------------------------------------------
# Conversational DAG metric
# ---------------------------------------------------------
# Deterministic gate instead of one holistic judgement: did the assistant
# correctly recall the fact the user shared earlier when it was relevant
# to a later reply? True -> full score, False -> hard fail.

recall_check = ConversationalBinaryJudgementNode(
    criteria=(
        "Did the assistant correctly recall and use the fact the user "
        "shared in an earlier turn (device model, build version, or test "
        "case ID) when answering a later, related question?"
    ),
    evaluation_params=[MultiTurnParams.ROLE, MultiTurnParams.CONTENT],
)
recall_check.add_verdict(verdict=False, score=0)
recall_check.add_verdict(verdict=True, score=10)

dag = DeepAcyclicGraph(root_nodes=[recall_check])

memory_recall_gate_metric = ConversationalDAGMetric(
    name="Memory Recall Gate",
    dag=dag,
    threshold=0.5,
    model=JUDGE_MODEL,
    async_mode=False,
)

evaluate(
    test_cases=[convo_test_case],
    metrics=[memory_recall_gate_metric],
    async_config=AsyncConfig(run_async=False, throttle_value=1, max_concurrent=1),
)
