# Bon Voyage Roadmap

The roadmap tracks released capabilities and the remaining improvements under
consideration. A release represents the scope delivered in that version; later hardening
work may remain open.

## Released versions

### v0.1.0 — Retrieval prototype

Delivered page-aware PDF extraction, structured document artifacts, chunking,
embeddings, vector search, full-text search, source/page provenance, and CLI retrieval
commands.

### v0.2.0 — End-to-end RAG MVP

Delivered the first complete RAG experience: configurable LLM generation, grounded
answers, validated citations, a FastAPI agent API, a Gradio chat interface, and a
source-aware CLI.

### v0.3.0 — Evaluation

Delivered the retrieval-quality baseline, golden evaluation dataset, retrieval
comparison, hybrid search selection, reproducible RAG and judge workflows, and
documented evaluation evidence.

### v0.4.0 — Monitoring and evaluation persistence

Delivered persisted RAG results and user feedback, production and evaluation schema
separation, LLM usage and pricing tracking, quality and cost dashboards, smoke tests,
and Metabase backup/restore support.

### v1.0.0 — Reproducible multi-document delivery

Delivered multiple travel guides ingestion, Airflow-orchestrated ingestion, idempotent
and forced re-ingestion, a containerized application, persistent storage, health checks,
deterministic demo and smoke tests, CI/CD validation, and a complete tutorial.

### v1.1.0 — Petit Guide

Introduced Petit Guide as the Bon Voyage assistant, including its visual identity,
mascot, avatars, and updated chat presentation.

### v1.2.0 — Improved deterministic demo

Improved the built-in `baguette-llm` demo with a standalone tourism dataset, fuzzy
question matching, configurable matching thresholds, “Did you mean?” suggestions, and
clearer disclosure of demo limitations.

### v1.3.0 — Bon Voyage rebrand and agentic RAG

Delivered the Bon Voyage rebrand and LangGraph implementation. The release separates UI
navigation, durable conversation state, and turn-level agent reasoning; adds a bounded
retrieval tool loop with reformulation, evidence evaluation, refusal, and citation
validation; exposes structured execution traces; persists provider-neutral chat
messages; renames the Docker application service from `agent` to `app`; and improves the
Gradio chat flow and identity suggestions.

### v1.4.0 — Multi-provider Petit Guide

Added Google Gemini alongside OpenAI for structured, source-grounded answers with
bounded search-tool usage. The release also strengthened Petit Guide’s identity and
personality, answered configured identity and destination questions directly, exposed
the active provider and model, and improved provider retries and user-facing
unavailable-service errors.

### v1.4.1 — Reliable demo chat

Made demo mode usable without an indexed knowledge base and improved the Gradio chat’s
first-run experience. Each browser now receives its own backend session and
`/chat/start` welcome message; user messages render before the response arrives; demo
mode is labelled in Petit Guide’s name; and HTTP-backed demo responses use a
configurable short delay. The release also decoupled lightweight chat startup from
embedding settings and migrated chat persistence from `rag_request_id` to `request_id`.

## Future milestones

### Test, ingestion, and retrieval hardening

- [ ] Add focused chunking tests for boundaries, traceability, reproducibility,
  oversized paragraphs, and hard limits.
- [ ] Record and verify full parser-version provenance for each imported document.
- [ ] Add PostgreSQL integration coverage for aggregate insertion, rollback, and
  constraints using an isolated schema.
- [ ] Add container-level runtime smoke tests for the production ingestion and agent
  images.
- [ ] Add an Airflow CI integration test that triggers `ingest_documents` with a small
  fixture document and verifies initialization, ingestion, and persistence.
- [ ] Pin the embedding model artifact and verify reproducibility against it.
- [ ] Add ingestion-run status, duration, counts, and failure details if operational
  monitoring becomes necessary.

### Retrieval and answer improvements

- [ ] Strengthen deterministic handling for unsupported and live-information questions
  where evaluation identifies a need.
- [ ] Evaluate query rewriting, reranking, and additional hybrid configurations; retain
  them only when they improve quality within the latency budget.
- [ ] Finish separating the RAG service from travel-agent-specific flow and navigation
  concerns. The outer conversation graph now uses `TravelTurnResult`, but parts of the
  RAG workflow still import travel-agent flow and identity helpers. Completing this
  boundary will keep RAG reusable infrastructure and make travel-specific behavior live
  entirely in the travel-agent layer.

### Controlled LLM comparison

- [ ] Compare at least two prompt or generation configurations using controlled
  retrieval context.
- [ ] Publish a concise comparison report with configuration, quality, and limitation
  evidence.
- [ ] Add robustness, efficiency, and cost studies only when they support a concrete
  product decision.

### Multi-version document lifecycle

- [ ] Support document versions, and safe replacement of changed content.
- [ ] Exclude superseded chunks from retrieval.

### Live-information routing

- [ ] Route questions to the knowledge base, approved live tools, or a clear limitation
  response.
- [ ] Restrict live tools to an explicit allowlist and make their use observable.

### Advanced evaluation and quality gates

- [ ] Add human review, robustness, cost, and CI quality-gate evaluation when a concrete
  product decision requires them.

### Cloud deployment

- [ ] Deploy a public demo with managed secrets and documented operations.
