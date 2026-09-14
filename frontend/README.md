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
refresh, then `GET /auth/me`. Permissions come from `/auth/me`; `RequirePermission` and the
sidebar use the same `can()`.

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

Static build (`npm run build` → `dist/`). `vercel.json` rewrites every non-`/api/` path to
`index.html` for client-side routing. Set `VITE_API_BASE_URL` to the API origin at build time
and make sure the API's `APP_CORS_ORIGINS` includes the SPA origin; if the SPA and API are on
different sites, set `APP_REFRESH_COOKIE_SAMESITE=none` (which requires HTTPS).
