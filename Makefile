# Bitlux CRM -- developer and operations entry points.
#
# Every target that touches the database honours DATABASE_URL; the default below
# is the local docker-compose stack (host port 5433, see docker-compose.yml).

SHELL := /bin/bash
PY := backend/.venv/bin/python
export DATABASE_URL ?= postgresql+asyncpg://bitlux:bitlux@localhost:5433/bitlux_crm

.PHONY: help venv test up down wait migrate downgrade partition-maintenance seed verify-seed psql psql-app reset

help: ## List targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-24s\033[0m %s\n", $$1, $$2}'

venv: ## Create backend/.venv and install the backend (editable) with dev extras (needs uv)
	cd backend && uv venv .venv && uv pip install --python .venv/bin/python -e ".[dev]"

test: ## Run the repository test-suite against the seeded local database (as bitlux_app)
	cd backend && .venv/bin/python -m pytest -q

up: ## Start postgres:16 (host port 5433)
	docker compose up -d

down: ## Stop the stack (keeps the data volume)
	docker compose down

wait: ## Block until postgres reports healthy
	@for i in $$(seq 1 30); do \
	  case "$$(docker compose ps --format '{{.Status}}' postgres 2>/dev/null)" in *healthy*) echo "postgres healthy"; exit 0;; esac; \
	  sleep 2; \
	done; echo "postgres did not become healthy" >&2; exit 1

migrate: ## alembic upgrade head
	cd backend && .venv/bin/alembic upgrade head

downgrade: ## alembic downgrade -1 (one step)
	cd backend && .venv/bin/alembic downgrade -1

partition-maintenance: ## Ensure 12 months of audit_logs partitions; exit 1 if the default partition has rows
	$(PY) backend/scripts/partition_maintenance.py

seed: ## Insert/refresh the "Demo Brokerage" tenant (idempotent)
	$(PY) backend/scripts/seed.py

verify-seed: ## Assert the demo tenant looks right; exit non-zero on any FAIL
	$(PY) backend/scripts/verify_seed.py

psql: ## psql as the schema owner (superuser -- RLS is bypassed)
	docker compose exec postgres psql -U bitlux -d bitlux_crm

psql-app: ## psql as the application role (RLS enforced; remember SET LOCAL app.client_id)
	docker compose exec -e PGPASSWORD=bitlux_app postgres psql -U bitlux_app -h 127.0.0.1 -d bitlux_crm

reset: ## DESTROY the local volume, then up + migrate + partition-maintenance + seed + verify-seed
	docker compose down -v
	$(MAKE) up wait migrate partition-maintenance seed verify-seed
