---
name: ragas-evaluation
description: Guides end-to-end RAGAS evaluation for LLM pipeline quality — covers dataset preparation, metric scoring (faithfulness, answer relevancy, context precision), pass/fail threshold check, and Phase 3 gate evidence generation. Use when evaluating RAG pipeline quality for P3-GATE closure.
---

When the user requests a RAGAS evaluation:

## 1. Prerequisites

Verify the following are available before running:
- `ragas` Python package installed (`pip show ragas`)
- LiteLLM proxy accessible at `LITELLM_URL` (used as the judge model)
- A test dataset of question/context/answer triples in JSON format
- ChromaDB or vector store accessible via MCP Gateway (`chroma.search` tool)

## 2. Dataset Format

The evaluation dataset must be a JSON file with this structure:
```json
[
  {
    "question": "What is the ward-level voter turnout in Kibera?",
    "contexts": ["<retrieved chunk 1>", "<retrieved chunk 2>"],
    "answer": "<LLM-generated answer>",
    "ground_truth": "<reference answer>"
  }
]
```

Minimum dataset size: **20 QA pairs** for statistically meaningful RAGAS scores.
For P3-GATE evidence, use at least **50 QA pairs** from production-representative queries.

## 3. Metrics to Evaluate

Run all four core RAGAS metrics:

| Metric | Target (P3-GATE) | What it measures |
|--------|-----------------|-----------------|
| **Faithfulness** | ≥ 0.85 | Are claims in the answer supported by the retrieved contexts? |
| **Answer Relevancy** | ≥ 0.80 | Does the answer directly address the question? |
| **Context Precision** | ≥ 0.75 | Are the retrieved chunks relevant to the question? |
| **Context Recall** | ≥ 0.70 | Does the retrieved context cover the ground truth? |

## 4. Running the Evaluation

```python
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall
from datasets import Dataset

# Load your QA dataset
data = Dataset.from_json("eval_dataset.json")

results = evaluate(
    dataset=data,
    metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
    llm=<litellm_langchain_wrapper>,   # connect to LITELLM_URL
    embeddings=<embedding_model>,
)

print(results)
```

## 5. Scoring and Gate Decision

Output a RAGAS Score Summary table:

| Metric | Score | Target | Status |
|--------|-------|--------|--------|
| Faithfulness | X.XX | ≥ 0.85 | PASS / FAIL |
| Answer Relevancy | X.XX | ≥ 0.80 | PASS / FAIL |
| Context Precision | X.XX | ≥ 0.75 | PASS / FAIL |
| Context Recall | X.XX | ≥ 0.70 | PASS / FAIL |
| **Overall P3-GATE** | — | All PASS | **APPROVED / BLOCKED** |

## 6. Gate Evidence Artefact

If all metrics pass, generate a gate evidence JSON file:
```json
{
  "gate": "P3-GATE-RAGAS",
  "evaluated_at": "<ISO timestamp>",
  "dataset_size": 50,
  "scores": {
    "faithfulness": 0.88,
    "answer_relevancy": 0.83,
    "context_precision": 0.79,
    "context_recall": 0.74
  },
  "decision": "APPROVED",
  "model_judge": "<litellm model name>"
}
```

Save as `platform/testing/ragas-gate-evidence.json`.

## 7. If Any Metric Fails

- **Low Faithfulness** → Review prompt template; add explicit "answer only from context" instruction.
- **Low Answer Relevancy** → Check system prompt for topic drift; reduce max_tokens.
- **Low Context Precision** → Tune ChromaDB top-k; increase similarity threshold.
- **Low Context Recall** → Increase chunk size; review embedding model choice.

Do not mark P3-GATE as APPROVED until all four metrics meet their targets.
