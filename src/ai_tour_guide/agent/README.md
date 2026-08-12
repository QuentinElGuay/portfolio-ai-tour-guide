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
4. The configured `LLMClient` generates an answer.
5. The agent returns the answer and retrieved source metadata.

The project currently supports the OpenAI API for answer generation. Additional LLM
providers may be added in the future.

If no OpenAI API key is configured, the agent returns a clear configuration-required
answer and does not query the knowledge base.

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
```

Run directly with Python after configuring `DB_*`, `EMBEDDING_*`, and `AGENT_OPENAI_*`:

```bash
uv run portfolio-ai-tour-guide-agent search --mode vector --k 5 'Where is Dinan?'
uv run portfolio-ai-tour-guide-agent ask --k 5 'What should I visit in Brittany?'
```

`search` supports `vector`, `text`, and `hybrid` modes. `ask` uses vector retrieval by
default and accepts the same `--mode` and `--k` options.

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
  "answer": "The guide recommends ...",
  "sources": [
    {
      "title": "Guide to the Region of Brittany",
      "page_start": 12,
      "page_end": 13
    }
  ]
}
```

The chat groups repeated documents and deduplicates their page numbers for display.
These are retrieved sources supplied as context, not model-validated citations.

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
