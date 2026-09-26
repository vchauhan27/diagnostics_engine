# DeepEval Evaluation Results

## ❌ test_case_0

### Metrics
| Status | Metric | Score | Threshold | Reason |
|---|---|---|---|---|
| FAIL | Answer Relevancy | 0.00 | 0.70 | The score is 0.00 because the actual output only indicates that a Jira ticket was created, which does not provide information about similar past defects or recent code changes related to the failure, making it completely irrelevant to the question. |
| PASS | Faithfulness | 1.00 | 0.70 | The score is 1.00 because there are no contradi... |
| PASS | Contextual Relevancy | 0.78 | 0.70 | The score is 0.78 because while the retrieval c... |
| FAIL | Contextual Precision | 0.40 | 0.70 | The score is 0.40 because, although the relevant nodes at ranks 2, 6, and 8 contain useful defect information (e.g., 'It contains the error description ...', 'It provides the specific error ...', 'It includes the precise stack trace line ...'), many irrelevant nodes appear before or between them, lowering precision. For instance, the first relevant node (rank 2) follows an irrelevant node at rank 1 ('It is only a tool update message ...'), the second relevant node (rank 6) comes after irrelevant nodes at ranks 3‑5 (all tool‑update messages), and the third relevant node (rank 8) is preceded by an irrelevant node at rank 7 ('It is only a tool update ... lacking any concrete code change information'). This ordering means that a substantial portion of irrelevant nodes are ranked higher than relevant ones, resulting in a contextual precision of 0.40. |
| FAIL | Contextual Recall | 0.67 | 0.70 | The score is 0.67 because sentence 1 is supported by node 2 and sentence 3 by node 5, whereas sentence 2 lacks any matching node in the retrieval context. |

## Aggregate Metrics

| Metric | Average Score | Pass Rate | Total |
|---|---|---|---|
| Answer Relevancy | 0.00 | 0.00% | passed=0 | failed=1 | 1 |
| Faithfulness | 1.00 | 100.00% | passed=1 | failed=0 | 1 |
| Contextual Relevancy | 0.78 | 100.00% | passed=1 | failed=0 | 1 |
| Contextual Precision | 0.40 | 0.00% | passed=0 | failed=1 | 1 |
| Contextual Recall | 0.67 | 0.00% | passed=0 | failed=1 | 1 |

---
*Report cleaned and structured automatically.*