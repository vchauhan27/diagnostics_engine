# Multi-Turn Evaluation Framework (Conversational Workflow)

This suite evaluates the Diagnostic Agent's behavior across a **multi-turn, Human-in-the-Loop (HITL) conversation**. 

While other suites test the agent on a single prompt-and-response, this suite feeds the agent an entire chat history to test its memory, state-machine transitions, and conversational consistency.

## Key Metrics

- **Conversational Memory**: Does the agent remember context from earlier in the chat? (e.g., If the user mentions "Galaxy S24" in turn 1, the agent shouldn't ask for the device model in turn 3).
- **Role Adherence**: Does the agent stay in its persona as an expert Diagnostic Assistant across 5+ messages, or does it get distracted and break character?
- **State-Machine Workflow (HITL)**: If the agent requires human approval to execute a script or close a Jira ticket, does it correctly halt the conversation, ask for permission, and correctly resume when the user replies "Approved"?

## Application in Diagnostics
We simulate a back-and-forth debugging session. DeepEval grades the agent on how well it tracks the context of the bug, handles follow-up questions, and respects the boundaries of the LangGraph checkpointer.
