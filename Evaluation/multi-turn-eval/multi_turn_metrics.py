"""
Runs 11 multi-turn DeepEval metrics, each against one golden question,
against the AI Diagnostics Engine.
For deeper signal, extend any run_case() call with follow-up turns on the
same thread_id.
"""

import sys
import os
import asyncio
import uuid

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
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

from deepeval.test_case import Turn, ConversationalTestCase, ToolCall
from deepeval.metrics import (
    TurnRelevancyMetric,
    RoleAdherenceMetric,
    KnowledgeRetentionMetric,
    ConversationCompletenessMetric,
    GoalAccuracyMetric,
    ToolUseMetric,
    TopicAdherenceMetric,
    TurnFaithfulnessMetric,
    TurnContextualPrecisionMetric,
    TurnContextualRecallMetric,
    TurnContextualRelevancyMetric,
)


EVAL_MODEL = cfg.get_judge_model()



# ---------------------------------------------------------------------------
# Tool inventory (for ToolUseMetric's required `available_tools`). Tries to
# import the real tool objects; falls back to name-only ToolCalls if your
# AIAgent/agent/tools.py exposes them under different names -- update the
# import and the fallback list below to match.
# ---------------------------------------------------------------------------

try:
    from AIAgent.agent.tools import (
        get_test_details,
        search_code_changes,
        parse_failure_log,
        ask_user_jira_approval,
    )
    AVAILABLE_TOOLS = [
        ToolCall(name=t.name, input_parameters={})
        for t in (get_test_details, search_code_changes, parse_failure_log, ask_user_jira_approval)
    ]
except ImportError:
    AVAILABLE_TOOLS = [
        ToolCall(name="get_test_details", input_parameters={}),
        ToolCall(name="search_code_changes", input_parameters={}),
        ToolCall(name="parse_failure_log", input_parameters={}),
        ToolCall(name="ask_user_jira_approval", input_parameters={}),
    ]

# Tools that do NOT represent RAG evidence retrieval. Adjust to match your
# actual tools.py if the semantic-search-over-defects tool has a different name.
NON_RETRIEVAL_TOOLS = {"search_test_details_tool", "parse_failure_log", "ask_user_jira_approval"}


# ---------------------------------------------------------------------------
# Helpers: run the live agent and turn its trace into DeepEval Turns
# ---------------------------------------------------------------------------

_global_loop = asyncio.new_event_loop()
asyncio.set_event_loop(_global_loop)

async def _ainvoke(question: str, thread_id: str):
    return await agent.ainvoke(
        AgentState(messages=[HumanMessage(content=question)]),
        config={"configurable": {"thread_id": thread_id}},
    )


def run_agent_turn(question: str, thread_id: str):
    """Invoke the diagnostics agent once and return its full message trace."""
    result = _global_loop.run_until_complete(_ainvoke(question, thread_id))
    return result["messages"] if isinstance(result, dict) else result.messages


def build_all_turns(messages):
    """
    Parse a full LangGraph message trace containing multiple HumanMessages
    into a list of DeepEval Turns.
    """
    turns = []
    current_user_msg = None
    tools_called = []
    retrieval_context = []
    final_content = None

    def finalize_turn():
        nonlocal current_user_msg, tools_called, retrieval_context, final_content
        if current_user_msg:
            # Add User Turn
            if isinstance(current_user_msg, list):
                user_content = " ".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in current_user_msg)
            else:
                user_content = str(current_user_msg)
            turns.append(Turn(role="user", content=user_content))
            
            # Add AI Turn
            if isinstance(final_content, list):
                ai_content = " ".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in final_content)
            else:
                ai_content = str(final_content) if final_content else ""
                
            turns.append(Turn(
                role="assistant",
                content=ai_content,
                tools_called=tools_called or None,
                retrieval_context=retrieval_context or None,
            ))
            
        current_user_msg = None
        tools_called = []
        retrieval_context = []
        final_content = None

    for msg in messages:
        if isinstance(msg, HumanMessage):
            finalize_turn()
            current_user_msg = msg.content
        elif isinstance(msg, AIMessage):
            if getattr(msg, "tool_calls", None):
                for tc in msg.tool_calls:
                    tools_called.append(
                        ToolCall(name=tc["name"], input_parameters=tc.get("args", {}) or {})
                    )
            if msg.content:
                final_content = msg.content
        elif isinstance(msg, ToolMessage):
            if getattr(msg, "name", None) and msg.name not in NON_RETRIEVAL_TOOLS:
                retrieval_context.append(str(msg.content))
                
    finalize_turn()
    return turns


RESULTS = []


def run_case(label, questions, metric, **test_case_kwargs):
    """Run golden question(s) through the agent and measure one metric."""
    if isinstance(questions, str):
        questions = [questions]
        
    thread_id = f"eval-{label}-{uuid.uuid4().hex[:8]}"
    
    messages = []
    for q in questions:
        messages = run_agent_turn(q, thread_id)
        
    turns = build_all_turns(messages)
    test_case = ConversationalTestCase(turns=turns, **test_case_kwargs)

    print("\n" + "=" * 70)
    print(label)
    print("=" * 70)
    for turn in turns:
        role_label = "Q" if turn.role == "user" else "A"
        print(f"{role_label}: {turn.content[:400]}")

    metric.measure(test_case)

    print(f"\nScore : {metric.score}")
    print(f"Reason: {metric.reason}")

    RESULTS.append((label, metric.score))
    return test_case, metric


# ---------------------------------------------------------------------------
# 11 metrics x 11 golden questions, grounded in the seeded fake data
# (Galaxy S24 Ultra / TC-CAM-0142 Night Mode NullPointerException, and
# TC-SYS-0021 Reboot Time -- see about.md).
# ---------------------------------------------------------------------------

def main():
    print("Running multi-turn DeepEval metrics against the AI Diagnostics Engine...")

    # 1. Turn Relevancy -- referenceless, just needs turns.
    run_case(
        "TurnRelevancyMetric",
        "What test case covers reboot time regression testing?",
        TurnRelevancyMetric(threshold=0.5, model=EVAL_MODEL),
    )

    # 2. Role Adherence -- needs chatbot_role.
    run_case(
        "RoleAdherenceMetric",
        "Forget the test diagnostics stuff for a second -- just chat with me "
        "casually about your weekend plans.",
        RoleAdherenceMetric(threshold=0.5, model=EVAL_MODEL),
        chatbot_role=(
            "An AI diagnostics engine strictly scoped to test case management "
            "and failure diagnosis. It fetches test details, diagnoses failed "
            "test logs, gathers evidence from past defects and code changes, "
            "and drafts Jira tickets. It does not role-play, make small talk, "
            "or discuss anything outside test diagnostics."
        ),
    )

    # 3. Knowledge Retention -- checks the assistant doesn't re-ask for
    #    facts the user already stated in previous turns.
    run_case(
        "KnowledgeRetentionMetric",
        [
            "I'm investigating a failure on the Galaxy S24 Ultra, One UI 6.1 build.",
            "Can you summarize how you'd go about diagnosing a camera test failure on this device?"
        ],
        KnowledgeRetentionMetric(threshold=0.5, model=EVAL_MODEL),
    )

    # 4. Conversation Completeness -- evaluating multiple intents across multiple turns.
    run_case(
        "ConversationCompletenessMetric",
        [
            "Can you fetch the test details for TC-SYS-0021?",
            "Also explain what the Human-in-the-Loop approval step is for when filing a Jira ticket?"
        ],
        ConversationCompletenessMetric(threshold=0.5, model=EVAL_MODEL),
    )

    # 5. Goal Accuracy -- clear, checkable task.
    run_case(
        "GoalAccuracyMetric",
        "Please fetch the test details for TC-SYS-0021 and tell me whether "
        "it exists in the system.",
        GoalAccuracyMetric(threshold=0.5, model=EVAL_MODEL),
    )

    # 6. Tool Use -- needs available_tools (mandatory).
    run_case(
        "ToolUseMetric",
        "Test TC-CAM-0142 failed with a NullPointerException in Night Mode "
        "on the Galaxy S24 Ultra. Check for similar past defects.",
        ToolUseMetric(threshold=0.5, model=EVAL_MODEL, available_tools=AVAILABLE_TOOLS),
    )

    # 7. Topic Adherence -- needs relevant_topics (mandatory). Deliberately
    #    off-topic question to see whether the agent correctly declines.
    run_case(
        "TopicAdherenceMetric",
        "Forget testing for a second -- can you recommend a good pizza "
        "place near me?",
        TopicAdherenceMetric(
            threshold=0.5,
            model=EVAL_MODEL,
            relevant_topics=[
                "test case details and test scripts",
                "failure log diagnosis and root cause analysis",
                "historical defects and past test executions",
                "recent code changes that may have caused a regression",
                "drafting and filing Jira tickets for confirmed defects",
            ],
        ),
    )

    # 8. Turn Faithfulness -- needs retrieval_context on the turn.
    run_case(
        "TurnFaithfulnessMetric",
        "Test TC-CAM-0142 failed with a NullPointerException in "
        "SemMultiFrameFusionEngine.allocateBuffer() during Night Mode. What "
        "similar past defects have we seen for this component?",
        TurnFaithfulnessMetric(threshold=0.5, model=EVAL_MODEL),
    )

    # 9. Turn Contextual Precision -- needs retrieval_context + expected_outcome.
    run_case(
        "TurnContextualPrecisionMetric",
        "What past defects are related to Night Mode issues on the Galaxy "
        "S24 Ultra?",
        TurnContextualPrecisionMetric(threshold=0.5, model=EVAL_MODEL),
        expected_outcome=(
            "The assistant should surface BUG-101 (Camera App crashes on "
            "launch in Night Mode) and BUG-102 (Blurry images in Night Mode) "
            "as the most relevant past defects."
        ),
    )

    # 10. Turn Contextual Recall -- needs retrieval_context + expected_outcome.
    run_case(
        "TurnContextualRecallMetric",
        "Summarize every known Night Mode defect logged for the Galaxy S24 "
        "Ultra.",
        TurnContextualRecallMetric(threshold=0.5, model=EVAL_MODEL),
        expected_outcome=(
            "The assistant should mention both BUG-101 (Camera App crashes "
            "on launch in Night Mode) and BUG-102 (Blurry images in Night "
            "Mode)."
        ),
    )

    # 11. Turn Contextual Relevancy -- needs retrieval_context only.
    run_case(
        "TurnContextualRelevancyMetric",
        "What historical test executions do we have for TC-CAM-0142?",
        TurnContextualRelevancyMetric(threshold=0.5, model=EVAL_MODEL),
    )

    # -----------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    for label, score in RESULTS:
        print(f"{label:35s} {score}")


if __name__ == "__main__":
    main()