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
SIMULATE_ARGS ?=
CHAT_GRAPH ?= docs/diagrams/chat-graph.mmd
CORPUS_ROOT ?= fixtures/corpus
EVALUATION ?= all
DASHBOARD_BACKUP ?= fixtures/metabase/metabase.sql
METABASE_DB_NAME ?= metabase
FORCE ?= 0
DOCKER_SOCKET ?= /var/run/docker.sock
DOCKER_GID ?= $(shell stat -c '%g' "$(DOCKER_SOCKET)" 2>/dev/null || stat -f '%g' "$(DOCKER_SOCKET)" 2>/dev/null)
DEBUG_FLAG = $(if $(filter 1 true yes,$(DEBUG)),--debug,)
INGEST_EXISTING_FLAG = $(if $(filter 1 true yes,$(FORCE)),--force,--skip-existing)
COMPOSE_DEBUG_FLAG = $(if $(filter 1 true yes,$(DEBUG)),--verbose,)
ASK_VERBOSE_FLAG = $(if $(filter 1 true yes,$(VERBOSE)),--verbose,)
DATABASE_UP = $(COMPOSE) $(COMPOSE_DEBUG_FLAG) up -d --wait database

DB_SCHEMA = $(SCHEMA)
export DB_SCHEMA

.PHONY: airflow annotate-dataset app ask chat-graph cli-chat dashboard dashboard-export dashboard-init dashboard-restore db-init db-reset db-reset-schema db-validate-schema evaluate evaluate-all evaluate-judge evaluate-rag evaluate-search export-corpus export-csv help ingest load-corpus purge simulate-rag smoke-test stop text_search validate-dashboard-backup vector_search

airflow: ## Start Airflow and its host-Docker ingestion orchestration.
	@case "$(DOCKER_GID)" in *[!0-9]*|'') echo "Could not determine the Docker socket group ID from $(DOCKER_SOCKET)." >&2; exit 1;; esac
	DOCKER_GID="$(DOCKER_GID)" $(COMPOSE) $(COMPOSE_DEBUG_FLAG) --profile airflow up --build -d --wait \
		database airflow-webserver airflow-scheduler airflow-dag-processor

annotate-dataset: ## Interactively annotate golden-dataset answers and source pages.
	uv run python tools/golden_dataset_annotator.py $(ANNOTATOR_ARGS)

app: db-init ## Initialize the database and start the app API and Gradio chat interface.
	@if ! $(COMPOSE) --profile app up --build -d --wait database app; then \
		echo "App startup failed. Recent app diagnostics:" >&2; \
		$(COMPOSE) --profile app logs --tail=20 app >&2 || true; \
		exit 1; \
	fi
	@if ! $(COMPOSE) --profile app up -d --wait --no-build chat; then \
		echo "Chat startup failed. Recent chat diagnostics:" >&2; \
		$(COMPOSE) --profile app logs --tail=20 chat >&2 || true; \
		exit 1; \
	fi
ask: ## Answer a QUESTION using retrieved context and optional K.
	@test -n "$(QUESTION)" || (echo "QUESTION is required; for example: make ask QUESTION='Where is the Brittany coast?'" >&2; exit 1)
	$(COMPOSE) --profile app run --rm -T app \
		portfolio-ai-tour-guide-agent ask $(ASK_VERBOSE_FLAG) --k "$(K)" "$(QUESTION)"

chat-graph: ## Export the chat workflow as Mermaid (CHAT_GRAPH=path/to/file.mmd).
	uv run python tools/export_chat_graph.py --output "$(CHAT_GRAPH)"

cli-chat: ## Start the interactive terminal chat after the app is ready.
	$(COMPOSE) --profile app up -d --wait app
	$(COMPOSE) --profile app run --rm -T app \
		portfolio-ai-tour-guide-agent chat --k "$(K)"

dashboard: dashboard-init ## Start and initialize PostgreSQL and the Metabase dashboard.
	$(COMPOSE) $(COMPOSE_DEBUG_FLAG) --profile dashboard up --build -d --wait database dashboard

dashboard-export: dashboard dashboard-init ## Export the dashboard application database into the repository.
	$(COMPOSE) $(COMPOSE_DEBUG_FLAG) --profile dashboard up -d --wait database dashboard
	@mkdir -p "$(dir $(DASHBOARD_BACKUP))"
	@$(COMPOSE) exec -T database \
		sh -c 'pg_dump --username "$${POSTGRES_USER}" \
		--clean --if-exists --no-owner --no-privileges \
		--dbname="$(METABASE_DB_NAME)"' \
		> "$(DASHBOARD_BACKUP).tmp"
	@mv "$(DASHBOARD_BACKUP).tmp" "$(DASHBOARD_BACKUP)"
	$(COMPOSE) --profile dashboard build metabase-database
	@echo "Exported dashboard configuration to $(DASHBOARD_BACKUP)"

dashboard-init: ## Start Metabase and initialize its first admin user.
	$(COMPOSE) --profile dashboard run --rm dashboard-init

dashboard-restore: validate-dashboard-backup ## Restore the bundled dashboard application database.
	$(COMPOSE) $(COMPOSE_DEBUG_FLAG) --profile dashboard up -d --wait database
	@if [ "$(FORCE)" = "1" ]; then \
		$(COMPOSE) --profile dashboard stop dashboard >/dev/null 2>&1 || true; \
		$(COMPOSE) exec -T database sh -c \
			'psql --username "$${POSTGRES_USER}" --dbname "$${POSTGRES_DB}" \
			--command "DROP DATABASE IF EXISTS \"$(METABASE_DB_NAME)\" WITH (FORCE)"'; \
	else \
		database_exists=$$($(COMPOSE) exec -T database sh -c \
			'psql --username "$${POSTGRES_USER}" --dbname "$${POSTGRES_DB}" -tAc \
			"SELECT 1 FROM pg_database WHERE datname = '\''$(METABASE_DB_NAME)'\''"' | tr -d '[:space:]'); \
		if [ "$$database_exists" = 1 ]; then \
			table_count=$$($(COMPOSE) exec -T database sh -c \
				'psql --username "$${POSTGRES_USER}" --dbname "$(METABASE_DB_NAME)" -tAc \
				"SELECT count(*) FROM pg_catalog.pg_tables WHERE schemaname = '\''public'\''"' | tr -d '[:space:]'); \
			test "$$table_count" -eq 0 || \
				(echo "Metabase database is not empty; use FORCE=1 to overwrite it." >&2; exit 1); \
		fi; \
	fi
	$(COMPOSE) --profile dashboard build metabase-database
	$(COMPOSE) --profile dashboard run --rm metabase-database

db-init: db-validate-schema ## Start PostgreSQL and initialize its schema.
	$(COMPOSE) --profile tools build ai-tour-guide-base init-db
	$(COMPOSE) --profile tools run --rm init-db \
		python -m ai_tour_guide.knowledge_base.database.init \
		--schema "$(SCHEMA)"

db-reset: db-validate-schema ## Reset the selected application schema without touching Metabase.
	@echo "Resetting application schema '$(SCHEMA)'; the Metabase database is preserved."
	$(MAKE) db-reset-schema SCHEMA="$(SCHEMA)"

db-reset-schema: db-validate-schema ## Delete and recreate only the selected schema.
	@test "$(origin SCHEMA)" = "command line" || \
		(echo "SCHEMA must be provided explicitly, for example: make db-reset-schema SCHEMA=evaluation" >&2; exit 1)
	$(DATABASE_UP)
	$(COMPOSE) exec -T database sh -c \
		'psql --username "$$POSTGRES_USER" \
		--dbname "$$POSTGRES_DB" \
		--command "DROP SCHEMA IF EXISTS $(SCHEMA) CASCADE"'
	$(MAKE) db-init SCHEMA="$(SCHEMA)"

db-validate-schema:
	@case "$(SCHEMA)" in *[!a-z0-9_]*|[0-9]*|'') echo "SCHEMA must be a lowercase PostgreSQL identifier" >&2; exit 1;; esac

evaluate: ## Run all evaluation metrics.
	@case "$(EVALUATION)" in search|retrieval|rag|judge|all) ;; *) echo "EVALUATION must be search, retrieval, rag, judge, or all" >&2; exit 1;; esac
	$(DATABASE_UP)
	$(MAKE) load-corpus CORPUS_ROOT="$(CORPUS_ROOT)" SCHEMA=evaluation
	@if [ "$(EVALUATION)" = search ] || [ "$(EVALUATION)" = retrieval ] || [ "$(EVALUATION)" = all ]; then \
		uv run python -m evaluation.search.run --corpus "$(CORPUS_ROOT)" --dataset evaluation/datasets --k "$(K)"; \
	fi
	@if [ "$(EVALUATION)" = rag ] || [ "$(EVALUATION)" = all ]; then \
		uv run python -m evaluation.rag.run rag --corpus "$(CORPUS_ROOT)" --dataset evaluation/datasets --k "$(K)"; \
	fi
	@if [ "$(EVALUATION)" = judge ] || [ "$(EVALUATION)" = all ]; then \
		uv run python -m evaluation.rag.run judge --provider "$(JUDGE_PROVIDER)" --corpus "$(CORPUS_ROOT)" --dataset evaluation/datasets --k "$(K)"; \
	fi

evaluate-all: evaluate

evaluate-judge: EVALUATION=judge
evaluate-judge: evaluate

evaluate-rag: EVALUATION=rag
evaluate-rag: evaluate

evaluate-search: EVALUATION=search
evaluate-search: evaluate

export-corpus: ## Overwrite the current knowledge-base corpus export.
	uv run python scripts/export_corpus.py --root "$(CORPUS_ROOT)"

export-csv: db-validate-schema ## Export ingestion tables as deterministic CSV files.
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

help: ## Show the available commands.
	@echo "Available commands:"
	@echo "  make airflow                         Start Airflow for parameterized ingestion"
	@echo "  make annotate-dataset                Fill answers and source pages interactively"
	@echo "  make annotate-dataset ANNOTATOR_ARGS='--resume'"
	@echo "  make app                             Start the app API and Gradio chat"
	@echo "  make ask QUESTION='...'              Answer with retrieved context (K defaults to 5)"
	@echo "  make ask QUESTION='...' VERBOSE=1    Print the complete serialized RAG trace"
	@echo "  make cli-chat                        Start the interactive terminal chat"
	@echo "  make dashboard                       Start and initialize PostgreSQL and Metabase"
	@echo "  make dashboard DEBUG=1               Start dashboard with Docker Compose diagnostics"
	@echo "  make dashboard-export                Export the dashboard application database"
	@echo "  make dashboard-init                  Initialize an already running Metabase instance"
	@echo "  make dashboard-restore               Restore the dashboard if its database is empty"
	@echo "  make dashboard-restore FORCE=1       Overwrite and restore the dashboard"
	@echo "  make db-init                         Initialize the PostgreSQL schema"
	@echo "  make db-init SCHEMA=evaluation       Initialize another PostgreSQL schema"
	@echo "  make db-reset                        Reset the selected application schema"
	@echo "  make db-reset-schema SCHEMA=evaluation Delete and recreate one schema"
	@echo "  make db-validate-schema              Validate the selected database schema"
	@echo "  make evaluate                        Run search, RAG, and judge evaluation"
	@echo "  make evaluate K=10                   Evaluate the first 10 ranked chunks"
	@echo "  make evaluate-all                    Run all evaluation metrics"
	@echo "  make evaluate-judge                  Generate and judge RAG answers only"
	@echo "  make evaluate-rag                    Run online RAG metrics without judging"
	@echo "  make evaluate-search                 Run offline search metrics only"
	@echo "  make export-corpus                   Overwrite the current corpus export"
	@echo "  make export-csv                      Export ingestion tables to CSV"
	@echo "  make export-csv CSV_LIMIT=100        Limit each export to 100 data rows"
	@echo "  make export-csv EXPORT_DIR=path      Export CSV files to another directory"
	@echo "  make help                            Show the available commands"
	@echo "  make ingest                          Ingest source_files.json"
	@echo "  make ingest DEBUG=1                  Ingest and retain debug artifacts"
	@echo "  make ingest FORCE=1                  Replace documents already ingested"
	@echo "  make ingest SOURCE_FILES=path.json   Ingest another JSON input file"
	@echo "  make load-corpus                     Replace the public database corpus"
	@echo "  make load-corpus SCHEMA=evaluation   Replace the evaluation corpus"
	@echo "  make purge                           Stop everything and remove volumes (destructive)"
	@echo "  make simulate-rag                    Populate dashboards with synthetic RAG traffic"
	@echo "  make simulate-rag SIMULATE_ARGS='--days 30 --requests-per-day 50'"
	@echo "  make smoke-test                      Run deterministic end-to-end RAG smoke tests"
	@echo "  make stop                            Stop every Compose profile and remove containers"
	@echo "  make text_search QUESTION='...'      Run full-text search (K defaults to 5)"
	@echo "  make validate-dashboard-backup       Validate the Metabase dashboard backup"
	@echo "  make vector_search QUESTION='...'    Run semantic search (K defaults to 5)"
	@echo "  DEBUG=1                              Enable verbose Docker Compose diagnostics"

ingest: ## Ingest the documents described by SOURCE_FILES.
	@test -f "$(SOURCE_FILES)" || (echo "Input file not found: $(SOURCE_FILES)" >&2; exit 1)
	@if [ -n "$(DEBUG_FLAG)" ]; then mkdir -p tmp && chmod 0777 tmp; fi
	$(COMPOSE) --profile ingestion run --rm -T ingestion \
		python -m ai_tour_guide.ingestion.cli run $(DEBUG_FLAG) $(INGEST_EXISTING_FLAG) - < "$(SOURCE_FILES)"

load-corpus: ## Replace the knowledge-base corpus in the selected SCHEMA.
	@test -f "$(CORPUS_ROOT)/embedding_models.jsonl" \
		&& test -f "$(CORPUS_ROOT)/documents.jsonl" \
		&& test -f "$(CORPUS_ROOT)/document_chunks.jsonl" \
		|| (echo "Corpus files are missing from $(CORPUS_ROOT). Run 'make export-corpus' first." >&2; exit 1)
	uv run python scripts/setup_corpus.py --root "$(CORPUS_ROOT)" --schema "$(SCHEMA)" --allow-destructive

purge: ## Stop everything and remove containers, networks, orphans, and volumes.
	$(COMPOSE) --profile "*" down --volumes --remove-orphans

simulate-rag: ## Populate operational dashboards with deterministic synthetic RAG traffic.
	$(DATABASE_UP)
	uv run python -m tools.simulate_rag_traffic $(SIMULATE_ARGS)

smoke-test: ## Run deterministic RAG smoke tests against the isolated smoke schema.
	$(MAKE) db-reset-schema SCHEMA=smoke
	AGENT_LLM_PROVIDER=baguette-llm \
	AGENT_LLM_API_KEY= \
	DB_SCHEMA=smoke \
	uv run pytest tests/smoke

stop: ## Stop every Compose profile and remove containers, networks, and orphans.
	$(COMPOSE) --profile "*" down --remove-orphans

text_search: ## Search chunks lexically using QUESTION and optional K.
	@test -n "$(QUESTION)" || (echo "QUESTION is required; for example: make text_search QUESTION='Brittany coast'" >&2; exit 1)
	$(COMPOSE) --profile app run --rm -T app \
		portfolio-ai-tour-guide-agent search --mode text --k "$(K)" "$(QUESTION)"

validate-dashboard-backup:
	@test -s "$(DASHBOARD_BACKUP)" || \
		(echo "Dashboard backup not found: $(DASHBOARD_BACKUP). Run 'make dashboard-export' first." >&2; exit 1)
	@case "$(METABASE_DB_NAME)" in *[!a-z0-9_]*|[0-9]*|'') echo "METABASE_DB_NAME must be a lowercase PostgreSQL identifier" >&2; exit 1;; esac
	@case "$(FORCE)" in 0|1) ;; *) echo "FORCE must be 0 or 1" >&2; exit 1;; esac

vector_search: ## Search chunks semantically using QUESTION and optional K.
	@test -n "$(QUESTION)" || (echo "QUESTION is required; for example: make vector_search QUESTION='Where is the Brittany coast?'" >&2; exit 1)
	$(COMPOSE) --profile app run --rm -T app \
		portfolio-ai-tour-guide-agent search --mode vector --k "$(K)" "$(QUESTION)"
