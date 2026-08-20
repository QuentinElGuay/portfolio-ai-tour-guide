.DEFAULT_GOAL := help

COMPOSE ?= docker compose
SCHEMA ?= public
SOURCE_FILES ?= source_files.json
EXPORT_DIR ?= tmp
CSV_LIMIT ?= 1000
DEBUG ?= 0
VERBOSE ?= 0
QUESTION ?=
K ?= 5
JUDGE_PROVIDER ?= openai
ANNOTATOR_ARGS ?=
CORPUS_ROOT ?= fixtures/corpus
EVALUATION ?= all
DEBUG_FLAG = $(if $(filter 1 true yes,$(DEBUG)),--debug,)
ASK_VERBOSE_FLAG = $(if $(filter 1 true yes,$(VERBOSE)),--verbose,)

DB_SCHEMA = $(SCHEMA)
export DB_SCHEMA

.PHONY: help init-db reset-db reset-schema init-dashboard ingest export-csv export-corpus load-corpus evaluate evaluate-search evaluate-rag evaluate-judge evaluate-all smoke-test validate-db-schema vector_search text_search ask cli-chat annotate-dataset app

help: ## Show the available commands.
	@echo "Available commands:"
	@echo "  make init-db                         Initialize the PostgreSQL schema"
	@echo "  make reset-db                        Delete and recreate the database"
	@echo "  make init-db SCHEMA=evaluation       Initialize another PostgreSQL schema"
	@echo "  make reset-schema SCHEMA=evaluation  Delete and recreate one schema"
	@echo "  make init-dashboard                  Start and initialize Metabase"
	@echo "  make ingest                          Ingest source_files.json"
	@echo "  make ingest DEBUG=1                  Ingest and retain debug artifacts"
	@echo "  make ingest SOURCE_FILES=path.json   Ingest another JSON input file"
	@echo "  make export-csv                      Export ingestion tables to CSV"
	@echo "  make export-csv EXPORT_DIR=path      Export CSV files to another directory"
	@echo "  make export-csv CSV_LIMIT=100        Limit each export to 100 data rows"
	@echo "  make export-corpus                   Overwrite the current corpus export"
	@echo "  make load-corpus                     Replace the public database corpus"
	@echo "  make load-corpus SCHEMA=evaluation   Replace the evaluation corpus"
	@echo "  make evaluate                        Run search, RAG, and judge evaluation"
	@echo "  make evaluate-search                 Run offline search metrics only"
	@echo "  make evaluate-rag                    Run online RAG metrics without judging"
	@echo "  make evaluate-judge                  Generate and judge RAG answers only"
	@echo "  make evaluate K=10                   Evaluate the first 10 ranked chunks"
	@echo "  make smoke-test                      Run deterministic end-to-end RAG smoke tests"
	@echo "  make vector_search QUESTION='...'    Run semantic search (K defaults to 5)"
	@echo "  make text_search QUESTION='...'      Run full-text search (K defaults to 5)"
	@echo "  make ask QUESTION='...'              Answer with retrieved context (K defaults to 5)"
	@echo "  make ask QUESTION='...' VERBOSE=1    Print the complete serialized RAG trace"
	@echo "  make cli-chat                        Start the interactive terminal chat"
	@echo "  make annotate-dataset                Fill answers and source pages interactively"
	@echo "  make annotate-dataset ANNOTATOR_ARGS='--resume'"
	@echo "  make app                             Start the agent API and Gradio chat"

init-db: validate-db-schema ## Start PostgreSQL and initialize its schema.
	$(COMPOSE) --profile tools run --rm init-db \
		python -m ai_tour_guide.knowledge_base.database.init \
		--schema "$(SCHEMA)"

reset-db: validate-db-schema ## Delete the PostgreSQL volume and initialize a fresh database.
	@echo "Deleting the PostgreSQL volume and all stored application data..."
	$(COMPOSE) --profile dashboard down --volumes --remove-orphans
	$(COMPOSE) --profile tools run --rm init-db \
		python -m ai_tour_guide.knowledge_base.database.init \
		--schema "$(SCHEMA)"

reset-schema: validate-db-schema ## Delete and recreate only the selected schema.
	@test "$(origin SCHEMA)" = "command line" || \
		(echo "SCHEMA must be provided explicitly, for example: make reset-schema SCHEMA=evaluation" >&2; exit 1)
	$(COMPOSE) up -d --wait database
	$(COMPOSE) exec -T database sh -c \
		'psql --username "$$POSTGRES_USER" \
		--dbname "$$POSTGRES_DB" \
		--command "DROP SCHEMA $(SCHEMA) CASCADE"'
	$(MAKE) init-db SCHEMA="$(SCHEMA)"

init-dashboard: ## Start Metabase and initialize its first admin user.
	$(COMPOSE) --profile dashboard run --rm dashboard-init

ingest: ## Ingest the documents described by SOURCE_FILES.
	@test -f "$(SOURCE_FILES)" || (echo "Input file not found: $(SOURCE_FILES)" >&2; exit 1)
	@if [ -n "$(DEBUG_FLAG)" ]; then mkdir -p tmp && chmod 0777 tmp; fi
	$(COMPOSE) --profile ingestion run --rm -T ingestion \
		python -m ai_tour_guide.ingestion.cli run $(DEBUG_FLAG) - < "$(SOURCE_FILES)"

validate-db-schema:
	@case "$(SCHEMA)" in *[!a-z0-9_]*|[0-9]*|'') echo "SCHEMA must be a lowercase PostgreSQL identifier" >&2; exit 1;; esac

export-csv: validate-db-schema ## Export ingestion tables as deterministic CSV files.
	@case "$(CSV_LIMIT)" in *[!0-9]*|'') echo "CSV_LIMIT must be a positive integer" >&2; exit 1;; esac
	@test "$(CSV_LIMIT)" -gt 0 || (echo "CSV_LIMIT must be greater than zero" >&2; exit 1)
	@mkdir -p "$(EXPORT_DIR)"
	@$(COMPOSE) exec -T database sh -c \
		'psql --no-psqlrc --quiet --set=ON_ERROR_STOP=1 --username "$$POSTGRES_USER" --dbname "$$POSTGRES_DB" --command "\copy (SELECT * FROM $(SCHEMA).embedding_models ORDER BY embedding_model_id LIMIT $(CSV_LIMIT)) TO STDOUT WITH (FORMAT CSV, HEADER true)"' \
		> "$(EXPORT_DIR)/embedding_models.csv.tmp"
	@mv "$(EXPORT_DIR)/embedding_models.csv.tmp" "$(EXPORT_DIR)/embedding_models.csv"
	@$(COMPOSE) exec -T database sh -c \
		'psql --no-psqlrc --quiet --set=ON_ERROR_STOP=1 --username "$$POSTGRES_USER" --dbname "$$POSTGRES_DB" --command "\copy (SELECT * FROM $(SCHEMA).documents ORDER BY document_id LIMIT $(CSV_LIMIT)) TO STDOUT WITH (FORMAT CSV, HEADER true)"' \
		> "$(EXPORT_DIR)/documents.csv.tmp"
	@mv "$(EXPORT_DIR)/documents.csv.tmp" "$(EXPORT_DIR)/documents.csv"
	@$(COMPOSE) exec -T database sh -c \
		'psql --no-psqlrc --quiet --set=ON_ERROR_STOP=1 --username "$$POSTGRES_USER" --dbname "$$POSTGRES_DB" --command "\copy (SELECT * FROM $(SCHEMA).document_chunks ORDER BY document_id, chunk_index LIMIT $(CSV_LIMIT)) TO STDOUT WITH (FORMAT CSV, HEADER true)"' \
		> "$(EXPORT_DIR)/document_chunks.csv.tmp"
	@mv "$(EXPORT_DIR)/document_chunks.csv.tmp" "$(EXPORT_DIR)/document_chunks.csv"
	@echo "Exported up to $(CSV_LIMIT) data rows per table to $(EXPORT_DIR)/"

export-corpus: ## Overwrite the current knowledge-base corpus export.
	uv run python scripts/export_corpus.py --root "$(CORPUS_ROOT)"

load-corpus: ## Replace the knowledge-base corpus in the selected SCHEMA.
	@test -f "$(CORPUS_ROOT)/embedding_models.jsonl" \
		&& test -f "$(CORPUS_ROOT)/documents.jsonl" \
		&& test -f "$(CORPUS_ROOT)/document_chunks.jsonl" \
		|| (echo "Corpus files are missing from $(CORPUS_ROOT). Run 'make export-corpus' first." >&2; exit 1)
	uv run python scripts/setup_corpus.py --root "$(CORPUS_ROOT)" --schema "$(SCHEMA)" --allow-destructive

evaluate: ## Run all evaluation metrics.
	@case "$(EVALUATION)" in search|retrieval|rag|judge|all) ;; *) echo "EVALUATION must be search, rag, judge, or all" >&2; exit 1;; esac
	$(COMPOSE) up -d --wait database
	$(MAKE) load-corpus CORPUS_ROOT="$(CORPUS_ROOT)" SCHEMA=evaluation
	@if [ "$(EVALUATION)" = search ] || [ "$(EVALUATION)" = retrieval ] || [ "$(EVALUATION)" = all ]; then \
		uv run python -m evaluation.search.run --corpus "$(CORPUS_ROOT)" --dataset evaluation/datasets --k "$(K)"; \
	fi
	@if [ "$(EVALUATION)" = rag ]; then \
		uv run python -m evaluation.rag.run rag --corpus "$(CORPUS_ROOT)" --dataset evaluation/datasets --k "$(K)"; \
	fi
	@if [ "$(EVALUATION)" = judge ] || [ "$(EVALUATION)" = all ]; then \
		uv run python -m evaluation.rag.run judge --provider "$(JUDGE_PROVIDER)" --corpus "$(CORPUS_ROOT)" --dataset evaluation/datasets --k "$(K)"; \
	fi

evaluate-search: EVALUATION=search
evaluate-search: evaluate

evaluate-rag: EVALUATION=rag
evaluate-rag: evaluate

evaluate-judge: EVALUATION=judge
evaluate-judge: evaluate

evaluate-all: evaluate

smoke-test: ## Run deterministic RAG smoke tests against the isolated smoke schema.
	$(COMPOSE) up -d --wait database
	uv run python -m ai_tour_guide.knowledge_base.database.init --schema smoke
	AGENT_LLM_PROVIDER=fixture \
	AGENT_LLM_API_KEY= \
	DB_SCHEMA=smoke \
	uv run pytest tests/smoke

vector_search: ## Search chunks semantically using QUESTION and optional K.
	@test -n "$(QUESTION)" || (echo "QUESTION is required; for example: make vector_search QUESTION='Where is the Brittany coast?'" >&2; exit 1)
	$(COMPOSE) --profile agent run --rm -T agent \
		portfolio-ai-tour-guide-agent search --mode vector --k "$(K)" "$(QUESTION)"

text_search: ## Search chunks lexically using QUESTION and optional K.
	@test -n "$(QUESTION)" || (echo "QUESTION is required; for example: make text_search QUESTION='Brittany coast'" >&2; exit 1)
	$(COMPOSE) --profile agent run --rm -T agent \
		portfolio-ai-tour-guide-agent search --mode text --k "$(K)" "$(QUESTION)"

ask: ## Answer a QUESTION using retrieved context and optional K.
	@test -n "$(QUESTION)" || (echo "QUESTION is required; for example: make ask QUESTION='Where is the Brittany coast?'" >&2; exit 1)
	$(COMPOSE) --profile agent run --rm -T agent \
		portfolio-ai-tour-guide-agent ask $(ASK_VERBOSE_FLAG) --k "$(K)" "$(QUESTION)"

cli-chat: ## Start the interactive terminal chat after the agent is ready.
	$(COMPOSE) --profile agent up -d --wait agent
	$(COMPOSE) --profile agent run --rm -T agent \
		portfolio-ai-tour-guide-agent chat --k "$(K)"

annotate-dataset: ## Interactively annotate golden-dataset answers and source pages.
	uv run python tools/golden_dataset_annotator.py $(ANNOTATOR_ARGS)

app: ## Start the agent API and Gradio chat interface.
	$(COMPOSE) --profile app up --build
