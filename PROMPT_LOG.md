# Prompt Log

A record of the prompts that shaped this repository, and what each one produced.
Newest last.

---

## 2026-09-14 — Design the data model

**Prompt (abridged):** Plan the complete data model for a private aviation CRM.
Core graph: Clients (tenant root) → Segments → Contacts → Passengers → Account
Holders. Also aircraft manufacturers → models → tail numbers → operators; trips →
legs → passenger manifests → crew; polymorphic documents; quotes → bookings →
invoices; empty legs; operator safety ratings; audit logs; tasks. For each table:
columns, types, FKs, indexes, enums. Output an ASCII ER diagram. Do not write
code yet.

**Decisions taken (asked and answered before designing):**

| Question | Answer |
|---|---|
| Database engine | PostgreSQL |
| What is a "Client"? | The tenant/brokerage — tenant root, `client_id` everywhere |
| Primary keys | UUIDv7 |
| Lifecycle machinery | Soft delete + append-only audit log + versioned quotes |

**Produced:** `DATA_MODEL.md` — 37 tables, 47 enums, conventions, seven ASCII ER
diagrams (master + one per cluster), design notes, and an explicit deferred-scope
list. No code, as instructed.

**Notable design calls, with the alternatives rejected:**

- **Polymorphism** via link table + shared `entity_type` enum + validation
  trigger, rather than ~25 nullable exclusive-arc FK columns (a migration per new
  attachable entity) or JSONB blobs (unindexable). Exclusive-arc FKs *were* used
  for `travel_documents`, which has only two targets.
- **Shared reference catalog** (`manufacturers`, `aircraft_models`, `airports`,
  `fbos`) with **nullable `client_id`**: NULL = global row, set = tenant override.
  Requires `UNIQUE NULLS NOT DISTINCT`, which is why the floor is PG15+.
- **Quote revisions are immutable.** A sent quote is never mutated; an edit
  inserts `revision + 1` and supersedes the old row. This is what survives a
  customer disputing what they were quoted.
- **`audit_logs` kept separate from `activities`.** Machine-written and immutable
  vs. human-written and editable. Merging them would make the audit trail
  untrustworthy.

---

## 2026-09-14 — Generate the migration set

**Prompt (abridged):** Update `DATA_MODEL.md` for four decisions (app-layer
UUIDv7, PostgreSQL 16, no PostGIS locally, RLS deployment model), then generate
Alembic migrations 001–015 in a fixed order with `upgrade()` and `downgrade()`,
comments referencing `DATA_MODEL.md`, and `op.execute()` for what Alembic cannot
express. Add `backend/alembic.ini` + `env.py` (async, `DATABASE_URL`, SQLModel
metadata) and a root `docker-compose.yml` running postgres:16. Run the migrations
and confirm tables, enums, indexes and RLS policies. Update this log. Commit.

**Doc changes:** added §1.4 (PG16 feature matrix — every feature used, with the
version that introduced it), §1.5 (application-side UUIDv7), §1.6 (core `point`
instead of PostGIS, with the planar-distance tradeoff stated), §1.7 (RLS
deployment model). Removed every `DEFAULT uuidv7()`.

**Produced:** 15 migrations, `backend/alembic/{alembic.ini,env.py}`,
`backend/migration_helpers.py`, `docker-compose.yml`, `docker/initdb/`,
`backend/scripts/post_migrate_grants.sql`.

**Things that turned out to be harder than they looked:**

1. **The build order forces forward references.** Migration 003 (reference
   catalog) precedes 004 (`clients`, `users`), so `client_id`/`created_by`/
   `updated_by` on those four tables cannot have FKs at `CREATE TABLE` time.
   Twelve FKs in total are created bare and attached in the migration that
   creates the *referenced* table (004, 007, 009, 010, 011). Each is commented at
   both ends. `trips ↔ quotes ↔ bookings` is genuinely circular and uses
   `DEFERRABLE INITIALLY DEFERRED`.

2. **RLS was silently doing nothing, and the first test wrongly said it passed.**
   The `postgres:16` image creates `POSTGRES_USER` as a **superuser**, and
   superusers bypass RLS *unconditionally* — `FORCE ROW LEVEL SECURITY` only
   binds a non-superuser owner. The initial verification ran as `bitlux` and
   showed tenant A reading tenant B's rows. Fixes:
   - `DATA_MODEL.md` §1.7 rewritten with the actual three-tier rule (superuser /
     owner+FORCE / ordinary role). The earlier text said "the owner is exempt and
     FORCE fixes it", which is wrong in the case that matters locally.
   - `docker/initdb/10-app-role.sql` provisions `bitlux_app`
     (`NOSUPERUSER NOBYPASSRLS`) plus `ALTER DEFAULT PRIVILEGES`, so isolation can
     actually be exercised in dev and CI.
   - Re-verified as `bitlux_app`: each tenant sees exactly its own row, an unset
     `app.client_id` returns zero rows, and cross-tenant and global-catalog writes
     are both rejected by `WITH CHECK`.

   **Lesson worth keeping:** a passing RLS test proves nothing unless you know
   what role ran it.

3. **Seed data collides with its own policies.** Migration 015 writes
   `client_id = NULL` global rows, which no tenant policy permits, so it runs
   `SET LOCAL row_security = off` for its transaction — the owner-only escape
   hatch, scoped as narrowly as possible.

4. **`ALTER DEFAULT PRIVILEGES` over-granted `audit_logs`**, handing the app role
   UPDATE/DELETE on an append-only table. `backend/scripts/post_migrate_grants.sql`
   takes it back on the parent and every partition. The migration 013 trigger was
   already blocking it — this closes the privilege layer too.

**Verified against postgres:16 in Docker:** 37 model tables, 13 audit partitions
(12 monthly + default), 47 enums / 390 values, 381 indexes, 37 RLS policies, 55
triggers, 1 exclusion constraint, 49 CHECK constraints, 12 generated columns.
Functionally confirmed: tenant isolation, fail-closed unset tenant, cross-tenant
write rejection, `updated_at` maintenance, polymorphic validation (bogus,
cross-tenant, valid, and global-catalog targets), audit append-only,
non-overlapping aircraft tenure, generated margin/balance columns, partial-unique
soft-delete key reuse, and a clean 15-up / 15-down round-trip leaving no residue.

**Deviation from the brief, and why:** tables are created with
`op.create_table()` rather than raw SQL, with `op.execute()` reserved for what
Alembic genuinely cannot express (extensions, enums, `UNIQUE NULLS NOT
DISTINCT`, the `point` generated column, `EXCLUDE`, partitioning, triggers, RLS).
Keeping columns in `op.create_table()` means SQLAlchemy still knows the types,
which matters for the autogenerate support `env.py` is being wired up for.

---

## 2026-09-14 — Append-only enforcement, partition maintenance, demo seed

**Prompt (abridged):** (1) Fold the `audit_logs` REVOKE into migration 012 and make
"append-only" the default grant, with explicit `UPDATE, DELETE` per table; add an
invariant check in 015. (2) `partition_maintenance.py` + `make partition-maintenance`
+ an Operational Runbook. (3) `seed.py`: one deterministic, idempotent demo tenant
(uuid5 ids) written under the app's RLS context. (4) `verify_seed.py` with six
PASS/FAIL checks. (5) Docs and commit.

**Correction to the prompt's premise, and what it changed.** The
`ALTER DEFAULT PRIVILEGES` was never in migration 001 — it lived in
`docker/initdb/10-app-role.sql`, and so did the *creation* of `bitlux_app`. That
means a `REVOKE … FROM bitlux_app` in 012 would fail on any database where initdb
didn't run (Neon, CI). So the full option was taken rather than the minimal one:

- Migration 001 bootstraps `bitlux_app` (`NOLOGIN NOBYPASSRLS`) if absent.
- Every table-creating migration grants the role its DML explicitly via
  `grant_app_dml()` — 36 tables get `SELECT, INSERT, UPDATE, DELETE`; `audit_logs`
  (012) gets `SELECT, INSERT` and has `UPDATE, DELETE` revoked from the role and
  from `PUBLIC` before the first partition exists.
- 015 ends the chain by asserting, with `has_table_privilege()` (which also sees
  grants arriving via `PUBLIC` or role membership — exactly how an accident would
  arrive), that the role still has neither. Tested: granting `UPDATE` inside a
  transaction makes the block raise.
- initdb's default privileges dropped to `SELECT, INSERT` — a floor for anything
  created outside the chain, never a source of write access.
- `post_migrate_grants.sql` deleted; nothing manual remains.

**Two facts about partitions, verified empirically, that shaped the design:**

1. PostgreSQL checks privileges on the table *named in the query*. Inserting through
   `audit_logs` succeeded as `bitlux_app` into a partition that had `REVOKE ALL` —
   so the maintenance job never needs to grant.
2. The corollary is a hole: a partition has no RLS policy of its own, so any
   *direct* grant on one (which local `ALTER DEFAULT PRIVILEGES` was creating) is a
   cross-tenant read. 012 and the maintenance job now `REVOKE ALL` on every
   partition from the app role. Access to `audit_logs` is via the parent only.

**Partition job.** Ensures the current month + 12 ahead, skips existing, revokes
direct access on new ones, confirms `audit_logs_immutable` was inherited, and
exits 1 if `audit_logs_default` holds rows (2 if a create failed). First run:
created `2027_09`, 12 already present, default empty. Runbook in README, including
the hard date: without the job on a schedule, 2027-09-01 is when audit rows start
landing in the default partition.

**Seed.** 237 rows across 33 tenant tables (plus Heathrow and the Citation X+
added to the *global* catalog, since duplicating Gulfstream into the tenant would
have been wrong). Phase A resolves the reference catalog by natural key as the
owner; phase B writes the tenant through `SET LOCAL ROLE bitlux_app` + tenant
`set_config`, and refuses to run if the effective role would bypass RLS. Two runs
produce identical counts. Dates are relative to today (overdue tasks, a passport
expiring in 60 days) while ids stay fixed, so re-running refreshes in place.

**Bugs on the way, all caught by the scripts' own checks:** the first `users` row
cited `created_by = broker` before broker existed (self-referential table — the
bootstrap rows are now authored by nobody, which is also the truth); the deposit
invoice line had a different shape from the balance lines (the upsert now takes the
union of keys); the count loops asked `clients` for a `client_id` it doesn't have
(the tenant root keys on `id`); and — found only by re-running verify after a
rebuild — `audit_logs` doubled on every run, because immutable rows keyed
`(id, occurred_at)` were being given a `NOW`-relative `occurred_at`, so each run
inserted a *new* row under the same id. Immutable rows need timestamps as fixed
as their ids; they are now anchored inside 2026-09, the partition 012 always
creates. The lesson generalises: idempotency on an append-only table is a
property of the key, not of `ON CONFLICT`.

**Round-trip.** `downgrade base` correctly *refuses* over seeded data — 015's
downgrade deletes global airports that demo legs reference, and RESTRICT stops
it rather than cascading. On a clean database: 15 up, 15 down, no residue.

**Verification (`make verify-seed`, run as `bitlux_app` under RLS):** counts match
`expected_counts()` (computed from the same builder, never hand-maintained); the
BLX-2026-001 manifest is Priya Raman + Rafael Mendes; N650BX carries the insurance
and AOC certificates; two passports expire within 180 days; zero lapsed ratings;
zero overlapping legs on N650BX; and a seventh check confirms another tenant id
sees nothing. All PASS.

---

## 2026-09-14 — Sprint 2: SQLModel ORM and repository layer

**Prompt (abridged):** (0) Align `DATA_MODEL.md` §1.7 with the shipped role model,
one commit. (1) Bootstrap with `sqlacodegen --generator sqlmodels`, then refactor
into `app/models/` by migration cluster, with mixins, Python enums matching the
PG types, UUIDv7 `default_factory`, relationships for parent/child edges only,
plain deferrable FKs for the trip/quote/booking cycle, a read-only `AuditLog`,
and an id-only `__repr__`. (2) `app/repositories/` with a tenant-safe
`BaseRepository`, a contextvars `TenantContext` + transaction wrapper, and 17
concrete repositories. (3) `polymorphic.py`. (4) 13 named pytest tests against
the seeded DB. (5) Docs, commit. No FastAPI yet.

**Bootstrap, and what it was used for.** `sqlacodegen` needs a *sync* driver to
reflect, so it ran over `postgresql+psycopg://`, not the asyncpg URL. Its 3,305
lines (47 enums, 37 tables, 14 partition classes) were the reference for how
reflection renders the schema — which is exactly what `alembic check` compares
against. The committed modules were then produced by a generator that replays
migrations 003–012 against a recorder standing in for `alembic.op`, so every
`Column`, `CheckConstraint` and `Index` in the models is the same object the
DDL was built from; mixins, enums and relationships were layered on top. The
generator is not committed (it would invite regenerating over hand edits); the
sqlacodegen output was deleted once it had served, because a second set of
mapped classes for the same tables is a metadata collision waiting to happen.

**The bar: `alembic check` says "No new upgrade operations detected."** Models and
live schema agree on 37 tables, 381 indexes (partial `WHERE`s included), 47 enum
type names, server defaults, and both deferrable FKs. The one diff it found was
real: migration 012 sets the `audit_logs` table comment twice (`create_table`,
then `COMMENT ON`), and the model had the first.

**Design points worth knowing:**

- `client_id` is declared in exactly one file, `models/base.py` — `TenantColumnMixin`
  (NOT NULL) and `OptionalTenantColumnMixin` (catalog rows, audit_logs). Mixins
  use `sa_type` + `sa_column_kwargs`, never `sa_column`: a `Column` object can
  belong to one `Table`, so a mixin-level `Column` breaks on the second subclass.
- `pg_enum()` binds each Python enum to its PostgreSQL type by `__pg_name__` and
  persists *values*, not member names. Names matching is what keeps autogenerate
  from trying to recreate 47 enums.
- Relationships exist only where there is one FK path between the two tables
  (or the path is pinned with `foreign_keys`, as for `Trip.quotes` /
  `Trip.bookings`). Anything through `users` (owner + created_by + updated_by),
  self-references, the two-way trip↔empty-leg pair, and every polymorphic edge is
  a plain column.
- `AuditLog.__init__` raises; `before_update`/`before_delete` listeners raise;
  `AuditLogRepository.append()` inserts through Core and never instantiates the
  class. Three layers in Python before the database trigger even sees it.
- `BaseRepository._base_query()` always applies `deleted_at IS NULL` and
  `client_id = current_client_id()`. RLS is the guarantee; the predicate is
  defence in depth *and* the reason a missing context is an exception, not an
  empty list.
- `tenant_transaction()` uses `set_config(name, value, is_local => true)` — the
  bind-parameter-friendly spelling of `SET LOCAL`, same transaction scope.

**Tests: 16 passed**, each inside a rolled-back transaction, connected as
`bitlux_app` so RLS is real. Bugs the suite caught on the way:

1. A nested `tenant_transaction()` for tenant B left PostgreSQL believing the
   tenant was B after the block, while Python had reverted to the demo tenant —
   every query then returned nothing. `set_config(..., true)` is transaction-
   scoped, not savepoint-scoped, so the wrapper now records and restores the
   outer tenant on exit. This is the kind of bug that produces "no data" in
   production with no error anywhere.
2. A failed flush poisons its session by design; the ORM-level immutability
   check now runs in a throwaway session on the same connection.
3. My own arithmetic: BLX-2026-002's margin is 442,000, also under the 600,000
   threshold I had asserted would match only one trip.
