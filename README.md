# Brittany AI Tour Guide

[![GitHub Release](https://img.shields.io/github/v/release/QuentinElGuay/portfolio-ai-tour-guide)](https://github.com/QuentinElGuay/portfolio-ai-tour-guide/releases)

Degemer mat ("Welcome" in Breton)!

An AI tour guide for Brittany, France. It uses **Retrieval-Augmented Generation (RAG)**
to answer travellers' questions from an indexed tourism guide.

> [!IMPORTANT]
> 🚧 This project is under **<ins>active development</ins>**.

## Table of contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Question scope](#question-scope)
- [Documentation](#documentation)
- [Data source](#data-source)
- [Prerequisites](#prerequisites)
- [Quick start](#quick-start)
- [Common commands](#common-commands)
- [Roadmap](#roadmap)
- [Capstone success criteria](#capstone-success-criteria)
- [Contributing](#contributing)
- [License](#license)

## Overview

Created as a capstone project for
[LLM Zoomcamp](https://github.com/DataTalksClub/llm-zoomcamp) by
[DataTalks.Club](https://datatalks.club), this project turns a Brittany tourism guide
into a question-answering experience that helps travellers explore the region. It
processes the guide into searchable passages, uses **vector embeddings** and
**PostgreSQL with pgvector** to retrieve relevant context, then asks an LLM to generate
an answer based on that context.

The project is designed as a focused portfolio demonstration of the full RAG workflow:

- Document ingestion
- Retrieval and prompt construction
- LLM integration
- A browser chat interface

The project also focuses on the practices that make RAG applications reliable:

- Keeping answers grounded in retrieved context
- Validating citations
- Evaluating retrieval and answer quality
- Adding guardrails for unsupported or overly specific questions

## Architecture

The ingestion pipeline indexes the tourism guide in PostgreSQL with pgvector. The chat
interface sends questions to the agent API, which retrieves context and calls an LLM API
to generate an answer.

```mermaid
flowchart LR
    PDF[Tourism guide PDF] --> Ingestion[Ingestion pipeline]
    Ingestion --> KB[(PostgreSQL + pgvector)]
    User --> Chat[Chat]
    Chat --> Agent[Agent API]
    Agent <--> KB
    Agent <--> LLM[LLM API]
    Agent --> Chat
```

## Question scope

The project supports English questions about Brittany's regions, geography and natural
landscapes, climate, transport, cost of living, real estate, family relocation and
education, outdoor recreation, history and heritage, and Breton culture, food,
festivals, and local life.

Supported examples:

- ✅ “What are the main places to visit in Brittany?”
- ✅ “What is special about Breton culture?”

Unsupported questions include:

- ❌ “What are the best places to visit in Normandy?” — another destination.
- ❌ “What is the weather in Brest today?” — current information absent from the guide.
- ❌ “Can you book a hotel in Saint-Malo for this weekend?” — booking, availability, or
  reservation requests.
- ❌ “Should I invest in renewable-energy stocks?” — an unrelated finance topic.
- ❌ “How does quantum entanglement work?” — an unrelated science topic.

> [!NOTE]
> English is the only supported language. This keeps the demonstration lightweight and
> suitable for a smaller model.

## Documentation

- [Ingestion guide](src/ai_tour_guide/ingestion/README.md): document definitions,
  pipeline stages, artifacts, and ingestion configuration.
- [Agent guide](src/ai_tour_guide/agent/README.md): RAG flow, CLI, HTTP API, and agent
  configuration.
- [Chat guide](src/ai_tour_guide/agent/chat/README.md): Gradio service and its HTTP
  integration.
- [Roadmap](roadmap.md): delivered work and planned validation, evaluation, and
  monitoring.

## Data source

The project indexes the freely available
*[Discovering Brittany](https://www.ibanista.com/wp-content/uploads/2025/11/Guide-Discover-Brittany-Nov-2025.pdf)*
guide published by [Ibanista](https://www.ibanista.com/). It is used for educational
purposes only and is not redistributed in this repository.

## Prerequisites

The recommended workflow requires _Git_, _Docker_ with _Docker Compose_, and _GNU Make_.

For direct Python commands, install _Python 3.14_ or newer and
_[uv](https://docs.astral.sh/uv/)_. _GitHub Codespaces_ can run the project without
local installation.

## Quick start

Clone the repository and create your environment file:

```bash
git clone https://github.com/QuentinElGuay/portfolio-ai-tour-guide.git
cd portfolio-ai-tour-guide
cp .env.template .env
```

Set an OpenAI API key in `.env` to generate answers:

```dotenv
AGENT_OPENAI_API_KEY=your-api-key
```

> [!NOTE]
> OpenAI is the only currently supported LLM provider at the moment but more might be
> added in the future.

Initialize the database, ingest the bundled source definitions, and start the app:

```bash
make init-db
make ingest
make app
```

Open `http://localhost:7860` to use the chat. The agent API is available at
`http://localhost:8000`; its interactive API documentation is at
`http://localhost:8000/docs`.

The first ingestion or image build can download the configured embedding model. To
recreate the local database, use `make reset-db`, then run `make ingest` to populate the
public schema. A reset intentionally leaves the database empty until ingestion
completes. Use `DB_SCHEMA` to target another schema in the same PostgreSQL database, for
example when isolating future evaluation data from local development data.

> [!WARNING]
> `make reset-db` permanently deletes the project's PostgreSQL volume.

## Common commands

Run `make help` for every available shortcut.

| Command                                 | Description                                          |
| --------------------------------------- | ---------------------------------------------------- |
| `make init-db`                          | Start PostgreSQL and initialise the pgvector schema. |
| `make ingest`                           | Ingest documents defined in `source_files.json`.     |
| `make export-corpus`                    | Overwrite the current knowledge-base corpus export.  |
| `make load-corpus DB_SCHEMA=evaluation` | Load the corpus into the evaluation schema.          |
| `make evaluate`                         | Load the corpus and run search evaluation.           |
| `make evaluate EVALUATION=rag`          | Load the corpus and run RAG evaluation.              |
| `make evaluate EVALUATION=both`         | Load the corpus and run both evaluations.            |
| `make vector_search QUESTION='...'`     | Search chunks semantically.                          |
| `make text_search QUESTION='...'`       | Search chunks with PostgreSQL full-text search.      |
| `make ask QUESTION='...'`               | Generate an answer from retrieved context.           |
| `make ask QUESTION='...' VERBOSE=1`     | Print the complete serialized RAG trace.             |
| `make app`                              | Start the agent API and Gradio chat interface.       |

See the [ingestion guide](src/ai_tour_guide/ingestion/README.md) and
[agent guide](src/ai_tour_guide/agent/README.md) for command options and local Python
workflows.

## Roadmap

The complete plan, including milestones and deferred work, is maintained in
[roadmap.md](roadmap.md).

### Current release — v0.2.0: RAG MVP

This release delivers the first end-to-end RAG experience for the Brittany guide:

- Grounded answers generated from retrieved context
- Retrieved source references with deduplicated page numbers
- A basic Gradio chat interface

### Next release — v0.3.0: Evaluation

The next goal is to validate and measure answer quality: build a reviewed evaluation
dataset, compare retrieval and prompt configurations, and introduce verified citations
based on LLM-returned chunk identifiers.

### Capstone success criteria

The project follows the
[LLM Zoomcamp capstone evaluation criteria](https://github.com/DataTalksClub/llm-zoomcamp/blob/main/project.md#evaluation-criteria).
A complete submission should demonstrate the following features:

- ✅ A clearly defined problem, target users, supported questions, and limitations.
- ✅ An accessible source dataset and reproducible instructions for running the project.
- ✅ Automated ingestion from source documents into a searchable knowledge base.
- ✅ A RAG flow that retrieves relevant context from the knowledge base before an LLM
  generates an answer.
- ✅ Retrieval evaluation that compares multiple approaches and adopts the strongest
  configuration.
- ⏳ LLM-answer evaluation that compares multiple prompt or generation approaches and
  selects the best one.
- ✅ A usable interface for asking questions, such as the chat application and HTTP API.
- ⏳ Monitoring through user feedback and a dashboard that makes application behaviour
  visible.
- 🔄 Containerised services, pinned dependency versions, and clear setup instructions for
  a reproducible local run.
- ⏳ Retrieval best practices evaluated for their value: hybrid search, reranking, and
  query rewriting.
- ⏳ Automated tests and CI/CD, followed by a cloud deployment as an optional extension.

#### Delivery status

- **✅ Passed / core complete** — the milestone's core deliverable is usable; remaining
  items are polish or follow-up
- **🔄 In progress** — work has started, but the milestone is not complete
- **⏳ Planned** — work has not started yet

## Contributing

This is a personal portfolio and learning project. External contributions are not
currently accepted, but feedback, bug reports, and suggestions are welcome through
GitHub Issues.

After `uv sync`, install the local quality hooks once:

```bash
uv run pre-commit install
```

Run all checks manually with:

```bash
uv run pre-commit run --all-files
```

## License

This repository is publicly available for educational, portfolio, and evaluation
purposes. You may browse and clone it to review the implementation, but its source code
is **not licensed for reuse**. All rights are reserved unless stated otherwise; copying,
modifying, redistributing, or incorporating this code into other projects requires prior
written permission.

The tourism guide used as the knowledge source remains the property of its copyright
holder and is not redistributed as part of this repository.
