# Chat interface

The Gradio chat is the user interface for the RAG agent. It does not retrieve documents
or access an LLM provider directly. Instead, it sends each question to the agent's HTTP
API and displays the grounded answer with its source pages.

Return to the [project overview](../../../../README.md) or the
[agent guide](../README.md).

## Table of contents

- [Run with Docker](#run-with-docker)
- [Run locally](#run-locally)
- [HTTP contract](#http-contract)

## Run with Docker

After initializing and ingesting the database, set `AGENT_LLM_API_KEY` in `.env` and
run:

```bash
make app
```

Open `http://localhost:7860`. Docker Compose starts:

- the agent API at `http://localhost:8000`, with database and OpenAI access;
- the Gradio interface at `http://localhost:7860`, configured to call the agent.

## Run locally

Start the API and chat in separate terminals:

```bash
uv run uvicorn ai_tour_guide.agent.api:app --host 127.0.0.1 --port 8000
```

```bash
uv run python -m ai_tour_guide.agent.chat.app
```

The defaults in `.env.template` configure the chat to call `http://localhost:8000/ask`.
`CHAT_API_URL`, `CHAT_HOST`, `CHAT_PORT`, and `CHAT_TITLE` can be changed for another
environment.

The assistant can answer which destinations it covers from the titles of the currently
indexed guides. It uses retrieved passages for all destination details and other travel
questions, so this catalog never substitutes for source-grounded advice.

`CHAT_API_URL` is required when starting the chat service. The application does not use
a local fallback in production. The agent service raises a configuration error when no
OpenAI API key is configured.

`create_app()` uses `DemoBackend` only when no backend is injected. This keeps UI tests
and local interface development independent of the agent API; the demo response says
that no backend is available.

## HTTP contract

The chat sends the latest user question:

```json
{
  "question": "What should I visit in Normandy?"
}
```

The agent returns its answer and validated source references:

```json
{
  "schema_version": 1,
  "answer": "The guide recommends ...",
  "sources": [
    {
      "source_url": "https://example.com/normandy-guide.pdf",
      "version": "2026",
      "title": "Guide to the Region of Normandy",
      "publisher": "Regional Tourism Board",
      "collection": "Tour Guides",
      "publication_date": "2026-01-01",
      "pages": [12, 13]
    }
  ]
}
```

`HttpChatBackend` validates the schema version and passes this dictionary to Gradio.
Gradio controls presentation; its default view renders the answer followed by each
source title and its pages in parentheses.
