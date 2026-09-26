# AI Diagnostics Engine: Graph Logic & Architecture

Welcome to the AI Diagnostics Engine. This document provides a narrative overview of how the engine operates, detailing its capabilities, underlying graph logic, memory management, and how it collaborates with human engineers to diagnose test failures and suggest fixes.

## Overview

The Diagnostics Engine is designed as a centralized "Brain" that manages conversational interactions with users. However, it is strictly scoped to test case management and diagnostics. 

When you converse with the engine, it performs two primary functions:
1. **Fetching Test Details:** You can ask it for the specifics of any test case, and it will retrieve the information.
2. **Diagnosing Failures:** You can upload a failed log, and the engine will diagnose the root cause, gather evidence, and suggest a fix, culminating in a ready-to-file Jira ticket.

## The Graph Logic

The engine is powered by a state-machine architecture (using LangGraph) where execution flows through a series of specialized nodes. 

### 1. The Agent Node
Everything starts at the `agent_node`. This is the orchestrator. It receives user messages and decides what to do next. It is equipped with specific tools:
* If a user asks for test details, it calls the `search_test_details_tool` and routes to the `tools_node` to execute it.
* If a user uploads a log or asks for a diagnosis, it ensures it has the necessary details. It can use the `parse_failure_log` tool to extract structured data (like `test_case_id`, `error_message`, `component`, etc.) from raw text.
* Once it has the details, it calls `start_diagnosis` to trigger the diagnostic loop.

### 2. The Diagnostic Loop (RAG in Action)
When `start_diagnosis` is called, the graph enters a specialized evidence-gathering loop:
* **Query Enhancement (`query_enhancement_node`):** The engine takes the raw error message and failure details and rewrites them into a highly optimized search query.
* **Evidence Gathering (`evidence_gathering_node`):** This is the RAG (Retrieval-Augmented Generation) core. The engine uses vector search (`pgvector`) to fetch:
  * **Historical Failures:** Semantically similar past defects and test executions from PostgreSQL.
  * **Code Changes:** Recent commits or pull requests that might have impacted the failing component.
* **Evidence Checking (`check_evidence_node`):** An LLM evaluates the gathered evidence. Is it sufficient to identify a root cause? Are there contradictions? 
  * If the evidence is insufficient, it generates feedback, refines the search query, and routes back to the enhancement/gathering nodes (up to 3 retries).
  * If the evidence is sufficient, the flow routes back to the `agent_node` with the findings.

### 3. Submitting the Diagnosis
Once the agent has digested the evidence, it can formulate a diagnosis (Root Cause, Probable Cause, Suggested Fix) and call `submit_diagnosis`. This routes to the `jira_ticket_node`, which compiles the findings into a structured Jira Ticket format.

## Human-in-the-Loop (HITL)

The engine isn't purely autonomous; it is designed to collaborate. 
* **Approval Checkpoints:** The engine has tools like `ask_user_jira_approval`. If the agent encounters conflicting evidence or is unsure about the suggested fix, it will pause the graph and ask the user for guidance or approval before finalizing the Jira ticket.
* **Interactive Refinement:** Because it handles conversations, the user can provide extra context, point the engine to a specific component, or correct its assumptions mid-flight.

## Memory and State

The graph relies on a persistent `AgentState` object that travels with every node execution.
* **Conversational Memory:** It tracks the entire `messages` history so the agent maintains context across multiple turns of conversation.
* **State Management:** The `AgentState` holds structured objects like `FailureInput` (the parsed failure), `retrieved_evidence` (RAG results), and the final `DiagnosisReport`.
* **Persistence:** The engine uses LangGraph's `MemorySaver` (checkpointing) to ensure that if a process stops or waits for human input, the exact state of the investigation is preserved and can be resumed seamlessly.

By combining structured graph routing, semantic RAG, and conversational memory, the AI Diagnostics Engine acts as an expert pair-programmer, turning raw failure logs into actionable, evidence-backed engineering tasks.

## Data

### Fake PostgreSQL and pgvector Database Data
The diagnostic engine uses PostgreSQL to simulate an engineering environment. The database schema includes:
* **projects**: Seeded with "Galaxy S24 Ultra", "Galaxy S23", and "One UI 6.1".
* **test_cases**: Contains structured test scripts and steps (e.g., `TC-CAM-0142` for Night Mode captures, `TC-SYS-0021` for Reboot Time).
* **defects**: Includes mock bug tickets like "Camera App crashes on launch in Night Mode" (BUG-101) and "Blurry images in Night Mode" (BUG-102). This table is embedded into `pgvector` for semantic search.
* **test_executions**: Contains mock historical executions (pass/fail status, device, environment, notes). This is also embedded using `pgvector` to find semantic similarities with past test failures.

### The `sample.log`
The `indexer/data/sample.log` file simulates a device diagnostic bundle, specifically for a failed camera night-mode test (`TC-CAM-0142`) on a Samsung Galaxy S24 Ultra.
It contains:
* Device metadata (Build version, One UI version, Camera App version).
* ADB logcat output starting from the `SmartCamera_RegressionSuite_Nightly` suite execution.
* A detailed trace of the camera app launching, the night mode being triggered in low light, and the subsequent `NullPointerException` inside `SemMultiFrameFusionEngine.allocateBuffer()`.
* Background noise typical of a real device log (BatteryStatsService, vold, SamsungAnalytics) to ensure the AI parses only the relevant crash data out of 46,000+ lines.
