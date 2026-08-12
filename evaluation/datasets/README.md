# Golden datasets

Each version lives in `evaluation/datasets/vN/golden_dataset.jsonl` and contains
questions plus expected outcomes for evaluation against a selected corpus.

`golden_dataset.example.jsonl` is only a schema skeleton. Copy it to the desired
version directory as `golden_dataset.jsonl` and replace every TODO with real
values derived from the corpus. Do not use invented chunk identifiers.
