# Bitlux CRM -- developer and operations entry points.
#
# Every target that touches the database honours DATABASE_URL; the default below
# is the local docker-compose stack (host port 5433, see docker-compose.yml).

SHELL := /bin/bash
PY := backend/.venv/bin/python
export DATABASE_URL ?= postgresql+asyncpg://bitlux:bitlux@localhost:5433/bitlux_crm

.PHONY: help venv test api web web-install web-test web-build screenshots verify-ui up down wait migrate downgrade partition-maintenance seed verify-seed psql psql-app reset \
	db-check-prod app-role-prod migrate-prod partition-maintenance-prod seed-prod docker-build docker-run

help: ## List targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-24s\033[0m %s\n", $$1, $$2}'

venv: ## Create backend/.venv and install the backend (editable) with dev extras (needs uv)
	cd backend && uv venv .venv && uv pip install --python .venv/bin/python -e ".[dev]"

test: ## Run the repository + API test-suites against the seeded local database (as bitlux_app)
	cd backend && .venv/bin/python -m pytest -q

PORT ?= 8000
api: ## Run the API with reload on $(PORT) (docs at /api/v1/docs)
	cd backend && .venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port $(PORT)

web-install: ## npm install the frontend
	cd frontend && npm install --no-audit --no-fund

web: ## Run the Vite dev server on :5173 (expects the API on :8000)
	cd frontend && npm run dev

web-test: ## Typecheck, lint and run the frontend test-suite
	cd frontend && npm run typecheck && npm run lint && npm test

web-build: ## Production build to frontend/dist
	cd frontend && npm run build

screenshots: ## Drive the running app with Chrome and write docs/screenshots/*.png
	cd frontend && npm run screenshots

verify-ui: ## Check sidebar scroll, layout gap, top bar and theme toggle in Chrome (app must be running)
	cd frontend && npm run verify:ui

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

# ---------------------------------------------------------------------------
# Production database (Neon). Every *-prod target runs against $DATABASE_URL,
# which must be the Neon OWNER url, explicitly exported -- the local default
# above is refused. Redacted before it is echoed.
#   export DATABASE_URL='postgresql://<owner>:<pw>@<host>.neon.tech/bitlux_crm?sslmode=require'
# ---------------------------------------------------------------------------
REDACTED_URL = $$(printf '%s' "$$DATABASE_URL" | sed -E 's,://([^:/@]+)(:[^@]*)?@,://\1:***@,')
define require_prod_url
	@if [ -z "$$DATABASE_URL" ] || printf '%s' "$$DATABASE_URL" | grep -Eq 'localhost|127\.0\.0\.1'; then \
	  echo "DATABASE_URL must be exported and point at the production database (it is unset or the local default)." >&2; exit 1; fi
	@echo "target: $(REDACTED_URL)"
endef

db-check-prod: ## SELECT 1 against $$DATABASE_URL; prints role, server, alembic head; exit 1 on failure
	$(require_prod_url)
	cd backend && .venv/bin/python scripts/db_check.py

app-role-prod: ## Create/update the bitlux_app LOGIN role on $$DATABASE_URL (needs APP_DB_PASSWORD=...)
	$(require_prod_url)
	cd backend && .venv/bin/python scripts/app_role.py

migrate-prod: ## alembic upgrade head against $$DATABASE_URL
	$(require_prod_url)
	cd backend && .venv/bin/alembic upgrade head

partition-maintenance-prod: ## Ensure 12 months of audit_logs partitions on $$DATABASE_URL
	$(require_prod_url)
	cd backend && .venv/bin/python scripts/partition_maintenance.py

seed-prod: ## Insert/refresh the Demo Brokerage tenant on $$DATABASE_URL (5-second abort window)
	$(require_prod_url)
	@echo "About to write the DEMO tenant (owner@demo.test / broker@ / ops@, password Demo!2026) into the database above."
	@echo "This is idempotent but it is demo data on a production database. Ctrl-C within 5 seconds to abort."
	@for i in 5 4 3 2 1; do printf '  %s...\r' $$i; sleep 1; done; echo
	cd backend && .venv/bin/python scripts/seed.py

docker-build: ## Build the API image exactly as Render does (context = backend/)
	docker build -t bitlux-api backend

docker-run: ## Run the image against the local stack on :8000 (APP_DATABASE_URL -> bitlux_app on host 5433)
	docker run --rm --network host -e APP_ENV=local \
	  -e APP_DATABASE_URL=postgresql+asyncpg://bitlux_app:bitlux_app@127.0.0.1:5433/bitlux_crm bitlux-api
