# BreizhGuide Roadmap

> [!NOTE]
> This roadmap had been created by ChatGPT as a first draft and might evolve over time.

## Priority legend

- **P0** — Required for a working project
- **P1** — Required for a strong course submission
- **P2** — Optional improvement
- **P3** — Stretch goal

## Delivery status

- **✅ Passed / core complete** — the milestone's core deliverable is usable; remaining
  items are polish or follow-up
- **🔄 In progress** — work has started, but the milestone is not complete
- **⏳ Planned** — work has not started yet
- **🟢 Ready to ship** — the release scope is complete; publication is pending
- **📦 Shipped** — the release is available
- **🗓️ Planned release** — the release is not available yet

______________________________________________________________________

# ✅ Milestone 1 — Project Foundation

## [P0] Create initial README

**Labels:** `documentation`

- [x] Add project title
- [x] Add project description
- [x] Add project status
- [x] Add table of contents
- [x] Add overview
- [x] Add data source
- [x] Add roadmap
- [x] Add contributing section
- [x] Add license

**Acceptance criteria**

- [x] A visitor understands the project's purpose
- [x] The data source is documented
- [x] Repository structure is easy to navigate

______________________________________________________________________

## [P0] Define project scope

**Labels:** `planning`, `documentation`

- [x] Define target users
- [x] Define supported questions
- [x] Define unsupported questions
- [x] Define supported languages
- [x] Define success criteria

**Acceptance criteria**

- [x] Scope is documented in `README.md`
- [x] Limitations are explicit
- [x] Example use cases are included

**Tools**

- Markdown
- Mermaid
- GitHub Issues

______________________________________________________________________

## [P0] Create project structure

**Labels:** `setup`, `developer-experience`

- [x] Create Python project
- [x] Add dependency management
- [x] Add environment configuration
- [x] Add basic logging
- [x] Add test structure

**Acceptance criteria**

- [x] Project installs with one command
- [x] Application starts locally
- [x] Tests can be executed

**Tools**

- Python
- uv
- Pydantic Settings
- pytest

______________________________________________________________________

# ✅ Milestone 2 — Document Ingestion

## [P0] Inspect the tourism brochure

**Labels:** `data`, `research`

- [x] Verify text is selectable
- [x] Inspect pages, columns, maps, and tables
- [x] Check repeated headers and footers
- [x] Verify source and redistribution rights

**Acceptance criteria**

- [x] Extraction risks are documented
- [x] Source URL and license notes are recorded

**Tools**

- PyMuPDF
- Jupyter

______________________________________________________________________

## [P0] Extract structured PDF content

**Labels:** `ingestion`, `pdf`

- [x] Extract text page by page
- [x] Preserve original page numbers

<!-- - [ ] Preserve document title and author -->

- [x] Reconstruct logical paragraphs
- [x] Detect section titles from typography
- [x] Infer heading levels
- [x] Record page ranges for every paragraph
- [x] Actually remove repeated headers and footers from content
- [x] Export the parsed document as structured JSON

**Acceptance criteria**

- [x] Each paragraph contains text, `page_start`, and `page_end`
- [x] Each section contains title, heading level, page range, and paragraphs
- [x] French characters are preserved
- [x] Header/footer text is absent from exported content
- [x] Sample paragraphs and headings match the original document
- [x] Parsing the same PDF twice produces identical output

______________________________________________________________________

## [P0] Preserve document hierarchy

**Labels:** `ingestion`, `document-model`

- [x] Derive parent sections from heading levels
- [x] Preserve nested sections in the parsed document
- [x] Build heading paths for retrieval chunks
- [x] Preserve section and paragraph ordering
- [x] Preserve paragraph and section page ranges

**Acceptance criteria**

- [x] Child sections are nested under their parents
- [x] Paragraph order is deterministic
- [x] Heading paths are correct

**Example heading path**

`["Brittany", "Family life", "Schools"]`

______________________________________________________________________

## [P0] Implement document chunking

**Labels:** `ingestion`, `rag`

- [x] Chunk paragraphs within section boundaries
- [x] Preserve heading paths
- [x] Preserve page ranges
- [x] Add deterministic chunk identifiers
- [x] Add configurable target and maximum character sizes
- [x] Prevent chunks from crossing section boundaries
- [x] Store document title and section path with each chunk
- [x] Record chunk position and character count
- [x] Build separate embedding input from title, heading path, and body
- [ ] Add automated tests for chunk traceability and boundary preservation
- [ ] Add reproducibility tests for identical input and configuration
- [ ] Add tests for oversized paragraphs, labeled entries, and hard size limits

**Acceptance criteria**

- [x] Every chunk can be traced to source pages and a heading path
- [x] Every chunk has `page_start` and `page_end`
- [ ] Chunks never cross unrelated section boundaries
- [x] Character-based chunking parameters are configurable through the CLI
- [ ] Chunk identifiers and output are reproducible
- [x] Stored `text` does not contain synthetic heading enrichment
- [x] Synthetic heading enrichment is stored separately in `embedding_text`

______________________________________________________________________

## [P1] Create ingestion interfaces and a CLI

**Labels:** `ingestion`, `cli`

- [x] Add typed download, parse, chunk, embed, and load stages
- [x] Add one CLI command for each independent stage
- [x] Add a `run` command that processes one or more documents sequentially
- [x] Keep normal end-to-end execution in memory
- [x] Retain every intermediate artifact only in debug mode
- [x] Add versioned JSON artifacts between independent stages
- [x] Make chunked and embedded artifacts self-contained
- [x] Read optional collection metadata from the document input
- [x] Calculate and persist the PDF source checksum
- [x] Generate chunks as part of the ingestion pipeline
- [x] Generate embeddings before database upload
- [x] Upload the document and chunks in one database transaction
- [x] Reject an existing source URL without mutating stored data
- [x] Print concise completion summaries for the pipeline and individual stages
- [x] Return validation and stage failures as nonzero CLI errors

**Acceptance criteria**

- [x] Ingestion runs without a notebook
- [x] Every independent command processes exactly one document
- [x] Only `run` accepts an array of documents
- [x] Normal execution creates no intermediate files
- [x] Debug execution creates PDF, text, Markdown, and all JSON artifacts
- [x] Reprocessing an unchanged source URL does not create duplicates
- [x] Invalid input or stage artifacts fail before database insertion
- [x] CLI help documents commands and their required inputs

**Current scope decision**

The CLI deliberately uses insert-only document semantics. An existing source URL is
rejected instead of being upserted, because replacing document metadata without
replacing all chunks and embeddings would create an inconsistent aggregate.
Version-aware replacement is postponed to the document lifecycle stretch goal.

**Tools**

- Click
- Pydantic Settings
- Standard logging
- `uv`

______________________________________________________________________

## [P0] Persist documents and chunks in PostgreSQL

**Labels:** `database`, `ingestion`, `pgvector`

- [x] Define embedding model, document, and document chunk tables
- [x] Use `(document_id, chunk_id)` as the chunk primary key
- [x] Require every document to reference an embedding model
- [x] Store timezone-aware PDF creation and modification timestamps
- [x] Store vectors in a pgvector column with a configured dimension
- [x] Map domain dataclasses to SQLAlchemy rows
- [x] Insert a complete document aggregate transactionally
- [x] Reuse matching embedding model metadata
- [x] Reject incompatible embedding model configurations
- [x] Reject duplicate source URLs
- [x] Persist effective target and maximum chunk sizes
- [ ] Persist parser and chunking versions
- [ ] Add PostgreSQL integration tests for commit, rollback, and constraints

**Acceptance criteria**

- [x] Schema initialization is callable without a notebook
- [x] A document and all its chunks share one transaction
- [x] Duplicate detection does not alter existing rows
- [ ] A real PostgreSQL test proves rollback leaves no partial aggregate
- [ ] Stored processing provenance explains how chunks were produced

______________________________________________________________________

## 🔄 Milestone 2 follow-up

These are the remaining Milestone 2 hardening tasks. They can be polished after the core
delivery and do not block the v0.1.0 retrieval prototype:

- [ ] **P0 — Add focused chunking tests.** Cover section boundaries, page and
  heading-path traceability, deterministic identifiers, reproducible output, labeled
  entries, oversized paragraphs, and hard character limits.
- [ ] **P0 — Persist processing provenance.** Populate `parser_version` and
  `chunking_version`; effective target and maximum chunk sizes are now stored with each
  document.
- [ ] **P0 — Add PostgreSQL integration coverage.** Initialize a temporary test database
  and verify aggregate insertion, duplicate rejection, constraints, and rollback after a
  chunk failure.
- [ ] **P0 — Run and record an end-to-end ingestion smoke test.** Ingest the configured
  Brittany PDF through Docker, inspect debug artifacts and exported CSV data, and
  confirm that every stored chunk has a vector and source pages.

The following work is deliberately deferred and is not a Milestone 2 exit criterion:

- Versioned replacement and stale-chunk cleanup are part of the document lifecycle
  stretch goal.
- Persistent ingestion status, structured stage failures, and detailed telemetry are
  part of Milestone 7 observability.
- Token-based chunk sizing, overlap, and token counts
- Stable section and paragraph IDs beyond page ranges and heading paths

______________________________________________________________________

# ✅ Milestone 3 — Knowledge Base and Retrieval

## [P0] Generate lightweight English embeddings

**Labels:** `embeddings`, `rag`

- [x] Select an English embedding model
- [x] Select a lightweight inference runtime
- [x] Generate embeddings for all chunks
- [x] Use `embedding_text` as the embedding input
- [x] Process embeddings in configurable batches
- [x] Display embedding progress
- [x] Validate the number of returned vectors
- [x] Validate vector dimensions
- [x] Store embedding model metadata
- [x] Store whether vectors are normalized
- [x] Store a SHA-256 checksum of each embedding input
- [ ] Pin the embedding model revision or artifact version
- [x] Use the same model, revision, normalization, and runtime for queries
- [ ] Add embedding reproducibility tests
- [ ] Add retrieval smoke tests

**Selected implementation**

- Model: `BAAI/bge-small-en-v1.5`
- Runtime: FastEmbed with ONNX Runtime
- Vector dimensions: `384`
- Similarity: cosine similarity or dot product over normalized vectors
- Passage input: chunk `embedding_text`
- Query input: the same model and normalization configuration

**Acceptance criteria**

- [ ] English queries retrieve relevant English content
- [x] Every stored chunk has exactly one 384-dimensional vector
- [x] Stored and query embeddings use the same model configuration
- [ ] Embedding generation is reproducible for a pinned model artifact
- [ ] Unchanged `embedding_input_sha256` values can skip re-embedding
- [ ] Embeddings produced by different runtimes are never mixed in one index
- [ ] Retrieval smoke tests return the expected source sections and pages

**Tools**

- FastEmbed
- ONNX Runtime
- NumPy
- tqdm

______________________________________________________________________

## [P0] Implement vector search

**Labels:** `retrieval`, `vector-search`

- [x] Create a pgvector-backed chunk index
- [x] Store chunks and metadata
- [x] Implement top-k retrieval
- [x] Return page references with retrieved chunks
- [x] Return typed retrieval hits with scores and a clearly defined score contract
- [x] Use one scored search-result API for vector and full-text primitives
- [x] Return typed source provenance with each retrieved chunk

**Acceptance criteria**

- [x] Search returns ranked chunks
- [x] Results include page citations
- [x] Collection persists locally

**Tools**

- PostgreSQL with pgvector

______________________________________________________________________

## [P1] Implement PostgreSQL full-text search

**Labels:** `retrieval`, `search`

- [x] Index chunk text
- [x] Implement lexical retrieval
- [x] Return ranked chunks
- [ ] Test exact place-name queries

**Acceptance criteria**

- [x] Lexical retrieval can run independently
- [ ] Results are included in evaluation

**Tools**

- PostgreSQL full-text search

______________________________________________________________________

## [P1] Implement hybrid search

**Labels:** `retrieval`, `best-practice`

- [x] Combine vector and full-text search results
- [x] Implement reciprocal rank fusion
- [x] Make retrieval weights and the RRF rank constant configurable
- [x] Represent supported retrieval modes with an explicit `SearchMode` enum
- [ ] Compare against individual retrievers

**Current scope decision**

Hybrid tuning is available through typed `HybridSearchSettings` at the retrieval API
boundary. The vector and text weights default to `1.0`, and the RRF rank constant
defaults to `60`. These settings are intentionally not CLI flags yet; they should be
tuned through evaluation before becoming user-facing options.

**Acceptance criteria**

- [ ] Hybrid retrieval is evaluated
- [ ] Best configuration is documented

**Tools**

- PostgreSQL with pgvector and full-text search

______________________________________________________________________

# 🚀 Release v0.1.0 — Retrieval prototype

**📦 Shipped**

The core retrieval prototype is released in **v0.1.0**. Remaining unchecked items are
tracked as polish, hardening, and follow-up work.

This release includes:

- PDF extraction
- Chunking
- Embedding
- Full-text search
- Vector search
- CLI information retrieval

______________________________________________________________________

______________________________________________________________________

# ✅ Milestone 4 — RAG Application

## [P0] Implement the RAG pipeline

**Labels:** `rag`, `backend`

- [x] Accept a user question
- [x] Retrieve relevant chunks
- [x] Build the prompt
- [x] Call the LLM through a provider-neutral client
- [x] Return answer and retrieved sources
- [x] Deduplicate displayed retrieved sources and their page numbers

**Current implementation decisions**

- [x] Keep retrieved chunks, scores, and source metadata together in one result list
- [x] Expose `RAGResult.chunks` as a derived convenience property

**Service decision**

The agent process owns retrieval and the provider-neutral `LLMClient`. The Gradio chat
is a separate interface service and calls the agent over HTTP, so it has no dependency
on OpenAI settings or credentials.

- [x] Inject an `LLMClient` into the RAG pipeline
- [x] Add configuration for the direct model/provider
- [x] Expose the RAG pipeline through an HTTP API
- [x] Connect the Gradio chat to the agent API
- [x] Return a clear configuration-required response when no LLM API key is available

**Acceptance criteria**

- [x] Answers use retrieved context
- [x] Components can be tested independently

**Current source behaviour**

The application displays all retrieved sources, grouped by document with deduplicated
page numbers. These context references are not yet citations selected and validated from
the LLM response.

**Tools**

- Python
- OpenAI-compatible client

______________________________________________________________________

## [P0] Add a basic chat interface

**Labels:** `frontend`, `gradio`

- [x] Add chat input
- [x] Display conversation history
- [x] Show loading state
- [x] Display retrieved sources and page numbers
- [x] Add reset conversation button
- [x] Add suggested questions

**Acceptance criteria**

- [x] Users can complete a full conversation
- [x] Retrieved sources are visible
- [x] Errors are displayed clearly

**Tools**

- Gradio

______________________________________________________________________

## 🔄 Milestone 4 follow-up

The v0.2.0 MVP is shipped. These hardening tasks are intentionally deferred to the
evaluation milestone and do not change its delivered scope:

- [ ] **P0 — Validate answer behaviour.** Verify grounded answers, clear unsupported
  question responses, English-only responses, and protection against invented prices or
  opening hours.
- [ ] **P0 — Add verified citations.** Require cited `chunk_id` values in a structured
  LLM response, validate them against retrieved context, and display only valid sources.
- [ ] **P1 — Record prompt versions.** Version prompt changes before comparing them.
- [ ] **P2 — Evaluate query rewriting.** Preserve the original question and keep it only
  if evaluation improves retrieval.
- [ ] **P2 — Evaluate reranking.** Retrieve more candidates, rerank them, and keep the
  approach only if it improves quality within an acceptable latency budget.

______________________________________________________________________

# 🚀 Release v0.2.0 — RAG MVP

**📦 Shipped**

Delivers the first end-to-end RAG experience for the Brittany guide:

- Grounded answers
- Retrieved source pages
- Basic Gradio interface

______________________________________________________________________

# ⏳ Milestone 5 — Evaluation

## [P0] Validate generated answers and citations

**Labels:** `rag`, `validation`, `prompt-engineering`

- [ ] Define a structured LLM response containing the answer and cited chunk IDs
- [ ] Validate cited chunk IDs against the retrieved context
- [ ] Render only cited sources, grouped by document with sorted page references
- [ ] Answer only from retrieved context
- [ ] Refuse unsupported questions
- [ ] Avoid inventing prices and opening hours
- [ ] Answer in English
- [ ] Version prompt changes

**Acceptance criteria**

- [ ] Unsupported questions produce a clear limitation message
- [ ] Answers contain valid, verified citations
- [ ] Prompt versions are documented and compared

**Citation contract**

The LLM must return stable retrieved `chunk_id` values alongside its answer. The
application validates that each cited ID belongs to the retrieved context, discards
invalid IDs, and presents only the remaining sources with grouped, sorted pages.

**Tools**

- Plain prompt templates
- OpenAI-compatible client

## [P0] Create retrieval evaluation dataset

**Labels:** `evaluation`, `data`

- [ ] Create 40–60 questions
- [ ] Include English answerable and unsupported questions
- [ ] Record expected pages or topics
- [ ] Include misspellings and paraphrases

**Acceptance criteria**

- [ ] Dataset is versioned
- [ ] Expected results are manually reviewed

**Tools**

- JSONL
- Pandas

______________________________________________________________________

## [P0] Evaluate retrieval approaches

**Labels:** `evaluation`, `retrieval`

- [ ] Evaluate vector search
- [ ] Evaluate full-text search
- [ ] Evaluate hybrid search
- [ ] Compare chunking configurations
- [ ] Measure latency

**Metrics**

- [ ] Hit Rate at K
- [ ] Recall at K
- [ ] Mean Reciprocal Rank
- [ ] Mean latency

**Acceptance criteria**

- [ ] Results are reproducible
- [ ] Best retrieval configuration is selected
- [ ] Results table is included in documentation

**Tools**

- Pandas
- pytest
- Matplotlib or Plotly

______________________________________________________________________

## [P1] Evaluate LLM answers

**Labels:** `evaluation`, `llm`

- [ ] Compare at least two prompts
- [ ] Evaluate correctness
- [ ] Evaluate groundedness
- [ ] Evaluate citation accuracy
- [ ] Evaluate refusal quality
- [ ] Evaluate English-language responses

**Acceptance criteria**

- [ ] Multiple approaches are compared
- [ ] Best configuration is selected
- [ ] Manual review is included

**Tools**

- pytest
- Pandas
- Ragas or DeepEval optional

______________________________________________________________________

## [P2] Evaluate query rewriting

**Labels:** `rag`, `best-practice`

- [ ] Rewrite follow-up questions while preserving the original question
- [ ] Correct common place-name spelling errors
- [ ] Compare rewritten and original retrieval results

**Acceptance criteria**

- [ ] Query rewriting is optional and configurable
- [ ] It is kept only if evaluation improves retrieval

**Tools**

- OpenAI-compatible client
- Lightweight prompt chain

______________________________________________________________________

## [P2] Evaluate document reranking

**Labels:** `retrieval`, `best-practice`

- [ ] Retrieve a larger candidate set
- [ ] Rerank candidates
- [ ] Keep only the best chunks
- [ ] Measure quality and latency impact

**Acceptance criteria**

- [ ] Reranking is evaluated
- [ ] It is kept only if it improves retrieval within the latency budget

**Tools**

- sentence-transformers CrossEncoder

______________________________________________________________________

# 🚀 Release v0.3.0 — Evaluation

**🗓️ Planned release — not shipped**

Ships when **Milestone 5** passes its exit criteria:

- Golden dataset
- Full-text search comparison
- Hybrid search
- Validated citations and prompt evaluation

______________________________________________________________________

# ⏳ Milestone 6 — User Feedback

## [P1] Add user feedback

**Labels:** `monitoring`, `feedback`

- [ ] Add thumbs-up and thumbs-down
- [ ] Add optional feedback comment
- [ ] Store feedback with request ID
- [ ] Confirm feedback submission

**Acceptance criteria**

- [ ] Feedback is persisted
- [ ] Feedback can be linked to a question and answer

**Tools**

- SQLite
- Gradio

______________________________________________________________________

# ⏳ Milestone 7 — Monitoring

## [P1] Log application interactions

**Labels:** `monitoring`, `observability`

- [ ] Log questions and answers
- [ ] Log retrieved chunks
- [ ] Log model and prompt version
- [ ] Log latency
- [ ] Log errors
- [ ] Avoid storing unnecessary personal data

**Acceptance criteria**

- [ ] Logs are structured
- [ ] Each request has a unique ID
- [ ] Monitoring data can be queried

**Tools**

- SQLite
- Structlog

______________________________________________________________________

## [P2] Add ingestion observability

**Labels:** `ingestion`, `monitoring`, `operations`

- [ ] Assign an identifier to every ingestion run
- [ ] Record document and stage status transitions
- [ ] Persist structured failure details
- [ ] Record stage duration and chunk counts
- [ ] Record embedding model, dimensions, and normalization
- [ ] Add an optional detailed CLI summary

**Acceptance criteria**

- [ ] A failed run identifies its document and failing stage
- [ ] Operators can distinguish completed, rejected, and failed runs
- [ ] Operational records do not alter the document aggregate transaction
- [ ] Detailed telemetry is optional in normal CLI output

**Tools**

- Standard logging or Structlog
- PostgreSQL

______________________________________________________________________

## [P1] Build monitoring dashboard

**Labels:** `monitoring`, `dashboard`

- [ ] Add questions-per-day chart
- [ ] Add feedback chart
- [ ] Add latency chart
- [ ] Add insufficient-context chart
- [ ] Add error chart
- [ ] Add most-retrieved destinations chart

**Acceptance criteria**

- [ ] Dashboard contains at least five charts
- [ ] Charts use persisted application data

**Tools**

- Gradio
- Plotly
- Pandas

______________________________________________________________________

# 🚀 Release v0.4.0 — Monitoring

**🗓️ Planned release — not shipped**

Ships when **Milestone 7** passes its exit criteria:

- Feedback
- Logs
- Dashboard

______________________________________________________________________

# 🔄 Milestone 8 — Reproducibility and Delivery

## [P0] Containerize the application

**Labels:** `docker`, `deployment`

- [x] Create application Dockerfiles
- [x] Add persistent PostgreSQL volume
- [x] Add service health checks and startup dependencies
- [x] Run database, ingestion, agent API, and chat services through Docker Compose
- [ ] Document or add optional local LLM provider support

**Acceptance criteria**

- [x] Application runs through Docker Compose
- [x] Data survives container restart
- [x] Services start in the correct order

**Tools**

- Docker
- Docker Compose

______________________________________________________________________

## [P0] Complete project documentation

**Labels:** `documentation`

- [x] Explain the problem
- [x] Document the data source
- [x] Add architecture diagram
- [x] Explain ingestion and retrieval
- [ ] Include evaluation results
- [ ] Include screenshots
- [x] Add setup and usage instructions
- [x] Add configuration guide
- [x] Add ingestion command examples
- [x] Add chat usage examples
- [x] Document limitations

**Acceptance criteria**

- [x] A new user can run the project
- [ ] Every evaluation criterion has visible evidence
- [x] Dependency versions are locked

**Tools**

- Markdown
- Mermaid
- uv.lock

______________________________________________________________________

## [P1] Add automated tests and CI

**Labels:** `testing`, `ci`

- [x] Test PDF extraction
- [x] Test chunk metadata
- [x] Test retrieval
- [ ] Test citation generation
- [ ] Test unsupported-question handling
- [ ] Run tests on pull requests

**Acceptance criteria**

- [ ] CI passes on the main branch
- [x] Core pipeline has automated coverage

**Tools**

- pytest
- GitHub Actions

______________________________________________________________________

## [P1] Record project demo

**Labels:** `documentation`, `demo`

- [ ] Show ingestion
- [ ] Show a grounded answer
- [ ] Show an unsupported question
- [ ] Show sources
- [ ] Show monitoring dashboard

**Acceptance criteria**

- [ ] Demo is linked from the README
- [ ] Demo is short and understandable

**Tools**

- Loom
- OBS Studio

______________________________________________________________________

# 🚀 Release v1.0.0 — Final submission

**🗓️ Planned release — not shipped**

Ships when **Milestone 8** passes its exit criteria:

- Docker Compose
- Tests and CI
- Documentation
- Demo video

______________________________________________________________________

# Stretch Goals

## [P2] Ingest multiple brochures

- [ ] Add document filters
- [ ] Add region and topic metadata
- [ ] Define document identity independently from a mutable source URL
- [ ] Detect unchanged and changed source checksums
- [ ] Add explicit document versions and deprecation status
- [ ] Replace a document, its chunks, and its embeddings atomically
- [ ] Soft-delete or deprecate superseded document versions
- [ ] Remove or exclude stale chunks from retrieval
- [ ] Test concurrent and repeated document updates

## [P2] Add agentic routing and live tools

- [ ] Classify questions as knowledge-base, live-information, or unsupported requests
- [ ] Decide whether retrieval is needed before answering
- [ ] Select an appropriate retrieval mode when searching the knowledge base
- [ ] Use a static workflow for deterministic actions, such as input validation,
  unsupported-question responses, and source formatting
- [ ] Allow the agent to select from approved live-information tools only when needed
- [ ] Return a clear limitation when no knowledge-base result or approved tool can
  answer the question

### Live-information tools

- [ ] Weather service
- [ ] Public transport service
- [ ] Current opening-information service

**Acceptance criteria**

- [ ] Deterministic actions do not depend on an LLM decision
- [ ] Tool calls are limited to an explicit allowlist
- [ ] The selected route and tool use are observable

**Tools**

- Static Python workflow
- OpenAI tool calling
- Open-Meteo
- Public tourism or transport APIs

## [P3] Deploy to the cloud

- [ ] Select hosting provider
- [ ] Configure secrets
- [ ] Add deployment documentation
- [ ] Verify public demo
