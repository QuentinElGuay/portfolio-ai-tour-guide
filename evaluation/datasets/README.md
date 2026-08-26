# Golden datasets

The dataset lives in `evaluation/datasets/golden_dataset.jsonl` and contains questions
plus expected outcomes for evaluation against the current corpus. The example schema is
in `golden_dataset.example.jsonl`. Evidence uses the stable RAG identity
`(source_url, version)` plus one slugified section path, never chunk IDs or pages.

```json
{
  "id": 1,
  "category": "Climate and seasonal weather",
  "question": "What are typical summer temperatures in Normandy?",
  "expected": {
    "answerable": true,
    "reference_answer": "...",
    "relevant_source": {
      "source_url": "https://example.com/normandy-guide.pdf",
      "version": null,
      "section_path": [
        "guide-to-the-region-of-normandy",
        "geography-and-climate",
        "climate"
      ]
    }
  }
}
```

Use `answerable: false` and `reference_answer: null` without a `relevant_source` for an
intentional insufficient-context case. Do not include expected provider, database, or
parsing errors here; those are operational-failure tests, not corpus-ground-truth data.

`section_path` identifies expected provenance. It is slugified and contains the document
section path with its final heading removed. A result matches when its reduced,
slugified section path is equal to the expected path.

When `make evaluate-judge` is used, `reference_answer` is supplied to the optional LLM
judge to assess the generated answer semantically. It is not used by search or the
deterministic citation and latency metrics.
