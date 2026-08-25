# "Baguette Voyages" tutorial

This tutorial walks through ingestion, the Baguette Voyages chat app, evaluation, and
monitoring. See the [project README](../README.md) for prerequisites and environment
configuration.

## Ingestion with Airflow

Start the Airflow environment:

```bash
make airflow
```

The command starts Airflow, the ingestion image, and the required databases. It returns
only after the Airflow API, metadata database, scheduler, and DAG processor are ready.
It does not ingest documents by itself.

Open the Airflow interface at [http://localhost:8080](http://localhost:8080) and sign in
with `AIRFLOW_ADMIN_USERNAME` and `AIRFLOW_ADMIN_PASSWORD` from `.env`. The values below
are development defaults from `.env.template`; change them before sharing an Airflow
instance:

```
Username: admin
Password: pa$$word123
```

![Airflow sign in screen](tutorial/00_airflow_sign_in.png "Airflow sign in screen")

Open the **DAGs** tab and click **Trigger** for the `ingest_documents` DAG.

![DAGs screen](tutorial/01_airflow_dags.png "Click on 'Trigger the DAG'")

Copy the JSON array from `source_files.json` into the **Source files** field, then click
**Trigger**. The DAG first initializes the application database, then runs one ingestion
task per source file.

By default, an already ingested document is skipped successfully. Select **Force
re-ingestion** only when you intend to replace a document: it deletes the existing
document and its related chunks before inserting the replacement.

![Trigger DAG screen](tutorial/02_airflow_trigger_dag.png "Set the DAG parameters")

Wait for the DAG run to finish. Ingestion duration depends on the number and size of the
documents, and the first run may need to download the embedding model.

![All the tasks are marked as success](tutorial/03_airflow_dag_run.png "Successful DAG")

## Ingestion with the command line

Use the command line when you do not need Airflow's task orchestration or web interface.
The Docker Compose shortcut initializes the application schema, then ingests every
document definition in `source_files.json`:

```bash
make init-db
make ingest
```

To use another JSON definition file or retain intermediate parsing artifacts, run:

```bash
make ingest SOURCE_FILES=data/another-source.json
make ingest DEBUG=1
```

Like Airflow, `make ingest` skips a document when the same `(source_url, version)` is
already present. To intentionally replace a document and its related chunks, run:

```bash
make ingest FORCE=1
```

For a local Python workflow, install the project with `uv sync`, start and initialize
the database with `make init-db`, then run the ingestion CLI directly:

```bash
uv run portfolio-ai-tour-guide-ingestion run source_files.json
```

The direct CLI also supports `--skip-existing` and `--force`; these options are mutually
exclusive. See the [ingestion guide](../src/ai_tour_guide/ingestion/README.md) for the
full command reference and document-definition format.

## Chat app

Once at least one document has been ingested, start the Baguette Voyages chat app:

```bash
make app
```

The command starts the agent API and the Gradio chat interface. Open
[http://localhost:7860](http://localhost:7860) in your browser. The API is available at
[http://localhost:8000](http://localhost:8000), with interactive documentation at
[http://localhost:8000/docs](http://localhost:8000/docs).

The chat can answer which destinations are covered from the titles of the indexed
guides. For detailed questions, ask about a destination covered by the guides—for
example:

```text
Which destinations do you cover?
What are the main places to visit in Normandy?
What should I see in Occitanie?
```

The first question uses the indexed destination catalog. The detailed questions use
retrieved passages and display their source titles and page numbers below the answer.
Use the Like and Dislike controls to record feedback about an answer.

![Chat app welcome screen](tutorial/04_chat_app_welcome.png "Baguette Voyages chat")

![Chat app answer with sources](tutorial/05_chat_app_answers.png "Answer with sources")

## Evaluation

The evaluation workflow measures retrieval quality and answer quality against the
repository's golden dataset. It loads the evaluation corpus into a separate `evaluation`
schema, so it does not replace the public application corpus.

Run the retrieval evaluation first:

```bash
make evaluate-search
```

To evaluate the RAG pipeline without making additional judge-model calls, run:

```bash
make evaluate-rag
```

To generate answer-correctness scores with the configured LLM judge, run:

```bash
make evaluate-judge
```

The judge requires an OpenAI API key. Set `EVALUATION_OPENAI_JUDGE_API_KEY` and
`EVALUATION_OPENAI_JUDGE_MODEL` in `.env`; when they are absent, the workflow reuses the
agent's `AGENT_LLM_API_KEY` and `AGENT_LLM_MODEL`. To run the complete evaluation suite,
use `make evaluate`.

Evaluation is intended for comparing the current pipeline and configuration, not for
populating the production knowledge base. The latest reports and baseline results are
described in the [project README](../README.md#evaluation).

## Monitoring

The project includes a Metabase dashboard for inspecting persisted RAG requests, answer
feedback, quality metrics, and model usage costs.

Start PostgreSQL and Metabase:

```bash
make dashboard
```

Create the initial Metabase administrator and register the application database:

```bash
make dashboard-init
```

Open [http://localhost:3000](http://localhost:3000) and sign in with
`METABASE_ADMIN_EMAIL` and `METABASE_ADMIN_PASSWORD` from `.env`. To create example
operational traffic for the dashboards, run:

```bash
make simulate-rag
```

The simulated traffic is clearly marked as synthetic and is useful for exploring the
dashboard before real chat requests and feedback have accumulated. To preserve the
current dashboard configuration, run `make dashboard-export`; to restore the bundled
configuration into an empty dashboard database, run `make dashboard-restore`.
