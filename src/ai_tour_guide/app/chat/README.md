# Chat interface

The Gradio chat is the user interface for the travel agent. It does not retrieve
documents or access an LLM provider directly. Instead, it sends each question to the
agent's HTTP API and displays the grounded answer with its source pages. Each session
starts with a welcome from **Petit Guide**, followed by example questions. Assistant and
user messages are labelled **Petit Guide** and **You**, respectively.

Return to the [project overview](../../../../README.md) or the
[agent guide](../agent/README.md).

## Table of contents

- [Run with Docker](#run-with-docker)
- [Run locally](#run-locally)
- [HTTP contract](#http-contract)

## Run with Docker

After initializing the database, set `AGENT_LLM_API_KEY` in `.env` when using OpenAI and
run:

```bash
make app
```

Open `http://localhost:7860`. Docker Compose starts:

- the app API at `http://localhost:8000`, with database and OpenAI access;
- the Gradio interface at `http://localhost:7860`, configured to call the agent.

Ingestion is optional for the guided chat. If the database has no documents, the API
still starts and travel questions explain that source-grounded answers are unavailable.

## Run locally

Start the API and chat in separate terminals:

```bash
uv run uvicorn ai_tour_guide.app.api:app --host 127.0.0.1 --port 8000
```

```bash
uv run python -m ai_tour_guide.app.chat.app
```

The defaults in `.env.template` configure the chat to call `http://localhost:8000/chat`.
`CHAT_API_URL`, `CHAT_HOST`, `CHAT_PORT`, and `CHAT_TITLE` can be changed for another
environment. When the `baguette-llm` provider is active, the chat adds a randomized demo
response delay between `CHAT_DEMO_RESPONSE_DELAY_MIN_SECONDS` and
`CHAT_DEMO_RESPONSE_DELAY_MAX_SECONDS` (2–3 seconds by default).

The assistant can answer which destinations it covers from the titles of the currently
indexed guides. It uses retrieved passages for all destination details and other travel
questions, so this catalog never substitutes for source-grounded advice.

`CHAT_API_URL` is required when starting the chat service. The application does not use
a local fallback in production. The app service raises a configuration error when no
OpenAI API key is configured.

`create_app()` uses `DemoChatService` only when no service is injected. This keeps UI
tests and local interface development independent of the agent API; the demo response
says that no chat service is available.

## HTTP contract

The chat starts a session with `POST /chat/start`, then sends interactions to
`POST /chat/message`:

```json
{
  "session_id": "00000000-0000-0000-0000-000000000000",
  "expected_step_id": "welcome",
  "input_id": "FREE_TEXT",
  "text": "What should I visit in Normandy?"
}
```

The agent returns a renderable conversation response:

```json
{
  "session_id": "00000000-0000-0000-0000-000000000000",
  "step_id": "welcome",
  "message": "The guide recommends ...",
  "buttons": []
}
```

`HttpChatService` validates the typed response and passes it to Gradio. Gradio controls
presentation and renders service-provided buttons using their labels and input IDs. The
`FREE_TEXT` input sends its text separately; clients do not rebuild conversation
history. The response also includes the public provider and model identity, which the
Gradio interface displays in its footer; credentials are never included.
