# Client-independent chat contract

Bon Voyage exposes a conversation contract that does not require clients to know the
guided flow or LangGraph implementation.

## Boundaries

- Gradio and CLI retain only the latest `session_id` and `step_id`. They render the
  `message` and `buttons` returned by the backend.
- The HTTP API validates request shape and exposes `/chat/start`, `/chat/message`, and
  `/chat/feedback`.
- The checkpointed `ConversationGraph` owns durable session state and flow routing.
- A turn-level `TravelAgent` answers questions and uses retrieval without owning session
  state or UI transitions.

## Contract

`POST /chat/start` always creates a new session. It accepts no client-supplied session
ID and returns a `ConversationResponse` containing `session_id`, `step_id`, `message`,
and `buttons`.

`POST /chat/message` accepts:

```json
{
  "session_id": "00000000-0000-0000-0000-000000000000",
  "expected_step_id": "welcome",
  "input_id": "FREE_TEXT",
  "text": "What should I visit?"
}
```

`FREE_TEXT` requires non-empty `text`. Guided input IDs are opaque domain identifiers;
clients submit them as received and never turn them into questions.

`POST /chat/feedback` accepts a generated response `request_id`, a helpfulness value,
and an optional comment. A request ID links feedback and observability to an answer; it
is never used as conversation-flow state.

Free-text responses may include `request_id`, validated `sources`, and safe operational
`trace` metadata. The trace contains actions, tool inputs, retry counts, evidence
sufficiency, and final status; it never contains private model reasoning or raw provider
payloads.

The former `/ask` and `/feedback` routes are removed; clients use only the `/chat`
namespace.
