# DAG Evaluation Suite (Deep Acyclic Graph)

This folder contains the **DAG** (Deep Acyclic Graph) custom evaluation scripts. 

While `GEval` scores the subjective quality and style of text using a float (e.g., 0.8), **DAG builds deterministic, pass/fail decision trees**. It uses an LLM to answer strict "Yes/No" questions at critical gates. If the agent fails a hard requirement, it immediately scores a 0.

This is highly useful for tracing exactly *where* the agent failed in a logical process, rather than just knowing that the final answer was "poor quality."

---

## The DAG Scripts in this Folder

There are three DAG scripts here, each testing a specific logical decision tree:

### 1. `DAG.py` (Groundedness Gate)
*   **What it does:** Tests a strict, one-step deterministic rule: *Is every single claim in the final output directly supported by the retrieved context?* 
*   **Why it's unique:** It doesn't grade how well the report is written. It acts as an absolute safety gate: if the agent hallucinates a root cause that isn't in the logs, it receives a hard 0 (fail).

### 2. `reasoning_DAG.py` (Tool Choice & Reasoning Synthesis)
*   **What it does:** Implements a two-step decision tree to isolate exactly where the agent's logic broke down:
    1.  **Gate 1 (Tool Choice):** Did the agent pick the correct tools? (e.g., Did it realize it needed to search historical defects for this error?) If NO -> Score 0. If YES -> proceed to Gate 2.
    2.  **Gate 2 (Synthesis):** Given the data returned by the tools, does the agent's final conclusion logically follow? If NO -> Score 0. If YES -> Score 1.
*   **Why it's unique:** Instead of a single subjective score, it tells you exactly what broke: "The agent chose the right tool, but synthesized the result incorrectly."

### 3. `conversational_DAG.py` (Memory Recall Gate)
*   **What it does:** Evaluates a multi-turn conversation with a strict pass/fail condition: *Did the assistant correctly recall a fact the user shared earlier in the chat?*
*   **Why it's unique:** Unlike conversational GEval (which subjectively grades the "flow" and "consistency" of the chat), this is a binary check. Either the agent remembered the Test ID, or it forgot it (Hard Fail).

---

## How DAG Evals Differ from Built-in Agent, RAG, and Multi-Turn Evals

Just like GEvals, these DAG scripts are **custom criteria** you've written, evaluated by an LLM acting as a strict judge.

The built-in evaluation suites (Agent, RAG, Multi-Turn) are fundamentally different:

### 1. Agent Eval (Built-in Trajectory Metrics)
*   **What it tests:** DeepEval's built-in Agent Eval parses the exact JSON tool calls and the execution graph to see if the agent looped or hallucinated API parameters.
*   **Difference:** The DAG evals in this folder use an LLM to logically reason about *why* the agent chose those tools and if the conclusion made sense, rather than just parsing the JSON mechanics.

### 2. RAG Eval (Vector Search Metrics)
*   **What it tests:** DeepEval's built-in RAG metrics check the exact precision, recall, and vector similarity of the chunks returned by your database.
*   **Difference:** `DAG.py` only cares if the *final answer matches the chunks*. It doesn't know or care if the vector search algorithm itself is optimized.

### 3. Multi-Turn Eval
*   **What it tests:** Tests the raw LangGraph state transitions across multiple user messages (e.g., Did the human-in-the-loop state machine wait for human approval?).
*   **Difference:** `conversational_DAG.py` explicitly tests the LLM's *memory comprehension* over those turns, rather than the state-machine execution.

### Summary
*   **Agent / RAG Evals:** Test the **backend code execution and database accuracy** programmatically.
*   **GEvals:** Test the **subjective style, tone, and formatting** of the text using an AI judge (Float score).
*   **DAGs (This folder):** Test **strict logical rules, safety gates, and decision trees** using an AI judge (Binary Pass/Fail).
