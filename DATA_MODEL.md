# Bitlux CRM — Data Model Design

## Context

This is the authoritative logical data model for the Bitlux CRM — a private aviation (charter
brokerage) CRM. It is the source that the Alembic migration set under `backend/alembic/versions/`
is generated from, and the reference that ORM models and API resources must agree with.

**If you change the schema, change this document in the same commit.**

The business the schema has to represent: a brokerage sells charter flights. It keeps a book of
**clients/contacts**, knows which **passengers** actually fly and who **pays** for them, sources
aircraft from third-party **operators** whose **safety ratings** gate whether they may be used,
assembles **trips** out of **legs**, and turns a **quote** into a **booking** into an **invoice**.
Everything is regulated-adjacent: passport expiry, crew currency, insurance certificates, and
manifest records must be retrievable and provably unmodified, which is why documents and audit
logs are first-class rather than bolted on.

**Locked decisions (from user):**
- **PostgreSQL 16** — native `ENUM`, `JSONB`, partial/GIN/GiST/BRIN indexes, `citext`, `ltree`,
  exclusion constraints, declarative partitioning, `UNIQUE NULLS NOT DISTINCT`. Every feature this
  model relies on is verified available in PG16 in §1.4. Production is Neon (PG16); local dev is
  the `postgres:16` container in `docker-compose.yml`.
- **Client = tenant root.** Each `clients` row is a brokerage using the CRM. Every operational
  table carries `client_id` and is isolated by Row-Level Security.
- **UUIDv7 primary keys** everywhere, **generated in the application layer** (Python
  `uuid-utils`), never by the database. No column has a UUID default — see §1.5. Time-sortable,
  index-friendly, safe to expose, no cross-tenant ID enumeration.
- **Soft delete + append-only audit log + versioned (immutable-revision) quotes.**

---

## 1. Conventions

### 1.1 Standard columns

Every **tenant-scoped** table carries this block. It is omitted from the per-table specs below —
assume it is present unless a table explicitly says otherwise.

```
id           uuid         PK -- no DB default; app supplies UUIDv7 (§1.5)
client_id    uuid         NOT NULL, FK clients(id) ON DELETE RESTRICT
created_at   timestamptz  NOT NULL DEFAULT now()
updated_at   timestamptz  NOT NULL DEFAULT now()   -- maintained by trigger
deleted_at   timestamptz  NULL                     -- soft delete tombstone
created_by   uuid         NULL, FK users(id) ON DELETE SET NULL
updated_by   uuid         NULL, FK users(id) ON DELETE SET NULL
```

And the matching standard indexes:

```
IDX  (client_id)                                  -- tenant scan
IDX  (client_id, created_at DESC)                 -- default list ordering
IDX  (client_id, id) WHERE deleted_at IS NULL     -- live-row covering probe
```

### 1.2 Rules that apply model-wide

| Rule | Decision |
|---|---|
| Money | `bigint` **minor units** (cents). Never `float`. Every money-bearing table also stores `currency char(3)` (ISO 4217) — no enum, the list is too volatile. |
| Time | `timestamptz` for instants. `date` for calendar-only facts (passport expiry, invoice due date). Flight times additionally store `*_timezone text` (IANA) so local wall-clock can be reconstructed after a tz database change. |
| Distance/weight | `int` nautical miles, `numeric(6,1)` kg. Store one canonical unit; convert at the edge. |
| Case-insensitive text | `citext` for emails, codes, tail numbers, slugs, document/quote/invoice numbers. |
| Soft delete | `deleted_at IS NULL` is the live predicate. All uniqueness constraints are **partial** on it, so a deleted row does not block reuse of its number. |
| Uniqueness | Every business-key unique index is scoped `(client_id, …)`. Nothing is globally unique except the shared reference catalog. |
| FK delete behavior | `RESTRICT` by default (soft delete is the real deletion path). `SET NULL` for optional attribution (`created_by`, `owner_user_id`). `CASCADE` only for owned child rows that cannot exist alone (`quote_line_items`, `contact_channels`, junctions). |
| RLS | `USING (client_id = current_setting('app.client_id')::uuid)` on every tenant table. Shared-catalog tables use `USING (client_id IS NULL OR client_id = current_setting('app.client_id')::uuid)`. |
| Enums | Native PG `ENUM`. Values are `snake_case`. Enums are **append-only** in migrations (`ALTER TYPE … ADD VALUE`); a value is never renamed or removed once shipped. |
| JSONB | Used only for genuinely open-ended attribute bags (preferences, amenities, feature flags). Never for anything that gets filtered, joined, or reported on. |
| Encryption | Fields marked **[enc]** are encrypted application-side (envelope encryption, tenant-scoped DEK), stored `bytea`, with a plaintext `*_last4` for display/search. Passport numbers, KTN, tax IDs, crew license numbers. What this test project actually implements: §1.2.1. |
| Search | `search_tsv tsvector GENERATED ALWAYS AS (…) STORED` + GIN on the entity tables users type into (contacts, passengers, operators, aircraft, airports; manufacturers and aircraft models since 016). Trip and quote numbers use expression GIN indexes on `to_tsvector('simple', …)`. `/search` uses `websearch_to_tsquery` plus a prefix term; nothing uses `ILIKE`. |

### 1.2.1 Encryption status (test project scope)

The `[enc]` columns in this schema (`travel_documents.number`,
`passengers.known_traveler_number`, `passengers.redress_number`,
`account_holders.tax_id`, `crew_members.license_number`) are **designed** for
per-tenant envelope encryption with a KMS-managed key hierarchy: a Data Encryption
Key per tenant, wrapped by a master Key Encryption Key that never leaves the KMS.

What this test project actually ships:

- The columns are typed `bytea` as designed, and the `*_last4` companion columns
  are populated correctly everywhere.
- **The API encrypts on write** (`app/api/v1/_crud.py` → `app/security/crypto.py`)
  with a **single Fernet key** derived from the `APP_FIELD_ENCRYPTION_KEY` string.
  There is no per-tenant key, no KMS, and no rotation or re-encryption path.
- **The API never decrypts and never returns the raw column.** Read schemas expose
  only the `*_last4` variant; `redress_number`, which has no last4 column, is not
  exposed at all. `crypto.decrypt()` exists but has no caller.
- **The demo seed does not encrypt.** `scripts/seed.py` writes
  `b"demo-plaintext:" + value` into the `[enc]` columns through `enc()`, a
  placeholder whose docstring says so. Those bytes are not Fernet ciphertext and
  cannot be decrypted; nothing reads them, and the `*_last4` columns beside them
  carry the display value. The seed must never be pointed at real data.
- Audit `before`/`after` snapshots drop these fields (`crypto.redact()`), so the
  trail never carries plaintext, as §1.2 and §5 require.

Production deployment would additionally require:

- A KMS (AWS KMS, GCP Cloud KMS, HashiCorp Vault) holding the master KEK.
- Per-tenant DEKs wrapped by that KEK, cached per process, with a key-id stored
  next to each ciphertext so rotation can re-wrap without a full rewrite.
- A repository-layer wrapper replacing the current single-key calls: encrypt on
  write with the tenant's DEK, decrypt on read **only** on explicitly authorised
  paths (manifest filing, document verification), each decrypt audit-logged.
- Audit-log redaction for `[enc]` fields (already enforced; see above).
- A seed path that either uses the real wrapper or leaves the `[enc]` columns NULL.

### 1.3 Shared reference catalog

`manufacturers`, `aircraft_models`, `airports`, and `fbos` are **shared reference data with tenant
overrides**: `client_id` is **NULLABLE**.

- `client_id IS NULL` → global catalog row, readable by every tenant, writable only by the platform.
- `client_id = <tenant>` → tenant-private row (a bespoke type, a private strip, a custom FBO).

Uniqueness uses `UNIQUE NULLS NOT DISTINCT (client_id, <key>)` (PG15+) so a tenant may add its own
`KJFK` without colliding with the global one.


### 1.4 PostgreSQL 16 feature confirmation

Every non-baseline feature this model depends on, and the version that introduced it. All are
available in PG16, which is what both Neon and the local container run.

| Feature | Used by | Introduced | PG16 |
|---|---|---|---|
| `citext` extension | emails, codes, tail numbers, slugs, invoice/quote numbers | 8.4 (contrib) | yes |
| `ltree` extension | `segments.path` materialized ancestry | 7.3 (contrib) | yes |
| `btree_gist` extension | `=` on `uuid` inside the GiST EXCLUDE constraint | 8.2 (contrib) | yes |
| Native `ENUM` types | the whole §2 catalog | 8.3 | yes |
| `ALTER TYPE ... ADD VALUE` | append-only enum evolution | 9.1 | yes |
| Partial indexes (`WHERE`) | every soft-delete-scoped unique index | 7.2 | yes |
| Expression indexes (`lower(x)`) | case-insensitive business keys | 7.4 | yes |
| GIN indexes | `tsvector` search, `text[]` type ratings, `jsonb_path_ops` | 8.2 | yes |
| GiST indexes | `point` location, `ltree` path, EXCLUDE constraints | 8.2 | yes |
| BRIN indexes | `audit_logs.occurred_at` time-range scans | 9.5 | yes |
| `EXCLUDE USING GIST` | non-overlapping `aircraft_operator_assignments` | 9.0 | yes |
| Declarative RANGE partitioning | `audit_logs` monthly partitions | 10 | yes |
| `DEFAULT` partition | `audit_logs` overflow catch-all | 11 | yes |
| Row triggers on partitioned tables | `updated_at`, audit immutability | 13 | yes |
| Generated columns (`STORED`) | `margin_cents`, `balance_cents`, `search_tsv`, `location` | 12 | yes |
| Row-Level Security + `FORCE` | tenant isolation (§1.7) | 9.5 / 9.5 | yes |
| `UNIQUE NULLS NOT DISTINCT` | shared reference catalog keys (§1.3) | **15** | yes |
| `num_nonnulls()` | exclusive-arc CHECK on `travel_documents` | 9.6 | yes |
| `gen_random_uuid()` in core | not used — see §1.5 | 13 | yes |

The one thing that is **not** available in PG16 is a built-in `uuidv7()` (PG18). That is precisely
why identifiers are generated in the application — see §1.5.

### 1.5 Identifier generation — application-side UUIDv7

**Decision:** UUIDv7 values are generated by the Python application using the `uuid-utils`
package. No `DEFAULT` clause of any kind appears on a primary key column, and no UUID extension
(`pg_uuidv7`, `uuid-ossp`) is installed.

```python
import uuid_utils

new_id = uuid_utils.uuid7()          # time-ordered, RFC 9562
```

Why:

- **PG16 has no native `uuidv7()`.** The alternative is the third-party `pg_uuidv7` extension,
  which Neon does not offer and which would have to be built into the local image too. Requiring
  a non-core extension for something as fundamental as a primary key is a poor dependency.
- **The application needs the ID before the INSERT.** Creating a trip, its legs, and its quote in
  one transaction means the parent ID must exist in Python before any row is written. A DB-side
  default would force a `RETURNING` round-trip per row and rule out batch inserts.
- **Tests and fixtures become deterministic.** Seed data and factories can pin IDs.

Consequences the implementation must respect:

- Every SQLModel/SQLAlchemy model sets `default_factory=uuid_utils.uuid7` on its `id` field.
- A row inserted by raw SQL (a migration, a `psql` session, a data fix) **must supply an explicit
  id** — there is no default to fall back on. The seed migration (015) uses literal UUIDs.
- `uuid_utils.UUID` is not `uuid.UUID`; asyncpg needs the stdlib type. Convert at the boundary
  (`uuid.UUID(str(uuid_utils.uuid7()))`, or configure the codec once) rather than scattering casts.

### 1.6 Geospatial — core `point`, not PostGIS

**Context:** PostGIS is available in production (Neon) but is deliberately *not* installed in the
local `postgres:16` container, so the schema must not require it.

**Decision:** `airports.location` is a **core PostgreSQL `point`**, generated from the existing
`longitude`/`latitude` columns and indexed with the built-in GiST `point_ops` opclass:

```
location  point  GENERATED ALWAYS AS (point(longitude, latitude)) STORED
IDX USING GIST (location)
```

The two options considered, and why this one won:

| Option | Verdict |
|---|---|
| `geography(Point,4326)` + PostGIS | Correct great-circle distance and a rich operator set, but makes PostGIS a hard requirement for `alembic upgrade head`. Local dev, CI, and any contributor's laptop would all need a PostGIS image. Rejected for a single column. |
| **Core `point` + GiST, exact distance in the app** | **Chosen.** Zero extensions, identical DDL in dev and prod, and the index still does the expensive part (narrowing candidates by bounding box). |
| No column at all, everything in the app | Rejected — loses the index, turning "airports within 50nm" into a full scan of the airport catalog. |

**The tradeoff, stated plainly:** the `point` type is **planar**, not spherical. `<->` returns
Euclidean distance in degrees, which is not nautical miles and distorts badly at high latitudes
(a degree of longitude is ~60nm at the equator and ~30nm at 60°N). So:

- Use the GiST index only as a **prefilter** — "candidate airports in this degree box".
- Compute the **authoritative distance in the application** (haversine, or Vincenty if the
  accuracy is ever needed), and do the final sort and cutoff there.
- Never expose a `<->` result to a user or store it as a distance.
- `legs.distance_nm` is a real great-circle value computed by the application at leg creation, not
  derived from this column.

**Upgrade path:** if exact in-database distance is ever needed, PostGIS can be added in production
as a purely additive migration — a second `geography` column alongside `location`, backfilled from
lat/lng, guarded by `CREATE EXTENSION IF NOT EXISTS postgis`. Nothing in this model has to change
for that to happen, and local dev can continue without it.

### 1.7 Row-Level Security — deployment model

RLS is enabled with a tenant-isolation policy on every table (migration 014). It is worth being
explicit about when it actually does anything, because it is easy to believe you are protected
when you are not.

**The role model as shipped** (migrations 001–015; details follow):

| | |
|---|---|
| Application role | `bitlux_app` — `NOSUPERUSER NOBYPASSRLS`, owns nothing. Bootstrapped by **migration 001** (`NOLOGIN`, if absent) so it exists on Neon and in CI, not only where `docker/initdb/` ran. initdb's copy adds `LOGIN` + a dev password for local convenience, nothing more. |
| Where privileges come from | **Every table-creating migration calls `grant_app_dml()` explicitly.** Nothing in the chain relies on `ALTER DEFAULT PRIVILEGES`. |
| Ordinary tenant tables (36) | `SELECT, INSERT, UPDATE, DELETE` |
| `audit_logs` | **`SELECT, INSERT` only.** No `UPDATE`, no `DELETE` (revoked from the role and from `PUBLIC` in 012, before the first partition exists). |
| `audit_logs_*` partitions | **No direct privileges at all** — not even `SELECT`. Access is through the parent only; a partition has no RLS policy of its own. |
| Cross-tenant reads | Exactly two, both `SECURITY DEFINER` functions owned by the schema owner and executable only by `bitlux_app`: `auth_lookup_user()` (016, login by email) and `search_ids()` (017, indexed full-text search — see "RLS and index usage" below). |
| The invariant | **Migration 015 asserts** via `has_table_privilege('bitlux_app','audit_logs','UPDATE'/'DELETE')` that the above still holds at the end of the chain. `information_schema.role_table_grants` is deliberately *not* used: it lists direct grants only and misses privileges that arrive via `PUBLIC` or role membership — precisely how an accidental grant would arrive. |
| RLS on every tenant table | `ENABLE` **and `FORCE ROW LEVEL SECURITY`**, so even a non-superuser owner is bound. Policies key on `current_client_id()`. |

**Who RLS actually applies to.** Three tiers, and only the third is protected:

| Role | Policies apply? |
|---|---|
| `SUPERUSER`, or any role with `BYPASSRLS` | **Never.** Bypass is unconditional; `FORCE ROW LEVEL SECURITY` does not change it. |
| The table's owner (not a superuser) | Only with `FORCE ROW LEVEL SECURITY`. Without it the owner is exempt. |
| Any other role | Always, once RLS is enabled on the table. |

This matters locally: the `postgres:16` container creates `POSTGRES_USER` as a
**superuser**, so the `bitlux` role that runs migrations bypasses RLS entirely no
matter what the policies say. Enabling and forcing RLS is necessary but not
sufficient — isolation is only real when the querying role is neither a
superuser nor the owner.

The schema therefore has a second role, `bitlux_app` (`NOSUPERUSER NOBYPASSRLS`,
owns nothing). `bitlux` owns the schema and runs migrations; `bitlux_app` is what
the application connects as and what RLS actually constrains. The same split is
mandatory in production.

**Where privileges come from — migrations, not defaults.** The role bootstrap
lives in migration 001 rather than in `docker/initdb/` so that a fresh Neon or CI
database has the role before migration 003 first grants to it. Every migration
that creates a table then grants that role exactly what the table needs, via
`grant_app_dml()`:
`SELECT, INSERT, UPDATE, DELETE` on ordinary tenant tables, and **`SELECT, INSERT`
only on `audit_logs`** (migration 012, which also revokes `UPDATE, DELETE` from the
role and from `PUBLIC` before the first partition exists). Migration 015 — the
end of the chain — asserts with `has_table_privilege()` that `bitlux_app` still
has neither `UPDATE` nor `DELETE` on `audit_logs`, so a later grant cannot undo
it silently. It uses `has_table_privilege()` and not
`information_schema.role_table_grants` because the latter shows only direct
grants; a privilege inherited through `PUBLIC` or through membership in another
role is invisible to it, and that is the route an accident would take. Every write privilege in the schema is therefore an explicit,
greppable line in a migration, and dev and prod get identical privileges from
the same source.

`docker/initdb/10-app-role.sql` (local only) creates the same role earlier with
`LOGIN` and a dev password, and sets `ALTER DEFAULT PRIVILEGES` to `SELECT,
INSERT` as a safety net for anything created outside the migration chain —
read-plus-append is the floor; `UPDATE`/`DELETE` are never a default.

**Partitions are reachable only through the parent.** PostgreSQL checks
privileges on the table named in the query, so the parent's grant covers every
`audit_logs_YYYY_MM`, and a partition has no RLS policy of its own — a direct
grant on one, even `SELECT`, would be a cross-tenant read. Migration 012 and
`scripts/partition_maintenance.py` both `REVOKE ALL` on each partition from the
app role: `bitlux_app` holds no privilege of any kind on any partition.

The session variable used by every policy is `app.client_id`, read through a
helper so an unset or empty value fails closed rather than raising:

```sql
CREATE FUNCTION current_client_id() RETURNS uuid
LANGUAGE sql STABLE AS $$ SELECT NULLIF(current_setting('app.client_id', true), '')::uuid $$;
```

With `app.client_id` unset this returns `NULL`, every policy predicate evaluates to
`NULL`, and **no rows are visible** — the safe direction.

**Production deployment requirements (non-negotiable):**

1. The application **must connect as a non-owner, non-superuser role** — the
   `bitlux_app` equivalent. Migrations continue to run as the owner; the runtime
   must not. On Neon, the role the console hands you first is privileged: create
   a dedicated one rather than reusing it.
2. Every transaction **must set the tenant** before touching data, and must use
   `SET LOCAL` so the value cannot leak across pooled connections:
   ```sql
   BEGIN;
   SET LOCAL app.client_id = '0199…';
   -- queries here
   COMMIT;
   ```
   With PgBouncer in transaction pooling mode this is correct; a plain `SET` would
   be a cross-tenant data leak.
3. `audit_logs` is append-only for the app role at the privilege layer
   (migration 012, asserted by 015) and, for every role including the owner, by
   the trigger in migration 013.

**RLS and index usage — the non-leakproof rule.** Policy quals are security barriers, and
PostgreSQL will not evaluate a non-`LEAKPROOF` operator as an *index condition* beneath one. `=`
on uuid is leakproof; `@@` (`ts_match_vq`), `ILIKE` and `~~` are not. Consequence, measured: for
`bitlux_app`, `WHERE search_tsv @@ query` is always a sequential scan (≈15 ms at 50k rows), while
the identical statement as the owner is a `Bitmap Index Scan` on the GIN index (0.04 ms). The
GIN indexes are correct; RLS simply forbids the app role the path. Marking the catalog function
leakproof needs superuser (not available on Neon) and edits `pg_catalog`, so instead `/search`
goes through **`search_ids(type, tsquery, limit)`** (migration 017): the second and last
deliberate `SECURITY DEFINER` read beside `auth_lookup_user()`. It runs with `row_security = off`,
scopes by `current_client_id()` itself (the same trust root the policies use — an unset tenant
returns nothing), contains no dynamic SQL (one static branch per whitelisted type), returns only
`(id, rank)`, and the caller joins those ids from a statement that is still under RLS. Any future
predicate that must be indexed for the app role and uses a non-leakproof operator needs the same
treatment; a plain `WHERE` will silently seq-scan.

**Verifying isolation.** Migration 014 applies `FORCE ROW LEVEL SECURITY` to every
tenant table so that the non-superuser owner is bound too, but the only honest
test is to connect as `bitlux_app` and confirm that two tenants cannot see each
other. `psql -U bitlux` will always show everything and proves nothing.

Migration 015 needs the escape hatch in the other direction: it writes global
catalog rows with `client_id = NULL`, which no tenant policy permits, so it runs
`SET LOCAL row_security = off` for its own transaction.

---

## 2. Enum catalog

```
-- Tenancy & people
client_status          active | trialing | past_due | suspended | cancelled
user_role              owner | admin | broker | ops | finance | read_only
user_status            invited | active | disabled | locked
segment_type           uhnw | corporate | family_office | government | sports | entertainment |
                       medical | group_charter | cargo | broker_partner | other
contact_type           individual | company
contact_status         lead | prospect | active | dormant | churned | blocked
lead_source            referral | website | inbound_call | outbound | broker_network | event |
                       advertising | partner | empty_leg_alert | import | other
channel_type           email | phone | mobile | whatsapp | telegram | signal | fax | website |
                       linkedin | other
address_type           billing | home | office | shipping | other
passenger_status       active | inactive | deceased
pax_relationship       self | spouse | partner | child | family | employee | assistant |
                       colleague | guest | other
travel_document_type   passport | visa | national_id | drivers_license | residence_permit |
                       global_entry | known_traveler | crew_license | crew_medical | other

-- Accounts & money
account_type           individual | corporate | family_office | jet_card | fractional |
                       government | broker_partner
account_status         pending | active | on_hold | suspended | closed
payment_terms          prepaid | due_on_receipt | net_7 | net_15 | net_30 | net_45 | net_60 |
                       on_account
payment_method         wire | ach | sepa | credit_card | check | jet_card_debit | escrow |
                       crypto | other
payment_status         pending | cleared | failed | refunded | chargeback
invoice_type           deposit | balance | full | credit_note | adjustment
invoice_status         draft | issued | sent | partially_paid | paid | overdue | void |
                       refunded | written_off
line_item_type         flight_hours | positioning | fuel_surcharge | federal_excise_tax |
                       segment_fee | international_fee | landing_fee | ramp_fee | handling |
                       overflight | customs | catering | ground_transport | deicing |
                       overnight | crew_expense | wifi | pet_fee | peak_day_surcharge |
                       short_notice | discount | commission | credit_card_fee | other

-- Fleet
aircraft_category      piston | turboprop | very_light_jet | light_jet | midsize_jet |
                       super_midsize_jet | heavy_jet | ultra_long_range | vip_airliner |
                       helicopter
aircraft_status        active | maintenance | aog | stored | for_sale | sold | retired
operator_status        prospect | under_review | approved | conditional | suspended | blacklisted
regulatory_part        part_91 | part_91k | part_121 | part_135 | easa_cat | easa_nco |
                       easa_spo | other
safety_program         argus | wyvern | isbao | isbah | acsf | tsa_twelve_five | easa_sms | other
safety_rating_level    not_rated | argus_gold | argus_gold_plus | argus_platinum |
                       wyvern_registered | wyvern_wingman | wyvern_wingman_plus |
                       isbao_stage_1 | isbao_stage_2 | isbao_stage_3 | acsf_registered | other
crew_role              pic | sic | relief_pilot | flight_engineer | flight_attendant |
                       flight_nurse | flight_physician | ground_ops | observer
crew_status            active | inactive | training | on_leave | suspended | terminated

-- Trips
trip_type              charter | owner_flight | empty_reposition | demo | maintenance_ferry |
                       air_ambulance | cargo | group
trip_status            draft | sourcing | quoted | confirmed | in_progress | completed |
                       cancelled | archived
leg_status             scheduled | released | boarding | departed | enroute | arrived |
                       delayed | diverted | cancelled
leg_purpose            revenue | positioning | ferry | maintenance | training
empty_leg_status       draft | available | on_hold | booked | expired | cancelled
empty_leg_source       manual | operator_feed | avinode | email_parse | api_partner

-- Commerce
quote_status           draft | sent | viewed | negotiating | accepted | declined | expired |
                       withdrawn | superseded
booking_status         pending | confirmed | contract_sent | contract_signed | funds_pending |
                       funds_received | flown | completed | cancelled | disputed

-- Cross-cutting
document_type          contract | charter_agreement | quote_pdf | invoice_pdf | receipt |
                       passport_scan | visa_scan | id_scan | insurance_certificate |
                       aoc_certificate | ops_specification | safety_audit_report | w9 |
                       tax_form | catering_order | handling_confirmation | flight_release |
                       gendec | weight_balance | apis_manifest | trip_sheet | photo | other
document_status        pending | under_review | approved | rejected | expired | superseded
storage_provider       s3 | gcs | azure_blob | local
task_status            open | in_progress | blocked | completed | cancelled
task_priority          low | normal | high | urgent
task_type              call | email | follow_up | document_request | document_expiry |
                       payment_chase | quote_prep | ops_check | compliance_review | other
activity_type          call | email | meeting | note | sms | whatsapp | site_visit | system
activity_direction     inbound | outbound | internal
audit_action           insert | update | delete | soft_delete | restore | login | login_failed |
                       logout | export | download | permission_change | impersonate_start |
                       impersonate_end
actor_type             user | system | api_key | integration | impersonation | anonymous
entity_type            client | user | segment | contact | passenger | account_holder |
                       travel_document | manufacturer | aircraft_model | aircraft | operator |
                       operator_safety_rating | crew_member | airport | fbo | trip | leg |
                       leg_passenger | leg_crew | empty_leg | quote | booking | invoice |
                       payment | document | task | activity
```

`entity_type` is the discriminator for every polymorphic association (documents, tags, tasks,
activities, audit). Adding a new attachable entity means one `ALTER TYPE … ADD VALUE`.

---

## 3. Table specifications

Notation: `FK →` foreign key. `UQ` unique index. `IDX` index. `CHK` check constraint.
`†` = standard columns from §1.1 also present. `[enc]` = application-encrypted.

### 3.1 Tenancy

```
clients                                    (NO client_id — this IS the tenant root)
  id                    uuid           PK
  slug                  citext         NOT NULL
  name                  text           NOT NULL
  legal_name            text
  status                client_status  NOT NULL DEFAULT 'trialing'
  default_currency      char(3)        NOT NULL DEFAULT 'USD'
  timezone              text           NOT NULL DEFAULT 'UTC'   -- IANA
  locale                text           NOT NULL DEFAULT 'en-US'
  billing_email         citext
  support_email         citext
  logo_url              text
  settings              jsonb          NOT NULL DEFAULT '{}'
  feature_flags         jsonb          NOT NULL DEFAULT '{}'
  trip_number_prefix    text                                    -- e.g. 'BLX'
  created_at / updated_at / deleted_at
  UQ   (slug) WHERE deleted_at IS NULL
  IDX  (status) WHERE deleted_at IS NULL
```

```
users †
  email                 citext         NOT NULL
  full_name             text           NOT NULL
  given_name            text
  family_name           text
  role                  user_role      NOT NULL DEFAULT 'broker'
  status                user_status    NOT NULL DEFAULT 'invited'
  phone                 text
  avatar_url            text
  timezone              text
  auth_provider         text                                    -- 'oidc','password','saml'
  auth_subject          text                                    -- external IdP subject
  mfa_enabled           boolean        NOT NULL DEFAULT false
  last_login_at         timestamptz
  password_hash         text                                    -- 016: argon2id; NULL = no password login
  password_changed_at   timestamptz                             -- 016
  UQ   (client_id, email) WHERE deleted_at IS NULL
  UQ   (auth_provider, auth_subject) WHERE auth_subject IS NOT NULL
  IDX  (client_id, role) WHERE deleted_at IS NULL
  IDX  (client_id, status)
```

```
refresh_tokens †                         (migration 016 — server-side state for refresh rotation + logout)
  user_id               uuid           NOT NULL FK → users(id) ON DELETE CASCADE
  token_hash            text           NOT NULL       -- sha256(token); the token itself is never stored
  issued_at             timestamptz    NOT NULL DEFAULT now()
  expires_at            timestamptz    NOT NULL
  revoked_at            timestamptz                   -- NULL = live
  replaced_by_id        uuid           FK → refresh_tokens(id) ON DELETE SET NULL  (rotation chain)
  user_agent            text
  ip_address            inet
  CHK  expires_at > issued_at
  UQ   (token_hash)
  IDX  (client_id, user_id)
  IDX  (expires_at) WHERE revoked_at IS NULL
```

Every refresh is a rotation: the presented token's row is revoked with `replaced_by_id` pointing at
its successor. Presenting an already-revoked token is treated as replay and revokes every live
token for that user. Logout revokes the presented token. Access tokens (15 min) are stateless JWTs;
only refresh tokens (7 days) have rows.

**`auth_lookup_user(email, client_slug)` — the one deliberate hole in tenant isolation.** Login has
to find a user by email *before* any tenant is known, which RLS forbids the application role.
Migration 016 adds a `SECURITY DEFINER` SQL function, owned by the schema owner, with
`row_security = off`, that performs exactly that lookup and nothing else: it returns the user id,
tenant id and slug, role, both statuses and the password hash. It is the only object `bitlux_app`
may execute across tenants (`REVOKE ALL … FROM PUBLIC; GRANT EXECUTE … TO bitlux_app`). If the
email exists in more than one tenant the API demands `client_slug`. Everything after login runs
inside a normal tenant transaction under RLS.

### 3.2 CRM spine — Segments → Contacts → Passengers → Account Holders

```
segments †
  name                  text           NOT NULL
  code                  citext
  segment_type          segment_type   NOT NULL DEFAULT 'other'
  description           text
  parent_segment_id     uuid           FK → segments(id) ON DELETE SET NULL   (self, hierarchy)
  path                  ltree                                 -- materialized ancestry
  color                 text                                  -- #RRGGBB for UI
  is_auto               boolean        NOT NULL DEFAULT false -- rule-driven membership
  criteria              jsonb          NOT NULL DEFAULT '{}'  -- rule DSL when is_auto
  sort_order            integer        NOT NULL DEFAULT 0
  UQ   (client_id, lower(name)) WHERE deleted_at IS NULL
  UQ   (client_id, code) WHERE code IS NOT NULL AND deleted_at IS NULL
  IDX  (client_id, parent_segment_id)
  IDX  USING GIST (path)
  CHK  parent_segment_id <> id
```

```
contacts †
  segment_id            uuid           FK → segments(id) ON DELETE SET NULL
  contact_type          contact_type   NOT NULL DEFAULT 'individual'
  status                contact_status NOT NULL DEFAULT 'lead'
  salutation            text
  first_name            text
  middle_name           text
  last_name             text
  suffix                text
  display_name          text           NOT NULL      -- person full name or company name
  company_name          text
  job_title             text
  parent_contact_id     uuid           FK → contacts(id) ON DELETE SET NULL  (employee → company)
  referred_by_contact_id uuid          FK → contacts(id) ON DELETE SET NULL
  owner_user_id         uuid           FK → users(id) ON DELETE SET NULL     (responsible broker)
  source                lead_source    NOT NULL DEFAULT 'other'
  primary_email         citext                        -- denormalized from contact_channels
  primary_phone         text                          -- denormalized from contact_channels
  preferred_language    text
  lifetime_value_cents  bigint         NOT NULL DEFAULT 0   -- materialized by job
  trip_count            integer        NOT NULL DEFAULT 0   -- materialized by job
  last_activity_at      timestamptz
  do_not_contact        boolean        NOT NULL DEFAULT false
  vip_notes             text
  preferences           jsonb          NOT NULL DEFAULT '{}'
  search_tsv            tsvector       GENERATED (display_name, company_name, primary_email,
                                                  primary_phone) STORED
  CHK  contact_type='company' → company_name IS NOT NULL
  CHK  contact_type='individual' → last_name IS NOT NULL
  CHK  parent_contact_id <> id
  IDX  (client_id, status) WHERE deleted_at IS NULL
  IDX  (client_id, segment_id) WHERE deleted_at IS NULL
  IDX  (client_id, owner_user_id) WHERE deleted_at IS NULL
  IDX  (client_id, primary_email)
  IDX  (client_id, parent_contact_id)
  IDX  (client_id, last_activity_at DESC)
  IDX  USING GIN (search_tsv)
```

```
contact_channels †                       (contact's emails / phones / handles)
  contact_id            uuid           NOT NULL FK → contacts(id) ON DELETE CASCADE
  channel_type          channel_type   NOT NULL
  value                 citext         NOT NULL
  label                 text                          -- 'work', 'assistant', 'yacht'
  is_primary            boolean        NOT NULL DEFAULT false
  verified_at           timestamptz
  opted_out_at          timestamptz
  UQ   (contact_id, channel_type, value) WHERE deleted_at IS NULL
  UQ   (contact_id, channel_type) WHERE is_primary AND deleted_at IS NULL
  IDX  (client_id, value)
```

```
addresses †                              (polymorphic — attached to contacts, operators, FBOs…)
  owner_type            entity_type    NOT NULL
  owner_id              uuid           NOT NULL       -- no FK; see §5 polymorphism
  address_type          address_type   NOT NULL DEFAULT 'other'
  line1                 text           NOT NULL
  line2                 text
  city                  text
  region                text
  postal_code           text
  country_code          char(2)        NOT NULL       -- ISO 3166-1 alpha-2
  latitude              numeric(9,6)
  longitude             numeric(9,6)
  is_primary            boolean        NOT NULL DEFAULT false
  IDX  (client_id, owner_type, owner_id) WHERE deleted_at IS NULL
  UQ   (owner_type, owner_id, address_type) WHERE is_primary AND deleted_at IS NULL
```

```
passengers †                             (a flying identity; may exist without a CRM contact)
  contact_id            uuid           FK → contacts(id) ON DELETE SET NULL   (NULLABLE)
  status                passenger_status NOT NULL DEFAULT 'active'
  first_name            text           NOT NULL
  middle_name           text
  last_name             text           NOT NULL
  preferred_name        text
  suffix                text
  date_of_birth         date
  nationality_code      char(2)
  gender_marker         text                          -- as printed on travel doc: M/F/X
  weight_kg             numeric(5,1)                  -- weight & balance
  guardian_passenger_id uuid           FK → passengers(id) ON DELETE SET NULL (unaccompanied minor)
  dietary_restrictions  text[]         NOT NULL DEFAULT '{}'
  allergies             text[]         NOT NULL DEFAULT '{}'
  mobility_assistance   boolean        NOT NULL DEFAULT false
  travels_with_pet      boolean        NOT NULL DEFAULT false
  pet_details           jsonb
  preferences           jsonb          NOT NULL DEFAULT '{}'  -- seat, beverage, temp, press
  known_traveler_number bytea          [enc]
  ktn_last4             text
  redress_number        bytea          [enc]
  emergency_contact_name  text
  emergency_contact_phone text
  notes                 text
  search_tsv            tsvector       GENERATED (first_name, last_name, preferred_name) STORED
  CHK  guardian_passenger_id <> id
  IDX  (client_id, contact_id) WHERE deleted_at IS NULL
  IDX  (client_id, lower(last_name), lower(first_name))
  IDX  (client_id, date_of_birth)
  IDX  USING GIN (search_tsv)
```

```
account_holders †                        (the commercial / billing entity — who pays)
  account_number        citext         NOT NULL       -- 'ACC-00417'
  name                  text           NOT NULL
  account_type          account_type   NOT NULL DEFAULT 'individual'
  status                account_status NOT NULL DEFAULT 'pending'
  primary_contact_id    uuid           NOT NULL FK → contacts(id) ON DELETE RESTRICT
  billing_contact_id    uuid           FK → contacts(id) ON DELETE SET NULL
  owner_user_id         uuid           FK → users(id) ON DELETE SET NULL
  currency              char(3)        NOT NULL DEFAULT 'USD'
  payment_terms         payment_terms  NOT NULL DEFAULT 'prepaid'
  credit_limit_cents    bigint         NOT NULL DEFAULT 0
  balance_cents         bigint         NOT NULL DEFAULT 0   -- materialized from invoices/payments
  prepaid_balance_cents bigint         NOT NULL DEFAULT 0   -- jet-card / block-hour wallet
  tax_id                bytea          [enc]
  tax_id_last4          text
  tax_exempt            boolean        NOT NULL DEFAULT false
  billing_address_id    uuid           FK → addresses(id) ON DELETE SET NULL
  contract_signed_at    timestamptz
  credit_reviewed_at    timestamptz
  notes                 text
  UQ   (client_id, account_number) WHERE deleted_at IS NULL
  IDX  (client_id, status) WHERE deleted_at IS NULL
  IDX  (client_id, primary_contact_id)
  IDX  (client_id, owner_user_id)
  IDX  (client_id, balance_cents) WHERE balance_cents > 0
```

```
account_holder_passengers †              (M:N — who may fly on whose account)
  account_holder_id     uuid           NOT NULL FK → account_holders(id) ON DELETE CASCADE
  passenger_id          uuid           NOT NULL FK → passengers(id) ON DELETE CASCADE
  relationship          pax_relationship NOT NULL DEFAULT 'other'
  is_authorized_booker  boolean        NOT NULL DEFAULT false
  spend_limit_cents     bigint                        -- per-trip cap for this passenger
  valid_from            date
  valid_to              date
  UQ   (account_holder_id, passenger_id) WHERE deleted_at IS NULL
  IDX  (client_id, passenger_id)
  CHK  valid_to IS NULL OR valid_to >= valid_from
```

```
travel_documents †                       (structured passport/visa data — the scan lives in documents)
  passenger_id          uuid           FK → passengers(id) ON DELETE CASCADE
  crew_member_id        uuid           FK → crew_members(id) ON DELETE CASCADE
  document_type         travel_document_type NOT NULL
  number                bytea          NOT NULL [enc]
  number_last4          text           NOT NULL
  full_name_on_document text           NOT NULL
  issuing_country       char(2)        NOT NULL
  nationality_code      char(2)
  place_of_birth        text
  issue_date            date
  expiry_date           date
  scan_document_id      uuid           FK → documents(id) ON DELETE SET NULL
  verified_at           timestamptz
  verified_by_user_id   uuid           FK → users(id) ON DELETE SET NULL
  is_primary            boolean        NOT NULL DEFAULT false
  CHK  num_nonnulls(passenger_id, crew_member_id) = 1        -- exclusive arc
  IDX  (client_id, passenger_id) WHERE deleted_at IS NULL
  IDX  (client_id, crew_member_id) WHERE deleted_at IS NULL
  IDX  (client_id, expiry_date) WHERE deleted_at IS NULL     -- expiry sweep → tasks
  UQ   (passenger_id, document_type) WHERE is_primary AND deleted_at IS NULL
```

### 3.3 Fleet — Manufacturers → Models → Aircraft → Operators

```
manufacturers †                          (client_id NULLABLE — shared catalog, §1.3)
  name                  text           NOT NULL       -- 'Gulfstream Aerospace'
  short_name            text                          -- 'Gulfstream'
  code                  citext                        -- 'GLF'
  country_code          char(2)
  website               text
  logo_url              text
  founded_year          smallint
  is_active             boolean        NOT NULL DEFAULT true
  search_tsv            tsvector       GENERATED (name, short_name, code) STORED     -- 016
  UQ   NULLS NOT DISTINCT (client_id, lower(name)) WHERE deleted_at IS NULL
  IDX  (lower(name))
  IDX  USING GIN (search_tsv)                                                    -- 016
```

```
aircraft_models †                        (client_id NULLABLE — shared catalog)
  manufacturer_id       uuid           NOT NULL FK → manufacturers(id) ON DELETE RESTRICT
  name                  text           NOT NULL       -- 'G650ER'
  family                text                          -- 'G650'
  icao_type_code        text                          -- 'GLF6'
  category              aircraft_category NOT NULL
  max_passengers        smallint
  typical_passengers    smallint
  range_nm              integer
  cruise_speed_kt       integer
  max_altitude_ft       integer
  baggage_capacity_cuft integer
  cabin_length_in       numeric(6,1)
  cabin_width_in        numeric(6,1)
  cabin_height_in       numeric(6,1)
  has_lavatory          boolean
  has_enclosed_lavatory boolean
  wifi_available        boolean
  cabin_crew_standard   boolean        NOT NULL DEFAULT false
  hourly_rate_low_cents  bigint                       -- market reference band
  hourly_rate_high_cents bigint
  production_start_year smallint
  production_end_year   smallint
  image_url             text
  search_tsv            tsvector       GENERATED (name, family, icao_type_code) STORED  -- 016
  IDX  USING GIN (search_tsv)                                                        -- 016
  UQ   NULLS NOT DISTINCT (client_id, manufacturer_id, lower(name)) WHERE deleted_at IS NULL
  IDX  (category, max_passengers)
  IDX  (icao_type_code)
  IDX  (manufacturer_id)
  IDX  (category, range_nm)                           -- "can it fly KTEB→EGGW nonstop?"
```

```
operators †                              (tenant-curated vendor records — client_id NOT NULL)
  legal_name            text           NOT NULL
  dba_name              text
  operator_code         citext                        -- internal short code
  status                operator_status NOT NULL DEFAULT 'prospect'
  country_code          char(2)
  regulatory_part       regulatory_part
  aoc_number            text
  aoc_expiry            date
  fleet_size            smallint       NOT NULL DEFAULT 0   -- materialized
  primary_contact_id    uuid           FK → contacts(id) ON DELETE SET NULL
  ops_email             citext
  ops_phone             text
  ops_24h_phone         text
  accounts_email        citext
  website               text
  insurance_expiry      date
  insurance_limit_cents bigint
  w9_on_file            boolean        NOT NULL DEFAULT false
  is_preferred          boolean        NOT NULL DEFAULT false
  blocklist_reason      text
  commission_rate       numeric(5,4)                  -- 0.0750 = 7.5%
  payment_terms         payment_terms  NOT NULL DEFAULT 'prepaid'
  notes                 text
  search_tsv            tsvector       GENERATED (legal_name, dba_name, operator_code) STORED
  CHK  status='blacklisted' → blocklist_reason IS NOT NULL
  UQ   (client_id, operator_code) WHERE operator_code IS NOT NULL AND deleted_at IS NULL
  UQ   (client_id, lower(legal_name)) WHERE deleted_at IS NULL
  IDX  (client_id, status) WHERE deleted_at IS NULL
  IDX  (client_id) WHERE is_preferred AND deleted_at IS NULL
  IDX  (client_id, insurance_expiry) WHERE deleted_at IS NULL
  IDX  (client_id, aoc_expiry) WHERE deleted_at IS NULL
  IDX  USING GIN (search_tsv)
```

```
operator_safety_ratings †
  operator_id           uuid           NOT NULL FK → operators(id) ON DELETE CASCADE
  program               safety_program NOT NULL
  rating_level          safety_rating_level NOT NULL
  rating_label          text                          -- raw string from the auditor
  issued_date           date
  expiry_date           date
  audit_reference       text
  auditor_name          text
  scope_notes           text                          -- e.g. limited to certain type ratings
  is_current            boolean        NOT NULL DEFAULT true
  report_document_id    uuid           FK → documents(id) ON DELETE SET NULL
  verified_at           timestamptz
  verified_by_user_id   uuid           FK → users(id) ON DELETE SET NULL
  UQ   (operator_id, program) WHERE is_current AND deleted_at IS NULL
  IDX  (client_id, operator_id, program)
  IDX  (client_id, expiry_date) WHERE is_current AND deleted_at IS NULL   -- renewal sweep
  IDX  (client_id, rating_level)
  CHK  expiry_date IS NULL OR issued_date IS NULL OR expiry_date > issued_date
```

```
aircraft †                               (a physical tail number)
  tail_number           citext         NOT NULL       -- 'N650BX'
  serial_number         text
  aircraft_model_id     uuid           NOT NULL FK → aircraft_models(id) ON DELETE RESTRICT
  operator_id           uuid           FK → operators(id) ON DELETE SET NULL  (CURRENT operator)
  owner_contact_id      uuid           FK → contacts(id) ON DELETE SET NULL   (beneficial owner)
  status                aircraft_status NOT NULL DEFAULT 'active'
  year_of_manufacture   smallint
  registration_country  char(2)
  home_base_airport_id  uuid           FK → airports(id) ON DELETE SET NULL
  max_passengers        smallint                      -- overrides model when configured
  configured_seats      smallint
  divans                smallint
  berths                smallint
  interior_refurb_year  smallint
  exterior_refurb_year  smallint
  wifi_provider         text                          -- 'Starlink', 'Ka-band', 'Gogo Avance'
  amenities             jsonb          NOT NULL DEFAULT '{}'
  pets_allowed          boolean
  smoking_allowed       boolean        NOT NULL DEFAULT false
  lavatory_type         text
  cargo_capacity_cuft   integer
  hourly_rate_cents     bigint
  is_available_for_charter boolean     NOT NULL DEFAULT true
  last_verified_at      timestamptz
  notes                 text
  search_tsv            tsvector       GENERATED (tail_number, serial_number) STORED
  UQ   (client_id, tail_number) WHERE deleted_at IS NULL
  IDX  (client_id, operator_id) WHERE deleted_at IS NULL
  IDX  (client_id, aircraft_model_id) WHERE deleted_at IS NULL
  IDX  (client_id, status, is_available_for_charter) WHERE deleted_at IS NULL
  IDX  (client_id, home_base_airport_id)
  IDX  USING GIN (search_tsv)
```

```
aircraft_operator_assignments †          (tails move between operators — keep the history)
  aircraft_id           uuid           NOT NULL FK → aircraft(id) ON DELETE CASCADE
  operator_id           uuid           NOT NULL FK → operators(id) ON DELETE RESTRICT
  effective_from        date           NOT NULL
  effective_to          date                          -- NULL = current
  is_current            boolean        NOT NULL DEFAULT true
  management_agreement_document_id uuid FK → documents(id) ON DELETE SET NULL
  notes                 text
  EXCLUDE USING GIST (aircraft_id WITH =,
                      daterange(effective_from, effective_to, '[)') WITH &&)
                      WHERE (deleted_at IS NULL)     -- no overlapping tenancies
  UQ   (aircraft_id) WHERE is_current AND deleted_at IS NULL
  IDX  (client_id, aircraft_id, effective_from DESC)
  IDX  (client_id, operator_id)
```

### 3.4 Geography

```
airports †                               (client_id NULLABLE — shared catalog)
  icao_code             char(4)
  iata_code             char(3)
  local_code            text                          -- FAA LID etc.
  name                  text           NOT NULL
  city                  text
  region                text
  country_code          char(2)        NOT NULL
  latitude              numeric(9,6)   NOT NULL
  longitude             numeric(9,6)   NOT NULL
  location              point          GENERATED ALWAYS AS (point(longitude, latitude)) STORED
                                                      -- core PG `point`, NOT PostGIS. See §1.6.
  elevation_ft          integer
  timezone              text           NOT NULL       -- IANA
  longest_runway_ft     integer
  has_customs           boolean        NOT NULL DEFAULT false
  is_towered            boolean
  is_private            boolean        NOT NULL DEFAULT false
  slot_restricted       boolean        NOT NULL DEFAULT false
  curfew                jsonb                         -- { start, end, exceptions }
  is_active             boolean        NOT NULL DEFAULT true
  search_tsv            tsvector       GENERATED (name, city, icao_code, iata_code) STORED
  UQ   NULLS NOT DISTINCT (client_id, icao_code) WHERE icao_code IS NOT NULL AND deleted_at IS NULL
  IDX  (iata_code) WHERE iata_code IS NOT NULL
  IDX  USING GIST (location)                          -- planar prefilter, see §1.6
  IDX  USING GIN (search_tsv)
  IDX  (country_code, is_active)
```

```
fbos †                                   (client_id NULLABLE — shared catalog)
  airport_id            uuid           NOT NULL FK → airports(id) ON DELETE CASCADE
  name                  text           NOT NULL
  brand                 text                          -- 'Signature','Atlantic','Jet Aviation'
  phone                 text
  unicom_frequency      text
  address_line          text
  fuel_brand            text
  has_customs           boolean        NOT NULL DEFAULT false
  hours_of_operation    text
  is_preferred          boolean        NOT NULL DEFAULT false
  notes                 text
  UQ   NULLS NOT DISTINCT (client_id, airport_id, lower(name)) WHERE deleted_at IS NULL
  IDX  (airport_id)
  IDX  (client_id) WHERE is_preferred AND deleted_at IS NULL
```

### 3.5 Crew

```
crew_members †
  operator_id           uuid           FK → operators(id) ON DELETE SET NULL  (NULL = in-house)
  first_name            text           NOT NULL
  last_name             text           NOT NULL
  primary_role          crew_role      NOT NULL DEFAULT 'pic'
  status                crew_status    NOT NULL DEFAULT 'active'
  date_of_birth         date
  nationality_code      char(2)
  email                 citext
  phone                 text
  license_number        bytea          [enc]
  license_last4         text
  license_type          text                          -- 'ATP', 'CPL'
  license_country       char(2)
  medical_class         text                          -- 'Class 1'
  medical_expiry        date
  type_ratings          text[]         NOT NULL DEFAULT '{}'   -- ICAO type codes
  total_hours           integer
  hours_on_type         jsonb          NOT NULL DEFAULT '{}'   -- { "GLF6": 1200 }
  base_airport_id       uuid           FK → airports(id) ON DELETE SET NULL
  photo_document_id     uuid           FK → documents(id) ON DELETE SET NULL
  last_recurrent_at     date
  next_recurrent_due    date
  notes                 text
  search_tsv            tsvector       GENERATED (first_name, last_name, email) STORED
  IDX  (client_id, operator_id) WHERE deleted_at IS NULL
  IDX  (client_id, status) WHERE deleted_at IS NULL
  IDX  USING GIN (type_ratings)                       -- "who is current on GLF6?"
  IDX  (client_id, medical_expiry) WHERE status='active' AND deleted_at IS NULL
  IDX  (client_id, next_recurrent_due) WHERE status='active' AND deleted_at IS NULL
  IDX  USING GIN (search_tsv)
```

### 3.6 Trips → Legs → Manifests → Crew

```
trips †
  trip_number           citext         NOT NULL       -- 'BLX-2026-00147'
  trip_type             trip_type      NOT NULL DEFAULT 'charter'
  status                trip_status    NOT NULL DEFAULT 'draft'
  account_holder_id     uuid           FK → account_holders(id) ON DELETE RESTRICT  (NULL until booked)
  primary_contact_id    uuid           FK → contacts(id) ON DELETE SET NULL
  lead_passenger_id     uuid           FK → passengers(id) ON DELETE SET NULL
  owner_user_id         uuid           FK → users(id) ON DELETE SET NULL   (broker)
  ops_user_id           uuid           FK → users(id) ON DELETE SET NULL   (trip support)
  accepted_quote_id     uuid           FK → quotes(id) DEFERRABLE INITIALLY DEFERRED
  booking_id            uuid           FK → bookings(id) DEFERRABLE INITIALLY DEFERRED
  source_empty_leg_id   uuid           FK → empty_legs(id) ON DELETE SET NULL
  source                lead_source    NOT NULL DEFAULT 'other'
  pax_count             smallint       NOT NULL DEFAULT 0
  leg_count             smallint       NOT NULL DEFAULT 0    -- materialized
  departure_date        date                          -- first leg, materialized
  return_date           date                          -- last leg, materialized
  currency              char(3)        NOT NULL DEFAULT 'USD'
  total_sell_cents      bigint         NOT NULL DEFAULT 0
  total_cost_cents      bigint         NOT NULL DEFAULT 0
  margin_cents          bigint         GENERATED ALWAYS AS (total_sell_cents - total_cost_cents) STORED
  special_requests      text
  internal_notes        text
  cancelled_at          timestamptz
  cancellation_reason   text
  CHK  status='cancelled' → cancelled_at IS NOT NULL
  UQ   (client_id, trip_number) WHERE deleted_at IS NULL
  IDX  USING GIN (to_tsvector('simple', trip_number))       -- 016: /search by number, no ILIKE
  IDX  (client_id, status, departure_date) WHERE deleted_at IS NULL
  IDX  (client_id, account_holder_id, departure_date DESC)
  IDX  (client_id, owner_user_id, status)
  IDX  (client_id, departure_date) WHERE status IN ('confirmed','in_progress')
```

> Circular-FK note: `trips ↔ quotes ↔ bookings` reference each other. The two columns on `trips`
> are `DEFERRABLE INITIALLY DEFERRED` so a trip + quote + booking can be created in one
> transaction. `quotes.trip_id` and `bookings.trip_id` are the non-deferred, authoritative edges.

```
legs †
  trip_id               uuid           NOT NULL FK → trips(id) ON DELETE CASCADE
  leg_number            smallint       NOT NULL       -- 1-based, ordered within trip
  status                leg_status     NOT NULL DEFAULT 'scheduled'
  purpose               leg_purpose    NOT NULL DEFAULT 'revenue'
  departure_airport_id  uuid           NOT NULL FK → airports(id) ON DELETE RESTRICT
  arrival_airport_id    uuid           NOT NULL FK → airports(id) ON DELETE RESTRICT
  departure_fbo_id      uuid           FK → fbos(id) ON DELETE SET NULL
  arrival_fbo_id        uuid           FK → fbos(id) ON DELETE SET NULL
  scheduled_departure_at timestamptz   NOT NULL
  scheduled_arrival_at  timestamptz    NOT NULL
  departure_timezone    text           NOT NULL       -- IANA, snapshotted from airport
  arrival_timezone      text           NOT NULL
  actual_departure_at   timestamptz
  actual_arrival_at     timestamptz
  block_time_minutes    integer
  flight_time_minutes   integer
  distance_nm           integer
  aircraft_id           uuid           FK → aircraft(id) ON DELETE SET NULL   (NULL until assigned)
  operator_id           uuid           FK → operators(id) ON DELETE SET NULL
  flight_number         text
  pax_count             smallint       NOT NULL DEFAULT 0
  baggage_notes         text
  catering_notes        text
  ground_transport      jsonb          NOT NULL DEFAULT '{}'
  customs_required      boolean        NOT NULL DEFAULT false
  is_tech_stop          boolean        NOT NULL DEFAULT false
  cost_cents            bigint         NOT NULL DEFAULT 0
  sell_cents            bigint         NOT NULL DEFAULT 0
  delay_minutes         integer
  delay_reason          text
  CHK  scheduled_arrival_at > scheduled_departure_at
  CHK  departure_airport_id <> arrival_airport_id OR purpose = 'training'
  UQ   (trip_id, leg_number) WHERE deleted_at IS NULL
  IDX  (client_id, scheduled_departure_at) WHERE deleted_at IS NULL
  IDX  (client_id, aircraft_id, scheduled_departure_at) WHERE deleted_at IS NULL  -- tail conflicts
  IDX  (client_id, departure_airport_id, scheduled_departure_at)
  IDX  (client_id, arrival_airport_id, scheduled_arrival_at)
  IDX  (client_id, operator_id, scheduled_departure_at)
  IDX  (client_id, status) WHERE status IN ('scheduled','released','departed','enroute')
```

```
leg_passengers †                         (the manifest)
  leg_id                uuid           NOT NULL FK → legs(id) ON DELETE CASCADE
  passenger_id          uuid           NOT NULL FK → passengers(id) ON DELETE RESTRICT
  is_lead_passenger     boolean        NOT NULL DEFAULT false
  seat_assignment       text
  travel_document_id    uuid           FK → travel_documents(id) ON DELETE SET NULL  -- doc flown on
  catering_selection    jsonb          NOT NULL DEFAULT '{}'
  special_requests      text
  checked_in_at         timestamptz
  boarded_at            timestamptz
  is_no_show            boolean        NOT NULL DEFAULT false
  manifest_submitted_at timestamptz                   -- APIS / eAPIS filing
  UQ   (leg_id, passenger_id) WHERE deleted_at IS NULL
  UQ   (leg_id) WHERE is_lead_passenger AND deleted_at IS NULL
  IDX  (client_id, passenger_id) WHERE deleted_at IS NULL   -- "where has this pax flown?"
  IDX  (client_id, leg_id)
```

```
leg_crew †                               (crew assignment)
  leg_id                uuid           NOT NULL FK → legs(id) ON DELETE CASCADE
  crew_member_id        uuid           NOT NULL FK → crew_members(id) ON DELETE RESTRICT
  crew_role             crew_role      NOT NULL
  duty_start_at         timestamptz
  duty_end_at           timestamptz
  hotel_details         jsonb          NOT NULL DEFAULT '{}'
  notes                 text
  UQ   (leg_id, crew_member_id) WHERE deleted_at IS NULL
  UQ   (leg_id) WHERE crew_role = 'pic' AND deleted_at IS NULL    -- exactly one PIC
  IDX  (client_id, crew_member_id, duty_start_at) WHERE deleted_at IS NULL  -- duty-time conflicts
  IDX  (client_id, leg_id)
  CHK  duty_end_at IS NULL OR duty_end_at > duty_start_at
```

### 3.7 Empty Legs

```
empty_legs †
  operator_id           uuid           NOT NULL FK → operators(id) ON DELETE CASCADE
  aircraft_id           uuid           FK → aircraft(id) ON DELETE SET NULL
  aircraft_model_id     uuid           FK → aircraft_models(id) ON DELETE SET NULL  -- if no tail
  source_leg_id         uuid           FK → legs(id) ON DELETE SET NULL  -- positioning leg that created it
  status                empty_leg_status NOT NULL DEFAULT 'draft'
  source                empty_leg_source NOT NULL DEFAULT 'manual'
  departure_airport_id  uuid           NOT NULL FK → airports(id) ON DELETE RESTRICT
  arrival_airport_id    uuid           NOT NULL FK → airports(id) ON DELETE RESTRICT
  earliest_departure_at timestamptz    NOT NULL
  latest_departure_at   timestamptz    NOT NULL       -- flex window
  seats_available       smallint
  asking_price_cents    bigint         NOT NULL
  floor_price_cents     bigint                        -- internal, never exposed
  currency              char(3)        NOT NULL DEFAULT 'USD'
  is_flexible_routing   boolean        NOT NULL DEFAULT false
  routing_radius_nm     integer                       -- willing to shift endpoints this far
  published_at          timestamptz
  expires_at            timestamptz
  booked_trip_id        uuid           FK → trips(id) ON DELETE SET NULL
  external_ref          text                          -- id in Avinode / operator feed
  notes                 text
  CHK  latest_departure_at >= earliest_departure_at
  CHK  status='booked' → booked_trip_id IS NOT NULL
  UQ   (client_id, source, external_ref) WHERE external_ref IS NOT NULL AND deleted_at IS NULL
  IDX  (client_id, status, earliest_departure_at) WHERE deleted_at IS NULL
  IDX  (client_id, departure_airport_id, arrival_airport_id, earliest_departure_at)
        WHERE status='available'
  IDX  (client_id, operator_id)
  IDX  (client_id, expires_at) WHERE status='available'       -- expiry sweep
```

### 3.8 Commerce — Quotes → Bookings → Invoices

```
quotes †                                 (immutable revisions: never edit a sent quote, supersede it)
  quote_number          citext         NOT NULL       -- stable across revisions
  revision              smallint       NOT NULL DEFAULT 1
  parent_quote_id       uuid           FK → quotes(id) ON DELETE SET NULL   (previous revision)
  is_current            boolean        NOT NULL DEFAULT true
  status                quote_status   NOT NULL DEFAULT 'draft'
  trip_id               uuid           FK → trips(id) ON DELETE CASCADE      (NULL = speculative)
  account_holder_id     uuid           FK → account_holders(id) ON DELETE RESTRICT
  contact_id            uuid           FK → contacts(id) ON DELETE SET NULL
  prepared_by_user_id   uuid           FK → users(id) ON DELETE SET NULL
  operator_id           uuid           FK → operators(id) ON DELETE SET NULL
  aircraft_model_id     uuid           FK → aircraft_models(id) ON DELETE SET NULL  -- offered type
  aircraft_id           uuid           FK → aircraft(id) ON DELETE SET NULL         -- specific tail
  currency              char(3)        NOT NULL DEFAULT 'USD'
  subtotal_cents        bigint         NOT NULL DEFAULT 0
  tax_cents             bigint         NOT NULL DEFAULT 0
  fees_cents            bigint         NOT NULL DEFAULT 0
  discount_cents        bigint         NOT NULL DEFAULT 0
  total_cents           bigint         NOT NULL DEFAULT 0
  cost_total_cents      bigint         NOT NULL DEFAULT 0
  margin_cents          bigint         GENERATED ALWAYS AS (total_cents - cost_total_cents) STORED
  valid_until           timestamptz
  sent_at               timestamptz
  first_viewed_at       timestamptz
  last_viewed_at        timestamptz
  view_count            integer        NOT NULL DEFAULT 0
  accepted_at           timestamptz
  declined_at           timestamptz
  decline_reason        text
  terms                 text
  customer_notes        text
  internal_notes        text
  pdf_document_id       uuid           FK → documents(id) ON DELETE SET NULL
  esign_envelope_id     text
  UQ   (client_id, quote_number, revision) WHERE deleted_at IS NULL
  IDX  USING GIN (to_tsvector('simple', quote_number))      -- 016: /search by number
  UQ   (client_id, quote_number) WHERE is_current AND deleted_at IS NULL
  UQ   (trip_id) WHERE status='accepted' AND deleted_at IS NULL   -- one accepted quote per trip
  CHK  parent_quote_id <> id
  CHK  status='accepted' → accepted_at IS NOT NULL
  IDX  (client_id, status, valid_until) WHERE deleted_at IS NULL
  IDX  (client_id, trip_id, revision DESC)
  IDX  (client_id, account_holder_id, created_at DESC)
  IDX  (client_id, prepared_by_user_id, status)
  IDX  (client_id, valid_until) WHERE status IN ('sent','viewed','negotiating')  -- expiry sweep
```

```
quote_line_items †
  quote_id              uuid           NOT NULL FK → quotes(id) ON DELETE CASCADE
  leg_id                uuid           FK → legs(id) ON DELETE SET NULL   -- which leg this priced
  line_type             line_item_type NOT NULL
  description           text           NOT NULL
  quantity              numeric(12,3)  NOT NULL DEFAULT 1
  unit                  text                          -- 'hour','leg','pax','night','gallon'
  unit_price_cents      bigint         NOT NULL DEFAULT 0
  sell_cents            bigint         NOT NULL DEFAULT 0
  cost_cents            bigint         NOT NULL DEFAULT 0
  is_taxable            boolean        NOT NULL DEFAULT true
  tax_rate              numeric(6,4)   NOT NULL DEFAULT 0
  is_pass_through       boolean        NOT NULL DEFAULT false   -- billed at cost, no margin
  is_optional           boolean        NOT NULL DEFAULT false
  sort_order            smallint       NOT NULL DEFAULT 0
  IDX  (client_id, quote_id, sort_order)
  IDX  (client_id, leg_id)
  IDX  (client_id, line_type)
```

```
bookings †
  booking_number        citext         NOT NULL
  trip_id               uuid           NOT NULL FK → trips(id) ON DELETE RESTRICT
  quote_id              uuid           NOT NULL FK → quotes(id) ON DELETE RESTRICT
  account_holder_id     uuid           NOT NULL FK → account_holders(id) ON DELETE RESTRICT
  status                booking_status NOT NULL DEFAULT 'pending'
  operator_id           uuid           FK → operators(id) ON DELETE SET NULL
  operator_confirmation_ref text                      -- operator's own booking reference
  contract_document_id  uuid           FK → documents(id) ON DELETE SET NULL
  signed_by_contact_id  uuid           FK → contacts(id) ON DELETE SET NULL
  esign_envelope_id     text
  currency              char(3)        NOT NULL DEFAULT 'USD'
  total_cents           bigint         NOT NULL DEFAULT 0
  cost_cents            bigint         NOT NULL DEFAULT 0
  margin_cents          bigint         GENERATED ALWAYS AS (total_cents - cost_cents) STORED
  deposit_required_cents bigint        NOT NULL DEFAULT 0
  deposit_due_at        timestamptz
  deposit_received_at   timestamptz
  confirmed_at          timestamptz
  contract_sent_at      timestamptz
  contract_signed_at    timestamptz
  cancelled_at          timestamptz
  cancellation_reason   text
  cancellation_policy   text
  cancellation_fee_cents bigint        NOT NULL DEFAULT 0
  UQ   (client_id, booking_number) WHERE deleted_at IS NULL
  UQ   (trip_id) WHERE status <> 'cancelled' AND deleted_at IS NULL   -- one live booking per trip
  CHK  status='cancelled' → cancelled_at IS NOT NULL
  IDX  (client_id, status) WHERE deleted_at IS NULL
  IDX  (client_id, account_holder_id, created_at DESC)
  IDX  (client_id, operator_id)
  IDX  (client_id, deposit_due_at) WHERE deposit_received_at IS NULL
```

```
invoices †
  invoice_number        citext         NOT NULL
  invoice_type          invoice_type   NOT NULL DEFAULT 'full'
  status                invoice_status NOT NULL DEFAULT 'draft'
  account_holder_id     uuid           NOT NULL FK → account_holders(id) ON DELETE RESTRICT
  booking_id            uuid           FK → bookings(id) ON DELETE RESTRICT
  trip_id               uuid           FK → trips(id) ON DELETE RESTRICT
  parent_invoice_id     uuid           FK → invoices(id) ON DELETE RESTRICT  -- credit notes
  issue_date            date
  due_date              date
  payment_terms         payment_terms  NOT NULL DEFAULT 'due_on_receipt'
  currency              char(3)        NOT NULL DEFAULT 'USD'
  exchange_rate         numeric(16,8)  NOT NULL DEFAULT 1   -- to tenant default_currency
  subtotal_cents        bigint         NOT NULL DEFAULT 0
  tax_cents             bigint         NOT NULL DEFAULT 0
  total_cents           bigint         NOT NULL DEFAULT 0
  amount_paid_cents     bigint         NOT NULL DEFAULT 0   -- materialized from payments
  balance_cents         bigint         GENERATED ALWAYS AS (total_cents - amount_paid_cents) STORED
  billing_address_id    uuid           FK → addresses(id) ON DELETE SET NULL
  pdf_document_id       uuid           FK → documents(id) ON DELETE SET NULL
  sent_at               timestamptz
  paid_at               timestamptz
  voided_at             timestamptz
  void_reason           text
  external_ref          text                          -- QuickBooks / Xero / NetSuite id
  notes                 text
  CHK  status='void' → voided_at IS NOT NULL AND void_reason IS NOT NULL
  CHK  invoice_type='credit_note' → parent_invoice_id IS NOT NULL
  CHK  parent_invoice_id <> id
  UQ   (client_id, invoice_number) WHERE deleted_at IS NULL
  UQ   (client_id, external_ref) WHERE external_ref IS NOT NULL AND deleted_at IS NULL
  IDX  (client_id, status, due_date) WHERE deleted_at IS NULL
  IDX  (client_id, account_holder_id, issue_date DESC)
  IDX  (client_id, due_date) WHERE status IN ('issued','sent','partially_paid','overdue')  -- AR aging
  IDX  (client_id, booking_id)
```

```
invoice_line_items †
  invoice_id            uuid           NOT NULL FK → invoices(id) ON DELETE CASCADE
  quote_line_item_id    uuid           FK → quote_line_items(id) ON DELETE SET NULL  -- provenance
  leg_id                uuid           FK → legs(id) ON DELETE SET NULL
  line_type             line_item_type NOT NULL
  description           text           NOT NULL
  quantity              numeric(12,3)  NOT NULL DEFAULT 1
  unit                  text
  unit_price_cents      bigint         NOT NULL DEFAULT 0
  amount_cents          bigint         NOT NULL DEFAULT 0
  is_taxable            boolean        NOT NULL DEFAULT true
  tax_rate              numeric(6,4)   NOT NULL DEFAULT 0
  tax_cents             bigint         NOT NULL DEFAULT 0
  gl_account_code       text                          -- accounting export
  sort_order            smallint       NOT NULL DEFAULT 0
  IDX  (client_id, invoice_id, sort_order)
  IDX  (client_id, line_type)
```

```
payments †
  account_holder_id     uuid           NOT NULL FK → account_holders(id) ON DELETE RESTRICT
  invoice_id            uuid           FK → invoices(id) ON DELETE RESTRICT  -- NULL = on-account
  method                payment_method NOT NULL
  status                payment_status NOT NULL DEFAULT 'pending'
  amount_cents          bigint         NOT NULL
  currency              char(3)        NOT NULL DEFAULT 'USD'
  exchange_rate         numeric(16,8)  NOT NULL DEFAULT 1
  fee_cents             bigint         NOT NULL DEFAULT 0    -- processor / card surcharge
  received_at           timestamptz    NOT NULL
  cleared_at            timestamptz
  reference             text                          -- wire ref, check number
  processor             text                          -- 'stripe','modern_treasury', etc.
  processor_txn_id      text
  refund_of_payment_id  uuid           FK → payments(id) ON DELETE RESTRICT
  notes                 text
  CHK  amount_cents <> 0
  CHK  refund_of_payment_id <> id
  UQ   (processor, processor_txn_id) WHERE processor_txn_id IS NOT NULL
  IDX  (client_id, invoice_id)
  IDX  (client_id, account_holder_id, received_at DESC)
  IDX  (client_id, status, received_at) WHERE deleted_at IS NULL
```

### 3.9 Cross-cutting

```
documents †                              (the file itself; attachment is via document_links)
  document_type         document_type  NOT NULL
  status                document_status NOT NULL DEFAULT 'pending'
  title                 text           NOT NULL
  description           text
  storage_provider      storage_provider NOT NULL DEFAULT 's3'
  bucket                text           NOT NULL
  storage_key           text           NOT NULL
  filename              text           NOT NULL
  mime_type             text           NOT NULL
  byte_size             bigint         NOT NULL
  checksum_sha256       text           NOT NULL
  version               smallint       NOT NULL DEFAULT 1
  supersedes_document_id uuid          FK → documents(id) ON DELETE SET NULL
  is_confidential       boolean        NOT NULL DEFAULT false
  effective_date        date
  expires_at            date                          -- insurance, AOC, passport
  retention_until       date                          -- legal hold / purge floor
  uploaded_by_user_id   uuid           FK → users(id) ON DELETE SET NULL
  ocr_text              text
  ocr_tsv               tsvector       GENERATED (title, description, ocr_text) STORED
  metadata              jsonb          NOT NULL DEFAULT '{}'
  CHK  supersedes_document_id <> id
  UQ   (bucket, storage_key)
  IDX  (client_id, document_type, status) WHERE deleted_at IS NULL
  IDX  (client_id, expires_at) WHERE expires_at IS NOT NULL AND deleted_at IS NULL  -- expiry sweep
  IDX  (client_id, checksum_sha256)                   -- dedupe detection
  IDX  USING GIN (ocr_tsv)
```

```
document_links †                         (POLYMORPHIC: one file may attach to many entities)
  document_id           uuid           NOT NULL FK → documents(id) ON DELETE CASCADE
  entity_type           entity_type    NOT NULL
  entity_id             uuid           NOT NULL       -- no FK, see §5
  link_role             text           NOT NULL DEFAULT 'attachment'  -- 'contract','passport_scan'
  is_primary            boolean        NOT NULL DEFAULT false
  UQ   (document_id, entity_type, entity_id, link_role) WHERE deleted_at IS NULL
  IDX  (client_id, entity_type, entity_id) WHERE deleted_at IS NULL   -- "docs for this trip"
  IDX  (client_id, document_id)
```

```
tasks †
  title                 text           NOT NULL
  description           text
  task_type             task_type      NOT NULL DEFAULT 'other'
  status                task_status    NOT NULL DEFAULT 'open'
  priority              task_priority  NOT NULL DEFAULT 'normal'
  assigned_to_user_id   uuid           FK → users(id) ON DELETE SET NULL
  assigned_team         text
  entity_type           entity_type                   -- POLYMORPHIC subject (nullable)
  entity_id             uuid
  parent_task_id        uuid           FK → tasks(id) ON DELETE CASCADE
  due_at                timestamptz
  reminder_at           timestamptz
  started_at            timestamptz
  completed_at          timestamptz
  completed_by_user_id  uuid           FK → users(id) ON DELETE SET NULL
  blocked_reason        text
  recurrence_rule       text                          -- RFC 5545 RRULE
  sla_due_at            timestamptz
  sla_breached_at       timestamptz
  source_system         text                          -- 'manual','expiry_sweep','automation'
  dedupe_key            text                          -- stops the sweep re-creating the same task
  CHK  (entity_type IS NULL) = (entity_id IS NULL)
  CHK  status='completed' → completed_at IS NOT NULL
  CHK  parent_task_id <> id
  UQ   (client_id, dedupe_key) WHERE dedupe_key IS NOT NULL AND status IN ('open','in_progress')
  IDX  (client_id, assigned_to_user_id, status, due_at) WHERE deleted_at IS NULL
  IDX  (client_id, entity_type, entity_id) WHERE deleted_at IS NULL
  IDX  (client_id, due_at) WHERE status IN ('open','in_progress')   -- the "my queue" index
  IDX  (client_id, priority, due_at) WHERE status = 'open'
```

```
activities †                             (CRM interaction log — human-facing, editable)
  activity_type         activity_type  NOT NULL
  direction             activity_direction NOT NULL DEFAULT 'outbound'
  subject               text
  body                  text
  user_id               uuid           FK → users(id) ON DELETE SET NULL
  contact_id            uuid           FK → contacts(id) ON DELETE CASCADE
  account_holder_id     uuid           FK → account_holders(id) ON DELETE CASCADE
  entity_type           entity_type                   -- POLYMORPHIC (trip, quote, operator…)
  entity_id             uuid
  occurred_at           timestamptz    NOT NULL DEFAULT now()
  duration_minutes      integer
  external_ref          text                          -- email Message-ID, call recording id
  metadata              jsonb          NOT NULL DEFAULT '{}'
  CHK  (entity_type IS NULL) = (entity_id IS NULL)
  IDX  (client_id, contact_id, occurred_at DESC) WHERE deleted_at IS NULL
  IDX  (client_id, entity_type, entity_id, occurred_at DESC) WHERE deleted_at IS NULL
  IDX  (client_id, user_id, occurred_at DESC)
  IDX  (client_id, occurred_at DESC)
```

```
audit_logs                               (APPEND-ONLY — no soft delete, no updated_at, no updated_by)
  id                    uuid           PK -- no DB default; app supplies UUIDv7 (§1.5)
  client_id             uuid           FK → clients(id)  (NULLABLE: platform-level events)
  occurred_at           timestamptz    NOT NULL DEFAULT now()     -- PARTITION KEY
  action                audit_action   NOT NULL
  entity_type           entity_type    NOT NULL
  entity_id             uuid
  entity_label          text                          -- human label, survives entity deletion
  actor_type            actor_type     NOT NULL DEFAULT 'user'
  actor_user_id         uuid           FK → users(id) ON DELETE SET NULL
  actor_label           text           NOT NULL       -- denormalized name+email at event time
  impersonated_by_user_id uuid         FK → users(id) ON DELETE SET NULL
  api_key_id            uuid
  changed_fields        text[]
  before                jsonb                         -- redacted: no [enc] plaintext ever
  after                 jsonb
  reason                text                          -- required for exports / permission changes
  request_id            uuid
  session_id            text
  ip_address            inet
  user_agent            text

  PARTITION BY RANGE (occurred_at), monthly; partitions detached to cold storage after 24 months
  Provisioning: migration 012 creates 2026-09 .. 2027-08 + DEFAULT; scripts/partition_maintenance.py
  (make partition-maintenance, run monthly) keeps >= 12 months of runway and alerts (exit 1) if the
  DEFAULT partition ever holds rows. Partitions have no direct grants: access is via the parent only.
  Grants: app role has SELECT + INSERT only (migration 012), asserted at the end of the chain (015);
  UPDATE/DELETE blocked for every role by trigger (013).
  IDX  (client_id, entity_type, entity_id, occurred_at DESC)   -- "history of this record"
  IDX  (client_id, actor_user_id, occurred_at DESC)            -- "what did this user do"
  IDX  (client_id, action, occurred_at DESC)
  IDX  USING BRIN (occurred_at)                                -- cheap time-range scans
  IDX  USING GIN (after jsonb_path_ops)                        -- optional, value forensics
```

```
tags †
  name                  citext         NOT NULL
  category              text                          -- 'risk','preference','campaign'
  color                 text
  description           text
  UQ   (client_id, name) WHERE deleted_at IS NULL
  IDX  (client_id, category)
```

```
entity_tags †                            (POLYMORPHIC)
  tag_id                uuid           NOT NULL FK → tags(id) ON DELETE CASCADE
  entity_type           entity_type    NOT NULL
  entity_id             uuid           NOT NULL
  UQ   (tag_id, entity_type, entity_id) WHERE deleted_at IS NULL
  IDX  (client_id, entity_type, entity_id)
  IDX  (client_id, tag_id)
```

---

## 4. ASCII ER diagram

**Legend**
```
  +====+  tenant root / hub table        1--*  one-to-many
  +----+  regular table                  *--*  many-to-many (via junction)
  (*)     shared reference catalog       -->   FK direction (child --> parent)
  [self]  self-referencing FK            ~~>   polymorphic (entity_type, entity_id)
```

### 4.1 Master overview

```
                                  +==========================+
                                  |        clients           |   TENANT ROOT
                                  |  (slug, currency, tz)    |   client_id on every table below
                                  +============+=============+
                                               |
        +-------------+-------------+----------+----------+-------------+-------------+
        |             |             |                     |             |             |
        v             v             v                     v             v             v
   +--------+   +----------+  +-----------+        +-----------+  +----------+  +-----------+
   | users  |   | segments |  | operators |        |   trips   |  |documents |  |audit_logs |
   +--------+   +----------+  +-----------+        +-----------+  +----------+  +-----------+
       |  \_ refresh_tokens (016)                        |             |          (partitioned
       |             v             |                     v             v           by month,
       |        +----------+       |                +---------+   +----------+     append-only)
       |        | contacts |       |                |  legs   |   |document_ |
       |        +----------+       |                +---------+   |  links   |~~> any entity
       |             |             |                     |        +----------+
       |             v             v                     v
       |      +-----------+  +-------------+      +--------------+
       |      |passengers |  |  aircraft   |      |leg_passengers|
       |      +-----------+  +-------------+      +--------------+
       |             |
       |             v
       |     +----------------+
       +---->| account_holders|
             +----------------+
                     |
                     v
        quotes --> bookings --> invoices --> payments
```

### 4.2 CRM spine — Clients → Segments → Contacts → Passengers → Account Holders

```
                          +==========================+
                          |         clients          |
                          +============+=============+
                                       | 1
                                       | *
                          +------------v-------------+
                    +---->|         segments         |   parent_segment_id [self]
                    +-----+------------+-------------+
                                       | 1
                                       | *
   +----------+  owner_user_id  +------v-------------+   parent_contact_id     [self]
   |  users   |<----------------+       contacts     +<-- referred_by_contact_id
   +----------+                 +--+-------+------+--+
                                   | 1     | 1    | 1
            +----------------------+       |      +-----------------------+
            | *                            | *                            | *
  +---------v----------+        +----------v---------+        +-----------v-----------+
  |  contact_channels  |        |     passengers     |        |    account_holders    |
  |  (email/phone/...) |        +--+--------------+--+        +-----------+-----------+
  +--------------------+           | 1            | *                     | 1
                                   |              |                       |
  +--------------------+           | *            |    +------------------+
  |     addresses      |~~>  +-----v----------+   |    | *
  | (polymorphic owner)|     |travel_documents|   |  +-v-------------------------------+
  +--------------------+     | passport/visa  |   +->|   account_holder_passengers     |
                             +-------+--------+      |  (relationship, spend_limit,    |
                                     |               |   is_authorized_booker)  *--*   |
                                     v               +---------------------------------+
                              documents (scan)
```

Reading the chain: a **segment** groups **contacts**; a contact may have zero or one
**passenger** identity (and a passenger may exist with no contact record at all — a guest);
passengers are linked M:N to **account holders**, the entity that actually pays. A guest flying
on someone else's account is one junction row, not a duplicate passenger.

### 4.3 Fleet — Manufacturers → Models → Aircraft → Operators

```
   +=====================+                        +=======================+
   |  manufacturers  (*) |                        |      operators        |
   |  Gulfstream, Dassault                        |  (AOC, part, status)  |
   +==========+==========+                        +==+=====+=====+========+
              | 1                                    |1    |1    |1
              | *                                    |     |     |
   +----------v----------+                           |     |     +--------------------+
   | aircraft_models (*) |                           |     |                          |
   |  G650ER, Falcon 8X  |                           | *   | *                        | *
   +----------+----------+          +----------------v--+ +v------------------+  +----v---------+
              | 1                   | operator_safety_  | |   crew_members    |  |  empty_legs  |
              | *                   |     ratings       | | (type_ratings[],  |  +------+-------+
   +----------v----------+          | ARGUS / Wyvern /  | |  medical_expiry)  |         |
   |      aircraft       |          | IS-BAO, expiry    | +---------+---------+         |
   |  tail_number N650BX +--------->+-------------------+           |                   |
   +--+---------------+--+  operator_id (current)                   | 1                 |
      | 1             | *                                           | *                 |
      |               +---------------------------+          +------v------+            |
      | *                                         |          |  leg_crew   |            |
   +--v-----------------------------+             |          +------+------+            |
   | aircraft_operator_assignments  |             |                 |                   |
   |  effective_from/to, GIST       |             |                 v                   |
   |  EXCLUDE: no overlaps          |             +------------> legs <-----------------+
   +--------------------------------+          aircraft_id                     source_leg_id
```

### 4.4 Trips → Legs → Manifests → Crew

```
   account_holders ---+                          +--- contacts (primary_contact_id)
                      |                          |
                      v                          v
                +=====+==========================+=====+
                |                trips                 |
                |  trip_number, status, dates, margin  |
                +==================+===================+
                                   | 1
                                   | *
      airports (*) <---------------+-------------------> airports (*)
      departure_airport_id  +======v==================+  arrival_airport_id
      fbos (*) <------------+          legs           +------------> fbos (*)
      departure_fbo_id      |  sched/actual times,    |  arrival_fbo_id
      aircraft <------------+  block & flight time,   |
      operators <-----------+  cost/sell per leg      |
                            +---+-----------------+---+
                                | 1               | 1
                                | *               | *
                  +-------------v------+   +------v-------------+
                  |  leg_passengers    |   |     leg_crew       |
                  |  THE MANIFEST      |   |  role, duty window |
                  |  seat, checked_in, |   |  UQ: one PIC/leg   |
                  |  APIS submitted    |   +---------+----------+
                  +----+-----------+---+             |
                       |           |                 v
                       v           v           crew_members
                 passengers  travel_documents
                             (doc flown on)
```

### 4.5 Empty Legs

```
   operators ----------+
   aircraft -----------+
   aircraft_models (*) -+---> +=====================+
   airports (*) x2 ----+      |     empty_legs      |
                       |      | window: earliest/   |
   legs ---------------+      |   latest departure  |
   (source_leg_id:            | asking / floor price|
    the positioning leg       | status, expires_at  |
    that created the offer)   +==========+==========+
                                         | booked_trip_id
                                         v
                                       trips  ---> (trips.source_empty_leg_id points back)
```

### 4.6 Commerce — Quotes → Bookings → Invoices → Payments

```
              trips                        account_holders
                | 1                              | 1
                | *                              | *
       +========v=====================+          |
   +-->|           quotes             |<---------+
   |   |  quote_number + revision     |
   +---+  parent_quote_id  [self]     |     immutable revisions:
 supersede  is_current, status, PDF   |     a sent quote is never edited,
       +===+==========================+     a new revision supersedes it
           | 1                  | 1
           | *                  | * (the one accepted quote)
  +--------v-----------+  +=====v=======================+
  | quote_line_items   |  |         bookings            |
  |  line_type, qty,   |  |  contract, e-sign, deposit, |
  |  cost vs sell,     |  |  operator confirmation ref  |
  |  leg_id            |  +==============+==============+
  +--------+-----------+                 | 1
           |                             | *
           | provenance           +======v======================+
           +--------------------->|         invoices            |<--+ parent_invoice_id
                                  |  type (deposit/balance/     |   | (credit notes)
                                  |   credit_note), AR aging    +---+
                                  +====+===================+====+
                                       | 1                 | 1
                                       | *                 | *
                       +---------------v----+      +-------v--------+
                       | invoice_line_items |      |    payments    |<--+ refund_of_payment_id
                       |  gl_account_code   |      | method, status |---+
                       +--------------------+      +----------------+
```

### 4.7 Cross-cutting / polymorphic

```
  +-------------+  1    *  +------------------+                 +---------------------------+
  |  documents  +----------+  document_links  |~~~~~~~~~~~~~~~~>| contacts, passengers,     |
  |  S3 key,    |          |  entity_type     |  (entity_type,  | operators, aircraft,      |
  |  checksum,  |          |  entity_id       |   entity_id)    | trips, legs, quotes,      |
  |  expires_at |          |  link_role       |                 | bookings, invoices,       |
  +-------------+          +------------------+                 | crew_members, ...         |
                                                                +---------------------------+
  +-------------+  1    *  +------------------+                              ^
  |    tags     +----------+   entity_tags    |~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~+
  +-------------+          +------------------+                              |
                                                                             |
  +-------------+          +------------------+          +---------------+   |
  |    tasks    |~~~~~~~~~~|    activities    |~~~~~~~~~~|  audit_logs   |~~~+
  | due queue,  |          | calls, emails,   |          | append-only,  |
  | SLA, RRULE  |          | meetings, notes  |          | partitioned   |
  +-------------+          +------------------+          +---------------+

  All four carry (entity_type, entity_id). entity_type is the single shared discriminator enum,
  so "everything about this trip" is four indexed lookups on the same key shape.
```

---

## 5. Design notes worth flagging

**Polymorphism.** Postgres cannot FK a polymorphic `entity_id`. Three options were considered:

| Option | Verdict |
|---|---|
| Nullable exclusive-arc FKs (one column per target) | Real referential integrity, but ~25 columns on `document_links` and a migration every time a new entity becomes attachable. Used only for `travel_documents` (2 targets). |
| **Link table + `entity_type` enum + validation trigger** | **Chosen.** One index shape, one code path, new targets are an enum value. Integrity enforced by a trigger that resolves `entity_type` → table and verifies the row exists in the same tenant; orphan sweep runs nightly. |
| JSONB attachment blobs | Rejected — unindexable, unqueryable, no integrity. |

**Soft delete + uniqueness.** Every business-key `UNIQUE` is partial on `deleted_at IS NULL`. This
is what lets a cancelled trip's number be reissued and stops a deleted contact from blocking an
email address forever. It also means **every application query must filter `deleted_at IS NULL`** —
enforce with a base query scope in the ORM plus RLS predicates, not by convention.

**Quote versioning.** A quote is never mutated after `sent_at`. Edits create `revision + 1` with
`parent_quote_id` pointing back; the old row flips `is_current = false`, `status = 'superseded'`.
`UQ (client_id, quote_number) WHERE is_current` guarantees exactly one live revision, and the
whole negotiation history is reconstructable — which is what matters when a customer disputes
what they were quoted.

**Materialized rollups.** `trips.total_*`, `invoices.amount_paid_cents`,
`account_holders.balance_cents`, `contacts.lifetime_value_cents`, `operators.fleet_size` are
denormalized for list-view performance. Each needs a recompute path (trigger or job) and a nightly
reconciliation check. They are reporting conveniences, never the source of truth — the line items
and payments are.

**Money.** `bigint` cents plus explicit `currency` on every money-bearing row, and
`exchange_rate` captured at invoice/payment time so historical totals don't drift when FX moves.

**Conflict detection.** Two indexes carry real operational weight:
`legs (client_id, aircraft_id, scheduled_departure_at)` catches double-booked tails, and
`leg_crew (client_id, crew_member_id, duty_start_at)` catches crew duty-time overlaps. Both are
range questions against a btree; if they become hot, promote to GiST exclusion constraints over
`tstzrange` the same way `aircraft_operator_assignments` already does.

**Compliance sweeps → tasks.** Five tables carry an indexed expiry date —
`travel_documents.expiry_date`, `operators.insurance_expiry`, `operators.aoc_expiry`,
`operator_safety_ratings.expiry_date`, `crew_members.medical_expiry`, plus
`documents.expires_at`. A nightly job scans them and creates `tasks` with a `dedupe_key` so
re-runs don't spam the queue. This is the main reason expiry columns are indexed at all.

**Audit vs activities.** Deliberately separate. `audit_logs` is machine-written, append-only,
partitioned, and immutable (UPDATE/DELETE revoked at the role level) — it answers "who changed
this field". `activities` is human-written and editable — it answers "when did we last talk to
this client". Merging them would make the audit trail untrustworthy.

**Encryption boundary.** Passport numbers, KTN, crew license numbers and tax IDs are envelope-
encrypted with a per-tenant DEK. The `*_last4` columns exist so staff can confirm a document
without decrypting. `audit_logs.before/after` must be redacted for these fields — an audit trail
that logs plaintext passport numbers defeats the encryption entirely. This is the design target;
the shipped state of this test project (single static key at the API, placeholder in the seed) is
stated in §1.2.1.

---

## 6. Scope boundary — deliberately deferred

Not in this model; each would be a follow-on design:

- **Operator sourcing / bid workflow** (broadcast an RFQ to N operators, collect bids). Today the
  cost side lives on `quote_line_items.cost_cents`. Adding `sourcing_requests` + `operator_bids`
  is additive and doesn't disturb anything above.
- **Jet card / block-hour programs** beyond the `prepaid_balance_cents` wallet field — real
  programs need hour ledgers, tier rules, and expiry.
- **Fractional ownership share tracking.**
- **Maintenance schedules / airworthiness tracking** — `aircraft.status` has `maintenance`/`aog`
  but there is no work-order model.
- **Flight tracking ingest** (ADS-B position feeds). `legs.actual_*` is the landing zone for it.
- **API keys, webhooks, integration credentials** — `audit_logs.api_key_id` anticipates the table.
- **Notification/message delivery log** (email sends, SMS). `activities` covers the CRM-visible
  side, not delivery mechanics.
- **Commission splits between multiple brokers** on one trip.

---

## 7. Verification

Since no code is being written in this step, "verification" is design review, not a test run.
Before any migration is authored, walk these end-to-end against the model above:

1. **Tenant isolation** — pick any table; confirm `client_id` is present, `NOT NULL` (or
   deliberately nullable for the shared catalog), and every unique index is tenant-scoped. Confirm
   no query path can join from tenant A to tenant B via the shared catalog.
2. **Trace the happy path** — inbound enquiry → `contacts` → `trips` (draft) → `legs` → `quotes`
   v1 → v2 → accepted → `bookings` → `invoices` (deposit + balance) → `payments` → trip flown →
   `leg_passengers` manifest closed. Every hop must be a declared FK above.
3. **Trace the awkward paths** — a guest passenger with no contact record; a trip cancelled after
   deposit (credit note); a tail that changes operator mid-trip; an empty leg that converts to a
   booked trip; a passenger whose passport expires between booking and departure.
4. **Answer the operational questions** from indexes alone, no sequential scans:
   "which passports expire in 30 days", "which operators have a lapsed ARGUS rating", "is N650BX
   double-booked on 12 March", "what is AR over 60 days", "show everything attached to trip
   BLX-2026-00147", "who edited this quote's price and when".
5. **Enum completeness** — for each enum, name a real-world value it cannot represent. If one
   exists, add it now; enums are append-only after launch.
6. **Estimate row counts and growth** for `audit_logs`, `activities`, `legs`, `document_links` —
   these dominate storage. Confirm the monthly partitioning and BRIN choice on `audit_logs` holds
   at projected volume.

Once reviewed, the next step is generating the migration set (extensions → enums → reference
catalog → tenant tables in FK dependency order → RLS policies → triggers → seed the global
airport/manufacturer/model catalog).
