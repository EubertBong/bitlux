# Bitlux CRM — frontend

Vite 6 · React 19 · TypeScript 5.9 (strict, no `any`, no `@ts-ignore`) · Tailwind 4 ·
React Router 7 · TanStack Query 5 / Table 8 · shadcn-style components on Radix ·
react-hook-form + zod · D3 v7 (force, selection, zoom, drag) · lucide-react · recharts · date-fns.

## Dev setup

```bash
# from the repo root
make up wait migrate seed     # database + demo tenant
make api                      # API on :8000
make web-install && make web  # http://localhost:5173
```

Sign in with `owner@demo.test` / `Demo!2026` (also `broker@`, `ops@`).

```bash
make web-test                 # tsc --noEmit, eslint, vitest
make web-build                # frontend/dist
make screenshots              # docs/screenshots/*.png via the system Chrome (app must be running)
make verify-ui                # sidebar scroll / layout gap / top bar / theme checks in Chrome (app must be running)
```

## Environment

| variable | default | notes |
|---|---|---|
| `VITE_API_BASE_URL` | `http://localhost:8000/api/v1` | no trailing slash; must be same-site with the SPA for the refresh cookie (localhost ports are same-site) |

Copy `.env.example` to `.env.local` to override.

## Auth model

The access token lives **in memory only** (`src/lib/api.ts` → `tokenStore`); it is never
written to `localStorage`, `sessionStorage`, or a readable cookie. The refresh token is an
**HttpOnly cookie** set by the API on login, rotated on refresh, cleared on logout; the SPA
never sees it. On a 401 the client calls `/auth/refresh` (cookie goes along with
`credentials: "include"`), stores the new access token in memory and retries the original
request **once**; concurrent 401s share one refresh. On page load the app performs a silent
refresh, then `GET /auth/me` — but only if the browser has signed in here before, which it
remembers with a boolean `bitlux-session` flag in `localStorage` (set on login, cleared on
logout). The flag is not a credential; it just avoids a guaranteed 401 on a first visit.
Permissions come from `/auth/me`; `RequirePermission` and the sidebar use the same `can()`.

**Sensitive fields never reach the browser.** The API does not return raw `[enc]`
values (passport / travel-document numbers, known-traveler and redress numbers, tax
IDs, crew licence numbers); read models carry only the `*_last4` companions, which is
what the UI renders. Forms send the plaintext once on create/update and the API
encrypts it. See `DATA_MODEL.md` §1.2.1 for the encryption scope of this test project.

## Theme

Light / dark / system, chosen from the toggle next to the avatar and stored under
`localStorage["bitlux-theme"]` (default `system`, which follows `prefers-color-scheme` live).
`src/lib/theme.tsx` owns it: one `dark` class plus `color-scheme` on `<html>`, applied again
inline in `index.html` before first paint so there is no flash. All colours are CSS variables
in `src/index.css` (`:root` light, `.dark` dark, including the `sidebar-*` set) exposed to
Tailwind through `@theme inline`; Tailwind 4's `@custom-variant dark` is the class-based dark
mode. The sidebar's thin hover-only scrollbar is the `.sidebar-scroll` utility in the same file.

## Layout

```
src/
├── lib/            api client, auth context + guards, query client, types, formatters
├── components/
│   ├── ui/         shadcn-style primitives (Button, Card, Dialog, Command, Select, Sheet, …)
│   ├── layout/     AppShell (sidebar / top bar / mobile tab bar) and the permission-gated nav
│   ├── common/     PageHeader, DataTable (server-driven TanStack table), loading/error states
│   ├── GlobalSearch/   ⌘K palette over /search (debounced 200 ms, grouped by type)
│   └── RelationshipGraph/  the D3 force graph over /graph/{entity}/{id}
├── pages/
│   ├── clients/    the fully implemented reference: list (filters, sort, paging, create) + detail (tabs, KPIs, graph)
│   ├── resources.tsx   skeleton list/detail for every other route (Sprint 5 fills these in)
│   └── Login, Dashboard, AuthCallback, NotFound
└── test/           vitest setup + render helpers
```

## The actions layer

`src/components/actions/` holds the CRUD primitives — `CreateButton`, `EditButton`,
`DeleteButton`, `ActionMenu` (⋯ Edit / Duplicate / Archive / Delete), `ConfirmDialog`,
`ResourceForm`, `EntityFormDialog`, `EntityFormPage` — and `useEntityActions.ts` holds the
mutations behind them (success toast with the entity's name, cache refresh, Undo for soft
delete via `POST /<resource>/<id>/restore`). They read one registry: each entity module in
`src/entities/` registers its endpoint, route, permission prefix, name function, optional
archive status and a form descriptor (Zod schema + field metadata + record↔payload
mapping). Adding an entity is a module plus pages; the primitives do not change. Server
422s land on the field they name; 403/404 are worded explicitly (`src/lib/errors.ts`).
Contacts (`src/pages/contacts/`) is the reference implementation.

**Testing note.** jsdom's selector engine `nwsapi` 2.2.27 makes every Radix menu open take
~12 s; `package.json` pins it to 2.2.16 via `overrides`, which brings it to ~60 ms. Keep
the override until jsdom ships a fixed version.

## The relationship graph

`<RelationshipGraph entityType="client" entityId={id} />` fetches
`/graph/{entity}/{id}?depth=1|2`, prepares the nodes (type filter, degree, root), runs a
d3-force simulation (link / many-body / center / collide) and renders SVG from React. D3 owns
the numbers — simulation, zoom transform, drag — React owns the DOM. Nodes are coloured and
iconed by type, sized by degree, labelled (truncated, full label in the tooltip), and are
keyboard-focusable buttons (Tab, Enter/Space to open). Edges carry arrowheads and labels (labels
hide when there are more than 60 edges or when zoomed out). Controls: depth 1/2, per-type
show/hide (also via the legend), zoom in/out, fit, reset. Loading is a pulsing skeleton; errors
show "Graph unavailable" with retry, and a 400 `graph_too_large` offers a way back to depth 1.
The simulation is stopped on unmount. SVG only — the backend caps depth 2 at 200 nodes, well
inside SVG's budget; canvas can be added behind the same data preparation if the cap rises.

## Deploy

Cloudflare Pages, root directory `frontend`, build `npm run build`, output `dist`.
`public/_redirects` rewrites every path to `index.html` for client-side routing and
`public/_headers` adds the security headers; both are copied into `dist/` by Vite.
`vite.config.ts` throws at build time if `VITE_API_BASE_URL` is not set (locally it
comes from `frontend/.env`). The API on Render is another site, so its
`REFRESH_COOKIE_SAMESITE=none` + `REFRESH_COOKIE_SECURE=true` and its `CORS_ORIGINS`
must name the exact Pages origin. Full sequence: [docs/DEPLOY.md](../docs/DEPLOY.md).
