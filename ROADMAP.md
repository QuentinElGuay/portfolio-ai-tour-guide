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

**Delivered:** project documentation, configuration, dependency management, logging, a
separated runtime/development/test dependency model, and unit-test structure.

______________________________________________________________________

## ✅ Milestone 2 — Document Ingestion

**Delivered:** page-aware PDF extraction from remote URLs or local files, structured
artifacts, section-aware chunking, embeddings, transactional persistence, and
independent ingestion commands.

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
failure handling, HTTP and CLI access, a Gradio chat interface, a deterministic fixture
LLM for end-to-end tests, and a zero-cost Brittany demo provider with friendly
supported-question suggestions.

______________________________________________________________________

## 📦 Release v0.2.0 — RAG MVP

**Status:** 📦 Shipped

Delivered the end-to-end Brittany-guide RAG experience with grounded answers, validated
citations, and a basic chat interface.

______________________________________________________________________

## ✅ Milestone 5 — Retrieval and RAG Evaluation

**Delivered:** a 105-case golden dataset, an annotator that can edit and create cases,
retrieval comparison and hybrid selection, reproducible search/RAG/judge workflows, and
isolated evaluation results and ratings.

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

## ✅ Milestone 7 — Monitoring

**Delivered:** persisted operational RAG records and user feedback, schema-separated
evaluation and production usage tracking, model pricing validation, curated cost views,
and preconfigured Quality and Costs dashboards.

______________________________________________________________________

## 📦 Release v0.4.0 — Monitoring

**Status:** 📦 Shipped

Delivered persisted operational RAG records, user feedback monitoring, offline
evaluation reporting, production quality and cost dashboards, schema-separated LLM usage
tracking, model pricing validation, and Metabase backup/restore support.

______________________________________________________________________

## ✅ Milestone 8 — Reproducibility and Delivery

**Delivered:** containerized application and Airflow-orchestrated ingestion services
with persistent storage and health checks, a no-cost Brittany demo, deterministic smoke
tests, CI validation and release-image publishing, current evaluation evidence, and
complete README, tutorial, screenshot, and configuration documentation.

______________________________________________________________________

## 📦 Release v1.0.0 — Final submission

**Status:** 📦 Shipped

The final submission expands the service from Brittany-only content to multi-regional
travel guides, with public screenshots and a tutorial. Delivery automation, evaluation
evidence, and a deterministic smoke test are also available.

______________________________________________________________________

## ⏳ Milestone 9 — Explicitly Agentic Travel Assistant

**Goal:** make the agent boundary explicit by separating UI navigation, conversation
state, and turn-level agent reasoning, then implement a bounded, inspectable tool loop.

### [P0] Separate responsibilities

- [ ] Keep guided buttons and labels as a chat-UI/navigation concern rather than the
  primary routing mechanism of the RAG agent.
- [ ] Keep session history, follow-up resolution, and thread checkpointing in a separate
  conversation layer.
- [ ] Define the travel-agent graph as the owner of one turn's planning, tool use,
  evidence evaluation, answer generation, and stopping decision.
- [ ] Replace `ChatBackend.ask(messages, option_id=...)` with an input that accepts the
  submitted question and optional guided-navigation ID.
- [ ] Remove app-side message construction and history normalization from the Gradio
  layer; retain only UI rendering and event adaptation there.

### [P0] Add an explicit bounded tool loop

- [ ] Extract retrieval into a typed `search_tourism_knowledge_base` tool returning
  passages, source identity, pages, and relevance metadata.
- [ ] Replace the mostly one-pass graph with explicit `plan -> tool -> evaluate`
  transitions.
- [ ] Let the agent select bounded actions: `search_knowledge_base`,
  `reformulate_search`, `answer_from_context`, or `refuse`.
- [ ] Add an evidence-evaluation node that checks whether retrieved context is
  sufficient before generation.
- [ ] Add bounded retry/reformulation for insufficient evidence, followed by refusal
  when the retry budget is exhausted.
- [ ] Keep citation validation as a mandatory post-generation safety boundary.
- [ ] Enforce limits on tool names, tool-call count, retrieval scope, and unsupported
  claims.

### [P1] Make agent behavior inspectable

- [ ] Define typed graph state for the question, intent, planned actions, tool calls,
  evidence, retry count, answer, citations, and final status.
- [ ] Record structured action metadata, without exposing private chain-of-thought, for
  CLI verbose output, API diagnostics, evaluation, and monitoring.
- [ ] Update the README and architecture diagrams to document the bounded agent loop and
  the separation between conversation orchestration and agent reasoning.
- [ ] Add tests for action routing, tool execution, evidence sufficiency, retry limits,
  refusal, citation validation, and trace output.

### [P1] LangGraph architecture hardening

- [ ] Refine the outer conversation graph to use explicit conditional edges or `Command`
  routing for initialization, guided actions, free text, and terminal states.
- [ ] Decompose the turn-level `TravelAgent` subgraph into explicit plan, tool,
  evaluate, answer, and refuse nodes where LangGraph provides a clear benefit.
- [ ] Keep checkpoint ownership exclusively in the outer conversation graph and verify
  the boundary with graph-state and checkpoint tests.

______________________________________________________________________

## ⏳ Release v1.3.0 — Bounded agentic RAG

**Status:** ⏳ Planned

This release will deliver a clearly separated, source-grounded travel agent with an
explicit retrieval tool, bounded planning and retry behavior, citation validation, and
observable execution traces. The Gradio chat remains a client of the conversation API,
while LangGraph owns the stateful turn-level agent workflow.

______________________________________________________________________

## Follow-up work after v1.0.0

These improvements are useful but are not priorities for the final submission.

### [P1] Test, ingestion, and retrieval hardening

- [ ] Add focused chunking tests for boundaries, traceability, reproducibility,
  oversized paragraphs, and hard limits.
- [ ] Record and verify full parser-version provenance for each imported document.
  Source checksums, chunking configuration, embedding metadata, and debug artifacts are
  already persisted or emitted.
- [ ] Add PostgreSQL integration coverage for aggregate insertion, rollback, and
  constraints; the current database fixtures are intentionally disabled until they guard
  an isolated schema.
- [x] Add deterministic ingestion and retrieval smoke coverage with a fixture LLM and an
  isolated schema.
- [x] Validate the Airflow Compose profile and DAG imports in CI.
- [ ] Add container-level runtime smoke tests for the production ingestion and agent
  images, rather than validating application behavior only through the host `uv`
  environment.
- [ ] Add an Airflow CI integration test that triggers `ingest_documents` with a small
  fixture document and verifies initialization, ingestion, and database persistence.
- [ ] Pin the embedding model artifact and verify reproducibility against it.
- [ ] Add ingestion-run status, duration, counts, and failure details if operational
  monitoring becomes necessary.
- [ ] Add detailed structured logs and traces only if future debugging needs justify
  them.

### [P2] Retrieval and answer improvements

- [ ] Strengthen deterministic handling for unsupported and live-information questions
  where evaluation identifies a need.
- [ ] Evaluate query rewriting, reranking, and additional hybrid configurations; retain
  them only when they improve quality within the latency budget.

### [P2] Conversation and agentic architecture

- [ ] Separate `RAGResult` from conversation messages and agent execution state so the
  assistant can support agentic actions, tool calls, and multi-step interactions rather
  than only pure RAG answers. Use the new conversation/assistant-turn model as the
  appropriate place to store answer emotion and other presentation metadata, while
  keeping retrieval provenance attached to RAG results.

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
