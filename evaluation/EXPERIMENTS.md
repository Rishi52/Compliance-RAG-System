# Retrieval Experiments

## Evaluation protocol

The retrieval benchmark uses CIS Controls v8.1.2 with
safeguard-level gold labels.

- Dataset version: `0.2.0`
- Total questions: 54
- Development questions: 36
- Held-out test questions: 18
- Dataset SHA-256:
  `aa7794e9c79a440c8deb11259ddb652c2a0bab7132d87a9b7fa79420ba00b2c0`
- Corpus SHA-256:
  `9fa609fc03235102b34122cd3317b2961066f42495b2f63346b4edcaafc2453f`

The test split was created and committed before retrieval
configuration was finalized. Test results must not be used for
model selection or parameter tuning.

## R-001: Expanded development benchmark

Date: 2026-09-05

### Configuration

| Component | Configuration |
|---|---|
| Dense embedding | `BAAI/bge-small-en-v1.5` |
| Sparse retrieval | BM25 |
| Dense candidates | 20 |
| Sparse candidates | 20 |
| Fusion | Reciprocal Rank Fusion, `k=60` |
| Reranker | `cross-encoder/ms-marco-MiniLM-L-6-v2` |
| Evaluation levels | Recall@1, Recall@3, Recall@5, MRR@5, nDCG@5 |

### Development results

| Method | Recall@1 | Recall@3 | Recall@5 | MRR@5 | nDCG@5 | Mean latency |
|---|---:|---:|---:|---:|---:|---:|
| Vector | 0.833 | 0.972 | 0.972 | 0.898 | 0.917 | 167.41 ms |
| BM25 | 0.611 | 0.806 | 0.806 | 0.685 | 0.716 | 2.90 ms |
| RRF | 0.778 | 0.889 | 0.944 | 0.843 | 0.868 | 170.64 ms |
| Hybrid reranked | **0.917** | **1.000** | **1.000** | **0.954** | **0.966** | 2791.02 ms |

Latency values are machine-dependent and should be interpreted
only within the same benchmark run.

### Error analysis

| Example | Gold | Top result | Gold rank | Observation |
|---|---|---|---:|---|
| `seed-011` | `11.1` | `17.3` | 3 | Recovery wording overlaps with incident-response processes |
| `seed-018` | `18.5` | `18.2` | 2 | Reranker confuses internal and external penetration tests |
| `dev-031` | `13.2` | `13.7` | 2 | Host intrusion detection and prevention are close semantic neighbors |

### Decision

The retrieval configuration is frozen without additional tuning.

The hybrid pipeline exceeds all development quality thresholds,
and every gold safeguard appears within the top three. Introducing
special-case lexical boosts for the three observed errors could
overfit the development benchmark.

The next action is a single evaluation of the previously unopened
held-out test split.

## R-002: Held-out test evaluation

Date: 2026-09-05

The retrieval configuration was committed and tagged as
`v0.2.0-retrieval-freeze` before this test was executed. The
held-out split was evaluated once without changing its questions,
labels, retrieval models, or parameters.

### Held-out results

| Method | Recall@1 | Recall@3 | Recall@5 | MRR@5 | nDCG@5 | Mean latency |
|---|---:|---:|---:|---:|---:|---:|
| Vector | 0.778 | 0.944 | 1.000 | 0.863 | 0.897 | 49.06 ms |
| BM25 | 0.778 | 0.889 | 0.944 | 0.838 | 0.865 | 1.36 ms |
| RRF | 0.833 | 0.944 | 0.944 | 0.880 | 0.896 | 50.62 ms |
| Hybrid reranked | **0.833** | **1.000** | **1.000** | **0.917** | **0.938** | 1519.69 ms |

Latency values are machine-dependent and should be interpreted
only within the same benchmark run.

### Held-out error analysis

| Example | Gold | Top result | Gold rank | Observation |
|---|---|---|---:|---|
| `test-001` | `1.5` | `1.3` | 2 | Active and passive asset discovery are close semantic alternatives |
| `test-007` | `7.7` | `16.2` | 2 | Vulnerability remediation overlaps with software vulnerability handling |
| `test-013` | `13.3` | `13.2` | 2 | Network and host intrusion detection differ mainly by deployment location |

### Generalization assessment

Hybrid Recall@1 decreased from `0.917` on development data to
`0.833` on held-out data. Recall@3 and Recall@5 remained `1.000`.
MRR@5 decreased from `0.954` to `0.917`, while nDCG@5 decreased
from `0.966` to `0.938`.

The system therefore generalizes reliably within the scope of this
small manually curated benchmark, particularly when the top three
safeguards are considered. The result should not be presented as a
universal compliance benchmark.

No retrieval tuning was performed after viewing the held-out
results.