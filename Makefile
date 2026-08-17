.DEFAULT_GOAL := help

COMPOSE ?= docker compose
DB_SCHEMA ?= public
SOURCE_FILES ?= source_files.json
EXPORT_DIR ?= tmp
CSV_LIMIT ?= 1000
DEBUG ?= 0
VERBOSE ?= 0
QUESTION ?=
K ?= 5
ANNOTATOR_ARGS ?=
CORPUS_ROOT ?= fixtures/corpus
EVALUATION ?= both
JUDGE ?= 0
DEBUG_FLAG = $(if $(filter 1 true yes,$(DEBUG)),--debug,)
ASK_VERBOSE_FLAG = $(if $(filter 1 true yes,$(VERBOSE)),--verbose,)

export DB_SCHEMA

.PHONY: help init-db reset-db ingest export-csv export-corpus load-corpus evaluate evaluate-search evaluate-rag evaluate-all validate-db-schema vector_search text_search ask annotate-dataset app

help: ## Show the available commands.
	@echo "Available commands:"
	@echo "  make init-db                         Initialize the PostgreSQL schema"
	@echo "  make reset-db                        Delete and recreate the database"
	@echo "  make init-db DB_SCHEMA=evaluation    Initialize another PostgreSQL schema"
	@echo "  make ingest                          Ingest source_files.json"
	@echo "  make ingest DEBUG=1                  Ingest and retain debug artifacts"
	@echo "  make ingest SOURCE_FILES=path.json   Ingest another JSON input file"
	@echo "  make export-csv                      Export ingestion tables to CSV"
	@echo "  make export-csv EXPORT_DIR=path      Export CSV files to another directory"
	@echo "  make export-csv CSV_LIMIT=100        Limit each export to 100 data rows"
	@echo "  make export-corpus                   Overwrite the current corpus export"
	@echo "  make load-corpus                     Replace the public database corpus"
	@echo "  make load-corpus DB_SCHEMA=evaluation Replace the evaluation corpus"
	@echo "  make evaluate                        Run search and RAG checks"
	@echo "  make evaluate-search                 Run search metrics only"
	@echo "  make evaluate-rag                    Run RAG citation and latency metrics"
	@echo "  make evaluate JUDGE=1                Also run the optional, costlier LLM judge"
	@echo "  make evaluate-all                    Alias for make evaluate JUDGE=1"
	@echo "  make evaluate K=10                   Evaluate the first 10 ranked chunks"
	@echo "  make vector_search QUESTION='...'    Run semantic search (K defaults to 5)"
	@echo "  make text_search QUESTION='...'      Run full-text search (K defaults to 5)"
	@echo "  make ask QUESTION='...'              Answer with retrieved context (K defaults to 5)"
	@echo "  make ask QUESTION='...' VERBOSE=1    Print the complete serialized RAG trace"
	@echo "  make annotate-dataset                Fill answers and source pages interactively"
	@echo "  make annotate-dataset ANNOTATOR_ARGS='--resume'"
	@echo "  make app                             Start the agent API and Gradio chat"

init-db: ## Start PostgreSQL and initialize its schema.
	$(COMPOSE) --profile tools run --rm init-db

reset-db: ## Delete the PostgreSQL volume and initialize a fresh database.
	@echo "Deleting the PostgreSQL volume and all stored application data..."
	$(COMPOSE) down --volumes
	$(COMPOSE) --profile tools run --rm init-db

ingest: ## Ingest the documents described by SOURCE_FILES.
	@test -f "$(SOURCE_FILES)" || (echo "Input file not found: $(SOURCE_FILES)" >&2; exit 1)
	@if [ -n "$(DEBUG_FLAG)" ]; then mkdir -p tmp && chmod 0777 tmp; fi
	$(COMPOSE) --profile ingestion run --rm -T ingestion \
		python -m ai_tour_guide.ingestion.cli run $(DEBUG_FLAG) - < "$(SOURCE_FILES)"

validate-db-schema:
	@case "$(DB_SCHEMA)" in *[!a-z0-9_]*|[0-9]*|'') echo "DB_SCHEMA must be a lowercase PostgreSQL identifier" >&2; exit 1;; esac

export-csv: validate-db-schema ## Export ingestion tables as deterministic CSV files.
	@case "$(CSV_LIMIT)" in *[!0-9]*|'') echo "CSV_LIMIT must be a positive integer" >&2; exit 1;; esac
	@test "$(CSV_LIMIT)" -gt 0 || (echo "CSV_LIMIT must be greater than zero" >&2; exit 1)
	@mkdir -p "$(EXPORT_DIR)"
	@$(COMPOSE) exec -T database sh -c \
		'psql --no-psqlrc --quiet --set=ON_ERROR_STOP=1 --username "$$POSTGRES_USER" --dbname "$$POSTGRES_DB" --command "\copy (SELECT * FROM $(DB_SCHEMA).embedding_models ORDER BY embedding_model_id LIMIT $(CSV_LIMIT)) TO STDOUT WITH (FORMAT CSV, HEADER true)"' \
		> "$(EXPORT_DIR)/embedding_models.csv.tmp"
	@mv "$(EXPORT_DIR)/embedding_models.csv.tmp" "$(EXPORT_DIR)/embedding_models.csv"
	@$(COMPOSE) exec -T database sh -c \
		'psql --no-psqlrc --quiet --set=ON_ERROR_STOP=1 --username "$$POSTGRES_USER" --dbname "$$POSTGRES_DB" --command "\copy (SELECT * FROM $(DB_SCHEMA).documents ORDER BY document_id LIMIT $(CSV_LIMIT)) TO STDOUT WITH (FORMAT CSV, HEADER true)"' \
		> "$(EXPORT_DIR)/documents.csv.tmp"
	@mv "$(EXPORT_DIR)/documents.csv.tmp" "$(EXPORT_DIR)/documents.csv"
	@$(COMPOSE) exec -T database sh -c \
		'psql --no-psqlrc --quiet --set=ON_ERROR_STOP=1 --username "$$POSTGRES_USER" --dbname "$$POSTGRES_DB" --command "\copy (SELECT * FROM $(DB_SCHEMA).document_chunks ORDER BY document_id, chunk_index LIMIT $(CSV_LIMIT)) TO STDOUT WITH (FORMAT CSV, HEADER true)"' \
		> "$(EXPORT_DIR)/document_chunks.csv.tmp"
	@mv "$(EXPORT_DIR)/document_chunks.csv.tmp" "$(EXPORT_DIR)/document_chunks.csv"
	@echo "Exported up to $(CSV_LIMIT) data rows per table to $(EXPORT_DIR)/"

export-corpus: ## Overwrite the current knowledge-base corpus export.
	uv run python scripts/export_corpus.py --root "$(CORPUS_ROOT)"

load-corpus: ## Replace the knowledge-base corpus in the selected DB_SCHEMA.
	@test -f "$(CORPUS_ROOT)/embedding_models.jsonl" \
		&& test -f "$(CORPUS_ROOT)/documents.jsonl" \
		&& test -f "$(CORPUS_ROOT)/document_chunks.jsonl" \
		|| (echo "Corpus files are missing from $(CORPUS_ROOT). Run 'make export-corpus' first." >&2; exit 1)
	uv run python scripts/setup_corpus.py --root "$(CORPUS_ROOT)" --schema "$(DB_SCHEMA)" --allow-destructive

evaluate: ## Run search and RAG checks, optionally including the LLM judge.
	@case "$(JUDGE)" in 0|1) ;; *) echo "JUDGE must be 0 or 1" >&2; exit 1;; esac
	@case "$(EVALUATION)" in search|retrieval|rag|both) ;; *) echo "EVALUATION must be search, rag, or both" >&2; exit 1;; esac
	$(COMPOSE) up -d --wait database
	$(MAKE) load-corpus CORPUS_ROOT="$(CORPUS_ROOT)" DB_SCHEMA=evaluation
	@if [ "$(EVALUATION)" = search ] || [ "$(EVALUATION)" = retrieval ] || [ "$(EVALUATION)" = both ]; then \
		uv run python -m evaluation.search.run --corpus "$(CORPUS_ROOT)" --dataset evaluation/datasets --k "$(K)"; \
	fi
	@if [ "$(EVALUATION)" = rag ] || [ "$(EVALUATION)" = both ]; then \
		uv run python -m evaluation.rag.run --corpus "$(CORPUS_ROOT)" --dataset evaluation/datasets --k "$(K)"; \
	fi
	@if [ "$(JUDGE)" = 1 ]; then \
		echo "RAG answer judging is not implemented yet. Use 'make evaluate' for citation and latency metrics." >&2; \
		exit 2; \
	fi

evaluate-search: EVALUATION=search
evaluate-search: evaluate

evaluate-rag: EVALUATION=rag
evaluate-rag: evaluate

evaluate-all: JUDGE=1
evaluate-all: evaluate

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

annotate-dataset: ## Interactively annotate golden-dataset answers and source pages.
	uv run python tools/golden_dataset_annotator.py $(ANNOTATOR_ARGS)

app: ## Start the agent API and Gradio chat interface.
	$(COMPOSE) --profile app up --build
