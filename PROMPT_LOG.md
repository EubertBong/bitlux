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

---

## 2026-09-14 — Sprint 3: FastAPI endpoints, RBAC, search, relationship graph

**Prompt (abridged):** App skeleton (`main`, `config`, `deps`, `api/v1/*`), Pydantic
schemas per resource, argon2 + JWT auth with rotation, a role→permission map,
`/search` on the tsvector indexes (no ILIKE), `/graph/{entity}/{id}` for D3 with a
200-node cap, one error shape with request-id logging, 13 httpx tests, docs. No
frontend. Also: note the duplicate 012 comment in the model; don't touch shipped
migrations.

**What was already there.** The working tree held ~7,700 uncommitted lines of this
sprint — the whole layout above, migration 016, schemas, 14 API tests — from a
session that stopped mid-router (`api/v1/invoices.py` imported a repository that
had never been written; the API had never imported, the tests had never run).
The choice was to review and finish it or to rewrite it. It was reviewed file by
file, its design held up, and it was finished. Not reading it and not rewriting
it were both wrong answers.

**Design points that survived review and are worth knowing:**

- **`auth_lookup_user()` is the one deliberate hole in tenant isolation.** Login
  must find a user by email before a tenant is known, which RLS forbids the app
  role. Migration 016 adds a `SECURITY DEFINER` function with `row_security = off`
  that does that lookup and nothing else; it is the only thing `bitlux_app` can
  execute across tenants. Everything after login is a normal tenant transaction.
- Refresh tokens are stateful (SHA-256 in `refresh_tokens`), rotated on every use;
  a replayed token revokes the user's whole family. Access tokens are 15-minute
  stateless JWTs, but every request re-reads the user row under RLS, so role
  changes and deactivation are immediate. The row's role, not the token's, decides.
- `_crud.install_crud()` builds the six standard operations once per resource
  from a `ResourceSpec`; domain routes are registered *before* it so literal
  paths like `/invoices/ar-aging` beat `/{item_id}`. Every mutation appends a
  redacted audit event; `[enc]` inputs are encrypted there and never travel further.
- `/search` OR-s `websearch_to_tsquery` with a prefix term on the last word so
  "gulf" finds Gulfstream. Trip/quote numbers got expression GIN indexes in 016 so
  number search is an index scan like every other type. Types the caller cannot
  view are dropped before the query runs.
- `/graph` skips node types the caller may not view and 404s an invisible root —
  the same "absent, not forbidden" rule as the rest of the API.

**What was wrong, in the order it was found:**

1. `InvoiceLineItemRepository` did not exist — where the previous session stopped.
2. `POST /auth/login` returned 422 for every demo user: pydantic's `EmailStr`
   (email-validator) rejects the reserved `.test` TLD. Replaced with a tolerant
   `EmailAddress` type (trim, lower-case, obvious shape); deliverability is not
   this layer's concern, and demo/staging tenants live on `.test`/`.local`.
3. `cand.role.value` blew up: `auth_lookup_user()` is raw SQL and asyncpg returns
   PostgreSQL enums as plain strings. `LoginCandidate` now coerces its three enum
   columns once, at the boundary.
4. Admin users were mounted at `/admin/admin/...` — `users_router` repeated the
   prefix. Found by listing the OpenAPI paths, not by a test. Now `/admin/users`.
5. Mine, this session: a `cat > README.md` ran after the shell's working directory
   had silently reverted to the repo root, overwriting the root README with the
   backend one. Git had it; restored, and every path in this sprint is absolute now.

**The finding: RLS was blocking the GIN indexes, and my first EXPLAIN write-up was
wrong.** The first `EXPLAIN` pass showed sequential scans on the tiny demo tables and
I wrote that this was table size and that `enable_seqscan = off` produced the GIN
plan. It did not: with seq scans disabled the planner walked btree indexes on
`client_id` instead — never `ix_contacts_search`. A 50k-row synthetic load
(inside a rolled-back transaction) still seq-scanned, and a first attempt at that
experiment was itself invalid because `ANALYZE` issued by `bitlux_app` is
silently skipped (non-owner), leaving the planner believing `client_id = …`
matched one row. Done properly — load and `ANALYZE` as the owner, plan taken after
`SET LOCAL ROLE bitlux_app` — the result was unambiguous and reproducible:

| who runs `WHERE search_tsv @@ query` | plan at 50,008 rows |
|---|---|
| owner (RLS bypassed) | Bitmap Index Scan on `ix_contacts_search`, 0.036 ms |
| `bitlux_app` (RLS enforced) | Seq Scan, ~15 ms |
| `bitlux_app` after `ALTER FUNCTION ts_match_vq LEAKPROOF` (experiment, rolled back) | Bitmap Index Scan on `ix_contacts_search`, 0.036 ms |

Mechanism: policy quals are security barriers and a non-`LEAKPROOF` operator cannot
be an index condition beneath one. `@@` is not leakproof (neither are `ILIKE`/`~~`).
So as shipped, `/search` could never use the indexes for the app role — the query
shape and the indexes were right, RLS stood between them. Fix: migration 017,
`search_ids(type, tsquery, limit)`, a `SECURITY DEFINER` function with
`row_security = off`, tenant-scoped by `current_client_id()` (the same trust root
RLS uses; unset ⇒ nothing), static SQL per whitelisted type, returning `(id,
rank)`; the repository joins those ids from a statement still under RLS. Tests
cover scoping, fail-closed, unknown type, and GIN eligibility of the inner
statement. The general rule is now in `DATA_MODEL.md` §1.7: any predicate that
must be indexed for the app role and uses a non-leakproof operator needs this
treatment, because a plain `WHERE` will seq-scan without a single error message.

**Verified:** 33 tests pass (19 repository + 14 API, all as `bitlux_app` in
rolled-back transactions); `alembic check` clean through 017; 117 paths / 190
operations in OpenAPI; live curl of login, `/search?q=gulf`, and
`/graph/client/<demo>?depth=2` (81 nodes, 117 edges, every node/edge in the D3
shape, every edge endpoint a node); the `EXPLAIN` table above.

**Also:** migration 016 is now described in `DATA_MODEL.md` (`refresh_tokens`, the
credential columns, `auth_lookup_user`, the new search indexes) — the previous
session had not done that, and the document's own rule is schema and doc in the
same commit. `backend/README.md` added. The API suite takes ~45 s because argon2id
at library defaults runs on every login fixture — acceptable, noted.

---

## 2026-09-14 — Sprint 4: frontend shell and the relationship visualiser

**Prompt (abridged):** Vite 6 + React 19 + TS 5.9 + Tailwind 4 scaffold with the
named libraries; auth (in-memory access token, HttpOnly refresh cookie, 401 →
refresh → retry once); permission-gated shell; skeleton pages for every route;
the D3 relationship graph as the hero, embedded as a tab on eight entity types;
⌘K global search; `/clients` + `/clients/:id` fully implemented as the reference
pattern; 15–20 Vitest/RTL tests; docs; screenshots. No other detail pages yet.

**Backend change the brief implied.** "Memory + refresh token in an HttpOnly
cookie" needs the API to *set* that cookie. `/auth/login` and `/auth/refresh` now
set `bitlux_refresh` (HttpOnly, path-scoped to `/api/v1/auth`, SameSite=Lax,
Secure outside local), `/auth/refresh` and `/auth/logout` accept it in place of a
body, and logout clears it. Body tokens still work for non-browser clients. The
SPA never sees the refresh token; the access token is a module-level variable in
`src/lib/api.ts`. Verified in the screenshot run: `localStorage` and
`sessionStorage` empty after login, `document.cookie` empty, the refresh cookie
present in the browser jar with `httpOnly: true`.

**Decisions worth knowing:**

- **A Client is the tenant** (DATA_MODEL 3.1) and RLS shows a user one tenant, so
  `/clients` lists the tenants you belong to — one row for the demo. The page
  still implements the whole pattern (URL-backed page/sort/filters, TanStack
  table, permission-gated create dialog) because that pattern is what Sprint 5
  copies onto the multi-row resources. The brief's tab list (Segments, Contacts,
  Passengers, Account Holders, Trips) only makes sense for the tenant root, which
  confirms the reading. "Archive" suspends rather than soft-deletes: soft-deleting
  the tenant root would hide it from RLS and lock everyone, including the
  archiver, out.
- **shadcn components are hand-written.** The CLI's flags changed again and it
  hung on a prompt; the components are ~250 lines of Radix + cva + `cn` and it is
  better to own them than to fight a generator.
- **The graph is SVG only.** The backend caps depth 2 at 200 nodes, comfortably
  inside SVG's budget; the brief allowed "SVG, virtualise if needed". Data
  preparation (`simulation.ts`) is renderer-agnostic if canvas is ever wanted.
- **D3 owns the numbers, React owns the DOM.** The simulation mutates node
  positions and bumps a counter once per animation frame; zoom is a transform on
  the inner `<g>`; drag behaviours are bound to the `<g>` elements React rendered.
- **Search groups are the brief's eight plus Manufacturers and Aircraft models**,
  otherwise the "gulf" demo returns nothing (Gulfstream is a manufacturer; the
  aircraft are tail numbers). Both got skeleton routes so hits land somewhere.

**Two backend bugs the browser found that the API suite could not.** The first
screenshot run stalled on the Relationship tab, and the API log explained why:

1. **Every login was silently rolled back.** `refresh_tokens` had zero rows and no
   `login` audit row existed, although `/auth/login` returned 200 every time. The
   handler runs `login_candidates()` *before* entering `tenant_transaction()`;
   that first statement autobegins a session transaction, `tenant_transaction`
   saw `in_transaction()` and treated itself as nested — a SAVEPOINT, released on
   exit — and the autobegun outer transaction was never committed, so the
   request-scoped session rolled it back on close. The test-suite is
   structurally blind to this: its sessions already live inside a savepoint
   chain where nothing ever needs a real commit to be visible. Fix: nesting is
   now tracked explicitly (a depth contextvar); the outermost call *owns*
   whatever transaction is open and commits it, savepoints are only for genuine
   nesting. Regression tests now drive login through the ASGI app with real
   per-request sessions and check visibility from a second connection, plus the
   exact autobegin shape on its own.
2. `GET /activities` (and `/documents`) returned 500: `metadata_: … Field(alias=
   "metadata")` with `from_attributes=True` made pydantic read `.metadata` off
   the SQLModel instance — SQLAlchemy's `MetaData` object, not the column.
   `validation_alias=AliasChoices("metadata_", "metadata")` reads the attribute
   and still accepts either spelling in JSON.

Both are the same lesson as Sprint 2's nested-tenant bug: the seams between
"works in the harness" and "works with real sessions" are where the silent
failures live, and only an end-to-end run finds them.

**jsdom versus a real browser, twice more.** (a) One vitest run kept ending with an
"unhandled" `TypeError` from inside React's `act()`; the trace bottomed out in
`d3-drag/src/nodrag.js`, which reads `event.view.document`, and user-event's
synthetic mousedown in jsdom has `event.view === null`. d3-drag runs its `filter`
before `nodrag`, so the drag filter now also requires an event that came from a
window — a no-op in a browser. (b) The ⌘K palette passed its RTL test and opened
in Chrome, yet Playwright's `getByLabel("Search query")` could not find the
input: cmdk labels its input with `aria-labelledby` pointing at its own
`<label>`, which is empty unless `Command` is given `label`, and `aria-labelledby`
beats `aria-label` in the accessible-name computation. RTL matches `aria-label`
directly, so jsdom was satisfied while every screen reader would have heard
nothing. `CommandDialog` now passes its title as the `Command` label. The
screenshot script also learned that Ctrl+K in headless Chrome is a *browser*
shortcut that navigates away — the shortcut is covered by the unit test; the
e2e path opens the palette by its button.

**Bugs the frontend suite caught:** binding d3-drag with a keyed data join
(`.data(nodes, d => d.id)`) crashed because d3 evaluates the key on the existing
React-rendered elements, which carry no datum yet — replaced with a per-element
`datum()` bind by `data-node` id. `.transition()` needs `d3-transition` imported
for its `Selection` augmentation.

**Verified:** 21 Vitest tests and 35 backend tests pass (graph: node/edge counts, type filter,
depth refetch, error+retry, click navigation; search: 200 ms debounce,
grouping/routing; clients: rows, paging, tabs, embedded graph; auth: redirect,
forbidden, manage-implies, login redirect; API client: 401→refresh→retry once,
give-up path, error envelope; nav gating; formatters). `tsc --noEmit` and eslint
(no `any`, no `@ts-ignore`) clean. Screenshots in `docs/screenshots/`: client
Relationship tab at depth 1 and 2 (81 nodes / 117 edges at depth 2 on the demo
client), ⌘K search for "gulf", client overview, dashboard.

## 2026-09-14 — UI polish: sidebar scroll, layout gap, top bar, theme toggle

**Prompt (abridged):** Four fixes, conservative, no redesign: (1) a thin, hover-only,
theme-matched sidebar scrollbar as a reusable utility class; (2) no white gap under
the sidebar when the main region scrolls; (3) real vertical padding and a separator
on the top bar, search input a consistent height, avatar centred, same on mobile;
(4) a light / dark / system theme toggle persisted under `bitlux-theme`, default
`system`, one class on `<html>`, the full shadcn token set plus the sidebar tokens
in both modes, graph legible in both. No layout, route, palette or component-API
changes; no new dependency unless needed.

**What changed and why:**

- **Scrollbar** — `.sidebar-scroll` in `src/index.css` (`@layer utilities`). Standard
  `scrollbar-width: thin` + `scrollbar-color`, transparent at rest and a 28%
  sidebar-foreground thumb on `:hover` / `:focus-within`; `scrollbar-gutter: stable`
  reserves the 10 px track so nav labels never sit under the thumb. The
  `::-webkit-scrollbar` rules are only a fallback inside
  `@supports not (scrollbar-color: auto)`, because Chrome 121+ ignores them once the
  standard properties are set and having both fight each other is how you get an
  always-visible bar.
- **Gap** — the shell is now `h-screen overflow-hidden`; the sidebar is `h-screen
  shrink-0` with the nav in the only sidebar scroller, and `<main>` is
  `min-h-0 flex-1 overflow-y-auto`. The window no longer scrolls, so the sidebar
  background always reaches the viewport bottom. The header dropped `sticky` because
  it no longer needs it. The mobile sheet nav uses the same scroll utility; the bottom
  tab bar was already `fixed` and is unaffected.
- **Top bar** — `h-14` became `py-3` + `shadow-xs`, keeping the `border-b`; the
  search trigger stays `h-9`, so the bar is 61 px tall with 12 px above and below the
  input. Avatar/name sit in the same flex row and centre with it.
- **Theme** — a 90-line `ThemeProvider` in `src/lib/theme.tsx` rather than
  `next-themes`: the requirement is small (read/write one key, toggle one class,
  follow `prefers-color-scheme` in system mode) and a dependency would have been the
  heavier choice. `index.html` applies the same rule in an inline script before
  first paint so there is no flash. `ThemeToggle` is the existing `DropdownMenu` +
  ghost `Button` with sun / moon / monitor, an `aria-label` that states the current
  mode, and a polite live region announcing changes. Sonner follows the resolved
  theme. Tailwind 4 has no `darkMode` config: the `@custom-variant dark` already in
  `index.css` is the v4 spelling of `darkMode: 'class'`.
- **Tokens** — light values are untouched. Added the missing
  `destructive-foreground`, `sidebar-primary(-foreground)`,
  `sidebar-accent-foreground`, `sidebar-border`, `sidebar-ring`, and full dark
  variants of every token including the sidebar set (the `.dark` block previously
  defined none of them). `color-scheme` is set per mode so native controls and
  scrollbars follow.
- **Graph / charts** — node circles were stroked `white`; now `var(--card)`, so the
  halo matches the card in dark mode. Labels, edges, arrowheads and the legend
  already used theme variables. The dashboard chart axes and tooltip now read
  `--muted-foreground` / `--popover`.
- **Console errors** — two showed up in the check. The missing favicon is now an
  inline SVG data URI. The other was the silent refresh on a browser that has never
  signed in: Chrome logs the resulting 401 as a console error. `lib/auth.tsx` now
  keeps a boolean `bitlux-session` hint in localStorage (set on login, cleared on
  logout) and only attempts the silent refresh when it is present. It is a flag,
  not a credential: the access token is still memory-only and the refresh token is
  still an HttpOnly cookie.

**Verification.** `npm run verify:ui` (`e2e/ui-polish.mjs`, also `make verify-ui`)
drives the running app in Chrome and asserts each requirement from computed styles
and DOM geometry — 23 checks, all passing: scrollbar thin/transparent at rest/themed
on hover/labels clear of the track; `<main>` is the scroller and the sidebar bottom
equals the viewport height on a long page at 1440×640 and on the 390-px mobile
layout; top-bar padding, border, `h-9` input, avatar offset < 2 px; theme default →
dark → reload → light → system with OS dark/light emulation → reload, each checking
`localStorage["bitlux-theme"]`, the `dark` class and the button label; the graph card,
label fill and edge stroke in dark mode; zero console errors across both themes.
Screenshots: `docs/screenshots/polish-{sidebar-scrollbar,long-page-bottom,topbar,theme-light,theme-dark,mobile-bottom}.png`.
`tsc --noEmit`, `eslint src` clean; 25 Vitest tests pass (4 new for the provider and
toggle).

**One test-environment finding.** Opening any Radix `DropdownMenu` under jsdom in
this suite — the theme menu or a bare one with no theme code — leaves work pending
that stalls the `afterEach` `act()` flush for ~15 s. The Vitest coverage therefore
exercises `setTheme()` directly and the toggle's trigger state, and leaves the
open/select/persist path to the Chrome script, where it is asserted for real.

## 2026-09-14 — Sprint 5A: deployment config (Render + Cloudflare Pages + Neon) and CI

**Prompt (abridged):** Dockerfile + `render.yaml`; `/health` with a DB probe (200 /
503, no auth, no tenant context); config reading `DATABASE_URL`, `CORS_ORIGINS`,
`JWT_*`, `REFRESH_COOKIE_*`; `make {migrate,seed,partition-maintenance,db-check}-prod`;
monthly partition workflow; Cloudflare `_headers` / `_redirects` and a build-time
`VITE_API_BASE_URL` guard; CI for both halves; `docs/DEPLOY.md`; README; commit. Do
not deploy.

**Where the brief and the codebase disagreed, and what was done:**

- **`DATABASE_URL` vs `APP_DATABASE_URL`.** The brief asked the runtime to read plain
  `DATABASE_URL`. That name is the schema *owner* (alembic, seed, maintenance);
  the API must connect as `bitlux_app`, because superusers and `BYPASSRLS` roles are
  not bound by the tenant policies and Neon's console roles carry `BYPASSRLS`.
  Collapsing the two would have deployed the API with tenant isolation silently
  off. Kept `APP_DATABASE_URL` for the runtime, made `render.yaml` ask for that
  name, and added a startup check that refuses to serve as a role with
  `rolsuper`/`rolbypassrls` (verified: the image exits with a clear message when
  given the owner URL). Every other variable now accepts the plain name the brief
  lists as well as the `APP_` form. In non-local envs, an unset
  `APP_DATABASE_URL` and `SameSite=none` without `Secure` are startup errors.
- **CORS parsing was broken for the documented format.** pydantic-settings insists
  a `list[str]` env value is JSON, so the comma-separated form in `.env.example`
  raised at startup and the `_split_csv` validator never ran. `NoDecode` +
  a validator that accepts both forms and strips trailing slashes.
- **Neon URLs would have crashed the engine.** SQLAlchemy forwards unknown query
  parameters to `asyncpg.connect()`, which has no `sslmode` or `channel_binding`.
  `asyncpg_engine_args()` rewrites the scheme, drops both, and maps `sslmode` onto
  asyncpg's `ssl=`. asyncpg's own DSN parser (used by the scripts) accepts both.
- **Dockerfile.** As specified, plus: two `uv sync` passes (`--no-install-project`
  before `COPY . .`) so the dependency layer caches; `PORT` honoured because
  Render injects it; `.dockerignore` keeps `.venv`, `.env` and tests out of the
  context. Image is ~1 GB because `build-essential`/`libpq-dev` stay in the final
  layer as the brief specified; a multi-stage build would halve it.
- **`render.yaml`** adds `APP_ENV=production` (without it the dev-default secret
  check does not run) and `FIELD_ENCRYPTION_KEY` (`generateValue`), which the brief
  omitted and which the startup check requires.
- **CI** runs from `backend/` with `--extra dev` (pytest is an optional extra, not a
  dependency group), publishes the Postgres port, creates the `bitlux_app` role
  from the same initdb SQL docker-compose uses, and runs migrate → check →
  partition-maintenance → seed → verify-seed → pytest, because the test-suite runs
  as `bitlux_app` against seeded data. The frontend job also runs `npm run build`
  with the variable set so the guard is exercised. The whole backend job was
  rehearsed locally against a throwaway `postgres:16` on :5434: all green.
- **Cloudflare** files as specified; `vercel.json` removed. The build guard uses
  `loadEnv` merged with `process.env` so `frontend/.env` still satisfies it locally.
- **Ops scripts.** `scripts/db_check.py` (SELECT 1, role kind, server version,
  alembic head, `bitlux_app` state) and `scripts/app_role.py` (idempotent
  `bitlux_app` LOGIN role + grants, prints the `APP_DATABASE_URL` to paste into
  Render), because Neon has no initdb hook. `*-prod` targets refuse an unset or
  localhost `DATABASE_URL` and echo the redacted target first.
- **Runbook corrections.** Demo credentials are `owner@demo.test` / `Demo!2026`
  (not `demo@demo.test`); the cookie is `bitlux_refresh` on `Path=/api/v1/auth`;
  migration 001 creates only `citext` and `ltree`. Added the third-party-cookie
  caveat: `*.pages.dev` → `*.onrender.com` is cross-site, so Safari and strict
  browsers drop the refresh cookie; custom domains on one site are the real fix.

**Verification (nothing deployed).** 35 backend tests; frontend tsc/eslint/25 tests;
`docker build` of the Render image and four runs: `/health` 200 as `bitlux_app`
with production settings, preflight from the Pages origin allowed with
credentials, login `Set-Cookie ... SameSite=none; Secure`; `/health` 503 with the
database unreachable; refusal to start as the owner; clear error with
`APP_DATABASE_URL` unset. `vite build` fails without `VITE_API_BASE_URL` and
succeeds with it, `dist/` containing `_headers` and `_redirects`. `make
db-check-prod` / `app-role-prod` exercised against the local stack (password
restored). YAML parsed; `uv sync --frozen --extra dev` resolves.

## 2026-09-14 — Encryption placeholder scope stated explicitly

**Prompt (abridged):** Before deploying, document that the seed's `[enc]` values are
a placeholder, not ciphertext: new DATA_MODEL §1.2.1, a README "Known limitations"
bullet, a frontend/API note that raw `[enc]` values are never returned, PROMPT_LOG.

**What the code actually does (checked, not assumed):** `scripts/seed.py::enc()`
returns `b"demo-plaintext:" + value` — marked plaintext, not Fernet output, with a
docstring that already said so (now sharpened). The API is further along than the
brief assumed: `_crud.py` encrypts `[enc]` inputs on write via `crypto.encrypt()`
(one Fernet key derived from `APP_FIELD_ENCRYPTION_KEY`), read schemas expose only
`*_last4`, `redress_number` is never exposed, `crypto.decrypt()` has no caller, and
audit snapshots pass through `crypto.redact()`. So §1.2.1 says "single static key
at the API layer, placeholder in the seed, no KMS / per-tenant DEK / rotation /
authorised decrypt path" rather than "no encryption", and lists what production
adds. No code behaviour changed.

## 2026-09-14 — backend/Makefile: production targets referenced by DEPLOY.md

**Prompt (abridged):** Add `db-check-prod`, `app-role-prod`, `migrate-prod`,
`seed-prod`, `partition-maintenance-prod` to `backend/Makefile` with a shared guard
(refuse unset / localhost `DATABASE_URL`, echo target + redacted url, use `.venv`),
psql-based `db-check-prod`, an idempotent role target that grants DML on all tables,
and verify `make venv / test / migrate / seed` still work.

**Premise corrections.** There was no `backend/Makefile`; the targets already existed
in the root Makefile from Sprint 5A. Rather than keep two copies, `backend/Makefile`
now owns every backend/database target (local and `*-prod`) and the root Makefile
delegates to it (`make X` == `make -C backend X`), so the runbook's root-level
commands still work and each recipe exists once. The requested blanket
`GRANT SELECT/INSERT/UPDATE/DELETE ON ALL TABLES` was **not** implemented: migration
015 asserts `bitlux_app` holds no UPDATE/DELETE on `audit_logs` (append-only), and
per-table DML is granted deliberately by each migration via `grant_app_dml()`.
`app-role-prod` grants CONNECT, schema USAGE and the read+append default
privileges — identical to `docker/initdb/10-app-role.sql` — and leaves DML to the
migrations. `db-check-prod` moved to pure `psql` (SELECT 1, server, role kind,
`bitlux_app` exists/LOGIN/BYPASSRLS/superuser, alembic head), so
`scripts/db_check.py` was removed; `psql` is now a documented prerequisite.
Redaction keeps the username (`user:****@host`) rather than the brief's
`s/:[^@]*@/:****@/`, which also swallowed the scheme's `//user`.

**Found while verifying.** `uv venv` (0.12) refuses to replace an existing `.venv`
without `--clear`, so `make venv` could never rebuild in place; fixed. The venv had
in fact been rebuilt without the editable project install by the previous sprint's
lock check, which is why the first `seed-prod` run failed on `import app`;
`make venv` restored it (now on uv's Python 3.12).

**Verified.** Guards: empty, unset (falls to the local default), explicit
`127.0.0.1`, from root and from `backend/`. Prod recipes exercised for real against
the compose container's bridge address (not localhost, so the guard passes):
`db-check-prod` as owner (RLS BYPASSED, head 017) and as `bitlux_app` (RLS enforced),
`app-role-prod` without password (refused) and with (role updated, URL printed,
dev password restored afterwards), `migrate-prod`, `partition-maintenance-prod`,
`seed-prod` with countdown. Local: `make venv`, `migrate`, `partition-maintenance`,
`seed`, `verify-seed` (ALL PASS), `test` (35 passed) from root and standalone.

## 2026-09-14 — Fix: owner membership in bitlux_app for SET LOCAL ROLE on Neon

**Prompt (abridged):** `make seed-prod` on a fresh Neon database fails with
`permission denied to set role "bitlux_app"` at `_db.enter_tenant()`. Grant the
owner membership in `app_role.py`, make the failure message explain itself, add a
test, note it in DEPLOY.md.

**Why it never showed locally or in CI:** both use a real superuser as the owner,
and a superuser may `SET ROLE` to anything. Neon's owner is a `neon_superuser`
member, not a superuser, so PostgreSQL requires explicit membership. (The brief's
"even a superuser" is not quite right, but the fix is.)

**Change.** `scripts/app_role.py` now exposes `ensure_app_role(conn, password)`
(create/alter, CONNECT, USAGE, default privileges, `GRANT bitlux_app TO
CURRENT_USER`, then verifies the state and reports `owner_is_member`); the CLI exits
1 if the role is not LOGIN / NOBYPASSRLS / member-granted. `enter_tenant()` catches
`InsufficientPrivilegeError` on `SET LOCAL ROLE`, prints the remedy (`make
app-role-prod` or the GRANT), and re-raises. New `tests/scripts/test_app_role.py`
runs as the owner, re-sets the password to the one already in `APP_DATABASE_URL`
(a no-op, so the rest of the suite is unaffected), asserts an explicit
`pg_auth_members` row -- `pg_has_role()` is vacuously true for a superuser and
would have passed before the fix -- proves `SET LOCAL ROLE` works, checks
idempotency (one membership row after two runs), and checks the printed URL uses
`postgresql+asyncpg://`. Verified the original error and the new message by
connecting as a temporary non-superuser owner without membership, then with it.

## 2026-09-14 — Actions layer, phases 1–2: action primitives and Contacts CRUD

**Prompt (abridged):** The app reads as a viewer. Build the "actions layer" in
phases, stopping after each for review. Phase 1: reusable primitives in
`components/actions/` (CreateButton, EditButton, DeleteButton, ActionMenu,
ConfirmDialog, ResourceForm) — permission-gated via RequirePermission, success
toasts with the entity name, cache refresh, field-level 422 mapping, explicit
403/404 handling, Undo for soft delete, audit via the API. Phase 2: wire it onto
Contacts as the reference (list with search/filters and a ⋯ menu, first-run empty
state, detail with Edit/Delete and log call/email/meeting, `/contacts/new` and
`/contacts/:id/edit`). Commit `feat: action primitives and Contacts CRUD`; show
`/contacts` empty, list, create dialog, detail-with-edit.

**Design.** One registry (`components/actions/registry.ts`): each entity module in
`src/entities/` registers its endpoint, route, permission prefix, name function,
optional archive status and a form descriptor (Zod schema + field metadata +
record↔payload mapping). The primitives read the registry and never special-case
an entity, so Phases 3–5 are entity modules plus pages. `ResourceForm` builds the
form from the descriptor, validates with Zod, maps FastAPI's `["body", field]`
422 locs onto the fields and toasts anything unmapped; `lib/errors.ts` words
403 (permission or tenant boundary) and 404 explicitly and always shows the API's
`code` and `message`. `RequirePermission` gained a `fallback` prop so buttons can
use the same primitive as pages and simply not render. **Archive vs Delete**:
the schema's one removal primitive is soft delete, so Delete = soft delete with a
5-second Undo (a new `POST /{resource}/{id}/restore`, audited as `restore`);
Archive follows the existing Clients convention and is a reversible status
transition (`dormant` for contacts) — Phase 7's "bulk archive (soft delete)" will
be reconciled with that when it comes.

**Backend additions (all tested, 43 API+repo tests pass):** the restore endpoint;
`?q=` on list endpoints for searchable resources, routed through the same
`search_ids()` SECURITY DEFINER path as `/search` so the GIN index is usable under
RLS and equality filters combine with it; `GET /admin/users/lookup` (id, name,
role of active colleagues) for owner/assignee pickers without `users.view`, which
would expose emails.

**Choices the brief left open.** "New Contact" is gated on `contacts.create`, the
permission the API enforces, not `contacts.edit`. The detail tabs are Overview |
Passengers | Documents | Activities | Relationship: "Application" in the brief had
no referent in the model, so the contact's linked passengers took the slot — easy
to rename. Segment and owner pickers hide themselves for roles that cannot list
the source. "Add passenger" on the contact header waits for Phase 3's entity.

**The Radix test stall, solved.** Opening any Radix DropdownMenu under jsdom took
~12 s (the earlier theme sprint worked around it). A CPU profile put the time in
jsdom's selector engine: `nwsapi` 2.2.27's `:fullscreen`/`:modal` pseudo-class
matching. Pinning `nwsapi` to 2.2.16 via package.json `overrides` brings a menu
open to ~60 ms, so menu-driven flows are now testable; the theme-toggle test
exercises the real menu again.

**A bug the tests caught.** Passing the loaded record through react-hook-form's
`values` prop reset the text inputs but left Controller-driven selects empty, so
editing a contact whose status was not the default could not be saved. The forms
are now keyed on the record and take it as `defaultValues`; the walkthrough
asserts the edit dialog shows a `prospect` contact's status and owner.

**Verification.** tsc, eslint, 35 Vitest tests (10 new: rows, first-run empty
state, q= + filters, create with derived display_name and toast, Zod then server
422 on the right fields, ⋯ Delete → confirm → DELETE + Undo toast, ⋯ Edit →
PATCH, detail header + tabs + Delete, log call → POST /activities bound to the
contact and user, read-only role sees no actions). `e2e/contacts-shots.mjs`
against the live app: empty state (list request stubbed), real list, q= search,
row-menu Edit showing a non-default status, create (201, toast, list refresh),
log call (201, appears), edit page (PATCH 200), delete (204) → Undo (restore 200)
→ row back, row-menu delete, no console errors. Screenshots:
`docs/screenshots/contacts-{empty,list,create,detail-edit}.png`.

## 2026-09-15 — Actions everywhere (Part 1 of the demo-readiness brief)

**Prompt (abridged):** Every list and detail page should carry visible, plausible
action buttons — wired where the API supports the operation, and *disabled with an
explanation* where it does not. Standard list header (New, ⋯ Actions, filters,
search, column chooser, CSV export), row checkbox + ⋯ menu (View / Edit /
Duplicate / Archive / Delete, in that order), standard detail header (Back, title,
status, Edit / Delete / ⋯ More) with a per-entity More menu, and "+ Add" on section
headers. Rule: no button that does nothing without explanation.

**How it was built.** The Sprint-6 registry already described entities; this extends
it rather than adding page-by-page code. New optional fields on an entity config:
`icon`, `statuses`, `moreActions`, `sections`, `hideFields`, `readOnly`, and `form`
became optional. A `MoreAction` is one of four kinds — `patch` (confirm then PATCH,
or POST to a resource route like `/tasks/{id}/complete`), `dialog` (a small
ResourceForm that PATCHes or POSTs), `link` (mailto/route), or `planned` (disabled,
with the reason). `SectionSpec` describes a related collection with an optional
inline "+ Add" form. The generic `resources.tsx` pages were rewritten from the old
skeleton into real list/detail pages driven entirely by that data, so every entity
gained the full vocabulary at once.

**Honesty rules, applied literally.** `PLANNED = "Coming in a future sprint"` is the
one wording. A disabled control is always wrapped in `<Planned>`, which puts the
reason in a tooltip *and* a `title` (a disabled button drops pointer events, so the
wrapper span carries them). Menu items that are planned stay visible, disabled, and
labelled. Where a reason is specific it says so, e.g. Trips → Generate quote reads
"Quote-from-trip endpoint is not in the API yet", Aircraft → Upload document reads
"File upload (S3 presign) is not in the API yet". Nothing shows a "coming soon"
toast: either it works or it is visibly disabled.

**Wired (API-backed) vs planned.** Forms exist for contacts, passengers, trips,
aircraft, operators, quotes, tasks and empty legs; those get working New / Edit /
Duplicate. Entities without a form (airports, crew, bookings, documents, account
holders, manufacturers, aircraft models, segments, users) keep the buttons but
disabled; delete still works where the API allows it. The audit log is `readOnly`,
so even Delete is disabled there. Per-entity More actions that are real: contact
log-activity / mailto / add-to-segment; passenger add-travel-document (nested POST)
and mark-inactive; aircraft change-status and assign-operator; operator
add-safety-rating (nested POST), update-insurance, set-primary-contact; trip
advance-status (walks draft → sourcing → quoted → confirmed → in_progress →
completed); quote send / revise (`POST /quotes/{id}/supersede`) / accept / decline;
invoice send / record-payment (`POST /payments`) / void; task complete
(`POST /tasks/{id}/complete`) / reassign / snooze / set-due-date; empty leg publish /
hold / expire.

**Two things added beyond the brief, both to serve its goal.** (1) List ⋯ Actions
does real work — CSV export of the rows on screen (visible columns only), a column
chooser, and refresh — rather than being another stub. (2) Detail pages resolved
`*_id` columns to raw UUID fragments, which reads as plumbing; `lib/fkLabels.ts` now
looks up only the collections a given record references, skips any the role cannot
read, and renders a link. "Account Holder: 9543ec19…" became "Halcyon Capital
Partners".

**Backend.** No new endpoints. Four more list endpoints became searchable
(`airports`, `documents`, `manufacturers`, `aircraft_models`) by declaring their
existing `search_type`.

**A test-suite fix worth recording.** Four backend tests asserted the seed's exact
contact count (`== 8`). The demo database is also clicked through by hand — a
contact created in the UI made them fail — so they now assert relative to the
tenant's own count (pagination arithmetic from the reported total, subset checks for
the segment filter, and a baseline captured before the tenant-isolation write). The
test intent is unchanged; the brittleness is gone. No demo data was deleted.

**Verification.** 43 backend tests, 40 frontend tests (5 new for the generic pages:
disabled New with the planned hint, wired New that POSTs, row-menu order and
disabled states, detail header + More with a wired Complete, planned items and
section "+ Add"), tsc and eslint clean. `npm run verify:actions`
(`e2e/actions-shots.mjs`) drives the live app: 14 checks covering header actions,
row-menu order, CSV download, detail header, wired vs planned More items, the
disabled-New tooltip text, the empty state, and the graph tab, with no console
errors. Screenshots: `docs/screenshots/actions-*.png`.

## 2026-09-15 — Navigation wiring, cursors and hover states

**Prompt (abridged):** Audit every route and every navigation systematically, fix
the breaks (dashboard KPIs, table primary columns, graph edges and empty state,
back buttons, tab state in the URL, ⌘K results, sidebar, user menu), add a route
smoke test; then make everything clickable show a hand cursor with a matching
hover state, and convert or fix any non-semantic click targets; add
navigation.test.tsx and cursor.test.tsx.

**The audit.** 49 routes (printed in the handover message); every `<Link>`,
`navigate()` and `href` call site was checked against that table. Nothing pointed
at a non-existent path. What was actually broken was narrower and more specific:

- **Dashboard KPI tiles were not links at all.** They are now whole-card links
  (`<Link data-clickable-card>`), seven of them, each to the list it counts.
  Two needed views the API had but the UI did not expose, so `/documents?expiring=30`
  and `/tasks?assigned=me` now map to the existing `/documents/expiring` and
  `/tasks/my-queue` endpoints and show a removable chip, rather than linking to an
  unfiltered list and quietly lying about the number.
- **Back buttons used `history.back()`**, which lands outside the app when a detail
  page is reached by a deep link or a refresh — exactly when a back button matters.
  `BackLink` is now a real `<Link>` to the parent list and names it ("Back to Trips").
  The same fix applied to the create/edit form pages.
- **Switching tabs replaced the whole query string.** Tabs now merge into the
  existing params and use `replace`, so `?tab=relationship&foo=bar` keeps `foo` and
  the tab survives a refresh.
- **Graph edges were decorative.** An edge is now a keyboard-reachable button that
  opens the record it points at, with a transparent 12px hit line over the 1.4px
  hairline. The graph also had **no empty state**: zero nodes rendered a blank
  canvas. It now explains why and offers the way back, with the list route taken
  from the entity registry (hand-pluralising gives "aircrafts" and "crew-members").
- **The user menu had only Sign out.** Profile and Admin were added, and
  `/settings/profile` is a real page (identity, role, timezone, theme, and the
  full permission list grouped by resource) rather than a stub.
- **The login page had no heading element** — its title was a `<div>` — so no page
  announced itself to assistive tech. `CardTitle` gained `asChild` and the login
  title is now the page's `<h1>`.

**Cursors.** The rules live in `src/styles/interactive.css` as plain CSS, imported
by `index.css`. Plain, not Tailwind, so the test can load the shipped file verbatim
and assert against the real selectors instead of a copy of them. Every rule pairs a
cursor with a visible hover state: cards lift and take a ring border, rows tint,
links underline. `aria-disabled` and `:disabled` get `not-allowed`, which is what
makes the "Planned" buttons from the last sprint read correctly.

**One thing the browser caught that jsdom could not.** `cursor` is an inherited
property, so every `<span>`, `<svg>` and `<path>` inside a button reports
`pointer`. The first pass of the "nothing inoperable looks clickable" check
flagged those as offenders. Both the unit test and the browser check now judge only
elements with no operable ancestor. The a11y audit itself came back clean: all four
non-semantic `onClick` sites already had `role`, `tabIndex` and an Enter/Space
handler, or were `<button>`/`<Link>` already.

**Tests.** `src/test/navigation.test.tsx` renders the real `<App/>` and covers 64
cases: every sidebar item clicked and asserted to reach a heading, every list and
detail route in the table, group labels asserted *not* to be links, active-section
marking, the user menu's three entries, deep-linked tabs, the explicit back link,
a genuinely unknown path reaching the 404 page with a way out, and a no-console-errors
pass. `src/test/cursor.test.tsx` adds 6. Frontend total is now 110 tests.
`npm run verify:nav` (`e2e/nav-shots.mjs`) repeats 25 of these in Chrome, including
the hover box-shadow actually changing, an edge click navigating, and a ⌘K result
landing on a detail page.

**Not done, deliberately.** Breadcrumbs. The brief said "from the earlier sprint if
implemented" — they were never implemented. A full `Home > Clients > Demo Brokerage
> Contacts > John Smith` trail needs each intermediate record resolved per route;
the back link covers the real need. Recorded in README's known limitations.
