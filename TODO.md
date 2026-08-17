# Remaining work

This list reflects the current state of `ft/kb_migration`. Migration items that have
already been implemented are intentionally omitted.

## High priority

- [ ] Replace the placeholder agent tests with real assertions and fixtures.
  - `tests/unit/ai_tour_guide/agent/test_cli.py` contains unconditional `assert False`
    cases and patches the old `retrieve` import path.
  - `tests/unit/ai_tour_guide/agent/test_rag.py` contains unconditional `assert False`
    cases and missing fixtures.
  - `tests/unit/ai_tour_guide/agent/test_api.py` still contains placeholder assertions.
- [ ] Make the full test suite pass after the agent test migration.
  - Focused tests for ingestion, embeddings, RAG sources, and the LLM client currently
    pass, but the placeholder agent tests still fail or cannot be collected.
- [ ] Regenerate the committed corpus using the section-aware schema.
  - Verify that `fixtures/corpus/document_chunks.jsonl` contains `section_id`,
    `section_chunk_index`, and `section_path` values compatible with the current restore
    logic.

## Evaluation

- [ ] Implement the RAG evaluation runner in `evaluation/rag/run.py`.
  - It currently raises `NotImplementedError` after loading the golden cases.
- [ ] Add deterministic evaluation metrics in `evaluation/rag/metrics.py` once the
  runner contract is finalized.
- [ ] Reconcile the `corpus_knowledge_base` fixture contract.
  - Its annotation and documentation expect a corpus-version argument, while the
    implementation currently exposes a zero-argument factory.

## Test infrastructure

- [ ] Add knowledge-base test factories after the final model and fixture contracts are
  stable (`tests/factories/knowledge_base.py`).
- [ ] Add a hard guard preventing tests from using a non-isolated database
  (`tests/conftest.py`) before enabling database-backed test fixtures.

## Cleanup

- [ ] Remove or resolve the remaining inline TODOs that represent unfinished product
  work, including the context formatting note in `agent/cli.py` and the document-version
  TODO in `domain/documents.py`.
- [ ] Decide whether the `TODO` placeholders in the evaluation and test infrastructure
  should become tracked issues once their implementation is scheduled.
