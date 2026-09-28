# Warehouse Copilot - common tasks. Run `make help` for the list.
.DEFAULT_GOAL := help
DBT_DIR := dbt/warehouse_copilot

.PHONY: help setup install ingest ingest-synthetic dbt-deps dbt-build dbt-test \
        mcp dagster lint fmt test docker-build clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

setup: ## Create a venv and install the project with dev + orchestration extras
	python3.12 -m venv .venv && . .venv/bin/activate && \
	  pip install -U pip && pip install -e ".[dev,orchestration]"

install: ## Install the project (editable) into the current environment
	pip install -e ".[dev,orchestration]"

ingest: ## Fetch the last 90 days of FX rates and load into Snowflake
	wc-ingest

ingest-synthetic: ## Load offline synthetic data (no internet / no API needed)
	wc-ingest --synthetic

dbt-deps: ## Install dbt packages (dbt_utils)
	cd $(DBT_DIR) && dbt deps

dbt-build: ## Run seeds + models + tests
	cd $(DBT_DIR) && dbt build

dbt-test: ## Run dbt tests only
	cd $(DBT_DIR) && dbt test

mcp: ## Start the MCP server (stdio) - use RO role in .env
	wc-mcp

mcp-inspector: ## Debug the MCP server in a browser UI
	npx @modelcontextprotocol/inspector wc-mcp

dagster: ## Launch the Dagster UI (ingestion -> dbt lineage)
	dagster dev -f orchestration/warehouse_copilot_dagster/definitions.py

lint: ## Lint Python (ruff)
	ruff check src tests

fmt: ## Auto-format / auto-fix (ruff)
	ruff check --fix src tests && ruff format src tests

test: ## Run the unit test suite
	pytest

docker-build: ## Build the container image
	docker build -t warehouse-copilot .

clean: ## Remove build/test artefacts
	rm -rf .pytest_cache .ruff_cache **/__pycache__ $(DBT_DIR)/target $(DBT_DIR)/dbt_packages
