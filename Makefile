# Bitlux CRM -- developer and operations entry points.
#
# Backend and database targets (local and *-prod) live in backend/Makefile and
# are delegated to from here, so `make migrate` and `make -C backend migrate`
# are the same thing. DATABASE_URL handling, including the production guard,
# is documented there.

SHELL := /bin/bash

BACKEND_TARGETS := venv test api migrate downgrade partition-maintenance seed verify-seed \
                   db-check-prod app-role-prod migrate-prod seed-prod partition-maintenance-prod

.PHONY: help $(BACKEND_TARGETS) web-install web web-test web-build screenshots verify-ui up down wait psql psql-app reset docker-build docker-run

help: ## List targets (root + backend)
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(firstword $(MAKEFILE_LIST)) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-28s\033[0m %s\n", $$1, $$2}'
	@$(MAKE) --no-print-directory -C backend help

$(BACKEND_TARGETS):
	@$(MAKE) --no-print-directory -C backend $@

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

psql: ## psql as the schema owner (superuser -- RLS is bypassed)
	docker compose exec postgres psql -U bitlux -d bitlux_crm

psql-app: ## psql as the application role (RLS enforced; remember SET LOCAL app.client_id)
	docker compose exec -e PGPASSWORD=bitlux_app postgres psql -U bitlux_app -h 127.0.0.1 -d bitlux_crm

reset: ## DESTROY the local volume, then up + migrate + partition-maintenance + seed + verify-seed
	docker compose down -v
	$(MAKE) up wait migrate partition-maintenance seed verify-seed

docker-build: ## Build the API image exactly as Render does (context = backend/)
	docker build -t bitlux-api backend

docker-run: ## Run the image against the local stack on :8000 (APP_DATABASE_URL -> bitlux_app on host 5433)
	docker run --rm --network host -e APP_ENV=local \
	  -e APP_DATABASE_URL=postgresql+asyncpg://bitlux_app:bitlux_app@127.0.0.1:5433/bitlux_crm bitlux-api
