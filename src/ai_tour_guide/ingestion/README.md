# Ingestion pipeline

This package transforms tourism-guide PDFs into searchable document chunks stored in the
knowledge base. The complete pipeline obtains a source PDF, parses it, chunks the
content, creates embeddings, and loads the result into PostgreSQL in one transaction.

Return to the [project overview](../../../README.md).

## Table of contents

- [Run the complete pipeline](#run-the-complete-pipeline)
- [Document definitions](#document-definitions)
- [Local Python workflow](#local-python-workflow)
- [Pipeline stages and artifacts](#pipeline-stages-and-artifacts)
- [Configuration](#configuration)

## Run the complete pipeline

The Docker workflow is the recommended path:

```bash
make init-db
make ingest
```

`make ingest` reads [`source_files.json`](../../../source_files.json). To use another
definition file or retain intermediate artifacts:

```bash
make ingest SOURCE_FILES=data/another-source.json
make ingest DEBUG=1
```

`make init-db` creates the tables and enables pgvector. Like the Airflow DAG,
`make ingest` skips a document whose `(source_url, version)` identity is already in the
database. To replace an existing document and its chunks, run `make ingest FORCE=1`. Use
`make reset-db` when you intentionally want to clear the selected application schema;
the separate Metabase database is preserved.

## Document definitions

The `run` command accepts one JSON object or a non-empty array of objects. Each
individual stage accepts exactly one object. A definition needs `title` and either
`source_url` or `source_path`. `source_url` is the persistent source identity; when both
are supplied, the pipeline reads the local file while retaining the URL for citations
and document identity:

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

An external orchestrator can download a document itself and pass its local path:

```json
{
  "title": "Guide to the Region of Brittany",
  "source_url": "https://example.com/brittany-guide.pdf",
  "source_path": "/data/brittany-guide.pdf"
}
```

When only `source_path` is supplied, its resolved `file://` URI becomes the source
identity.

All other fields are optional metadata or parsing options. Document titles in the same
input must produce unique filenames. See
[`source_files.json`](../../../source_files.json) for the repository's default input.

## Local Python workflow

For local ingestion, `.env` must define the database connection (`DB_NAME`, `DB_USER`,
and `DB_PASSWORD`) and embedding settings (`EMBEDDING_MODEL_NAME` and
`EMBEDDING_DIMENSIONS`). `DB_HOST`, `DB_PORT`, and `DB_SCHEMA` default to `localhost`,
`5432`, and `public`.

Install the project and run the pipeline:

```bash
uv sync
uv run portfolio-ai-tour-guide-ingestion run source_files.json
```

The Airflow ingestion DAG adds `--skip-existing`, so a document whose
`(source_url, version)` identity is already present is reported as skipped and the task
succeeds. The CLI remains strict by default; pass `--skip-existing` explicitly when a
local rerun should also treat existing documents as successful no-ops.

Use `--force` to replace an existing document. The replacement deletes the existing
document and its related chunks in the same database transaction as the new insertion.
The Airflow DAG exposes this as the `force_reingestion` trigger parameter; it is
mutually exclusive with skipping existing documents.

When connecting to the Compose database from the host, use the values in `.env`,
including `DB_HOST=localhost` and `DB_PORT=5432`.

Use `--debug` to retain stage artifacts. By default they are written under `tmp/`; use
`--artifact-dir` or `INGESTION_TMP_FOLDER` to select another directory:

```bash
uv run portfolio-ai-tour-guide-ingestion run \
  --debug \
  --artifact-dir tmp \
  source_files.json
```

## Pipeline stages and artifacts

Each ingestion step can also run independently. It reads the serialized result produced
by the previous step and writes its own result for the next one:

```bash
uv run portfolio-ai-tour-guide-ingestion download document.json --output tmp/guide.pdf

uv run portfolio-ai-tour-guide-ingestion parse \
  document.json tmp/guide.pdf --output tmp/guide.parsed.json

uv run portfolio-ai-tour-guide-ingestion chunk \
  tmp/guide.parsed.json --output tmp/guide.chunked.json

uv run portfolio-ai-tour-guide-ingestion embed \
  tmp/guide.chunked.json --output tmp/guide.embedded.json

uv run portfolio-ai-tour-guide-ingestion load tmp/guide.embedded.json
```

The parsed, chunked, and embedded JSON artifacts are versioned formats. Chunked and
embedded artifacts retain their document metadata, so each following stage needs only
the previous artifact.

When debug mode is enabled, each source can produce:

- `<stem>.pdf`
- `<stem>.parsed.txt`
- `<stem>.parsed.md`
- `<stem>.parsed.json`
- `<stem>.chunked.json`
- `<stem>.embedded.json`

For all options, run:

```bash
uv run portfolio-ai-tour-guide-ingestion --help
uv run portfolio-ai-tour-guide-ingestion chunk --help
```

The PDF parsing flow is documented in
[`docs/pdf/parsing-flow.md`](../../../docs/pdf/parsing-flow.md).

## Configuration

| Variable               | Purpose                                  | Template value           |
| ---------------------- | ---------------------------------------- | ------------------------ |
| `DB_HOST`              | Database host                            | `localhost`              |
| `DB_PORT`              | Database port                            | `5432`                   |
| `DB_NAME`              | PostgreSQL database name                 | `postgres`               |
| `DB_USER`              | PostgreSQL user                          | `postgres`               |
| `DB_PASSWORD`          | PostgreSQL password                      | `postgres`               |
| `DB_SCHEMA`            | PostgreSQL schema used by the pipeline   | `public`                 |
| `EMBEDDING_MODEL_NAME` | FastEmbed model for document vectors     | `BAAI/bge-small-en-v1.5` |
| `EMBEDDING_DIMENSIONS` | Vector dimension enforced by the schema  | `384`                    |
| `EMBEDDING_BATCH_SIZE` | Chunks embedded per inference batch      | `32`                     |
| `EMBEDDING_NORMALIZE`  | Whether vectors are L2-normalized        | `true`                   |
| `EMBEDDING_CACHE_DIR`  | Optional FastEmbed model cache directory | FastEmbed default        |
| `INGESTION_DEBUG`      | Retain intermediate artifacts            | `false`                  |
| `INGESTION_TIMEOUT`    | PDF download timeout in seconds          | `30`                     |
| `INGESTION_TMP_FOLDER` | Debug artifact directory                 | `tmp`                    |

`DB_SCHEMA` can isolate another knowledge base in the same PostgreSQL database, for
example `DB_SCHEMA=evaluation make init-db`. `EMBEDDING_DIMENSIONS` must match the
selected model. Changing it after database initialisation requires recreating the
schema, for example with `make reset-db`.

The Docker images preload `EMBEDDING_MODEL_NAME` during their build. Rebuild the images
after intentionally changing the model configuration.
