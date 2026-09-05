# Evaluation Experiments

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

## G-001: Generation development evaluation

Date: 2026-09-05

### Evaluation protocol

The generation benchmark uses the same frozen dataset, corpus,
retrieval configuration, and 36-question development split as the
retrieval benchmark.

The complete pipeline includes hybrid retrieval, safeguard context
selection, Ollama generation, citation validation, and safe
single-source citation normalization.

All questions in dataset version `0.2.0` are answerable. Therefore,
this benchmark does not measure correct abstention on out-of-scope
questions.

### Frozen quality thresholds

| Metric | Minimum |
|---|---:|
| Retrieval hit rate | 0.950 |
| Context hit rate | 0.800 |
| Answer rate | 0.800 |
| Citation-valid rate | 0.800 |
| Expected-source hit rate | 0.800 |
| Mean citation coverage | 0.900 |

### Development results

| Metric | Initial run | Final run |
|---|---:|---:|
| Retrieval hit rate | 1.000 | 1.000 |
| Context hit rate | 0.917 | 0.917 |
| Answer rate | 0.417 | **1.000** |
| Abstention rate | 0.583 | **0.000** |
| Citation-valid rate | 0.472 | **1.000** |
| Expected-source hit rate | 0.917 | 0.917 |
| Mean citation coverage | 0.967 | **1.000** |
| Retry rate | 0.528 | **0.000** |
| Mean generation attempts | 1.528 | **1.000** |

The initial run showed that the model frequently produced grounded
answers without the required evidence-label syntax. Safe citation
normalization was therefore added only when exactly one evidence
source is available. When multiple sources are available, the
generator must still produce and validate its own citation labels.

Citation validation was also strengthened to reject malformed labels
such as `[S3.4]`. Evidence labels such as `[S1]` must not be confused
with CIS safeguard identifiers such as `3.4`.

### Final development latency

| Stage | Mean | p95 |
|---|---:|---:|
| Retrieval | 1676.24 ms | 2143.73 ms |
| Context selection | 0.02 ms | 0.04 ms |
| Generation | 35766.16 ms | 45351.50 ms |
| Total | 37442.45 ms | 47604.66 ms |

Latency is machine- and model-dependent. Generation accounts for
most end-to-end latency.

### Remaining error analysis

The expected source was absent from selected context for three of 36
questions:

| Example | Expected | Selected | Observation |
|---|---|---|---|
| `seed-011` | `11.1` | `17.3` | Data restoration was confused with incident reporting |
| `seed-018` | `18.5` | `18.2` | Internal penetration testing was confused with external testing |
| `dev-031` | `13.2` | `13.7` | Host intrusion detection was confused with host intrusion prevention |

These are retrieval/context-selection errors rather than citation
formatting errors. No special-case tuning was introduced because it
could overfit the development set.

### Interpretation and limitations

Citation validity measures citation syntax and whether labels refer
to supplied evidence. It does not independently prove that every
generated claim is semantically correct.

Expected-source hit rate provides a safeguard-level grounding proxy,
but a larger benchmark and human answer-quality assessment would be
needed to claim broad compliance accuracy.

The generation prompt, citation handling, quality thresholds, and
development configuration are frozen before the held-out generation
evaluation.

## G-002: Held-out generation evaluation

Date: 2026-09-05

The generation configuration, citation handling, quality
thresholds, and development results were committed and tagged as
`v0.3.0-generation-freeze` before this evaluation.

The 18-question held-out split was evaluated once. No configuration,
prompt, threshold, dataset, or model changes were made after viewing
the results.

### Held-out results

| Metric | Development | Held-out |
|---|---:|---:|
| Retrieval hit rate | 1.000 | 1.000 |
| Context hit rate | 0.917 | 0.833 |
| Answer rate | 1.000 | 1.000 |
| Abstention rate | 0.000 | 0.000 |
| Citation-valid rate | 1.000 | 1.000 |
| Expected-source hit rate | 0.917 | 0.833 |
| Mean citation coverage | 1.000 | 1.000 |
| Retry rate | 0.000 | 0.000 |
| Mean generation attempts | 1.000 | 1.000 |

All frozen generation quality thresholds passed.

### Held-out latency

| Stage | Mean | p95 |
|---|---:|---:|
| Retrieval | 2094.53 ms | 2557.00 ms |
| Context selection | 0.03 ms | 0.05 ms |
| Generation | 36381.23 ms | 44763.16 ms |
| Total | 38475.82 ms | 46834.70 ms |

### Held-out source-selection errors

The expected safeguard was absent from selected context for three
questions:

| Example | Expected | Top selection | Observation |
|---|---|---|---|
| `test-001` | `1.5` | `1.3` | Active and passive asset discovery overlap |
| `test-007` | `7.7` | `16.2` | General vulnerability remediation overlaps with application vulnerability handling |
| `test-013` | `13.3` | `13.2` | Network and host intrusion detection differ mainly by deployment location |

The expected source was selected for 15 of 18 held-out questions.
The result exceeds the frozen `0.800` threshold, but the small margin
and dataset size should be reported as limitations.

Citation validity confirms correct citation syntax and supplied-source
references. It does not independently establish semantic correctness.

No tuning was performed after the held-out evaluation.