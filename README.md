# Bitlux CRM

A CRM for private aviation charter brokerage.

* **[DATA_MODEL.md](DATA_MODEL.md)** — the authoritative data model: 37 tables,
  47 enums, conventions, and ASCII ER diagrams. Change it in the same commit as
  any schema change.
* **[PROMPT_LOG.md](PROMPT_LOG.md)** — how the repo got here, including the
  things that went wrong on the way.

`make help` lists every target below.

## Local Setup

Prerequisites: Docker (with Compose v2), Python 3.10+, and [`uv`](https://docs.astral.sh/uv/).

```bash
make venv            # backend/.venv: editable install of backend/pyproject.toml with dev extras
make up wait         # postgres:16 on host port 5433 (5432 is left to a system Postgres)
cp backend/.env.example backend/.env
```

Every `make` target that touches the database honours `DATABASE_URL`; the default is
the local stack: `postgresql+asyncpg://bitlux:bitlux@localhost:5433/bitlux_crm`.

### Two database roles, and why it matters

| Role | Purpose | RLS |
|---|---|---|
| `bitlux` | owns the schema, runs migrations. **Superuser.** | bypassed |
| `bitlux_app` | what the application connects as | **enforced** |

PostgreSQL superusers bypass Row-Level Security unconditionally, so connecting
as `bitlux` makes every tenant-isolation policy inert. `docker/initdb/` creates
`bitlux_app` for local dev; migration 001 creates it (`NOLOGIN`) anywhere else,
and each migration grants that role exactly the privileges its tables need.
Verify isolation as `bitlux_app` (`make psql-app`), never as `bitlux`, and give
the runtime the `bitlux_app` equivalent in production. See
[DATA_MODEL.md §1.7](DATA_MODEL.md).

Every query must run inside a transaction that has set the tenant:

```sql
BEGIN;
SET LOCAL app.client_id = '0199…';   -- SET LOCAL, not SET: pooling safety
...
COMMIT;
```

## Running Migrations

```bash
make migrate          # alembic upgrade head
make downgrade        # one step back
```

`backend/alembic/versions/001..015` are hand-written from `DATA_MODEL.md`, in this
order: extensions + app role → enums → shared reference catalog → tenancy → CRM
spine → fleet → crew → trips → empty legs → commerce → cross-cutting → audit
partitions → triggers → RLS → global catalog seed (which ends by asserting that
`audit_logs` is still append-only for the app role).

Do **not** run `alembic revision --autogenerate` until `backend/app/models.py`
covers the schema — `env.py` blocks it, because the diff against empty metadata
would be "drop every table".

## Seeding Demo Data

```bash
make seed             # insert / refresh the "Demo Brokerage" tenant
make verify-seed      # PASS/FAIL checks; exit 1 on any failure
```

`backend/scripts/seed.py` creates one tenant (`slug = demo`) with 3 users, 8
contacts, 6 passengers, 4 operators, 10 aircraft, 3 crew, 5 multi-leg trips, a
quote → booking → invoices → payments chain, documents, empty legs, tasks,
activities, tags, and an audit trail — 237 rows. It is **idempotent**: ids are
`uuid5(namespace, natural key)` and writes are upserts, so re-running refreshes
rather than duplicates.

Two things about how it writes:

* The tenant rows go in **through the application path** — `SET LOCAL ROLE
  bitlux_app` plus `app.client_id` for the transaction — so RLS is enforced on
  every insert. The script refuses to proceed if the effective role would
  bypass RLS.
* Global reference rows it needs that migration 015 did not ship (Heathrow, the
  Citation X+) are added to the **global** catalog (`client_id IS NULL`) as the
  schema owner, not duplicated into the tenant.

`make reset` destroys the local volume and rebuilds everything: up, migrate,
partition maintenance, seed, verify.

## ORM and Repository Layer

```
backend/app/models/         SQLModel classes, one module per migration cluster
backend/app/repositories/   the only way application code touches a table
backend/tests/              pytest, run as bitlux_app against the seeded demo tenant
```

**Models** (`app/models/`) mirror the migrations exactly — `alembic check` reports
no difference between the classes and the live schema, partial indexes and enum
type names included. Every tenant table inherits `TenantScopedMixin`
(`id`, `client_id`, `created_at`, `updated_at`, `deleted_at`, `created_by`,
`updated_by`) and declares none of those itself; the shared reference catalog
uses `SharedCatalogMixin` (nullable `client_id`). Ids are UUIDv7 from
`uuid_utils` — the database has no default. Polymorphic edges
(`document_links`, `entity_tags`, `tasks`, `activities`, `audit_logs`) are not
relationships; they are resolved through `app.repositories.polymorphic`. The
circular `trips.accepted_quote_id` / `trips.booking_id` are plain deferrable FK
columns. `AuditLog()` raises — the only writer is `AuditLogRepository.append()`.

**Repositories** (`app/repositories/`) all descend from `BaseRepository`, whose
`_base_query()` filters `deleted_at IS NULL` and adds
`client_id = current_client_id()` — defence in depth on top of RLS, and a
Python exception (`TenantContextMissing`) rather than an empty result when no
tenant is set. Enter a tenant with:

```python
async with tenant_transaction(session, client_id, user_id):
    trips = await TripRepository(session).by_status(TripStatus.CONFIRMED)
```

That sets `app.client_id` / `app.user_id` for the transaction (`set_config(...,
is_local => true)`, the parameterisable `SET LOCAL`) and binds the Python
context; nesting it for another tenant restores the outer one on exit.

```bash
make test        # 30 tests (repositories + API), each in a rolled-back transaction, as bitlux_app
```

## API

```bash
make api                                  # http://127.0.0.1:8000/api/v1/docs
curl -s -X POST localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' -d '{"email":"broker@demo.test","password":"Demo!2026"}'
```

FastAPI over the repository layer: JWT auth (argon2id passwords, 15-min access /
7-day rotating refresh tokens), role-based permissions, the standard six
operations on every resource, `GET /search` on the tsvector GIN indexes, and
`GET /graph/{entity}/{id}` for the D3 relationship view. Every request runs as
`bitlux_app` inside a tenant transaction, so RLS is live from the first query;
another tenant's row is a 404. Details, env vars, endpoint list and the auth flow
are in **[backend/README.md](backend/README.md)**.

## Frontend

```bash
make web-install && make web              # Vite dev server on http://localhost:5173 (API on :8000)
make web-test                             # tsc + eslint + vitest
make screenshots                          # docs/screenshots/*.png from the running app
make verify-ui                            # layout / scrollbar / top bar / theme checks in Chrome
```

Vite 6 / React 19 / TypeScript 5.9 / Tailwind 4, with React Router 7, TanStack
Query + Table, shadcn-style components, react-hook-form + zod, D3 v7. The shell
(sidebar, top bar with ⌘K search, mobile tab bar) is permission-gated from
`/auth/me`; the access token lives in memory only and the refresh token in an
HttpOnly cookie. Light / dark / system theme, persisted as `bitlux-theme`.
`/clients` and `/clients/:id` are the fully implemented
reference pages; every other route is a skeleton for Sprint 5. The hero is the
**relationship visualiser** — `<RelationshipGraph>` over `/graph/{entity}/{id}`,
embedded as a "Relationship" tab on every entity detail page. Details in
**[frontend/README.md](frontend/README.md)**.

![Client relationship graph](docs/screenshots/client-relationship-depth1.png)

## Deployment

| Layer    | Where                         | URL                                              |
|----------|-------------------------------|--------------------------------------------------|
| Backend  | Render, Docker web service (free) | https://bitlux-api.onrender.com (expected; confirm after the first deploy) |
| Frontend | Cloudflare Pages (free)        | fill in after the Cloudflare deploy, e.g. https://bitlux-crm.pages.dev |
| Database | Neon, PostgreSQL 16 (free)     | two roles: the owner for migrations, `bitlux_app` for the API |

Cost: $0. Render's free instance spins down after 15 idle minutes (first request
then takes up to a minute) and Neon's free compute autosuspends after 5; both are
cosmetic for a demo and a free uptime monitor on `/health` hides the former.

Config lives in the repo: `render.yaml` + `backend/Dockerfile`, Cloudflare's
`frontend/public/_headers` and `_redirects`, a build-time guard that fails the
frontend build if `VITE_API_BASE_URL` is unset, CI in `.github/workflows/ci.yml`,
and a monthly `partition-maintenance.yml`. The step-by-step runbook, including the
role split the API enforces at startup, is **[docs/DEPLOY.md](docs/DEPLOY.md)**.

```bash
export DATABASE_URL='postgresql://<owner>:<pw>@<endpoint>.neon.tech/bitlux_crm?sslmode=require'
make db-check-prod                 # SELECT 1 + role / server / alembic head
make app-role-prod                 # create bitlux_app (needs APP_DB_PASSWORD); prints APP_DATABASE_URL
make migrate-prod                  # alembic upgrade head
make partition-maintenance-prod    # audit_logs partitions, 12 months ahead
make seed-prod                     # demo tenant, 5-second abort window
make docker-build docker-run       # the Render image, locally, against docker-compose
```

## Known limitations (test project)

- **No breadcrumbs.** Detail pages carry an explicit "← Back to <list>" link rather
  than a full `Home > Clients > … > John Smith` trail. The trail needs each
  intermediate record's name resolved per route, which is a bigger change than the
  affordance it buys; the back link covers the actual need (getting out of a detail
  page reached by a deep link).

- **`[enc]` columns use a placeholder in the demo seed; production requires a
  KMS-backed key hierarchy.** The API itself encrypts passport numbers, KTNs,
  redress numbers, tax IDs and crew licence numbers on write with a single Fernet
  key and never returns them (only `*_last4`), but `scripts/seed.py` writes
  marked plaintext bytes into those columns instead. Details and the production
  requirements are in [DATA_MODEL.md §1.2.1](DATA_MODEL.md#121-encryption-status-test-project-scope).

## Operational Runbook

### `audit_logs` partitions — run `make partition-maintenance` monthly

`audit_logs` is RANGE-partitioned by month. Migration 012 provisioned
**2026-09 through 2027-08** plus a DEFAULT partition. Nothing provisions later
months on its own.

```bash
make partition-maintenance      # exit 0 healthy · 1 default partition has rows · 2 create failed
```

The job ensures a partition exists for the current month plus the next 12,
skips existing ones, revokes direct access on new ones (partitions have no RLS
of their own — access is only through the parent), confirms the append-only
trigger was inherited, and then **counts rows in `audit_logs_default`**.

**Schedule it.** Monthly is enough; weekly is cheap. Example cron on the host that
runs migrations:

```cron
0 3 1 * *  cd /srv/bitlux-crm && make partition-maintenance >> /var/log/bitlux/partitions.log 2>&1 || <alert>
```

**Alert if the default partition ever has rows.** A row there means an event
arrived for a month nobody provisioned. It is not lost, but while it sits
there, `CREATE TABLE … PARTITION OF` for that month fails, so the fix is: create
the missing month(s) — the job's error names them — move the rows out of the
default partition into them, re-run. The job exits 1 in this state precisely so
cron/CI can page on it.

**Deadline: this must be automated before 2027-08.** That is the last month
migration 012 provisioned. With the job on a schedule the horizon rolls forward
and this date never matters; without it, on 2027-09-01 every audit row starts
landing in the default partition and the situation above becomes chronic.

Running it manually anywhere else: `DATABASE_URL=… backend/.venv/bin/python
backend/scripts/partition_maintenance.py [--months N] [--dry-run]`, as the
schema owner.
