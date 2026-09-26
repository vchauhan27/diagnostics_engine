# AI Diagnostics Engine 🔍

The **AI Diagnostics Engine** is an intelligent, autonomous agent designed to help software engineering and QA teams handle test failures. Built on top of **LangGraph** and **LangChain**, this engine acts as a digital detective that automatically investigates test failures, identifies root causes, and drafts actionable bug reports (Jira tickets)—all while keeping humans in the loop for critical decisions.

---

## 🎯 Use Case

In modern CI/CD pipelines, test failures happen frequently. Developers and QA engineers spend countless hours sifting through massive logs, searching Jira for similar past issues, checking recent code commits, and writing up bug reports. 

**This project automates that tedious workflow.**

When a test fails, the AI Diagnostics Engine utilizes a **Centralized LLM Router** with a **Hybrid RAG** architecture:
1. **Intelligent Routing:** The main agent receives the user's input (a failure report or chat) and dynamically decides the next steps using its reasoning capabilities. Conversational chats are answered immediately, while failures are routed for diagnosis.
2. **Dynamic Query Enhancement:** For failure reports, the agent routes to a specialized node to enhance the search query, maximizing retrieval quality.
3. **Evidence Gathering:** The agent uses its toolset to:
   - Query the PostgreSQL database for test case details.
   - Search historical execution data to detect flakiness or regressions.
   - Use Vector Search (pgvector) to find semantically similar past defects and recent code changes.
4. **Sufficiency Checking & Iteration:** A specialized evidence checking node evaluates if the gathered evidence is sufficient. If not, it routes back to the agent or query enhancer for more context.
5. **Diagnosis & Validation:** The central agent synthesizes the evidence, determines the root cause, and validates the answer internally.
6. **Requests Human Approval (HITL):** If the agent is unsure or needs final sign-off, it requests human approval before formally filing a Jira ticket.
7. **Ticket Creation:** The agent ultimately routes to the Jira node to file a ticket complete with the root cause, evidence summary, and suggested fix.

---

## 🏗️ Architecture & Core Components

```mermaid
graph TD
    __start__((__start__)) --> agent_node
    
    agent_node -.-> tools_node
    agent_node -.-> query_enhancement
    agent_node -.-> jira_ticket
    agent_node -.-> __end__((__end__))
    
    tools_node --> agent_node
    
    query_enhancement --> evidence_gathering
    evidence_gathering --> check_evidence
    
    check_evidence -.-> agent_node
    check_evidence -.-> query_enhancement
    
    jira_ticket --> __end__((__end__))
```

The project is structured into several key modules:

### 1. `AIAgent/agent/` (The Brain)
- **`graph.py`**: Defines the LangGraph state machine utilizing a Centralized Tool Architecture. A main `agent_node` routes execution to various tools (`tools_node`), `query_enhancement`, or `jira_ticket` generation based on the LLM's decisions.
- **`nodes.py`**: Contains the core agent logic and LangChain setup. It orchestrates the main LLM agent and specialized nodes like query enhancement, evidence gathering, and checking evidence sufficiency.
- **`tools.py`**: Equips the AI with functions to search code changes, fetch test details from the DB, search historical failures via pgvector, and ask the human for approval (`ask_user_jira_approval`).
- **`state.py`**: Defines the typed state (memory) that is passed between nodes in the graph.

### 2. `AIAgent/parser.py` (The Log Translator)
Uses regex and string parsing to convert messy, unstructured failure logs into clean, structured `FailureInput` objects that the AI can understand.

### 3. `indexer/` (Vector Search Setup)
Scripts to ingest past defects, test executions, and code changes, converting them into vector embeddings for semantic search.

### 4. `agent-ui/` (The Front-End)
A web-based user interface to interact with the agent, view streaming logs, and provide Human-In-The-Loop (HITL) approvals.

### 5. `main.py` (The Entry Point)
A CLI script to test the engine locally, stream the AI's thought process to the console, and handle HITL prompts directly in the terminal.

---

## 🚀 How to Run the Project

### Prerequisites
- **Python 3.10+**
- **Node.js** (for the UI)
- **PostgreSQL** (with `pgvector` extension enabled)
- A valid LLM API Key (e.g., OpenRouter, OpenAI, or Anthropic)

### 1. Environment Setup

Clone the repository and set up your Python environment using `uv` (recommended) or `pip`:

```bash
# Using uv (Recommended)
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -r requirements.txt

# Or using pip
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Create a `.env` file in the root directory and add your configuration:
```env
OPENROUTER_API_KEY=your_api_key_here
DATABASE_URL=postgresql://user:password@localhost:5432/diagnostics_db

# LangSmith Tracing (Optional)
LANGSMITH_TRACING=true
LANGSMITH_PROJECT=diagnostics_engine
LANGSMITH_API_KEY=your_langsmith_api_key_here
```

### 2. Database Initialization
We recommend using Docker to run PostgreSQL with the `pgvector` extension enabled:

```bash
docker run --name diagnostics_db -e POSTGRES_USER=user -e POSTGRES_PASSWORD=password -e POSTGRES_DB=diagnostics_db -p 5432:5432 -d pgvector/pgvector:pg16
```

Then, initialize the schema and insert mock data:
```bash
# Mac/Linux (bash)
docker exec -i diagnostics_db psql -U user -d diagnostics_db < src/setup_db.sql
# Windows (PowerShell)
Get-Content src\setup_db.sql | docker exec -i diagnostics_db psql -U user -d diagnostics_db
```

### 3. Generate Vector Embeddings (Indexer)
Before the engine can run, you must generate embeddings for the vector search:
```bash
python indexer/run_indexer.py
```

### 4. Running the Engine (CLI Mode)
To see the agent in action via the terminal, run:
```bash
python main.py
```
This will start a streaming session where you can watch the agent parse a mock failure, gather evidence, reason through the problem, and optionally ask you for approval (HITL) before filing a ticket.

### 5. Running the Web UI with Python Backend
To use the visual chat interface with your actual Python engine, you need to run the Python API server and the Next.js frontend:

**Step 1: Start the Python Backend**
Open a terminal in the root directory and start the LangGraph API server:
```bash
langgraph dev --port 2024
```

**Step 2: Start the Web Frontend**
Open a second terminal, navigate to the `agent-ui` folder, and start **just** the frontend:
```bash
cd agent-ui
npm run dev --filter=web
```
Now, open your browser to [http://localhost:3000](http://localhost:3000) and the UI will automatically connect to your Python engine!

---

## 🗣️ Example User Queries
When using the Web UI, you can chat directly with the AI Diagnostics Engine. Here are some examples of how to interact with it:

- **Log Upload:** Click the **Attach Log** button in the chat interface and upload `indexer/data/sample.log`. The AI will parse the raw logcat output and automatically diagnose the failure for `TC-CAM-0142` (Galaxy S24 Ultra Night Mode).
- **Specific Investigation:** *"Test `TC-CAM-0142` failed on the Galaxy S24 Ultra. Can you check the database for any similar past defects and tell me if a recent code change caused this?"*
- **Flakiness Check:** *"We are seeing a `NullPointerException` in `AuthService.login`. Has this test failed before, or is it a new regression?"*
- **General Summary:** *"Can you give me a summary of the most frequent errors across all test runs in the last 24 hours?"*
- **Diagnostic Request with Stack Trace:** *"I'm getting a `ConnectionTimeoutException` during the checkout flow test. Here is the stack trace... Can you identify what might be causing this?"*
- **Conversational Chat:** *"Hi there! How do I use this tool?"* (The AI classifies this as non-diagnostic and replies instantly without running the expensive diagnostic workflow.)

---

## 🤝 Human-In-The-Loop (HITL)

Safety and accuracy are paramount. This engine is configured with an **Agent-Driven HITL workflow**. 

Instead of deterministically pausing on every action, the AI is instructed to use the `ask_user_jira_approval` tool if it is ever confused, lacks sufficient evidence, or wants final sign-off before proposing a Jira ticket. When this happens, execution pauses, and the system prompts the user (via CLI or UI) to `approve`, `reject`, or provide feedback, which is then fed directly back into the AI's context window.

---

## 📊 Evaluation Suite

The AI Diagnostics Engine includes a comprehensive evaluation framework (using DeepEval) to ensure the system's reliability, accuracy, and safety. The evaluation suite is located in the `Evaluation/` directory and is broken down into five distinct testing layers:

1. **Agent Evaluation (`agent-eval`):** Tests the backend machinery and execution trajectory. Ensures the agent correctly selects and executes tools without looping or passing bad arguments.
2. **RAG Evaluation (`rag-eval`):** Tests the vector database retrieval and ensures the engine returns highly relevant historical logs, and that the agent's final answer is strictly grounded in the retrieved evidence.
3. **Multi-Turn Evaluation (`multi-turn-eval`):** Tests the state machine and conversational workflow. Simulates debugging sessions to test conversational memory and handling of HITL workflows.
4. **GEval: Subjective Grading (`Geval`):** Uses an LLM judge to grade the style, formatting, logical flow, and internal coherence of the final diagnostic report.
5. **DAG: Deterministic Logic Gates (`DAG`):** Applies strict pass/fail safety rules and decision trees (e.g., automatically failing the agent if it hallucinates a fix not found in the logs).

For detailed instructions on running these evaluations, please refer to the [Evaluation Suite README](Evaluation/README.md).
