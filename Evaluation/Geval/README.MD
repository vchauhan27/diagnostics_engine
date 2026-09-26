# GEval Evaluation Suite

This folder contains the **GEval** (Generative Evaluation) scripts. GEval uses an LLM acting as a "judge" to score subjective criteria based on a specific prompt. 

These evaluations strictly grade the **human-readable text** that the agent generates at the very end. They evaluate the style, formatting, logic, and conversational flow of the agent's responses, acting much like a human reviewer grading a report.

---

## The GEval Scripts in this Folder

There are three distinct GEval scripts here, each testing a completely different aspect of the agent's text quality:

### 1. `GEval.py` (Format Adherence)
*   **What it does:** Grades the **structure and layout** of a single response. It reads the agent's output and checks if the required template was followed (e.g., Did it include a "Root Cause" section? Did it include a "Suggested Fix"? Did it clearly separate evidence from reasoning?).
*   **Why it's unique:** It focuses purely on presentation. An agent could write a highly logical response, but if it is formatted as one massive paragraph, it will fail this evaluation.

### 2. `coherence_GEval.py` (Coherence)
*   **What it does:** Grades the **internal logic and reasoning** of a single response. It checks if the diagnosis makes logical sense, ensuring the agent doesn't contradict itself and that the evidence it quotes actually supports its final conclusion.
*   **Why it's unique:** This catches "smart-sounding nonsense." A response might pass the Format Adherence eval because it has all the right headers, but fail the Coherence eval because the "Suggested Fix" has nothing to do with the "Root Cause."

### 3. `conversational_GEval.py` (Memory Consistency)
*   **What it does:** Grades the agent's behavior **across a multi-turn conversation**. It feeds the judge the entire chat history and checks if the agent remembers details from earlier in the chat (like the device model or test ID) and uses them later without asking for them again.
*   **Why it's unique:** While the first two evals test the agent in a vacuum (one question, one answer), this tests the agent's memory and conversational state over time.

---

## How GEval is Different from Agent, RAG, and Multi-Turn Evals

It is critical to understand that the GEval scripts in this folder have **nothing to do with testing the hidden backend machinery**. GEval only sees the final paragraph the agent outputs.

The other evaluation suites (Agent, RAG, Multi-Turn) test the deterministic backend code, database, and tool mechanics:

### 1. Agent Eval (The Machinery)
*   **What it tests:** Did the agent's brain work correctly? Did it trigger the Python function `search_test_details_tool("TC-1234")`? Did it pass a string or an int? Did it get stuck in an infinite loop? 
*   **Difference:** Agent Eval doesn't care if the final message is polite or well-formatted. It only cares that the agent successfully executed the right backend tools in the right order.

### 2. RAG Eval (The Database)
*   **What it tests:** When the agent asked for logs, did the `pgvector` database actually return the correct logs? Were they ranked properly?
*   **Difference:** RAG eval is testing your vector database search quality (Recall, Precision, Chunk Relevancy). GEval has no idea a database even exists.

### 3. Multi-Turn Eval (The Workflow)
*   **What it tests:** If you have a Human-in-the-Loop workflow, this tests the state machine. Did the agent wait for approval before executing a command? Did the graph checkpointer properly transition states?
*   **Difference:** True multi-turn workflow evals test the state-machine routing of your LangGraph setup over time, rather than just reading the text of the conversation.

### Summary
*   **Agent / RAG Evals:** Test the **backend code, database, and tool mechanics**. (Objective / Pass-Fail)
*   **GEvals (This folder):** Test the **frontend text quality, logic, and formatting**. (Subjective / Graded by an AI Judge)