# Bitlux CRM

A CRM for private aviation charter brokerage.

* **[DATA_MODEL.md](DATA_MODEL.md)** — the authoritative data model: 37 tables,
  47 enums, conventions, and ASCII ER diagrams. Change it in the same commit as
  any schema change.
* **[PROMPT_LOG.md](PROMPT_LOG.md)** — how the repo got here.

## Local development

```bash
docker compose up -d                 # postgres:16 on host port 5433

cd backend
uv venv .venv && uv pip install --python .venv/bin/python -r requirements.txt
cp .env.example .env
export DATABASE_URL="postgresql+asyncpg://bitlux:bitlux@localhost:5433/bitlux_crm"
.venv/bin/alembic upgrade head

# Take back the over-granted UPDATE/DELETE on the append-only audit table.
cd .. && docker compose exec -T postgres psql -U bitlux -d bitlux_crm \
  < backend/scripts/post_migrate_grants.sql
```

Host port is **5433**, not 5432, so the container does not collide with a
system PostgreSQL.

## Two database roles, and why it matters

| Role | Purpose | RLS |
|---|---|---|
| `bitlux` | owns the schema, runs migrations. **Superuser.** | bypassed |
| `bitlux_app` | what the application connects as | **enforced** |

PostgreSQL superusers bypass Row-Level Security unconditionally, so connecting
as `bitlux` makes every tenant-isolation policy inert. Verify isolation as
`bitlux_app`, never as `bitlux`, and give the runtime the `bitlux_app`
equivalent in production. See [DATA_MODEL.md](DATA_MODEL.md) §1.7.

Every query must run inside a transaction that has set the tenant:

```sql
BEGIN;
SET LOCAL app.client_id = '0199…';   -- SET LOCAL, not SET: pooling safety
...
COMMIT;
```

## Migrations

`backend/alembic/versions/001..015`, hand-written from `DATA_MODEL.md`:
extensions → enums → reference catalog → tenancy → CRM spine → fleet → crew →
trips → empty legs → commerce → cross-cutting → audit partitions → triggers →
RLS → seed.

Do **not** run `alembic revision --autogenerate` until `backend/app/models.py`
covers the schema — `env.py` blocks it, because the diff against empty metadata
would be "drop every table".
