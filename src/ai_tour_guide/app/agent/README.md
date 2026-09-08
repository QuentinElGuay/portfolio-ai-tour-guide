# Travel-agent API

The `agent` package owns travel-agent and conversation orchestration. `llm` provides
provider communication, while `services.demo` and `services.rag` provide deterministic
prepared questions and retrieval-augmented generation. Together, they are exposed
through a CLI and a small HTTP API. The browser interface is documented in the
[chat guide](../chat/README.md).

Return to the [project overview](../../../README.md).

## Table of contents

- [Request flow](#request-flow)
- [Run the services](#run-the-services)
- [CLI](#cli)
- [HTTP API](#http-api)
- [Configuration](#configuration)

## Request flow

1. The client starts a backend-owned session through `POST /chat/start`.
2. `ConversationGraph` checkpoints the session and validates each `input_id` against the
   current public `step_id`.
3. Free-text turns use the dynamically selected deterministic or LLM agent; guided
   actions are resolved deterministically by the outer conversation flow.
4. When retrieval is enabled, the shared retrieval tool searches the knowledge base and
   classifies evidence quality.
5. The LLM workflow generates only from valuable retrieved context; low-confidence
   retrieval returns a clear refusal. Deterministic retrieval displays formatted results
   directly, including low-confidence results.
6. The API and CLI return validated sources plus structured retrieval evidence.

Supported live LLM providers and recommended models:

- OpenAI (ChatGPT): `gpt-4.1-mini`
- Google Gemini: `gemini-3.5-flash-lite`

The bundled `baguette-llm` provider, `mini-croissant-1.0` model, is a no-cost
deterministic Brittany demo; it is not a general-purpose LLM. It retains its
deterministic matching behavior and does not use the LangGraph workflow.

The `baguette-llm` provider does not require an API key. OpenAI and Gemini require an
API key. If LLM execution is unavailable, the application automatically downgrades to
deterministic execution.

## Run the services

The agent requires the knowledge-base database. Initialise its schema before starting
the application:

```bash
make db-init
```

Ingestion is optional. With an empty knowledge base, deterministic execution uses
prepared questions and LLM execution remains limited to conversational or meta answers.
Run `make ingest` or `make load-corpus` to enable source-grounded travel answers.

The template enables both capabilities by default. Without a usable LLM API key, the
application automatically falls back to deterministic retrieval and then prepared
questions when the knowledge base is empty or unavailable.

To use live answer generation with ChatGPT, switch to OpenAI and add your API key. The
two capability flags control execution dynamically:

```dotenv
AGENT_LLM_PROVIDER=openai
AGENT_LLM_API_KEY=your-api-key
AGENT_LLM_MODEL=gpt-4.1-mini
APP_ENABLE_LLM=1
APP_ENABLE_RETRIEVAL=1
```

Set `APP_ENABLE_LLM=0` to force deterministic execution. Set `APP_ENABLE_RETRIEVAL=0` to
prevent retrieval and limit an enabled LLM to conversation; with LLM disabled as well,
the application uses prepared questions.

To use Google Gemini, set `AGENT_LLM_PROVIDER=gemini`, add your API key, and use
`AGENT_LLM_MODEL=gemini-3.5-flash-lite`.

Start the agent API and Gradio chat together:

```bash
make app
```

Docker Compose gives the optional OpenAI credential only to the `app` service. The
separate `chat` service calls `http://app:8000/chat` over the internal network.
`make app` initializes the database schema and starts the database service, but does not
ingest documents.

To run only the API locally:

```bash
uv run uvicorn ai_tour_guide.app.api:app --host 127.0.0.1 --port 8000
```

## CLI

The CLI uses the same retrieval and RAG pipeline. The Docker shortcuts start any needed
agent dependencies:

```bash
make vector_search QUESTION='Where are the Normandy D-Day beaches?'
make text_search QUESTION='Normandy coast'
make ask QUESTION='What are the best places to visit in Normandy?' K=5
make ask QUESTION='What are the best places to visit in Normandy?' K=5 VERBOSE=1
```

Run directly with Python after configuring `DB_*`, `EMBEDDING_*`, and `AGENT_LLM_*`:

```bash
uv run portfolio-ai-tour-guide-agent search --mode vector --k 5 'Where is Rouen?'
uv run portfolio-ai-tour-guide-agent ask --k 5 'What should I visit in Occitanie?'
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

`POST /chat/start` creates a session and returns the first renderable response. Then
`POST /chat/message` accepts a session, expected step, input ID, and optional text:

```json
{
  "session_id": "00000000-0000-0000-0000-000000000000",
  "expected_step_id": "welcome",
  "input_id": "FREE_TEXT",
  "text": "What should I visit in Normandy?"
}
```

It returns the next step, renderable buttons, an answer, validated source references,
and safe trace metadata:

```json
{
  "session_id": "00000000-0000-0000-0000-000000000000",
  "step_id": "welcome",
  "message": "The guide recommends ...",
  "request_id": "11111111-1111-1111-1111-111111111111",
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
  ],
  "trace": {
    "intent": "travel_question",
    "actions": ["search_knowledge_base", "answer_from_context"],
    "tool_inputs": ["places to visit in Normandy"],
    "tool_call_count": 1,
    "evidence_sufficient": true,
    "retries": 0,
    "final_status": "answered"
  }
}
```

Each source is a document identity `(source_url, version)` with sorted, deduplicated
pages. Sources are citations claimed by the model and validated against retrieved
knowledge-base evidence; retrieved-but-uncited chunks are not exposed through the chat
API. The detailed retrieval and citation trace remains available through
`make ask VERBOSE=1` and `RAGResult.to_dict()` for diagnostics and future evaluation.

The document identity constraint changed from `source_url` to `(source_url, version)`.
Reinitialize the database schema before using this version of the agent:

```bash
make db-reset
make ingest
```

`make db-reset` resets only the selected application schema and preserves Metabase.

## Configuration

| Variable               | Purpose                                | Template value      |
| ---------------------- | -------------------------------------- | ------------------- |
| `AGENT_LLM_PROVIDER`   | LLM provider for answer generation     | `openai`            |
| `AGENT_LLM_API_KEY`    | Required when LLM execution is enabled | Empty               |
| `AGENT_LLM_MODEL`      | LLM model identifier                   | See `.env.template` |
| `APP_ENABLE_LLM`       | Allow LLM execution                    | `1`                 |
| `APP_ENABLE_RETRIEVAL` | Allow RAG/retrieval                    | `1`                 |
| `APP_PORT`             | Host port for the agent API            | `8000`              |
| `DB_*`                 | Database connection used for retrieval | See `.env.template` |
| `EMBEDDING_*`          | Query embedding configuration          | See `.env.template` |

`DB_SCHEMA` selects the PostgreSQL schema used for retrieval. It defaults to `public`;
use the same value for schema initialization, ingestion, and the agent so RAG reads the
knowledge base you populated.

`AGENT_LLM_MODEL` is required by the settings class; `.env.template` provides the
`mini-croissant-1.0` default. OpenAI (ChatGPT) and Google Gemini are supported providers
for live answer generation.

For the chat service's `CHAT_*` settings and development-only `DemoChatService`, see the
[chat guide](chat/README.md).
