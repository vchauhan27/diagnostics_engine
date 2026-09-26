# Diagnostic Engine: Evaluation Suite

This directory contains the complete evaluation framework for the AI Diagnostics Engine. The evaluations are broken down into five distinct suites, each targeting a different layer of the agent's architecture (machinery, database, conversation, text quality, and logical safety).

---

## 1. Agent Evaluation (`agent-eval`)
**What it tests:** The backend machinery and execution trajectory. It ensures the agent correctly selects and executes tools (like `search_test_details_tool`) without looping or passing bad arguments.

**How to run:**
```bash
python agent-eval/agent-eval.py
```

## 2. RAG Evaluation (`rag-eval`)
**What it tests:** The vector database retrieval (`pgvector`). It ensures the engine returns highly relevant historical logs/defects and that the agent's final answer is strictly grounded in that retrieved evidence.

**How to run:**
```bash
python rag-eval/rag-eval.py
```

## 3. Multi-Turn Evaluation (`multi-turn-eval`)
**What it tests:** The state machine and conversational workflow. It simulates a debugging session to test if the agent remembers previous context (like test IDs) and handles Human-in-the-Loop (HITL) workflows correctly.

**How to run:**
```bash
python multi-turn-eval/multi_turn_metrics.py
```

## 4. GEval: Subjective Grading (`Geval`)
**What it tests:** The frontend text quality. It uses an LLM judge to grade the style, formatting, and logical flow of the final diagnostic report (e.g., ensuring it has a "Root Cause" and "Suggested Fix").

**How to run:**
```bash
# Test if the report format adheres to the required template
python Geval/GEval.py

# Test the internal coherence and logic of the generated report
python Geval/coherence_GEval.py

# Test if the agent's tone and memory are consistent over a conversation
python Geval/conversational_GEval.py
```

## 5. DAG: Deterministic Logic Gates (`DAG`)
**What it tests:** Strict pass/fail safety rules and decision trees. Instead of grading the style, it acts as a hard gate (e.g., if the agent hallucinates a fix not found in the logs, it receives an automatic score of 0).

**How to run:**
```bash
# Strict pass/fail gate for groundedness (No hallucinations)
python DAG/DAG.py

# Two-step gate: Did it choose the right tool? -> Did the conclusion follow?
python DAG/reasoning_DAG.py

# Binary check for conversational memory (Did it remember the device model?)
python DAG/conversational_DAG.py
```

---

## Environment Setup
Before running any of the suites above, ensure that your Python environment is active and all dependencies in `requirements.txt` are installed. Because these evaluations rely on an LLM Judge (via DeepEval), make sure your API credentials are set up properly in your `.env` file or environment variables.
