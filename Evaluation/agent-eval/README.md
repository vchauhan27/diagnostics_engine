# Agent Evaluation Framework (Diagnostic Agent)

This suite evaluates the **trajectory and backend machinery** of the AI Diagnostics Engine. It strictly looks at the steps the agent took to solve a ticket, ignoring the style of the final text.

## Part 1: Trace-Based Metrics (Trajectory)

These metrics analyze the agent's internal thought process and execution path while diagnosing a failure.

- **Task Completion (`TaskCompletionMetric`)**: Did the agent actually finish diagnosing the test failure (e.g., finding the root cause of `TC-CAM-0142`), or did it give up/crash?
- **Step Efficiency (`StepEfficiencyMetric`)**: Did the agent diagnose the issue optimally? (Penalizes the agent if it blindly searches for generic errors before looking up the specific test details).
- **Plan Adherence (`PlanAdherenceMetric`)**: Did the agent follow standard diagnostic operating procedures?
- **Plan Quality (`PlanQualityMetric`)**: Is the agent's troubleshooting plan safe and logical, avoiding dangerous assumptions?

**Application**: We feed the agent a query like *"Diagnose the failure in TC-SYS-0021"*. DeepEval traces the entire LangGraph execution, capturing every intermediate thought and tool call to grade the logic.

## Part 2: Tool-Call-Based Metrics

These metrics focus purely on whether the agent successfully manipulated its Python backend tools.

- **Tool Correctness (`ToolCorrectnessMetric`)**: Did the agent pick the right tool? (e.g., It should pick `search_test_details_tool` rather than hallucinating a `fix_database` tool).
- **Argument Correctness (`ArgumentCorrectnessMetric`)**: Did it pass the right arguments? (e.g., Did it correctly pass `{"test_id": "TC-SYS-0021"}` to the tool, or did it pass invalid JSON?).

**Application**: We define strict test cases specifying `expected_tools`. If the agent skips `parse_failure_log` when it was explicitly needed, it fails the evaluation.
