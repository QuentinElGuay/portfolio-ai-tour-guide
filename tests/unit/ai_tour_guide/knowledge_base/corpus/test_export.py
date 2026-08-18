"""Skeleton tests for corpus export."""


def test_export_corpus_writes_all_logical_files() -> None:
    """Call ``export_corpus(root=tmp_path, engine=engine)``.

    Required fixtures/mocks: ``tmp_path``, mocked engine.raw_connection/cursor/copy streams containing bytes.
    Expected verification: all CORPUS_FILES are created and exports include embeddings plus section_id and
    section_chunk_index while omitting PostgreSQL-generated search_vector.
    """


def test_export_corpus_disposes_only_owned_engine() -> None:
    """Call ``export_corpus`` once with injected engine and once with patched internally-created engine.

    Required mocks: database engine factory and raw connection/copy behavior.
    Expected verification: only the internally-created engine is disposed.
    """
