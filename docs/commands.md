# Make command reference

This reference documents every public command in the project `Makefile`. Run `make help`
for a short reminder in the terminal.

## Table of contents

- [Getting help](#getting-help)
- [Application and search](#application-and-search)
- [Database and corpus](#database-and-corpus)
- [Ingestion](#ingestion)
- [Evaluation](#evaluation)
- [Monitoring dashboard](#monitoring-dashboard)
- [Operations and maintenance](#operations-and-maintenance)
- [Shared options](#shared-options)

## Getting help

### `make help`

Print a compact alphabetical list of commands and their most common forms. Use this
reference when you need the complete behavior, options, or safety notes.

## Application and search

### `make app`

Build and start the agent API and Gradio chat interface. It waits for the services to
become healthy. Open the chat at <http://localhost:7860> and the API documentation at
<http://localhost:8000/docs>.

When the agent cannot start, the command prints its two most recent diagnostic log
lines. A common cause is an empty application schema; initialize it and ingest a corpus
before starting the app.

### `make ask QUESTION='...'`

Answer one question in the terminal with the agent RAG pipeline. The agent container is
created for the request and removed afterwards.

```bash
make ask QUESTION='What are the main places to visit in Brittany?'
make ask QUESTION='What are the main places to visit in Brittany?' K=10
make ask QUESTION='What are the main places to visit in Brittany?' VERBOSE=1
```

`K` controls the number of retrieved chunks (default: `5`). `VERBOSE=1` prints the
serialized RAG trace.

### `make cli-chat`

Start the agent service, then open an interactive terminal chat. Pass `K` to change the
number of chunks retrieved for each answer:

```bash
make cli-chat K=10
```

### `make vector_search QUESTION='...'`

Run semantic search only. This does not call an LLM.

```bash
make vector_search QUESTION='Brittany coast' K=10
```

### `make text_search QUESTION='...'`

Run PostgreSQL full-text search only. This does not call an LLM.

```bash
make text_search QUESTION='Brittany coast' K=10
```

## Database and corpus

### `make db-init`

Initialize the pgvector application schema. The default schema is `public`.

```bash
make db-init
make db-init SCHEMA=evaluation
```

### `make db-reset`

Delete and recreate the selected application schema, preserving the separate Metabase
database. This is destructive for the selected schema.

```bash
make db-reset
make db-reset SCHEMA=evaluation
```

### `make db-reset-schema SCHEMA=name`

Delete and recreate one explicitly named schema. `SCHEMA` must be supplied on the
command line as a lowercase PostgreSQL identifier, which makes destructive use more
intentional.

```bash
make db-reset-schema SCHEMA=evaluation
```

### `make db-validate-schema`

Validate the configured `SCHEMA` value without changing the database. It is also run by
the database commands that accept `SCHEMA`.

### `make load-corpus`

Replace the corpus in the selected schema with the JSONL export in `fixtures/corpus`.
The command is destructive for that schema.

```bash
make load-corpus
make load-corpus SCHEMA=evaluation
make load-corpus CORPUS_ROOT=path/to/corpus
```

The corpus directory must contain `embedding_models.jsonl`, `documents.jsonl`, and
`document_chunks.jsonl`.

### `make export-corpus`

Export the current knowledge base to JSONL files. The default output directory is
`fixtures/corpus`; existing export files are overwritten.

```bash
make export-corpus
make export-corpus CORPUS_ROOT=tmp/corpus-export
```

### `make export-csv`

Export deterministic CSV snapshots of the ingestion tables. It writes up to 1,000 rows
per table to `tmp/` by default.

```bash
make export-csv
make export-csv CSV_LIMIT=100 EXPORT_DIR=tmp/database-export
make export-csv SCHEMA=evaluation
```

## Ingestion

### `make ingest`

Ingest the document definitions in `source_files.json`. Initialize the schema first:

```bash
make db-init
make ingest
```

Existing documents with the same source URL and version are skipped. Set `FORCE=1` to
replace those documents and their chunks. Set `DEBUG=1` to retain intermediate parsing
artifacts in `tmp/`.

```bash
make ingest SOURCE_FILES=data/another-source-files.json
make ingest FORCE=1
make ingest DEBUG=1
```

### `make airflow`

Build and start the optional Airflow profile for parameterized ingestion. It waits for
the database, web server, scheduler, and DAG processor to become healthy. Then open
<http://localhost:8080> and trigger the `ingest_documents` DAG. See the
[tutorial](README.md#ingestion-with-airflow) for the workflow.

Before running raw Airflow Compose commands, export the Docker socket's group ID:

```bash
export DOCKER_GID="$(stat -c '%g' /var/run/docker.sock)"
docker compose --profile airflow up --build -d --wait \
  database airflow-webserver airflow-scheduler airflow-dag-processor
```

`make airflow` detects this value automatically.

### `make annotate-dataset`

Interactively fill answers and source pages in the golden dataset.

```bash
make annotate-dataset
make annotate-dataset ANNOTATOR_ARGS='--resume'
```

Pass any supported annotator command-line options through `ANNOTATOR_ARGS`.

## Evaluation

Every evaluation starts PostgreSQL and loads the corpus into the isolated `evaluation`
schema. `K` controls the number of ranked chunks considered (default: `5`), and
`CORPUS_ROOT` selects the corpus export.

### `make evaluate`

Run the default evaluation suite: offline search metrics and LLM-judge scoring.

```bash
make evaluate
make evaluate K=10
make evaluate CORPUS_ROOT=tmp/corpus-export
```

The judge makes model calls. `JUDGE_PROVIDER` defaults to `openai`.

### `make evaluate-all`

Alias for `make evaluate`.

### `make evaluate-search`

Run offline vector, full-text, and hybrid-search metrics only.

### `make evaluate-rag`

Run online RAG metrics, without LLM-judge scoring.

### `make evaluate-judge`

Generate RAG answers and score them with the configured LLM judge.

## Monitoring dashboard

### `make dashboard`

Start PostgreSQL and Metabase. On first use, it automatically restores the bundled
Metabase fixture, creates the initial administrator, and configures the dashboard data
sources. Open the dashboard at <http://localhost:3000>.

Use `DEBUG=1` for verbose Docker Compose diagnostics:

```bash
make dashboard DEBUG=1
```

### `make dashboard-init`

Run only the dashboard initialization step. It is useful when initializing an existing
Metabase instance; normal local setup should use `make dashboard`, which runs it
automatically.

### `make dashboard-restore`

Restore the bundled Metabase application-database backup when the Metabase database is
empty. It refuses to overwrite a populated database unless `FORCE=1` is explicit.

```bash
make dashboard-restore
make dashboard-restore FORCE=1
```

`FORCE=1` discards the current Metabase application database before restoring the
fixture.

### `make dashboard-export`

Export the current Metabase application database to `fixtures/metabase/metabase.sql` and
rebuild the image that bundles it. Use this after intentionally changing dashboard
configuration that should become the new fixture.

### `make validate-dashboard-backup`

Check that the configured dashboard backup exists and that `METABASE_DB_NAME` and
`FORCE` are valid. This validation command does not restore anything.

## Operations and maintenance

### `make simulate-rag`

Populate the monitoring dashboards with deterministic synthetic RAG traffic. The
simulation can include expected errors, but it suppresses their individual tracebacks
and prints a summary of the inserted objects when finished.

```bash
make simulate-rag
make simulate-rag SIMULATE_ARGS='--days 30 --requests-per-day 50'
```

### `make smoke-test`

Run deterministic end-to-end RAG smoke tests against an isolated `smoke` schema. The
command uses the strict fixture model, so it does not require a live LLM API key.

### `make stop`

Stop every Docker Compose profile and remove its containers, networks, and orphaned
containers. Persistent volumes are retained.

### `make purge`

Stop every Docker Compose profile and remove its containers, networks, orphaned
containers, and volumes. This deletes local PostgreSQL, Airflow, and Metabase data.

> [!CAUTION]
> `make purge` is destructive. Export any data or dashboard configuration you need
> before running it.

## Shared options

| Option             | Default                          | Used by                               | Meaning                                                                       |
| ------------------ | -------------------------------- | ------------------------------------- | ----------------------------------------------------------------------------- |
| `SCHEMA`           | `public`                         | Database and export commands          | Application PostgreSQL schema.                                                |
| `K`                | `5`                              | Search, chat, and evaluation          | Number of retrieved or ranked chunks.                                         |
| `DEBUG`            | `0`                              | Docker Compose, ingestion, dashboard  | Enables Compose diagnostics or retains ingestion artifacts.                   |
| `FORCE`            | `0`                              | Ingestion, dashboard restore          | Replaces existing documents or overwrites Metabase, depending on the command. |
| `QUESTION`         | Empty                            | `ask`, `text_search`, `vector_search` | Required question for one-off answer or search commands.                      |
| `SOURCE_FILES`     | `source_files.json`              | `ingest`                              | Input document-definition JSON file.                                          |
| `ANNOTATOR_ARGS`   | Empty                            | `annotate-dataset`                    | Extra options passed to the dataset annotator.                                |
| `SIMULATE_ARGS`    | Empty                            | `simulate-rag`                        | Extra options passed to the traffic simulator.                                |
| `VERBOSE`          | `0`                              | `ask`                                 | Prints the serialized RAG trace when set to `1`.                              |
| `CORPUS_ROOT`      | `fixtures/corpus`                | Corpus and evaluation commands        | Corpus JSONL directory.                                                       |
| `EVALUATION`       | `all`                            | `evaluate`                            | Selects `search`, `rag`, `judge`, or `all` evaluation behavior.               |
| `JUDGE_PROVIDER`   | `openai`                         | Evaluation judge                      | Provider used for LLM-judge scoring.                                          |
| `EXPORT_DIR`       | `tmp`                            | `export-csv`                          | CSV output directory.                                                         |
| `CSV_LIMIT`        | `1000`                           | `export-csv`                          | Maximum rows per exported table.                                              |
| `DASHBOARD_BACKUP` | `fixtures/metabase/metabase.sql` | Dashboard backup commands             | Metabase database-backup path.                                                |
| `METABASE_DB_NAME` | `metabase`                       | Dashboard backup commands             | Metabase application database name.                                           |

Most options are passed as `NAME=value`, for example:

```bash
make ingest FORCE=1 DEBUG=1
make export-csv SCHEMA=evaluation CSV_LIMIT=100
```
