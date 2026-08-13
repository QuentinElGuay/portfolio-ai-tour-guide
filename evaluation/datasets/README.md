# Golden datasets

The dataset lives in `evaluation/datasets/golden_dataset.jsonl` and contains questions
plus expected outcomes for evaluation against the current corpus. The example schema is
in `golden_dataset.example.jsonl`. Evidence uses the stable RAG identity
`(source_url, version)` plus individual source pages, never chunk IDs.

```json
{
  "id": 1,
  "category": "Climate and seasonal weather",
  "question": "What are typical summer temperatures in Brittany?",
  "expected": {
    "answerable": true,
    "reference_answer": "...",
    "relevant_sources": [
      {
        "source_url": "https://example.com/brittany-guide.pdf",
        "version": null,
        "pages": [8],
        "section_paths": [
          ["Climate and seasonal weather"]
        ]
      }
    ]
  }
}
```

Use `answerable: false`, `reference_answer: null`, and `relevant_sources: []` for an
intentional insufficient-context case. Do not include expected provider, database, or
parsing errors here; those are operational-failure tests, not corpus-ground-truth data.

`pages` and `section_paths` identify expected provenance. Section paths are more
specific than pages when available, but neither one alone proves that a chunk contains
the answer. Retrieval evaluation should treat an exact section-and-page match as the
strongest signal, a section-only match as weaker, and a page-only match as the weakest.
