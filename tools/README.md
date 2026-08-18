# Developer tools

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
