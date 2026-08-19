# IA Tour Guide Roadmap

> [!NOTE]
> A shipped release represents an agreed scope, not the completion of every later
> hardening or follow-up task listed below.

## Priority and status

- **P0** — required for a working project or release scope

- **P1** — required for a strong course submission

- **P2** — optional improvement

- **P3** — stretch goal

- **✅ Complete** — core milestone outcome is delivered

- **🔄 In progress** — active work remains

- **⏳ Planned** — not started

- **📦 Shipped** — released scope

______________________________________________________________________

## ✅ Milestone 1 — Project Foundation

**Delivered:** project documentation, configuration, dependency management, logging, and
test structure.

______________________________________________________________________

## ✅ Milestone 2 — Document Ingestion

**Delivered:** page-aware PDF extraction, structured artifacts, section-aware chunking,
embeddings, transactional persistence, and independent ingestion commands.

______________________________________________________________________

## ✅ Milestone 3 — Knowledge Base and Retrieval

**Delivered:** persisted embedding metadata and ranked vector, full-text, and hybrid
retrieval with source and page provenance.

______________________________________________________________________

## 📦 Release v0.1.0 — Retrieval prototype

**Status:** 📦 Shipped

Delivered PDF extraction, chunking, embeddings, vector search, full-text search, and CLI
retrieval.

______________________________________________________________________

## ✅ Milestone 4 — RAG Application

**Delivered:** configurable LLM generation, structured and validated citations, clear
failure handling, HTTP and CLI access, and a Gradio chat interface.

______________________________________________________________________

## 📦 Release v0.2.0 — RAG MVP

**Status:** 📦 Shipped

Delivered the end-to-end Brittany-guide RAG experience with grounded answers, validated
citations, and a basic chat interface.

______________________________________________________________________

## ✅ Milestone 5 — Retrieval and RAG Evaluation

**Delivered:** a 105-case golden dataset, retrieval comparison and hybrid selection,
reproducible search/RAG/judge workflows, and isolated evaluation results and ratings.

______________________________________________________________________

## 📦 Release v0.3.0 — Evaluation

**Status:** 📦 Shipped

Delivered the retrieval-quality baseline, selected hybrid configuration, runnable RAG
and judge workflows, and documented baseline evidence.

______________________________________________________________________

## ✅ Milestone 6 — User Feedback

**Delivered:** answer ratings and optional comments through chat, API, and CLI, linked
to persisted RAG results.

______________________________________________________________________

## 🔄 Milestone 7 — Monitoring

### [P0] Establish queryable RAG execution records

- [x] Persist the question, answer, success state, error details, source counts, model
  metadata, timings, and trace for each stored RAG result.
- [x] Link answer ratings to their stored RAG results.

**Acceptance criteria**

- [x] A stored result can be inspected with its answer, execution status, and associated
  ratings.

### [P1] Summarize RAG quality and operational signals

- [ ] Aggregate persisted RAG outcomes, ratings, latency, errors, and model usage into a
  concise report or view.
- [ ] Make the main quality and operational signals easy to inspect during a demo.

**Acceptance criteria**

- [ ] A reviewer can inspect answer quality, failure rates, and latency from persisted
  application data.
- [ ] The report distinguishes successful, insufficient-context, and failed work.

### [P2] Provide a monitoring view

- [ ] Add a lightweight dashboard for request volume, ratings, latency,
  insufficient-context outcomes, errors, and frequently retrieved destinations.

**Acceptance criteria**

- [ ] The dashboard presents the most useful quality and operational trends from
  persisted data.

______________________________________________________________________

## 🔄 Milestone 8 — Reproducibility and Delivery

### [P0] Containerize and document the project

- [x] Provide Dockerfiles, Docker Compose services, persistent database storage, and
  startup health checks.
- [x] Document setup, configuration, ingestion, usage, and limitations.
- [ ] Add public screenshots and final evaluation evidence to the project documentation.

**Acceptance criteria**

- [x] A new user can run the application through Docker Compose.
- [x] Services start in the required order and data persists across restarts.

### [P1] Add delivery automation and demo material

- [ ] Run the relevant test suite on pull requests.
- [ ] Record a concise demo showing ingestion, a grounded answer, an unsupported
  question, and sources.

**Acceptance criteria**

- [ ] A contributor can verify changes automatically before merge.
- [ ] A reviewer can understand the project outcome from the README and demo.

______________________________________________________________________

## 🗓️ Release v1.0.0 — Final submission

**Status:** ⏳ Planned

The final submission requires the remaining delivery work: CI, final documentation
evidence, and a concise demo.

______________________________________________________________________

## Follow-up work after v1.0.0

These improvements are useful but are not priorities for the final submission.

### [P1] Ingestion and retrieval hardening

- [ ] Add focused chunking tests for boundaries, traceability, reproducibility,
  oversized paragraphs, and hard limits.
- [ ] Record and verify full parser and chunking provenance for each imported document.
- [ ] Add PostgreSQL integration coverage for aggregate insertion, rollback, and
  constraints.
- [ ] Pin the embedding model artifact and add reproducibility and retrieval smoke
  coverage.
- [ ] Add ingestion-run status, duration, counts, and failure details if operational
  monitoring becomes necessary.
- [ ] Add detailed structured logs and traces only if future debugging needs justify
  them.

### [P2] Retrieval and answer improvements

- [ ] Strengthen deterministic handling for unsupported and live-information questions
  where evaluation identifies a need.
- [ ] Evaluate query rewriting, reranking, and additional hybrid configurations; retain
  them only when they improve quality within the latency budget.

### [P2] Controlled LLM comparison

- [ ] Compare at least two prompt or generation configurations using controlled
  retrieval context.
- [ ] Publish a concise comparison report with configuration, quality, and limitation
  evidence.
- [ ] Add robustness, efficiency, and cost studies only when they support a concrete
  product decision.

______________________________________________________________________

## Stretch goals

### [P2] Multi-document lifecycle

- [ ] Support multiple brochures, document versions, and safe replacement of changed
  content.
- [ ] Exclude superseded chunks from retrieval.

### [P2] Live-information routing

- [ ] Route questions to the knowledge base, approved live tools, or a clear limitation
  response.
- [ ] Restrict live tools to an explicit allowlist and make their use observable.

### [P3] Advanced evaluation and quality gates

- [ ] Add human review, robustness, cost, and CI quality-gate evaluation when a concrete
  product decision requires them.

### [P3] Cloud deployment

- [ ] Deploy a public demo with managed secrets and documented operations.
