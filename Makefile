.DEFAULT_GOAL := help

COMPOSE ?= docker compose
SOURCE_FILES ?= source_files.json
EXPORT_DIR ?= tmp
CSV_LIMIT ?= 1000
DEBUG ?= 0
DEBUG_FLAG = $(if $(filter 1 true yes,$(DEBUG)),--debug,)

.PHONY: help init-db reset-db ingest export-csv

help: ## Show the available commands.
	@echo "Available commands:"
	@echo "  make init-db                         Initialize the PostgreSQL schema"
	@echo "  make reset-db                        Delete and recreate the database"
	@echo "  make ingest                          Ingest source_files.json"
	@echo "  make ingest DEBUG=1                  Ingest and retain debug artifacts"
	@echo "  make ingest SOURCE_FILES=path.json   Ingest another JSON input file"
	@echo "  make export-csv                      Export ingestion tables to CSV"
	@echo "  make export-csv EXPORT_DIR=path      Export CSV files to another directory"
	@echo "  make export-csv CSV_LIMIT=100        Limit each export to 100 data rows"

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

export-csv: ## Export ingestion tables as deterministic CSV files.
	@case "$(CSV_LIMIT)" in *[!0-9]*|'') echo "CSV_LIMIT must be a positive integer" >&2; exit 1;; esac
	@test "$(CSV_LIMIT)" -gt 0 || (echo "CSV_LIMIT must be greater than zero" >&2; exit 1)
	@mkdir -p "$(EXPORT_DIR)"
	@$(COMPOSE) exec -T database sh -c \
		'psql --no-psqlrc --quiet --set=ON_ERROR_STOP=1 --username "$$POSTGRES_USER" --dbname "$$POSTGRES_DB" --command "\copy (SELECT * FROM public.embedding_models ORDER BY embedding_model_id LIMIT $(CSV_LIMIT)) TO STDOUT WITH (FORMAT CSV, HEADER true)"' \
		> "$(EXPORT_DIR)/embedding_models.csv.tmp"
	@mv "$(EXPORT_DIR)/embedding_models.csv.tmp" "$(EXPORT_DIR)/embedding_models.csv"
	@$(COMPOSE) exec -T database sh -c \
		'psql --no-psqlrc --quiet --set=ON_ERROR_STOP=1 --username "$$POSTGRES_USER" --dbname "$$POSTGRES_DB" --command "\copy (SELECT * FROM public.documents ORDER BY document_id LIMIT $(CSV_LIMIT)) TO STDOUT WITH (FORMAT CSV, HEADER true)"' \
		> "$(EXPORT_DIR)/documents.csv.tmp"
	@mv "$(EXPORT_DIR)/documents.csv.tmp" "$(EXPORT_DIR)/documents.csv"
	@$(COMPOSE) exec -T database sh -c \
		'psql --no-psqlrc --quiet --set=ON_ERROR_STOP=1 --username "$$POSTGRES_USER" --dbname "$$POSTGRES_DB" --command "\copy (SELECT * FROM public.document_chunks ORDER BY document_id, chunk_index LIMIT $(CSV_LIMIT)) TO STDOUT WITH (FORMAT CSV, HEADER true)"' \
		> "$(EXPORT_DIR)/document_chunks.csv.tmp"
	@mv "$(EXPORT_DIR)/document_chunks.csv.tmp" "$(EXPORT_DIR)/document_chunks.csv"
	@echo "Exported up to $(CSV_LIMIT) data rows per table to $(EXPORT_DIR)/"
