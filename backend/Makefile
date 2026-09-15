# Bitlux CRM backend -- database and API entry points.
#
# Run from backend/ (`make migrate`) or from the repo root, whose Makefile
# delegates every target here (`make migrate` == `make -C backend migrate`).
#
# DATABASE_URL is the schema OWNER url: alembic, seed, partition maintenance.
# The API itself runs as the bitlux_app role via APP_DATABASE_URL -- never the
# owner, or row-level security is silently off (DATA_MODEL.md 1.7, docs/DEPLOY.md).
# The default below is the local docker-compose stack; the *-prod targets refuse it.

SHELL := /bin/bash
VENV := .venv
PY := $(VENV)/bin/python
ALEMBIC := $(VENV)/bin/alembic
export DATABASE_URL ?= postgresql+asyncpg://bitlux:bitlux@localhost:5433/bitlux_crm

.PHONY: help venv test api migrate downgrade partition-maintenance seed verify-seed \
        db-check-prod app-role-prod migrate-prod seed-prod partition-maintenance-prod

help: ## List targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-28s\033[0m %s\n", $$1, $$2}'

# ---------------------------------------------------------------------------
# Local development (docker-compose stack on host port 5433)
# ---------------------------------------------------------------------------

venv: ## Create .venv and install the backend (editable) with dev extras (needs uv)
	uv venv --clear $(VENV) && uv pip install --python $(PY) -e ".[dev]"

test: ## Run the repository + API test-suites against the seeded local database (as bitlux_app)
	$(PY) -m pytest -q

PORT ?= 8000
api: ## Run the API with reload on $(PORT) (docs at /api/v1/docs)
	$(VENV)/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port $(PORT)

migrate: ## alembic upgrade head
	$(ALEMBIC) upgrade head

downgrade: ## alembic downgrade -1 (one step)
	$(ALEMBIC) downgrade -1

partition-maintenance: ## Ensure 12 months of audit_logs partitions; exit 1 if the default partition has rows
	$(PY) scripts/partition_maintenance.py

seed: ## Insert/refresh the "Demo Brokerage" tenant (idempotent)
	$(PY) scripts/seed.py

verify-seed: ## Assert the demo tenant looks right; exit non-zero on any FAIL
	$(PY) scripts/verify_seed.py

# ---------------------------------------------------------------------------
# Production database (Neon). Every *-prod target:
#   * refuses to run if DATABASE_URL is unset/empty or names localhost / 127.0.0.1
#     (an unset variable falls back to the local default above, which is refused)
#   * echoes the target and the url with the password redacted before acting
#   * runs the tools from .venv (the same as `source .venv/bin/activate`)
#   export DATABASE_URL='postgresql://<owner>:<pw>@<endpoint>.neon.tech/bitlux_crm?sslmode=require'
# ---------------------------------------------------------------------------

# psql wants the libpq form: drop SQLAlchemy's "+asyncpg" driver suffix.
PSQL_URL = $$(printf '%s' "$$DATABASE_URL" | sed -E 's|^postgres(ql)?\+[a-z0-9]+://|postgresql://|')
REDACTED = $$(printf '%s' "$$DATABASE_URL" | sed -E 's|(://[^:/@]+):[^@]*@|\1:****@|')

define prod_guard
	@if [ -z "$$DATABASE_URL" ]; then \
	  echo "$@: DATABASE_URL is not set. Export the production (Neon) OWNER url first." >&2; exit 1; fi
	@case "$$DATABASE_URL" in *localhost*|*127.0.0.1*) \
	  echo "$@: DATABASE_URL is unset or points at the local database ($(REDACTED)). Export the production (Neon) OWNER url first." >&2; exit 1;; esac
	@echo "$@ -> $(REDACTED)"
endef

db-check-prod: ## psql SELECT 1 against $$DATABASE_URL; reports bitlux_app (exists? BYPASSRLS?) and the alembic head
	$(prod_guard)
	@psql "$(PSQL_URL)" -v ON_ERROR_STOP=1 -qtAc "SELECT 1" >/dev/null && echo "  SELECT 1      : OK" \
	  || { echo "  SELECT 1      : FAILED" >&2; exit 1; }
	@psql "$(PSQL_URL)" -v ON_ERROR_STOP=1 -qtA \
	  -c "SELECT '  server        : PostgreSQL ' || current_setting('server_version')" \
	  -c "SELECT '  connected as  : ' || current_user || ' (superuser=' || current_setting('is_superuser') || ', bypassrls=' || r.rolbypassrls::text || ') -> RLS ' || CASE WHEN current_setting('is_superuser') = 'on' OR r.rolbypassrls THEN 'BYPASSED (owner/maintenance role)' ELSE 'enforced' END FROM pg_roles r WHERE r.rolname = current_user" \
	  -c "SELECT '  bitlux_app    : ' || COALESCE((SELECT 'exists, login=' || rolcanlogin::text || ', bypassrls=' || rolbypassrls::text || ', superuser=' || rolsuper::text || CASE WHEN rolbypassrls OR rolsuper THEN '  <-- WRONG: would bypass RLS' ELSE '' END FROM pg_roles WHERE rolname = 'bitlux_app'), 'MISSING (run: make app-role-prod)')" \
	  -c "SELECT '  alembic head  : ' || CASE WHEN to_regclass('public.alembic_version') IS NULL THEN 'no alembic_version table (run: make migrate-prod)' ELSE COALESCE((SELECT string_agg(version_num, ',') FROM alembic_version), 'empty') END"

app-role-prod: ## Create/update the bitlux_app LOGIN role (needs APP_DB_PASSWORD); prints APP_DATABASE_URL. Idempotent
	$(prod_guard)
	@if [ -z "$$APP_DB_PASSWORD" ]; then \
	  echo "$@: APP_DB_PASSWORD is not set. Generate one:  export APP_DB_PASSWORD=\"\$$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')\"" >&2; exit 1; fi
	$(PY) scripts/app_role.py

migrate-prod: ## alembic upgrade head against $$DATABASE_URL
	$(prod_guard)
	$(ALEMBIC) upgrade head

partition-maintenance-prod: ## Ensure 12 months of audit_logs partitions on $$DATABASE_URL
	$(prod_guard)
	$(PY) scripts/partition_maintenance.py --months 12

seed-prod: ## Insert/refresh the Demo Brokerage tenant on $$DATABASE_URL after a 5-second countdown (Ctrl-C aborts)
	$(prod_guard)
	@echo "  Seeding the DEMO tenant (owner@ / broker@ / ops@demo.test, password Demo!2026) into the database above."
	@echo "  Idempotent, but this is demo data on a production database. Ctrl-C to abort."
	@for i in 5 4 3 2 1; do printf '  starting in %s...\r' $$i; sleep 1; done; echo
	$(PY) scripts/seed.py
