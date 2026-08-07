.DEFAULT_GOAL := help

COMPOSE ?= docker compose
SOURCE_FILES ?= source_files.json

.PHONY: help init-db reset-db ingest

help: ## Show the available commands.
	@echo "Available commands:"
	@echo "  make init-db                         Initialize the PostgreSQL schema"
	@echo "  make reset-db                        Delete and recreate the database"
	@echo "  make ingest                          Ingest source_files.json"
	@echo "  make ingest SOURCE_FILES=path.json   Ingest another JSON input file"

init-db: ## Start PostgreSQL and initialize its schema.
	$(COMPOSE) --profile tools run --rm init-db

reset-db: ## Delete the PostgreSQL volume and initialize a fresh database.
	@echo "Deleting the PostgreSQL volume and all stored application data..."
	$(COMPOSE) down --volumes
	$(COMPOSE) --profile tools run --rm init-db

ingest: ## Ingest the documents described by SOURCE_FILES.
	@test -f "$(SOURCE_FILES)" || (echo "Input file not found: $(SOURCE_FILES)" >&2; exit 1)
	$(COMPOSE) --profile ingestion run --rm -T ingestion \
		python -m ai_tour_guide.ingestion.cli - < "$(SOURCE_FILES)"
