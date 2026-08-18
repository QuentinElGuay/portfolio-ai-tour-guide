# IA Tour Guide Roadmap

> [!NOTE]
> This roadmap might evolve over time.

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

## ✅ Milestone 1 — Project Foundation

### [P0] Create initial README

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

### [P0] Define project scope

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

### [P0] Create project structure

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

## ✅ Milestone 2 — Document Ingestion

### [P0] Inspect the tourism brochure

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

### [P0] Extract structured PDF content

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

### [P0] Preserve document hierarchy

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

### [P0] Implement document chunking

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

### [P1] Create ingestion interfaces and a CLI

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

### [P0] Persist documents and chunks in PostgreSQL

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

## ✅ Milestone 3 — Knowledge Base and Retrieval

### [P0] Generate lightweight English embeddings

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

### [P0] Implement vector search

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

### [P1] Implement PostgreSQL full-text search

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

### [P1] Implement hybrid search

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

## 🚀 Release v0.1.0 — Retrieval prototype

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

## ✅ Milestone 4 — RAG Application

### [P0] Implement the RAG pipeline

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
- OpenAI API client

______________________________________________________________________

### [P0] Add a basic chat interface

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

The v0.2.0 MVP is shipped. These hardening tasks do not change its delivered scope.

- [ ] **P1 — Add verified runtime citations.** Require cited `chunk_id` values in a
  structured LLM response, validate them against retrieved context, and display only
  valid sources.
- [ ] **P1 — Enforce runtime answer guardrails.** Add deterministic handling where
  useful for unsupported questions, English-only responses, and unsupported prices or
  opening hours.
- [ ] **P2 — Evaluate query rewriting.** Preserve the original question and keep it only
  if evaluation improves retrieval.
- [ ] **P2 — Evaluate reranking.** Retrieve more candidates, rerank them, and keep the
  approach only if it improves quality within an acceptable latency budget.

______________________________________________________________________

## 🚀 Release v0.2.0 — RAG MVP

**📦 Shipped**

Delivers the first end-to-end RAG experience for the Brittany guide:

- Grounded answers
- Retrieved source pages
- Basic Gradio interface

______________________________________________________________________

## ⏳ Milestone 5 — Retrieval and LLM Evaluation

Milestone 5 is intentionally focused on the two evaluation criteria required for the
project submission:

1. compare multiple retrieval approaches and use the best-performing one;
2. compare multiple LLM approaches and use the best-performing one.

Runtime guardrails, citation enforcement, CI gates, and broader end-to-end RAG quality
evaluation are tracked separately and do not block this milestone.

______________________________________________________________________

### [P0] Create search evaluation dataset

**Labels:** `evaluation`, `data`, `retrieval`

Create a manually reviewed golden dataset for measuring whether the retrieval layer
finds the evidence needed to answer representative Brittany tourism questions.

- [ ] Create 40–60 representative questions
- [ ] Record stable document/page evidence for each answerable question
- [ ] Include exact place-name queries
- [ ] Include paraphrases and common misspellings
- [ ] Include questions where lexical matching should be useful
- [ ] Include questions where semantic matching should be useful
- [ ] Keep unsupported questions in the LLM dataset unless they have a specific
  retrieval expectation

**Dataset shape**

Each case should contain enough information to evaluate retrieval without calling the
LLM, for example:

```json
{
  "id": "retrieval_001",
  "question": "Which places are recommended for families with children?",
  "expected_documents": ["guide-to-the-region-of-brittany"],
  "expected_pages": [18, 19],
  "expected_answer_topics": ["family activities", "children"]
}
```

**Acceptance criteria**

- [ ] Dataset is versioned
- [ ] Expected document/page evidence is manually reviewed
- [ ] Dataset labels remain stable when chunk IDs change
- [ ] Cases cover both lexical and semantic retrieval strengths
- [ ] The same dataset is used for all compared retrieval approaches

**Tools**

- JSONL
- Pandas

______________________________________________________________________

### [P0] Build the evaluation runners

**Labels:** `evaluation`, `developer-experience`

Create reproducible evaluation entry points against versioned datasets. Search
evaluation is offline; RAG and judge evaluation call live LLM providers and are
therefore online.

The evaluation runner is a development tool, not a long-running application service. It
should reuse the same retrieval and LLM application components used by the agent, but
run experiments independently from the Gradio interface and HTTP API.

The primary developer interface should be `make` targets, following the same pattern as
`make init-db`: the command should be simple to run, while Docker Compose can remain an
implementation detail when it provides the right database, network, and dependency
environment. If a Compose entry is added for evaluation, it should be a short-lived tool
service behind an evaluation profile, not an always-on application service.

- [x] Add evaluation entry points for search, RAG, and optional LLM judging
- [x] Add a CLI command for search evaluation
- [x] Add a CLI command for RAG and LLM-judge evaluation
- [x] Add `make evaluate-search`, `make evaluate-rag`, and `make evaluate-judge`
  shortcuts for the evaluation commands
- [x] Allow evaluation commands to run against an isolated PostgreSQL schema, for
  example `DB_SCHEMA=evaluation`
- [ ] Allow an experiment/configuration name to be recorded with each run
- [ ] Persist machine-readable results for every run
- [ ] Produce a concise human-readable comparison table or Markdown report
- [ ] Record the dataset version, retrieval configuration, prompt version, model, and
  key parameters used by each experiment
- [ ] Make repeated runs with the same dataset and deterministic configuration
  comparable

**Suggested interface**

```text
make evaluate-search -> uv run python -m evaluation.search.run
make evaluate-rag -> uv run python -m evaluation.rag.run
make evaluate-judge -> uv run python -m evaluation.rag.run --judge
```

This is a proposed interface for the new evaluation module. It follows the project's
existing `uv run` workflow without adding an unrelated project-specific command.

**Deliverables**

- `evals/` — versioned evaluation datasets and experiment definitions
- evaluation runners/CLI — executes search, RAG, and optional judge evaluations
- `results/` or equivalent generated artifacts — JSON/CSV metrics plus a Markdown
  summary
- documented winning retrieval configuration
- documented winning LLM/prompt configuration
- README section showing the comparison and explaining why each winner was selected

**Acceptance criteria**

- [x] Search, RAG, and LLM-judge evaluations can be executed without the chat UI
- [x] The runner uses production retrieval and LLM components rather than duplicate
  implementations
- [ ] Every experiment records enough configuration to reproduce the comparison
- [ ] Results from multiple approaches can be compared in one report
- [ ] The selected retrieval and LLM configurations are applied to the application

**Tools**

- Python
- Click
- JSONL

______________________________________________________________________

### [P1] Speed up online evaluations safely

**Labels:** `evaluation`, `performance`, `llm`

RAG and judge evaluations call external LLMs and currently process cases serially. Add
bounded asynchronous scheduling without exceeding provider limits or losing the stable
case ordering used by reports.

- [ ] Extract an async RAG evaluation path instead of creating one event loop per case
- [ ] Run independent cases concurrently with a configurable in-flight limit
- [ ] Add a shared requests-per-second limiter for answer and judge calls
- [ ] Retry transient failures and rate limits with bounded exponential backoff
- [ ] Preserve case order and aggregate failures without aborting the whole run
- [ ] Keep search evaluation independent from the online LLM scheduler

**Acceptance criteria**

- [ ] Online evaluations complete faster for the same dataset
- [ ] Concurrency and rate limits are configurable from the evaluation command
- [ ] The evaluator remains within the configured provider limits
- [ ] Results remain comparable with serial execution

______________________________________________________________________

### [P1] Performance improvements

**Labels:** `quality`, `performance`, `developer-experience`

- [x] Reuse the embedding model across requests with a process-local embedder cache
- [x] Run RAG evaluation cases asynchronously with progress based on completed cases
- [x] Rate-limit asynchronous LLM requests to a shared default of 5 requests per second
- [x] Centralize section-path slugification across ingestion and evaluation

______________________________________________________________________

### [P0] Evaluate retrieval approaches

**Labels:** `evaluation`, `retrieval`

Compare the retrieval approaches already implemented in Milestone 3 under the same
dataset, `top_k`, and scoring procedure.

**Approaches to compare**

- [ ] Vector search
- [ ] PostgreSQL full-text search
- [ ] Hybrid search with reciprocal rank fusion
- [ ] Optionally compare a small number of justified hybrid configurations if needed to
  select the final weights or RRF rank constant

Chunking changes, query rewriting, reranking, and other pipeline changes are excluded
from the core Milestone 5 comparison so that the retrieval experiment has a clear
independent variable.

**Primary metrics**

- [ ] Hit Rate at K
- [ ] Recall at K
- [ ] Mean Reciprocal Rank

**Secondary metrics**

- [ ] Mean retrieval latency

Recall at K is the primary quality metric because the generation stage cannot use
evidence that retrieval failed to provide. Ranking metrics and latency should be used to
break ties or explain tradeoffs.

**Experiment rules**

- [ ] Use the same evaluation dataset for every approach
- [ ] Use the same `top_k` when comparing approaches
- [ ] Keep embedding model and indexed corpus fixed
- [ ] Record all retrieval settings used by each run
- [ ] Do not select the winner from anecdotal examples alone

**Acceptance criteria**

- [ ] At least two materially different retrieval approaches are evaluated
- [ ] Vector, full-text, and hybrid retrieval are compared if all three remain available
- [ ] Results are reproducible from the evaluation runner
- [ ] A results table compares all approaches using the same metrics
- [ ] The best-performing retrieval configuration is selected and used by the
  application
- [ ] The selection rationale is documented, including any quality/latency tradeoff

**Tools**

- Pandas
- PostgreSQL with pgvector and full-text search
- Matplotlib or Plotly optional

______________________________________________________________________

### [P0] Create LLM evaluation dataset

**Labels:** `evaluation`, `data`, `llm`

Create a versioned set of final-answer cases for comparing alternative prompts or other
LLM-generation configurations.

The retrieval input must be controlled during prompt comparison. Each LLM approach
should receive the same question and the same retrieved context so that prompt quality
can be compared independently from retrieval quality.

- [ ] Include representative answerable questions
- [ ] Include unsupported questions
- [ ] Include questions about prices or opening hours when the retrieved context does
  not contain that information
- [ ] Include questions requiring synthesis across multiple retrieved chunks
- [ ] Record the retrieved context used for each evaluation case, or freeze it from the
  selected retrieval configuration
- [ ] Define the expected answer behaviour for each case
- [ ] Version the dataset independently from prompt versions

**Expected behaviour may include**

- answer should be supported by the supplied context;
- answer should not introduce unsupported facts;
- unsupported questions should produce a clear limitation;
- answer should be in English;
- cited or referenced evidence should correspond to supplied context where the evaluated
  prompt includes citations.

**Acceptance criteria**

- [ ] Dataset is versioned
- [ ] Expected behaviour is manually reviewed
- [ ] Every compared LLM approach receives equivalent input context
- [ ] Cases include both answerable and unsupported questions

**Tools**

- JSONL

______________________________________________________________________

### [P0] Evaluate LLM approaches

**Labels:** `evaluation`, `llm`, `prompt-engineering`

Compare at least two materially different prompt or generation approaches using the same
LLM evaluation cases and fixed retrieved context.

**Suggested approaches**

- [ ] Prompt v1 — baseline RAG instruction
- [ ] Prompt v2 — stricter grounding and unsupported-question behaviour
- [ ] Prompt v3 — optional structured/citation-aware variant if implemented during this
  milestone

The comparison should test meaningful prompt changes rather than minor wording
variations.

**Evaluation dimensions**

- [x] Optional structured LLM judge compares generated answers with the golden
  `reference_answer`; it is available through `make evaluate-judge`
- [ ] Answer correctness
- [ ] Groundedness / faithfulness to the supplied context
- [ ] Unsupported-question handling
- [ ] Unsupported-fact avoidance, especially prices and opening hours
- [ ] English-language compliance
- [ ] Citation accuracy if citations are part of an evaluated approach
- [ ] Manual review of representative successes and failures

The optional automated LLM judge is implemented for semantic answer correctness. A
small, clearly documented manual rubric remains useful for qualities the judge does not
measure reliably, such as nuanced groundedness and usefulness.

**Experiment rules**

- [ ] Use the same LLM evaluation dataset for every approach
- [ ] Use the same retrieved context for every compared prompt
- [ ] Keep model and generation settings fixed unless they are explicitly the variable
  being evaluated
- [ ] Version every compared prompt
- [ ] Record evaluation criteria before selecting the winner

**Acceptance criteria**

- [ ] At least two materially different LLM approaches are evaluated
- [ ] A comparison table summarizes the evaluation results
- [ ] Representative failures are documented instead of reporting only aggregate scores
- [ ] The best-performing prompt/configuration is selected and used by the application
- [ ] The selection rationale is documented
- [ ] Prompt versions and evaluation results are linked in project documentation

**Tools**

- Plain prompt templates
- OpenAI API client
- Ragas or DeepEval optional

______________________________________________________________________

### [P1] Document the evaluation methodology and results

**Labels:** `evaluation`, `documentation`

- [ ] Explain how the retrieval golden set was labeled
- [ ] Explain which retrieval approaches were compared
- [ ] Explain how LLM outputs were evaluated
- [ ] Document prompt versions and controlled variables
- [ ] Include retrieval comparison results
- [ ] Include LLM comparison results
- [ ] Identify the winning retrieval and LLM configurations
- [ ] Explain limitations of the evaluation dataset and methodology

**Acceptance criteria**

- [ ] A reviewer can see evidence for both project evaluation criteria
- [ ] The documented winner matches the configuration used by the application
- [ ] Evaluation limitations are explicit
- [ ] Results can be regenerated with the evaluation runners

______________________________________________________________________

## 🚀 Release v0.3.0 — Evaluation

**🗓️ Planned release — not shipped**

Ships when **Milestone 5** passes its exit criteria:

- Versioned search evaluation dataset
- Vector, full-text, and hybrid retrieval comparison
- Selected retrieval configuration used by the application
- Versioned LLM evaluation dataset
- Multiple prompt/LLM approaches compared under fixed retrieval context
- Selected LLM/prompt configuration used by the application
- Reproducible evaluation runners and documented results

______________________________________________________________________

## ⏳ Milestone 6 — User Feedback

### [P1] Add user feedback

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

## ⏳ Milestone 7 — Monitoring

### [P1] Log application interactions

**Labels:** `monitoring`, `observability`

- [ ] Log questions and answers
- [ ] Log retrieved chunks
- [ ] Log model and prompt version
- [ ] Log input, output, cached, and reasoning token usage
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

### [P2] Add ingestion observability

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

### [P1] Build monitoring dashboard

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

## 🚀 Release v0.4.0 — Monitoring

**🗓️ Planned release — not shipped**

Ships when **Milestone 7** passes its exit criteria:

- Feedback
- Logs
- Dashboard

______________________________________________________________________

## 🔄 Milestone 8 — Reproducibility and Delivery

### [P0] Containerize the application

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

### [P0] Complete project documentation

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

### [P1] Add automated tests and CI

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

### [P1] Record project demo

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

## 🚀 Release v1.0.0 — Final submission

**🗓️ Planned release — not shipped**

Ships when **Milestone 8** passes its exit criteria:

- Docker Compose
- Tests and CI
- Documentation
- Demo video

______________________________________________________________________

# Stretch Goals

### [P2] Ingest multiple brochures

- [ ] Add document filters
- [ ] Add region and topic metadata
- [ ] Define document identity independently from a mutable source URL
- [ ] Detect unchanged and changed source checksums
- [ ] Add explicit document versions and deprecation status
- [ ] Replace a document, its chunks, and its embeddings atomically
- [ ] Soft-delete or deprecate superseded document versions
- [ ] Remove or exclude stale chunks from retrieval
- [ ] Test concurrent and repeated document updates

### [P2] Add agentic routing and live tools

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

### [P3] Evaluate end-to-end RAG answer quality

**Labels:** `evaluation`, `rag`, `quality`

Extend the component-level Milestone 5 evaluation into an end-to-end RAG evaluation
where retrieval and generation run together exactly as they do in the application.

- [ ] Define an end-to-end golden set with questions and expected answer behaviour
- [ ] Measure answer correctness and groundedness using live retrieved context
- [ ] Measure whether final answers use the relevant retrieved evidence
- [ ] Measure unsupported-question refusal quality
- [ ] Analyze failures by stage: retrieval failure, context-selection failure, or
  generation failure
- [ ] Compare end-to-end quality before and after major RAG changes

**Acceptance criteria**

- [ ] End-to-end results are reproducible
- [ ] Failures can be attributed to retrieval or generation where possible
- [ ] The report includes representative failure cases, not only aggregate scores

**Tools**

- Existing evaluation runners
- Ragas, DeepEval, or a documented manual rubric

______________________________________________________________________

### [P3] Evaluate RAG robustness

**Labels:** `evaluation`, `rag`, `robustness`

Test whether the selected RAG flow remains useful when user questions are noisy or
differ from the clean evaluation examples.

- [ ] Evaluate paraphrases of known questions
- [ ] Evaluate common misspellings and place-name variants
- [ ] Evaluate underspecified and ambiguous questions
- [ ] Evaluate conversational follow-up questions
- [ ] Evaluate distractor or irrelevant retrieved chunks
- [ ] Measure quality degradation relative to the clean baseline

**Acceptance criteria**

- [ ] Robustness cases are versioned
- [ ] The project documents known failure modes
- [ ] Changes such as query rewriting are kept only when they improve measured
  robustness

______________________________________________________________________

### [P3] Evaluate RAG efficiency and cost

**Labels:** `evaluation`, `performance`, `cost`

Measure the operational tradeoffs of the selected RAG configuration without turning
performance into a Milestone 5 scoring requirement.

- [ ] Measure retrieval latency
- [ ] Measure end-to-end answer latency
- [ ] Record retrieved context size
- [x] Capture provider usage metadata in generated-answer and judge traces
- [ ] Aggregate LLM input, output, cached, and reasoning token usage in reports
- [ ] Estimate per-request LLM cost for evaluated configurations
- [ ] Compare quality/latency/cost tradeoffs for major configuration changes

**Acceptance criteria**

- [ ] Measurements are collected with a documented methodology
- [ ] The project can explain the main quality-versus-cost tradeoffs
- [ ] Performance measurements do not replace the quality metrics from Milestone 5

The current implementation captures provider usage metadata in memory, but does not yet
aggregate, persist, price, or alert on token consumption.

______________________________________________________________________

### [P3] Add human RAG quality evaluation

**Labels:** `evaluation`, `human-review`, `quality`

Add a lightweight human-review protocol for qualities that automated metrics may not
capture reliably.

- [ ] Define a short reviewer rubric
- [ ] Score usefulness, clarity, correctness, groundedness, and refusal quality
- [ ] Review a representative sample of end-to-end answers
- [ ] Record reviewer notes for systematic failure patterns
- [ ] Compare human judgments with automated evaluation results

**Acceptance criteria**

- [ ] Review criteria are documented before scoring
- [ ] Reviewed examples and aggregate results are retained
- [ ] Disagreements between automated and human evaluation are discussed

______________________________________________________________________

### [P3] Add CI/CD search evaluation quality gates

**Labels:** `evaluation`, `ci`, `deployment`, `experiments`, `post-capstone`

Run the search evaluation automatically before production deployment after the current
capstone goals are complete. The evaluator should remain runnable locally, while CI uses
its aggregate metrics and diagnostics as a deployment quality gate.

- [ ] Add a CI job that starts the evaluation database, loads the pinned corpus, and
  runs the search evaluation before deployment
- [ ] Define minimum thresholds for hit rate@K, recall@K, and MRR per search mode
- [ ] Fail the deployment when a metric regresses beyond the accepted tolerance
- [ ] Record run metadata: commit, dataset, corpus, search mode, `k`, embedding
  configuration, and execution timestamp
- [ ] Upload aggregate reports and representative failure diagnostics as CI artifacts
- [ ] Compare the current run with the main-branch or last-release baseline
- [ ] Add an optional durable store for historical runs after the CI artifact flow is
  reliable
- [ ] Keep local evaluation independent from CI services and historical persistence

**Acceptance criteria**

- [ ] Search evaluation runs automatically before production deployment
- [ ] A search regression blocks deployment with an actionable report
- [ ] Evaluation runs can be reproduced from their recorded configuration
- [ ] Aggregate results and failure diagnostics are retained as CI artifacts
- [ ] Historical persistence is additive and does not become a runtime dependency

______________________________________________________________________

### [P3] Add deterministic RAG integration tests

**Labels:** `testing`, `rag`, `post-capstone`

Add a deterministic integration-test path for the RAG pipeline after the current
capstone goals are complete. These tests should exercise retrieval, prompt construction,
structured generation, citation reconciliation, and `RAGResult` assembly without calling
an external LLM provider.

- [ ] Add a small fake LLM client implementing the existing `LLMClient` contract
- [ ] Add recorded structured responses for representative answer and refusal cases
- [ ] Test valid, repeated, unsupported, and page-less citations
- [ ] Test derived citation section paths in `RAGResult`
- [ ] Keep live-provider evaluation separate from the deterministic integration suite

**Acceptance criteria**

- [ ] The RAG pipeline can be tested without an API key or network access
- [ ] Tests cover the complete local pipeline from retrieval to normalized sources
- [ ] Recorded responses remain versioned and easy to update
- [ ] The fake client is used only for tests, not for benchmark conclusions

______________________________________________________________________

### [P3] Deploy to the cloud

- [ ] Select hosting provider
- [ ] Configure secrets
- [ ] Add deployment documentation
- [ ] Verify public demo
