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
make venv            # backend/.venv with alembic, asyncpg, sqlmodel, uuid-utils
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
