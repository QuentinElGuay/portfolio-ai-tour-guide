# Developer tools

## Simulate RAG traffic

Populate the public operational dashboards with deterministic traffic generated from the
golden dataset. This command always uses the local fixture LLM: it never calls OpenAI or
any other paid provider, and it never incurs an API bill. The `--model` option only
names the model used to calculate synthetic costs. By default, the tool also writes
explicitly marked synthetic token and cost events:

```bash
make simulate-rag
```

Customize the time range and volume with:

```bash
make simulate-rag SIMULATE_ARGS='--days 30 --requests-per-day 50 --error-rate 0.08'
```

Use `--variance 0` for constant daily volume or increase it up to `1` for more
variation. The default is `0.35`.

To replace a previous simulation instead of appending to it, add `--clear-simulated`.

`--no-simulated-usage` is optional. Use it only for a Quality-dashboard demo or a test
that needs RAG results and feedback without populating the Costs dashboard. The default
is recommended when demonstrating both dashboards. The generated rows are intended for
local dashboard demonstrations and should not be used as production telemetry.

## Annotate the golden dataset

Edit the golden dataset in place:

```bash
make annotate-dataset
```

The default input is `evaluation/datasets/golden_dataset.jsonl`. The tool saves the
dataset after every edit and when you choose **Save and quit**.

Choose **Edit answer and pages** to replace the reference answer and the page number(s)
for the first listed source. By default it starts at ID 1 and moves sequentially after
every edit. Choose **Next question** to move sequentially without editing, **Next
unanswered question** to skip ahead, **Jump to question ID** to navigate directly to a
case, or **Save and quit** to stop early. To resume at the first row with
`"_todo": true` and automatically skip answered rows, run:

```bash
make annotate-dataset ANNOTATOR_ARGS='--resume'
```

Use `ANNOTATOR_ARGS='--start-id 42'` to begin at a specific question or
`ANNOTATOR_ARGS='--input path'` to edit a different dataset. You can also invoke
`uv run python tools/golden_dataset_annotator.py` directly.
