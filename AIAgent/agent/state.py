from typing import Any

from langchain_core.messages import BaseMessage
from pydantic import BaseModel, Field
from langgraph.graph.message import add_messages
from typing import Annotated


# Input schema: raw details of a failed test case, fed into the graph
class FailureInput(BaseModel):
    test_case_id: str = Field(description="ID of the failed test case")
    error_type: str = Field(description="Type of the error eg. Nullpointexception")
    error_message: str = Field(description="Specific error message")
    component: str = Field(description="File and method")
    stack_trace: str = Field(default="", description="Stack trace of the error")
    build_version: str = Field(description="Build version which failed")
    environment: str = Field(description="Environment where the error occurred")
    product_name: str = Field(description="Product name")

# Structured output schema: the final diagnosis produced by the diagnosis node
class DiagnosisReport(BaseModel):
    root_cause: str
    probable_cause: str
    affected_component: str
    severity: str
    priority: str
    similar_historical_failures: list[str] = Field(default_factory=list)
    suggested_fix: str

    evidence_summary: list[str] = Field(default_factory=list)
    conflicting_evidence: list[str] = Field(default_factory=list)
    root_cause_status: str = Field(
        description="confirmed, strongly_supported, plausible, or unresolved"
    )

# Structured output schema: the Jira ticket generated from the diagnosis
class JiraTicketInput(BaseModel):
    title: str = Field(description="Title of the Jira ticket")
    description: str = Field(description="Description of the Jira ticket")
    priority: str = Field(description="Priority of the Jira ticket")
    severity: str = Field(description="Severity of the Jira ticket")
    assignee: str = Field(description="Assignee of the Jira ticket")
    components: list[str] = Field(description="List of components of the Jira ticket")
    labels: list[str] = Field(description="List of labels of the Jira ticket")

# This is the single object passed between every node in the graph.
class AgentState(BaseModel):
    # Optional on intake — the intake_node parses it from the first human message.
    failure_input: FailureInput | None = None
    historical_top_k: int = 5
    code_changes_top_k: int = 5
    retry_source: str | None = None
    messages: Annotated[list[BaseMessage], add_messages] = Field(default_factory=list)
    retrieved_evidence: dict = Field(default_factory=dict)
    sufficient: bool | None = None          
    check_feedback: str | None = None       
    check_attempts: int = 0                    
    diagnosis: DiagnosisReport | None = None
    jira_ticket: JiraTicketInput | None = None

    evidence_conflict: bool = False
    evidence_conflict_reason: str | None = None

    #HYBRID RAG
    enhanced_query: str | None = None
    answer_quality_ok: bool | None = None
    answer_feedback: str | None = None

    #PARSER OUTPUT VALIDATION
    parsed_failure: Any | None = None
    validation_errors: list[str] = Field(default_factory=list)

    #PII & INJECTION DETECTION
    parsed_failure_clean: dict = Field(default_factory=dict)
    pii_flags: list[str] = Field(default_factory=list)
    injection_flags: list[str] = Field(default_factory=list)

    #HITL
    diagnosis_hitl_approved: bool | None = None
    diagnosis_hitl_notes: str | None = None
    ticket_hitl_approved: bool | None = None
    ticket_hitl_notes: str | None = None

    #JIRA TICKET IDEMPOTENCY
    idempotency_key: str | None = None
    idempotency_hit: bool = False

    #JIRA TICKET VERIFICATION
    verification_passed: bool | None = None
    verification_errors: list[str] = Field(default_factory=list)

class CheckDecision(BaseModel):
    reasoning: str = Field(default="", description="Brief evidence-based reasoning.")

    sufficient: bool = Field(
        description=(
            "True only when the evidence is sufficient AND there is no "
            "unresolved material contradiction."
        )
    )

    feedback: str = Field(
        default="",
        description="Missing evidence, contradiction, or reasoning problem."
    )

    retry_source: str = Field(
        default="",
        description=(
            "historical_failures, code_changes, or test_details. "
            "Required when sufficient=false and more evidence could resolve the issue."
        )
    )

    conflict_detected: bool = Field(
        default=False,
        description="Whether a material chronology, version, or causal conflict exists in the evidence."
    )

    conflict_reason: str = Field(
        default="",
        description="Explain the contradiction using only retrieved evidence."
    )

class AnswerQualityDecision(BaseModel):
    reasoning: str = Field(default="", description="Reasoning for quality check")
    quality_ok: bool = Field(description="Is the answer quality sufficient?")
    feedback: str = Field(default="", description="Feedback if quality is not ok")
