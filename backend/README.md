# Bitlux CRM — backend

FastAPI + SQLModel + PostgreSQL 16. Everything here runs as the `bitlux_app` role
with Row-Level Security enforced; see [`../DATA_MODEL.md` §1.7](../DATA_MODEL.md).

## Run it

```bash
make up wait migrate seed     # postgres:16 on :5433, schema at 016, demo tenant
make api                      # uvicorn with reload on :8000  (PORT=8010 make api)
open http://127.0.0.1:8000/api/v1/docs
```

Demo users (password `Demo!2026`): `owner@demo.test`, `broker@demo.test`, `ops@demo.test`.

```bash
make test                     # 30 tests: repositories + API, each in a rolled-back transaction
```

## Environment

Settings are read by `app/config.py` with the `APP_` prefix (and from `backend/.env`).

| Variable | Default | Notes |
|---|---|---|
| `APP_DATABASE_URL` | `postgresql+asyncpg://bitlux_app:bitlux_app@localhost:5433/bitlux_crm` | **Must be the app role.** Migrations use `DATABASE_URL` (the owner). |
| `APP_JWT_SECRET` / `JWT_SECRET` | dev value | HS256 key for access tokens |
| `APP_JWT_REFRESH_SECRET` / `JWT_REFRESH_SECRET` | dev value | HS256 key for refresh tokens |
| `APP_FIELD_ENCRYPTION_KEY` | dev value | Fernet material for the `[enc]` columns |
| `APP_ENV` | `local` | Anything but `local`/`test` refuses to start on dev-default secrets |
| `APP_CORS_ORIGINS` | `http://localhost:5173,http://localhost:3000` | comma-separated |
| `APP_LOG_LEVEL` | `INFO` | |
| `APP_GRAPH_MAX_NODES` | `200` | `/graph` node cap |
| `APP_SEARCH_DEFAULT_LIMIT` / `APP_SEARCH_MAX_LIMIT` | `5` / `25` | per type |

## Auth flow

```
POST /api/v1/auth/login    {email, password[, client_slug]}  ->  {access_token, refresh_token, expires_in: 900}
GET  /api/v1/auth/me       Authorization: Bearer <access>    ->  profile + effective permissions
POST /api/v1/auth/refresh  {refresh_token}                   ->  new pair; the old refresh token is revoked
POST /api/v1/auth/logout   {refresh_token}                   ->  204; revokes it
```

* Passwords: argon2id (`argon2-cffi`). Tokens: PyJWT HS256; access 15 min, refresh 7 days.
* Refresh tokens are **stateful**: a SHA-256 of each lives in `refresh_tokens`; every refresh
  rotates, and presenting an already-rotated token revokes the user's whole family.
* Login is the one step that runs before a tenant is known. It uses `auth_lookup_user()`
  (migration 016), a `SECURITY DEFINER` function that finds a user by email across tenants and
  returns only what login needs. If the email exists in several tenants the response is 409 and
  `client_slug` is required. Everything afterwards runs inside a tenant transaction under RLS.
* The access token carries `role`, but every request re-reads the user row (under RLS); a
  demotion or deactivation takes effect on the next request.

## RBAC

Permission keys are `<resource>.<action>` (`view create edit delete manage`, plus
`documents.upload`, `billing.transfer`). `require_permission(key)` raises 403 with
`{"required": key, "role": ...}` in `details`. The map (`app/security/permissions.py`):

| role | grants |
|---|---|
| owner | `*` |
| admin | `*` except `billing.transfer` |
| broker | `clients.* contacts.* passengers.* trips.* quotes.* bookings.* documents.view documents.upload tasks.* activities.* empty_legs.view` |
| ops | `trips.* legs.* aircraft.view operators.view crew.* documents.view documents.upload tasks.*` |
| finance | `invoices.* payments.* quotes.view bookings.view billing.* documents.view` |
| read_only | `*.view` |

`GET /admin/roles` returns the expanded map.

## Endpoints

Every resource below has the standard six: `GET /x`, `GET /x/{id}`, `POST /x`, `PATCH /x/{id}`,
`DELETE /x/{id}` (soft delete), `GET /x/{id}/relationships` (depth-1 graph). Lists take `page`,
`page_size`, `order_by` (`-col` for descending) and the equality filters listed in each
operation's OpenAPI description. Full list: `/api/v1/openapi.json` (117 paths, 190 operations).

| prefix | extra routes |
|---|---|
| `/auth` | `login` `refresh` `logout` `me` |
| `/admin` | `users` (CRUD), `roles`, `audit-log`, `audit-log/{entity_type}/{entity_id}` |
| `/search` | `?q=&types=&limit=` |
| `/graph` | `/{entity}/{id}?depth=1\|2`, `/types` |
| `/clients` `/segments` | — |
| `/contacts` | `{id}/channels` (GET, POST) `{id}/passengers` `{id}/activities` |
| `/passengers` | `expiring-passports` `{id}/travel-documents` (GET, POST) `{id}/flight-history` |
| `/account_holders` | `{id}/invoices` |
| `/manufacturers` `/aircraft_models` | — (shared catalog: global rows + tenant overrides) |
| `/operators` | `lapsed-ratings` `insurance-expiring` `{id}/safety-ratings` (GET, POST) |
| `/aircraft` | `available` `by-tail/{tail}` `{id}/conflicts` `{id}/double-booked` |
| `/airports` | `by-code/{code}` `nearby` `{id}/fbos` |
| `/crew` | `medical-expiring` `with-rating/{icao_type}` |
| `/trips` | `upcoming` `thin-margin` `{id}/legs` `{id}/quotes` `{id}/booking` |
| `/legs` | `{id}/manifest` (GET, POST) `{id}/crew` (GET, POST) |
| `/empty_legs` | `search?origin=&destination=&date_from=&date_to=[&cabin_class=]` |
| `/quotes` | `{id}/line-items` (GET, POST) `{id}/revisions` `{id}/supersede` |
| `/bookings` | `awaiting-deposit` |
| `/invoices` | `ar-aging` `overdue` `{id}/line-items` (GET, POST) `{id}/payments` |
| `/payments` `/activities` | — |
| `/documents` | `expiring` `for/{entity_type}/{entity_id}` `{id}/links` (POST) |
| `/tasks` | `my-queue` `overdue` `{id}/complete` |

### `/search`

`GET /search?q=gulf&types=contacts,operators&limit=5`. Uses the generated `tsvector` columns and
their GIN indexes — never `ILIKE`. Input goes through `websearch_to_tsquery` (quotes, AND, OR,
`-not`) OR-ed with a prefix query on the last word so half-typed input matches. Results are
grouped by type; each hit is `{id, type, label, subtitle, url, rank}`. Types the caller lacks
`*.view` for are silently omitted; RLS scopes the rest.

The match itself runs inside `search_ids()` (migration 017), a `SECURITY DEFINER` function that
is tenant-scoped by `current_client_id()`. Reason: under RLS, PostgreSQL won't use a
non-leakproof operator such as `@@` as an index condition, so a plain `WHERE search_tsv @@ …`
from the app role is always a sequential scan. The function returns `(id, rank)` and the API
joins those ids from a query that is still under RLS. Details: `DATA_MODEL.md` §1.7.

### `/graph/{entity}/{id}?depth=`

Returns `{"nodes": [{id, type, label, subtitle, url}], "edges": [{from, to, type, label}]}` —
D3 `forceLink` takes it as-is with `id` accessors. `depth=1` is direct neighbours, `depth=2`
neighbours of neighbours; more than `APP_GRAPH_MAX_NODES` (200) nodes returns
`400 graph_too_large`. Node types the caller may not view are skipped; a root the caller may not
view is a 404, like a row in another tenant. Edge specs per type live in
`app/repositories/graph.py::EDGES`.

## Errors and logging

Every error has one shape:

```json
{"error": {"code": "not_found", "message": "Contact not found", "details": {"id": "…"}}}
```

`unauthorized` 401 · `permission_denied` 403 · `not_found` 404 (another tenant's row is
indistinguishable from a missing one — nothing leaks) · `conflict` 409 · `validation_error` 422 ·
`graph_too_large` 400 · `internal_error` 500 with `request_id`. Every response carries
`X-Request-ID` (honoured if the client sends one), and every request logs one line:
`METHOD path status=… duration_ms=… user_id=… client_id=… rid=…`.

## Sensitive fields

`[enc]` columns (`DATA_MODEL.md` §1.2 — passport numbers, KTN, redress, tax id, crew licence)
are accepted as plaintext on write, stored as Fernet ciphertext with a `*_last4` beside them, and
**never returned**; only the `*_last4` appears in any schema. Audit `before`/`after` snapshots
drop them entirely. `test_encrypted_fields_not_in_response` asserts the plaintext is absent from
every response body that could carry it.
