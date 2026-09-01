# v1.3.0 agentic migration

Implement these phases in order. Keep each phase small, run its checks, and avoid mixing
UI refactors with agent-graph changes.

## Phase 1 — Establish the boundaries

- [ ] Read the current request path from `chat/app.py` through `chat/backends.py`,
  `api.py`, `conversation.py`, and `rag/agent_workflow.py`.
- [ ] Write down the contracts between the chat UI, conversation layer, and turn-level
  travel agent before changing code.
- [ ] Keep guided labels and button transitions in `chat/navigation.py`; treat their
  submitted questions as ordinary API input.
- [ ] Keep session history, follow-up resolution, and checkpointing in
  `conversation.py`.
- [ ] Define the travel-agent graph as responsible for one turn: planning, tool use,
  evidence evaluation, answer generation, and stopping.

Checkpoint: the README or a design note can show these three layers without referring to
UI navigation as agent reasoning.

## Phase 2 — Simplify the chat-backend contract

- [ ] Change `ChatBackend.ask(messages, option_id=...)` to accept a submitted `question`
  and optional guided `option_id`.
- [ ] Update `HttpChatBackend` to send `question`, `option_id`, and its `session_id`
  directly to `POST /ask`.
- [ ] Update `DemoBackend` to resolve deterministic answers from the submitted question
  without inspecting conversation history.
- [ ] Remove app-side `normalize_history`, message construction, and the related
  `Message`/`Role` imports.
- [ ] Keep request-ID tracking, response rendering, option display, and feedback-event
  mapping in the Gradio app.

Checkpoint: the chat app has no responsibility for conversation history, and both
backends satisfy the same question-based contract.

## Phase 3 — Introduce a typed retrieval tool

- [ ] Keep `OpenAIClient` (and every other provider client) limited to the commercial
  LLM interface: request/response conversion, structured-output parsing, rate limiting,
  and provider errors. It must not own agent state, tool execution, or routing.
- [ ] Create a typed `search_tourism_knowledge_base` tool in the agent/RAG package.
- [ ] Make the tool call the existing retrieval implementation and return structured
  passages, source identity, pages, and relevance metadata.
- [ ] Define one canonical input schema for the search query and one canonical output
  schema for evidence.
- [ ] Replace the inline OpenAI tool schema with the shared tool contract, or add a
  narrowly scoped adapter if the low-level OpenAI client remains in use.
- [ ] Add unit tests for valid queries, empty results, provenance, and retrieval errors.

Checkpoint: the tool can be tested independently of the LLM and its output contains all
data required for citation validation.

## Phase 4 — Create the real agent boundary

- [ ] Add an explicit provider-neutral `TravelAgent` (or equivalent agent service) that
  receives an LLM client and approved tools through dependency injection.
- [ ] Give the agent responsibility for planning, selecting actions, executing tools,
  evaluating evidence, deciding whether to retry, and deciding when to answer or refuse.
- [ ] Keep the agent independent from OpenAI-specific request types and from Gradio,
  FastAPI, and navigation labels.
- [ ] Define the agent's public input/output contract around a question, context, and
  structured result/trace rather than provider responses.
- [ ] Add unit tests with a fake LLM client and fake retrieval tool so agent behavior
  can be tested without network calls or a commercial API key.

Checkpoint: replacing OpenAI with another implementation of the LLM client does not
require changing the agent's planning or tool-execution code.

## Phase 5 — Implement the agent loop in LangGraph

- [ ] Define typed graph state for `question`, `intent`, `planned_action`, `tool_calls`,
  `evidence`, `retry_count`, `answer`, `citations`, and `final_status`.
- [ ] Add an intent/classification node for metadata, factual tourism, and unsupported
  requests.
- [ ] Add a planning node whose bounded actions are `search_knowledge_base`,
  `reformulate_search`, `answer_from_context`, and `refuse`.
- [ ] Add a tool node that executes only the approved retrieval tool.
- [ ] Add an evidence-evaluation node that decides whether context is sufficient for an
  answer.
- [ ] Add conditional transitions: sufficient evidence to generation; insufficient
  evidence to one bounded reformulation; exhausted retries to refusal.
- [ ] Keep identity and other metadata answers as an explicit, safe branch that never
  claims unsupported tourism facts.
- [ ] Keep citation validation mandatory after generation and before returning a result.
- [ ] Enforce a maximum tool-call/retry budget and reject unknown actions or tools.

Checkpoint: the graph visibly implements `plan -> tool -> evaluate -> answer/refuse`,
and the graph can terminate without calling the LLM generation step when evidence is
absent.

## Phase 6 — Keep conversation orchestration separate

- [ ] Make `ConversationGraph` pass one user question and the session flow state to the
  turn-level travel-agent graph.
- [ ] Ensure only `ConversationGraph` owns checkpointed message history and follow-up
  context.
- [ ] Ensure the turn-level graph does not inherit the conversation checkpointer for
  runtime retrieval objects.
- [ ] Preserve `session_id` behavior in the API and the existing feedback linkage.
- [ ] Add an integration test covering two turns in one session, including a follow-up
  question and an agent trace.

Checkpoint: the two graphs have distinct responsibilities and can be tested
independently.

## Phase 7 — Expose an inspectable agent trace

- [ ] Add structured action metadata for intent, selected actions, tool inputs,
  tool-call count, evidence sufficiency, retries, and final status.
- [ ] Keep private chain-of-thought out of API responses and logs.
- [ ] Include the trace in verbose CLI output and diagnostic `RAGResult` metadata.
- [ ] Persist only the operational fields needed by evaluation and monitoring.
- [ ] Update API models and chat rendering only if a user-facing trace is intentionally
  added.

Checkpoint: a reviewer can see what the agent did and why it stopped without seeing
private reasoning.

## Phase 8 — Documentation and release validation

- [ ] Update `README.md`, `src/ai_tour_guide/agent/README.md`, and architecture diagrams
  to describe the bounded agent loop and layer boundaries.
- [ ] Update tests for the chat app, both backends, API, conversation graph, retrieval
  tool, graph routing, refusal, retry limits, citation validation, and trace output.
- [ ] Run focused tests after each phase, then run the complete relevant agent and
  database test suites.
- [ ] Run Ruff, formatting checks, Markdown formatting checks, and `git diff --check`.
- [ ] Update `ROADMAP.md` milestone status and mark Release v1.3.0 shipped only after
  all checkpoints and release validation pass.

Final acceptance: the project can accurately describe itself as a bounded,
source-grounded travel agent using LangGraph for orchestration, a typed retrieval tool
for external knowledge, an LLM for planning/generation, and citation validation as a
safety boundary.
