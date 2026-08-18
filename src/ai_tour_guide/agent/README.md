# Agent and RAG API

This package owns retrieval, prompt construction, and LLM generation. It exposes those
capabilities through a CLI and a small HTTP API. The browser interface is documented in
the [chat guide](chat/README.md).

Return to the [project overview](../../../README.md).

## Table of contents

- [Request flow](#request-flow)
- [Run the services](#run-the-services)
- [CLI](#cli)
- [HTTP API](#http-api)
- [Configuration](#configuration)

## Request flow

1. The agent receives a question through the CLI or `POST /ask`.
2. It retrieves the most relevant chunks from PostgreSQL using vector search by default.
3. It builds a prompt containing the retrieved context and question.
4. The configured `LLMClient` generates an answer and document/page citations.
5. The agent validates citations against the retrieved provenance, then returns only
   validated source references to user interfaces.

The project currently supports the OpenAI API for answer generation. Additional LLM
providers may be added in the future.

If no OpenAI API key is configured, the service raises a configuration error before
querying the knowledge base.

## Run the services

The agent requires the knowledge-base database. Initialise its schema and ingest at
least one document before starting the RAG application:

```bash
make init-db
make ingest
```

For the RAG application, `.env` must define `AGENT_OPENAI_API_KEY`; it also needs the
database and embedding settings used for retrieval. The template provides a default
`AGENT_OPENAI_MODEL`.

Add your API key:

```dotenv
AGENT_OPENAI_API_KEY=your-api-key
```

Start the agent API and Gradio chat together:

```bash
make app
```

Docker Compose gives the OpenAI credential only to the `agent` service. The separate
`chat` service calls `http://agent:8000/ask` over the internal network. `make app`
starts the database service as an agent dependency, but it does not initialise or ingest
the database.

To run only the API locally:

```bash
uv run uvicorn ai_tour_guide.agent.api:app --host 127.0.0.1 --port 8000
```

## CLI

The CLI uses the same retrieval and RAG pipeline. The Docker shortcuts start any needed
agent dependencies:

```bash
make vector_search QUESTION='Where is the Brittany coast?'
make text_search QUESTION='Brittany coast'
make ask QUESTION='What are the best places to visit in Brittany?' K=5
make ask QUESTION='What are the best places to visit in Brittany?' K=5 VERBOSE=1
```

Run directly with Python after configuring `DB_*`, `EMBEDDING_*`, and `AGENT_OPENAI_*`:

```bash
uv run portfolio-ai-tour-guide-agent search --mode vector --k 5 'Where is Dinan?'
uv run portfolio-ai-tour-guide-agent ask --k 5 'What should I visit in Brittany?'
```

`search` supports `vector`, `text`, and `hybrid` modes. `ask` uses vector retrieval by
default and accepts the same `--mode` and `--k` options. Its default output is the same
JSON payload as the HTTP API. `VERBOSE=1` adds the full `RAGResult` trace: ranked
retrieval, prompt context, raw citations, validated sources, invalid citations, timing,
metadata, and any handled operational error.

## HTTP API

`GET /health` reports whether the process is ready:

```json
{"status": "ok"}
```

`POST /ask` accepts a non-empty question:

```json
{
  "question": "What should I visit in Brittany?"
}
```

It returns an answer and source references:

```json
{
  "schema_version": 1,
  "answer": "The guide recommends ...",
  "sources": [
    {
      "source_url": "https://example.com/brittany-guide.pdf",
      "version": "2026",
      "title": "Guide to the Region of Brittany",
      "publisher": "Regional Tourism Board",
      "collection": "Tour Guides",
      "publication_date": "2026-01-01",
      "pages": [12, 13]
    }
  ]
}
```

Each source is a document identity `(source_url, version)` with sorted, deduplicated
pages. Sources are citations claimed by the model and validated against retrieved
knowledge-base evidence; retrieved-but-uncited chunks are not exposed through `/ask`.
The detailed retrieval and citation trace remains available through `make ask VERBOSE=1`
and `RAGResult.to_dict()` for diagnostics and future evaluation.

The document identity constraint changed from `source_url` to `(source_url, version)`.
Reinitialize the database schema before using this version of the agent:

```bash
make reset-db
make ingest
```

## Configuration

| Variable               | Purpose                                | Template value      |
| ---------------------- | -------------------------------------- | ------------------- |
| `AGENT_OPENAI_API_KEY` | OpenAI API key for answer generation   | Empty               |
| `AGENT_OPENAI_MODEL`   | OpenAI model for answer generation     | `gpt-4.1-mini`      |
| `AGENT_PORT`           | Host port for the agent API            | `8000`              |
| `DB_*`                 | Database connection used for retrieval | See `.env.template` |
| `EMBEDDING_*`          | Query embedding configuration          | See `.env.template` |

`DB_SCHEMA` selects the PostgreSQL schema used for retrieval. It defaults to `public`;
use the same value for schema initialization, ingestion, and the agent so RAG reads the
knowledge base you populated.

`AGENT_OPENAI_MODEL` is required by the settings class; `.env.template` provides a
default. OpenAI is the only provider currently supported by the default client.

For the chat service's `CHAT_*` settings and development-only `DemoBackend`, see the
[chat guide](chat/README.md).
