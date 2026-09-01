# Chat message-ownership migration

- [ ] Replace `ChatBackend.ask(messages, option_id=...)` with an input that accepts the
  submitted question and optional guided-navigation ID.
- [ ] Update `HttpChatBackend` to send the question, option ID, and session ID directly
  to the agent API.
- [ ] Update `DemoBackend` to resolve deterministic answers from the submitted question
  without receiving or inspecting chat history.
- [ ] Remove `normalize_history`, app-side `Message` construction, and the related
  `Message`/`Role` imports from the Gradio app.
- [ ] Keep only UI responsibilities in the Gradio app: input handling, answer and source
  rendering, guided-option display, and feedback-event mapping.
- [ ] Ensure the API conversation graph remains the sole owner of message history,
  follow-up context, routing, and session state.
- [ ] Update unit tests for both backends and the chat app to use the revised backend
  contract.
- [ ] Run Ruff, formatting checks, focused chat tests, and the relevant API/conversation
  tests.
