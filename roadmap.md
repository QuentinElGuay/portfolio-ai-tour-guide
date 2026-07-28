# BreizhGuide Roadmap

> [!note]
> This roadmap had been created by ChatGPT as a first draft and might evolve over time.
## Priority legend

- **P0** — Required for a working project
- **P1** — Required for a strong course submission
- **P2** — Optional improvement
- **P3** — Stretch goal

---

# Milestone 1 — Project Foundation

## [P0] Define project scope

**Labels:** `planning`, `documentation`

- [ ] Define target users
- [ ] Define supported questions
- [ ] Define unsupported questions
- [ ] Define supported languages
- [ ] Define success criteria

**Acceptance criteria**

- [ ] Scope is documented in `README.md`
- [ ] Limitations are explicit
- [ ] Five example use cases are included

**Tools**

- Markdown
- Mermaid
- GitHub Issues

---

## [P0] Create project structure

**Labels:** `setup`, `developer-experience`

- [ ] Create Python project
- [ ] Add dependency management
- [ ] Add environment configuration
- [ ] Add basic logging
- [ ] Add test structure

**Acceptance criteria**

- [ ] Project installs with one command
- [ ] Application starts locally
- [ ] Tests can be executed

**Tools**

- Python
- uv
- Pydantic Settings
- pytest

---

# Milestone 2 — Document Ingestion

## [P0] Inspect the tourism brochure

**Labels:** `data`, `research`

- [ ] Verify text is selectable
- [ ] Inspect pages, columns, maps, and tables
- [ ] Check repeated headers and footers
- [ ] Verify source and redistribution rights
- [ ] Record document metadata

**Acceptance criteria**

- [ ] Extraction risks are documented
- [ ] Source URL and license notes are recorded

**Tools**

- PyMuPDF
- Jupyter

---

## [P0] Extract PDF content

**Labels:** `ingestion`, `pdf`

- [ ] Extract text page by page
- [ ] Preserve page numbers
- [ ] Preserve document title and source
- [ ] Remove repeated headers and footers
- [ ] Export records to JSONL

**Acceptance criteria**

- [ ] Each record contains text and page metadata
- [ ] French characters are preserved
- [ ] Sample pages match the original document

**Tools**

- PyMuPDF
- Pydantic
- JSONL

---

## [P0] Implement document chunking

**Labels:** `ingestion`, `rag`

- [ ] Implement page-aware chunks
- [ ] Preserve section titles
- [ ] Add chunk identifiers
- [ ] Add configurable chunk size and overlap
- [ ] Store document metadata with each chunk

**Acceptance criteria**

- [ ] Every chunk can be traced to a page
- [ ] Chunking parameters are configurable
- [ ] Chunk output is reproducible

**Tools**

- Python
- tiktoken or Hugging Face tokenizers

---

## [P1] Create an ingestion CLI

**Labels:** `ingestion`, `cli`

- [ ] Add command to ingest a PDF
- [ ] Add collection name option
- [ ] Add document version or checksum
- [ ] Print ingestion summary
- [ ] Make repeated ingestion idempotent

**Acceptance criteria**

- [ ] Ingestion runs without a notebook
- [ ] Reprocessing does not create duplicates
- [ ] Errors are logged clearly

**Tools**

- Typer
- Structlog or standard logging

---

# Milestone 3 — Knowledge Base and Retrieval

## [P0] Generate multilingual embeddings

**Labels:** `embeddings`, `rag`

- [ ] Select a multilingual model
- [ ] Generate embeddings for all chunks
- [ ] Store embedding model metadata
- [ ] Validate vector dimensions

**Acceptance criteria**

- [ ] French and English queries retrieve relevant French content
- [ ] Embedding generation is reproducible

**Tools**

- sentence-transformers
- Hugging Face models

---

## [P0] Implement vector search

**Labels:** `retrieval`, `vector-search`

- [ ] Create vector collection
- [ ] Store chunks and metadata
- [ ] Implement top-k retrieval
- [ ] Return scores and page references

**Acceptance criteria**

- [ ] Search returns ranked chunks
- [ ] Results include page citations
- [ ] Collection persists locally

**Tools**

- Qdrant

---

## [P1] Implement BM25 search

**Labels:** `retrieval`, `search`

- [ ] Index chunk text
- [ ] Implement lexical retrieval
- [ ] Return ranked chunks and scores
- [ ] Test exact place-name queries

**Acceptance criteria**

- [ ] BM25 retrieval can run independently
- [ ] Results are included in evaluation

**Tools**

- rank-bm25
- SQLite FTS5

---

## [P1] Implement hybrid search

**Labels:** `retrieval`, `best-practice`

- [ ] Combine vector and BM25 results
- [ ] Implement reciprocal rank fusion
- [ ] Make retrieval weights configurable
- [ ] Compare against individual retrievers

**Acceptance criteria**

- [ ] Hybrid retrieval is evaluated
- [ ] Best configuration is documented

**Tools**

- Qdrant
- rank-bm25

---

# Milestone 4 — RAG Application

## [P0] Implement the RAG pipeline

**Labels:** `rag`, `backend`

- [ ] Accept a user question
- [ ] Retrieve relevant chunks
- [ ] Build the prompt
- [ ] Call the LLM
- [ ] Return answer and sources

**Acceptance criteria**

- [ ] Answers use retrieved context
- [ ] Sources include page numbers
- [ ] Components can be tested independently

**Tools**

- Python
- Ollama
- OpenAI-compatible client

---

## [P0] Add grounded answer rules

**Labels:** `prompt-engineering`, `safety`

- [ ] Answer only from retrieved context
- [ ] Refuse unsupported questions
- [ ] Avoid inventing prices and opening hours
- [ ] Answer in the user's language
- [ ] Cite relevant pages

**Acceptance criteria**

- [ ] Unsupported questions produce a clear limitation message
- [ ] Answers contain valid citations
- [ ] Prompt is versioned in the repository

**Tools**

- Plain prompt templates
- Jinja2 optional

---

## [P2] Add conversation-aware query rewriting

**Labels:** `rag`, `best-practice`

- [ ] Rewrite follow-up questions
- [ ] Preserve original query
- [ ] Correct common place-name spelling errors
- [ ] Evaluate rewritten versus original queries

**Acceptance criteria**

- [ ] Rewriting is optional and configurable
- [ ] Evaluation shows whether it improves retrieval

**Tools**

- Ollama
- Lightweight prompt chain

---

## [P2] Add document reranking

**Labels:** `retrieval`, `best-practice`

- [ ] Retrieve a larger candidate set
- [ ] Rerank candidates
- [ ] Keep only the best chunks
- [ ] Measure quality and latency impact

**Acceptance criteria**

- [ ] Reranking is evaluated
- [ ] It is kept only if results improve

**Tools**

- sentence-transformers CrossEncoder

---

# Milestone 5 — Evaluation

## [P0] Create retrieval evaluation dataset

**Labels:** `evaluation`, `data`

- [ ] Create 40–60 questions
- [ ] Include French and English questions
- [ ] Include answerable and unanswerable questions
- [ ] Record expected pages or topics
- [ ] Include misspellings and paraphrases

**Acceptance criteria**

- [ ] Dataset is versioned
- [ ] Expected results are manually reviewed

**Tools**

- JSONL
- Pandas

---

## [P0] Evaluate retrieval approaches

**Labels:** `evaluation`, `retrieval`

- [ ] Evaluate vector search
- [ ] Evaluate BM25
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

---

## [P1] Evaluate LLM answers

**Labels:** `evaluation`, `llm`

- [ ] Compare at least two prompts
- [ ] Evaluate correctness
- [ ] Evaluate groundedness
- [ ] Evaluate citation accuracy
- [ ] Evaluate refusal quality
- [ ] Evaluate language consistency

**Acceptance criteria**

- [ ] Multiple approaches are compared
- [ ] Best configuration is selected
- [ ] Manual review is included

**Tools**

- pytest
- Pandas
- Ragas or DeepEval optional

---

# Milestone 6 — User Interface

## [P0] Build the chat interface

**Labels:** `frontend`, `streamlit`

- [ ] Add chat input
- [ ] Display conversation history
- [ ] Show loading state
- [ ] Display sources and page numbers
- [ ] Add reset conversation button
- [ ] Add suggested questions

**Acceptance criteria**

- [ ] Users can complete a full conversation
- [ ] Sources are visible
- [ ] Errors are displayed clearly

**Tools**

- Streamlit

---

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
- Streamlit

---

# Milestone 7 — Monitoring

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

---

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

- Streamlit
- Plotly
- Pandas

---

# Milestone 8 — Reproducibility and Delivery

## [P0] Containerize the application

**Labels:** `docker`, `deployment`

- [ ] Create application Dockerfile
- [ ] Add Qdrant service
- [ ] Add Ollama service or document external setup
- [ ] Add persistent volumes
- [ ] Add health checks

**Acceptance criteria**

- [ ] Application runs through Docker Compose
- [ ] Data survives container restart
- [ ] Services start in the correct order

**Tools**

- Docker
- Docker Compose

---

## [P0] Complete project documentation

**Labels:** `documentation`

- [ ] Explain the problem
- [ ] Document the data source
- [ ] Add architecture diagram
- [ ] Explain ingestion and retrieval
- [ ] Include evaluation results
- [ ] Include screenshots
- [ ] Add setup and usage instructions
- [ ] Document limitations

**Acceptance criteria**

- [ ] A new user can run the project
- [ ] Every evaluation criterion has visible evidence
- [ ] Dependency versions are locked

**Tools**

- Markdown
- Mermaid
- uv.lock

---

## [P1] Add automated tests and CI

**Labels:** `testing`, `ci`

- [ ] Test PDF extraction
- [ ] Test chunk metadata
- [ ] Test retrieval
- [ ] Test citation generation
- [ ] Test unsupported-question handling
- [ ] Run tests on pull requests

**Acceptance criteria**

- [ ] CI passes on the main branch
- [ ] Core pipeline has automated coverage

**Tools**

- pytest
- GitHub Actions

---

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

- Streamlit recording
- Loom
- OBS Studio

---

# Stretch Goals

## [P2] Ingest multiple brochures

- [ ] Add document filters
- [ ] Add region and topic metadata
- [ ] Support document updates

## [P2] Add OCR fallback

- [ ] Detect image-only pages
- [ ] Run OCR only when required
- [ ] Record OCR confidence

**Tools**

- Tesseract
- pytesseract

## [P3] Add map visualization

- [ ] Extract destinations
- [ ] Geocode locations
- [ ] Show results on a map

**Tools**

- OpenStreetMap
- Nominatim
- Folium

## [P3] Add live information tools

- [ ] Weather
- [ ] Public transport
- [ ] Current opening information

**Tools**

- Open-Meteo
- Public tourism or transport APIs

## [P3] Deploy to the cloud

- [ ] Select hosting provider
- [ ] Configure secrets
- [ ] Add deployment documentation
- [ ] Verify public demo

---

# Suggested release plan

## v0.1.0 — Retrieval prototype

- PDF extraction
- Chunking
- Vector search
- CLI question answering

## v0.2.0 — RAG MVP

- Grounded answers
- Citations
- Streamlit interface

## v0.3.0 — Evaluation

- Golden dataset
- BM25 comparison
- Hybrid search
- Prompt evaluation

## v0.4.0 — Monitoring

- Feedback
- Logs
- Dashboard

## v1.0.0 — Final submission

- Docker Compose
- Tests and CI
- Documentation
- Demo video
