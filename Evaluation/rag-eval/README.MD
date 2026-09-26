# RAG Evaluation Framework (Retrieval-Augmented Generation)

This suite evaluates the **pgvector database retrieval** and how the Diagnostic Agent uses historical evidence (past defects, logs, code changes). 

Unlike GEval (which grades text style) or Agent Eval (which grades tool execution), RAG Eval explicitly tests the accuracy of your search engine and the factual groundedness of the agent's claims.

## Key Metrics

- **Contextual Precision & Recall**: When the agent queries the vector database for "NullPointerException in Night Mode", does the database return the most highly relevant defect tickets at the top of the search results? Did it miss any crucial historical logs?
- **Answer Relevancy**: Is the final root cause provided by the agent actually relevant to the original test failure?
- **Faithfulness / Groundedness**: **(Critical Safety Metric)** Is every claim the agent makes directly supported by the logs and defect history retrieved? If the agent hallucinates a root cause that isn't present in the retrieved chunks, it fails this metric.

## Application in Diagnostics
When the agent uses `query_logs` or searches for past defects, we capture the exact text chunks returned by `pgvector`. DeepEval then grades whether those chunks were actually helpful, and ensures the agent didn't invent a fake remediation step.
