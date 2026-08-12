# Chat interface

The Gradio chat is the user interface for the RAG agent. It does not retrieve documents
or access an LLM provider directly. Instead, it sends each question to the agent's HTTP
API and displays the grounded answer with its source pages.

## Run with Docker

After initializing and ingesting the database, set `AGENT_OPENAI_API_KEY` in `.env` and
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

`CHAT_API_URL` is required when starting the chat service. The application does not use
a local fallback in production. The agent returns the LLM-configuration-required
response without querying the knowledge base when no OpenAI API key is configured.

`create_app()` uses `DemoBackend` only when no backend is injected. This keeps UI tests
and local interface development independent of the agent API; the demo response only
explains that an LLM configuration is required.

## HTTP contract

The chat sends the latest user question:

```json
{
  "question": "What should I visit in Brittany?"
}
```

The agent returns its answer and retrieved source references:

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
