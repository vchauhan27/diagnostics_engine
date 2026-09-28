from deepteam import Guardrails
from deepteam.guardrails.guards.prompt_injection_guard.prompt_injection_guard import PromptInjectionGuard
from deepteam.guardrails.guards.hallucination_guard.hallucination_guard import HallucinationGuard
from deepteam.guardrails.guards.topical_guard.topical_guard import TopicalGuard
from deepteam.guardrails.guards.privacy_guard.privacy_guard import PrivacyGuard
from Evaluation.config import get_judge_model

judge = get_judge_model()

guardrails = Guardrails(
    evaluation_model=judge,  # type: ignore
    input_guards=[
        PromptInjectionGuard(model=judge),  # type: ignore
        #PrivacyGuard(model=judge),  # type: ignore
        TopicalGuard(
            model=judge,  # type: ignore
            allowed_topics=[
            "software debugging",
            "test case failures",
            "error messages",
            "stack traces",
            "historical failures",
            "code changes",
            "diagnostics",
            "jira tickets",
            "software testing",
            "system logs",
            "device logs",
            "telemetry",
            "queries related to fetching or checking test details",
            "approving, declining, or responding to human-in-the-loop requests",
            "general conversational acknowledgments (yes, no, ok, cancel, stop, thank you, hi, hey, hello, )",
            "generic conversational questions (why, how, what, when, where)"
        ])
    ],
    output_guards=[
        HallucinationGuard(model=judge),  # type: ignore
        #PrivacyGuard(model=judge)  # type: ignore
    ],
)
