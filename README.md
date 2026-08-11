# Brittany AI Tour Guide

[![GitHub Release](https://img.shields.io/github/v/release/QuentinElGuay/portfolio-ai-tour-guide)](https://github.com/QuentinElGuay/portfolio-ai-tour-guide/releases)

Degemer mat ("Welcome" in Breton)!

This project builds an AI tour guide for Brittany, France, using **Retrieval-Augmented
Generation (RAG)** to answer travelers' questions from official tourism guides.

> [!IMPORTANT]
> 🚧 This project is under **<ins>active development</ins>.**

## Table of Contents

- [Overview](#overview)
- [Data source](#data-source)
- [Prerequisites](#prerequisites)
- [Quick start](#quick-start)
- [Document input](#document-input)
- [Using the ingestion pipeline](#using-the-ingestion-pipeline)
- [Makefile commands](#makefile-commands)
- [Configuration](#configuration)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [License](#license)

## Overview

This project was created as the capstone project for the
[LLM Zoomcamp](https://github.com/DataTalksClub/llm-zoomcamp)
[DataTalks.Club](https://datatalks.club).

This project demonstrates how to build an end-to-end RAG application following modern
LLM engineering practices. It indexes a tourism guide for Brittany and allows users to
ask natural-language questions about the region's culture, history, geography, and
attractions while grounding every answer in the source document.

The project covers document ingestion, chunking, embeddings, vector search, retrieval
evaluation, prompt engineering, monitoring, and a Streamlit user interface.

## Data source

This project uses the freely available
*[Discovering Brittany](https://www.ibanista.com/wp-content/uploads/2025/11/Guide-Discover-Brittany-Nov-2025.pdf)*
guide published by [Ibanista](https://www.ibanista.com/).

The guide is used solely for educational purposes and remains the property of its
respective copyright holder. It is not redistributed as part of this repository.

## Prerequisites

> [!NOTE]
> Running the project directly in `Docker Codespaces` allow for an execution
> without any installation.

The recommended Docker workflow requires:

- Git
- Docker with Docker Compose
- GNU Make

To run the Python commands directly, also install:

- Python 3.14 or newer
- [uv](https://docs.astral.sh/uv/)

## Quick start

Clone the repository, create the local environment file, initialize the database, and
run the example ingestion:

```bash
git clone https://github.com/QuentinElGuay/portfolio-ai-tour-guide.git
cd portfolio-ai-tour-guide
cp .env.template .env
make init-db
make ingest
```

`make init-db` starts PostgreSQL, enables pgvector, and creates the application tables.
`make ingest` downloads and processes every document in `source_files.json`, then
inserts each document and its chunks in one database transaction.

The embedding model may be downloaded the first time ingestion runs. An existing source
URL is rejected instead of replacing its document and chunks. Use `make reset-db` when
you intentionally want to recreate the development database and ingest the same source
again.

## Document input

The complete `run` command accepts either one JSON object or an array of objects. Each
independent stage accepts exactly one document.

The mandatory fields are `title` and `source_url`:

```json
{
  "title": "Guide to the Region of Brittany",
  "source_url": "https://example.com/brittany-guide.pdf",
  "collection": "Regional Guides",
  "publisher": "Example publisher",
  "keywords": ["Tourism", "Brittany", "France"],
  "excluded_leading_pages": 4,
  "excluded_trailing_pages": 2,
  "ignored_text_patterns": ["example\\.com"]
}
```

`collection` and the remaining metadata and parsing options are optional. See
[`source_files.json`](source_files.json) for the input used by the default Makefile
command.

## Using the ingestion pipeline

### End-to-end ingestion

The `run` command executes download, parsing, chunking, embedding, and database loading
sequentially. Intermediate values stay in memory.

Database loading requires `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, and
`EMBEDDING_DIMENSIONS` in the process environment. The Docker and Makefile workflows set
these automatically. When running locally against the Compose database, set them to
values matching `.env`; for example:

```bash
export DB_HOST=localhost
export DB_PORT=5432
export DB_NAME=postgres
export DB_USER=postgres
export DB_PASSWORD=postgres
export EMBEDDING_DIMENSIONS=384
```

Install the project and run the complete pipeline:

```bash
uv sync
uv run portfolio-ai-tour-guide-ingestion run source_files.json
```

Enable debug mode to retain every intermediate artifact:

```bash
uv run portfolio-ai-tour-guide-ingestion run \
  --debug \
  --artifact-dir tmp \
  source_files.json
```

For each source, debug mode creates:

- `<stem>.pdf`
- `<stem>.parsed.txt`
- `<stem>.parsed.md`
- `<stem>.parsed.json`
- `<stem>.chunked.json`
- `<stem>.embedded.json`

### Independent stages

Each pipeline boundary is also callable independently, making the flow usable from
Airflow or another workflow orchestrator:

```bash
uv run portfolio-ai-tour-guide-ingestion download \
  document.json \
  --output tmp/guide.pdf

uv run portfolio-ai-tour-guide-ingestion parse \
  document.json \
  tmp/guide.pdf \
  --output tmp/guide.parsed.json

uv run portfolio-ai-tour-guide-ingestion chunk \
  tmp/guide.parsed.json \
  --output tmp/guide.chunked.json

uv run portfolio-ai-tour-guide-ingestion embed \
  tmp/guide.chunked.json \
  --output tmp/guide.embedded.json

uv run portfolio-ai-tour-guide-ingestion load \
  tmp/guide.embedded.json
```

The parsed, chunked, and embedded outputs are versioned JSON artifacts. The chunked and
embedded artifacts contain both document metadata and chunks, so the following task
needs only one input file.

Run the command help to see stage-specific options such as HTTP timeout, chunk size,
embedding model, batch size, and vector normalization:

```bash
uv run portfolio-ai-tour-guide-ingestion --help
uv run portfolio-ai-tour-guide-ingestion chunk --help
```

The pipeline architecture and function flow are documented in
[`docs/pdf/parsing-flow.md`](docs/pdf/parsing-flow.md).

## Makefile commands

Run `make` or `make help` to list the available shortcuts.

| Command                              | Description                                                            |
| ------------------------------------ | ---------------------------------------------------------------------- |
| `make init-db`                       | Start PostgreSQL and initialize the pgvector schema.                   |
| `make reset-db`                      | Delete the PostgreSQL volume, then create a fresh database and schema. |
| `make ingest`                        | Ingest the documents from `source_files.json`.                         |
| `make ingest DEBUG=1`                | Ingest and retain intermediate files in `tmp/`.                        |
| `make ingest SOURCE_FILES=path.json` | Ingest a different document definition file.                           |
| `make export-csv`                    | Export the ingestion tables to CSV files in `tmp/`.                    |
| `make export-csv CSV_LIMIT=100`      | Limit each CSV export to 100 data rows.                                |
| `make export-csv EXPORT_DIR=path`    | Write the CSV exports to another directory.                            |
| `make vector_search QUESTION='...'`  | Embed a question and search for the nearest document chunks.           |
| `make text_search QUESTION='...'`    | Search document chunks with PostgreSQL full-text search.                |

> [!WARNING]
> `make reset-db` runs `docker compose down --volumes` and permanently
> deletes the project's PostgreSQL volume.

CSV export creates `embedding_models.csv`, `documents.csv`, and `document_chunks.csv`.
The database service must be running before `make export-csv` is called.

The Makefile variables can be combined:

```bash
make ingest SOURCE_FILES=data/another-source.json DEBUG=1
make export-csv EXPORT_DIR=tmp/evaluation CSV_LIMIT=250
make vector_search QUESTION='Where is the Brittany coast?' K=10
make text_search QUESTION='Brittany coast'
```

## Configuration

Copy `.env.template` to `.env` before using Docker Compose. The main ingestion settings
are:

| Variable               | Purpose                                          | Default                  |
| ---------------------- | ------------------------------------------------ | ------------------------ |
| `POSTGRES_DB`          | PostgreSQL database name                         | `postgres`               |
| `POSTGRES_USER`        | PostgreSQL user                                  | `postgres`               |
| `POSTGRES_PASSWORD`    | PostgreSQL password                              | `postgres`               |
| `POSTGRES_PORT`        | Optional host port exposed by Compose            | `5432`                   |
| `EMBEDDING_MODEL_NAME` | FastEmbed model used for document vectors        | `BAAI/bge-small-en-v1.5` |
| `EMBEDDING_DIMENSIONS` | Vector dimension enforced by the database schema | `384`                    |
| `EMBEDDING_BATCH_SIZE` | Number of chunks embedded per inference batch    | `32`                     |
| `EMBEDDING_NORMALIZE`  | Whether stored vectors are L2-normalized         | `true`                   |
| `EMBEDDING_CACHE_DIR`  | Optional local directory for FastEmbed model files | FastEmbed default       |
| `INGESTION_DEBUG`      | Retain intermediate artifacts                    | `false`                  |
| `INGESTION_TIMEOUT`    | PDF download timeout in seconds                  | `30`                     |
| `INGESTION_TMP_FOLDER` | Debug artifact directory                         | `tmp`                    |

The direct Python CLI reads `EMBEDDING_*` and `INGESTION_*` settings from `.env`. Docker
Compose forwards the PostgreSQL and embedding settings to application containers; other
container settings use their application defaults unless explicitly passed to the service.

The Docker agent and ingestion images preload `EMBEDDING_MODEL_NAME` during their build,
so vector searches do not download the embedding model at runtime. Rebuild the images
after intentionally changing the model configuration.

`EMBEDDING_DIMENSIONS` must match the selected model. Changing it after the database has
been initialized requires recreating the schema, which can be done in development with
`make reset-db`.

## Roadmap

See the project's [roadmap](roadmap.md) *(work in progress)*.

## Contributing

This repository is maintained as a personal portfolio and learning project. While
external contributions are not currently accepted, feedback, bug reports, and
suggestions are always welcome through GitHub Issues.

## License

This repository is publicly available for educational, portfolio, and evaluation
purposes.

You may browse and clone this repository to review the implementation, but the source
code is **not licensed for reuse**. Unless otherwise stated, all rights are reserved by
the author. Copying, modifying, redistributing, or incorporating this code into other
projects requires prior written permission.

The tourism guide used as the knowledge source remains the property of its respective
copyright holder and is not redistributed as part of this repository.
