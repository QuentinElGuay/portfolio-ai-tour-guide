# Corpus fixtures

Each corpus version is a logical export of the knowledge-base tables:

```text
fixtures/corpus/
└── v{N}/
    ├── embedding_models.jsonl
    ├── documents.jsonl
    └── document_chunks.jsonl
```

Create these files with `scripts/export_corpus.py`. They are intentionally not
populated with example rows because their identifiers, vectors, and metadata must
come from a real database export.
