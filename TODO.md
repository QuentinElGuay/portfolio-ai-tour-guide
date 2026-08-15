# KB Migration TODO

Review target: `ft/kb_migration`

This file contains the remaining issues found after the latest migration push.
Items are ordered by priority. Completed items from earlier reviews are omitted
except for the short verification section at the end.

## P0 — Runtime blockers

- [ ] Fix `RetrievedContext.section_path` usage in `agent/rag/prompting.py`.
  - `_format_context()` currently uses `context.section_path`.
  - `RetrievedContext` currently defines only:
    - `section_id`
    - `text`
    - `search_results`
    - `sources`
  - Recommended fix: add `section_path: tuple[str, ...]` to `RetrievedContext`
    and populate it in `build_retrieved_contexts()` from the selected section.
  - Alternative: derive it from `context.sources[0].section_path`, but keeping the
    section path directly on the context makes the context self-describing.
  - Files:
    - `src/ai_tour_guide/agent/rag/prompting.py`
    - `src/ai_tour_guide/knowledge_base/retrieval/models.py`
    - `src/ai_tour_guide/knowledge_base/retrieval/context.py`

- [ ] Fix `validate_citations()` iteration over retrieved contexts.
  - Current code tries to access `retrieved.sources` even though `retrieved` is a
    `Sequence[RetrievedContext]`.
  - It then treats each source as though it had a nested `.source` object.
  - Iterate contexts first, then their `SourceDocumentMetadata` entries directly.
  - Target shape:

    ```python
    for context in retrieved:
        for source in context.sources:
            documents.setdefault(
                (source.url, source.version),
                [],
            ).append(source)
    ```

  - File:
    - `src/ai_tour_guide/agent/rag/sources.py`

- [ ] Migrate the HTTP API to `RAGResult.sources`.
  - `agent/api.py` still reads `result.chunks`, which no longer exists.
  - It also constructs `SourceResponse` with `page_start` / `page_end`, although
    `SourceResponse` expects:
    - `source_url`
    - `version`
    - `title`
    - `publisher`
    - `collection`
    - `publication_date`
    - `pages`
  - The API should map the already validated `result.sources` into
    `SourceResponse`.
  - Do not reconstruct public citations from contexts or raw search results.
  - File:
    - `src/ai_tour_guide/agent/api.py`

- [ ] Make retrieval evaluation use raw `search()` results.
  - `evaluation/retrieval/run.py` still calls `retrieve()`.
  - `retrieve()` returns `RetrievedContext`, while the evaluator expects objects
    with `.source`.
  - Import and call `search()` from `ai_tour_guide.knowledge_base.search`.
  - Update the renamed provenance field from `source.source_url` to `source.url`.
  - This is also required semantically: retrieval evaluation must measure the raw
    ranking before sibling/context expansion.
  - File:
    - `evaluation/retrieval/run.py`

- [ ] Update `test_rag_sources.py` so pytest can collect it.
  - It still imports removed types:
    - `RetrievedChunk`
    - `SourceMetadata`
    - `ScoreKind` from `knowledge_base.retrieval`
  - Rebuild its fixtures around `RetrievedContext` plus
    `SourceDocumentMetadata`.
  - File:
    - `tests/unit/ai_tour_guide/agent/test_rag_sources.py`

## P1 — Behavioral correctness

- [ ] Make the CLI `search` command call `search()`, not `retrieve()`.
  - The current implementation calls `retrieve()` and then flattens each
    context's `search_results`.
  - Section grouping can change the original global ranking order.
    Example: raw ranks `A1, B2, A3` can be printed as `A1, A3, B2`.
  - The CLI command named `search` should expose raw ranked `SearchResult`s.
  - Keep `retrieve()` for the RAG/LLM context path only.
  - File:
    - `src/ai_tour_guide/agent/cli.py`

- [ ] Preserve exact citation evidence when formatting LLM context.
  - `_format_sources()` currently collapses all sibling source ranges into a
    sorted set of page numbers.
  - The system prompt asks the LLM to copy page bounds exactly.
  - Prefer rendering exact page ranges from `SourceDocumentMetadata`
    (deduplicated as necessary) so the LLM cannot accidentally infer a range
    containing unsupported pages.
  - Example preferred representation:

    ```text
    Source: Guide to Brittany
    URL: ...
    Version: 2026
    Pages: 8-9, 11
    ```

  - File:
    - `src/ai_tour_guide/agent/rag/prompting.py`

- [ ] Decide and enforce the invariant that a `RetrievedContext` always has at
  least one source.
  - `_format_sources()` indexes `source_documents[0]`.
  - Today this should normally be true because a context is built from an
    existing matched section, but the invariant is implicit.
  - Either:
    - validate it in `RetrievedContext.__post_init__`, or
    - make the formatter explicitly handle an empty source tuple.
  - Files:
    - `src/ai_tour_guide/knowledge_base/retrieval/models.py`
    - `src/ai_tour_guide/agent/rag/prompting.py`

## P2 — Data and test migration

- [ ] Regenerate the committed corpus with sibling metadata.
  - The current `fixtures/corpus/document_chunks.jsonl` still lacks
    `section_id` and `section_chunk_index`.
  - The new restore path reads both fields.
  - The current database schema requires `section_id NOT NULL`.
  - Regenerate the corpus from a database populated by the sibling-aware
    ingestion pipeline; do not invent section IDs during restore.
  - Files:
    - `fixtures/corpus/document_chunks.jsonl`
    - `src/ai_tour_guide/knowledge_base/corpus/export.py`
    - `src/ai_tour_guide/knowledge_base/corpus/restore.py`

- [ ] Port the remaining agent tests to the new contracts.
  - `test_cli.py` still constructs `RAGResult(context='')`, but `context` is no
    longer a field.
  - Several CLI/RAG tests still contain unconditional `assert False`.
  - `test_api.py` still contains placeholder `assert True` tests rather than
    validating the API response.
  - Replace old `RetrievedChunk` expectations with:
    - `SearchResult` for raw search behavior
    - `RetrievedContext` for LLM context behavior
    - `SourceReference` for public answer sources
  - Files:
    - `tests/unit/ai_tour_guide/agent/test_cli.py`
    - `tests/unit/ai_tour_guide/agent/test_rag.py`
    - `tests/unit/ai_tour_guide/agent/test_rag_sources.py`
    - `tests/unit/ai_tour_guide/agent/test_api.py`

- [ ] Fix the `corpus_knowledge_base` fixture contract.
  - It is annotated as `Callable[[int], AbstractContextManager[None]]`.
  - Its documentation calls `corpus_knowledge_base(1)`.
  - The implementation returns a zero-argument lambda.
  - Either restore the explicit corpus-version argument or change the
    annotation/example to match the actual API.
  - File:
    - `tests/conftest.py`

- [ ] Reconcile corpus versioning with the previously selected evaluation
  contract.
  - Current corpus helpers use one fixed `fixtures/corpus` directory.
  - If the explicit integer corpus-version contract is still desired, centralize
    path resolution in the corpus package rather than duplicating it in tests or
    scripts.
  - Files:
    - `src/ai_tour_guide/knowledge_base/corpus/format.py`
    - `src/ai_tour_guide/knowledge_base/corpus/context.py`
    - `src/ai_tour_guide/knowledge_base/corpus/export.py`
    - `src/ai_tour_guide/knowledge_base/corpus/restore.py`

## P3 — Cleanup

- [ ] Remove the duplicate `contexts` key from `RAGResult.to_dict()`.
  - The dictionary literal currently defines `contexts` twice.
  - The first value (`self.contexts`) is silently overwritten by the serialized
    contexts value.
  - Keep only the serialized version.
  - File:
    - `src/ai_tour_guide/agent/rag/models.py`

- [ ] Remove stale `build_context_from_chunks` from `prompting.__all__`.
  - The function no longer exists.
  - `from ai_tour_guide.agent.rag.prompting import *` would attempt to export a
    missing name.
  - File:
    - `src/ai_tour_guide/agent/rag/prompting.py`

- [ ] Remove stale/unused imports left by the migration.
  - `agent/rag/prompting.py` still imports `format_page_range` and
    `SearchResult`, although the current formatter no longer uses them.
  - `agent/rag/pipeline.py` still imports `LLM_CONFIGURATION_REQUIRED_ANSWER`
    although the current function does not use it.
  - `agent/rag/models.py` still imports `DocumentChunkRow` without using it.
  - Files:
    - `src/ai_tour_guide/agent/rag/prompting.py`
    - `src/ai_tour_guide/agent/rag/pipeline.py`
    - `src/ai_tour_guide/agent/rag/models.py`

- [ ] Validate `SearchMode` before creating a database engine in public
  `search()`.
  - `search_with_session()` performs `SearchMode(mode)` validation, but public
    `search()` creates the engine first.
  - Converting the mode before engine creation keeps invalid arguments as pure
    input errors and avoids unnecessary DB configuration work.
  - File:
    - `src/ai_tour_guide/knowledge_base/search/service.py`

## Verified fixed in the latest branch

- [x] `answer_question()` now constructs `RAGResult` using `contexts` rather
  than the removed `retrieved_contexts` field.
- [x] Retrieval/generation error paths no longer pass the removed
  `RAGResult.answer` constructor argument.
- [x] `SearchMode` is imported from the search package in the RAG pipeline.
- [x] Docker `init-db` now points to
  `ai_tour_guide.knowledge_base.database.init`.
- [x] Ingestion now imports `insert_document_with_chunks` from
  `knowledge_base.database`.
- [x] `SourceDocumentMetadata.url` is propagated by the provenance builder and
  the RAG serializer.
- [x] LLM prompt formatting now includes title, URL, version, and pages rather
  than retrieval score/debug metadata.

## Suggested implementation order

1. Fix `RetrievedContext.section_path` / prompt rendering.
2. Fix citation validation.
3. Fix API adaptation.
4. Switch retrieval evaluation to `search()`.
5. Switch CLI `search` to `search()`.
6. Regenerate the corpus.
7. Port the old agent tests.
8. Implement the new knowledge-base skeleton tests.
9. Apply P3 cleanup.
10. Run the full unit + integration + evaluation suite before removing any
    remaining compatibility code.
