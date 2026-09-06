# Security Model

## Scope

Compliance RAG is a local evidence-grounded question-answering
application for the CIS Controls corpus. It is not an authorization,
policy-enforcement, or autonomous compliance decision system.

## Protected assets

- Local CIS source documents and processed data
- Chroma vector database
- Model and service configuration
- Application logs
- System and generation prompts
- Host Ollama service

## Trust boundaries

User questions are untrusted input. The processed CIS corpus,
application configuration, and locally built vector index are trusted
deployment inputs.

The API validates question length, rejects unexpected request fields,
blocks unsafe control characters, and rejects common explicit
prompt-control instructions before retrieval.

## Implemented controls

- Evidence-only generation instructions
- Allowlisted evidence citation labels
- Malformed and unknown citation rejection
- Safe single-source citation normalization
- Strict request schema
- Generic public pipeline errors
- Internal structured error logging
- Localhost-only Docker port binding
- CORS origin allowlist
- Liveness and readiness separation
- Automated unit and integration tests

## Limitations

Prompt-injection detection is pattern-based and cannot guarantee
detection of every adversarial instruction.

Citation validity proves that citation labels reference supplied
evidence. It does not independently prove semantic correctness.

The current benchmark contains answerable compliance questions.
A separate safety benchmark is required to measure abstention on
unsupported or out-of-scope questions.

Authentication and rate limiting are not implemented. The service
should remain behind a trusted local or authenticated reverse proxy
if deployed beyond a developer workstation.

The vector index and processed corpus must be protected from
unauthorized modification because retrieved evidence is treated as
trusted reference data.

## Reporting

Do not include secrets, private document contents, environment values,
or internal filesystem paths in public issue reports.

## Dependency audit

The dependency audit identified patched releases for aiohttp,
cryptography, Pillow, setuptools, and PyTorch. The project pins the
available fixed releases.

ChromaDB `1.5.9` remains affected by published server-side security
advisories for authorization bypass and unsafe remote embedding-model
configuration. No patched PyPI release was available when this audit
was completed.

The current application does not run the ChromaDB HTTP/FastAPI server.
It uses an embedded `PersistentClient` with a locally generated,
trusted collection. Users cannot create collections, update embedding
functions, select model repositories, or access ChromaDB API routes
through the Compliance RAG API.

Until a patched ChromaDB version is released:

- Do not run `chroma run` or expose a ChromaDB server.
- Keep the vector database local and read-only to untrusted users.
- Do not load embedding configurations from user input.
- Keep the Compliance RAG API bound to localhost or behind an
  authenticated reverse proxy.
- Recheck ChromaDB advisories before each release.

These mitigations reduce exposure but do not remove the vulnerable
dependency. The exception must be removed when a compatible patched
release becomes available.

## Residual generation risk

A citation-valid response may still contain an unsupported,
contradictory, or incorrectly interpreted statement. Citation
validation verifies evidence-label syntax and source membership; it
does not perform semantic entailment checking.

The local language model may add unnecessary explanatory sentences
that conflict with an otherwise correct answer. Compliance responses
must therefore be treated as decision-support output and reviewed
against the returned source text before operational use.