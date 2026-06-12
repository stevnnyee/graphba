.DEFAULT_GOAL := help

# Self-documenting help: prints every target that has a "## description" comment.
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

up: ## Start Postgres in the background
	docker compose up -d

down: ## Stop Postgres (keeps data)
	docker compose down

reset: ## Stop Postgres and DELETE all data (fresh DB)
	docker compose down -v

ps: ## Show container status
	docker compose ps

logs: ## Tail the Postgres logs
	docker compose logs -f db

psql: ## Open a psql shell inside the container
	docker exec -it graphba-db psql -U graphba -d graphba

install: ## Install Python deps from requirements.txt
	pip install -r requirements.txt

freeze: ## Snapshot current deps into requirements.txt
	pip freeze > requirements.txt

healthcheck: ## Verify the DB connection works (SELECT 1)
	python -m scripts.healthcheck

ingest-teams: ## Ingest NBA teams into the database (idempotent)
	python -m scripts.ingest_teams

ingest-players: ## Ingest the NBA player universe into the database (idempotent)
	python -m scripts.ingest_players

ingest-rosters: ## Crawl team rosters into the database (resumable, long-running)
	python -m scripts.ingest_rosters

schema: ## Apply db/schema.sql to the database
	docker exec -i graphba-db psql -U graphba -d graphba < db/schema.sql

test: ## Run unit tests (mocked, no network)
	pytest

test-live: ## Run integration tests that hit the real NBA API
	pytest --run-integration

lint: ## Check code with ruff (lint + import order)
	ruff check .

format: ## Auto-format code with ruff
	ruff format .

.PHONY: help up down reset ps logs psql install freeze healthcheck ingest-teams ingest-players ingest-rosters schema test test-live lint format
