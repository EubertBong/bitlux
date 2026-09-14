/**
 * Skeleton pages for every route Sprint 5 will fill in: a heading, a loading
 * state, an error state, and a first page of rows so the navigation is real.
 * Detail pages for the eight graph-bearing entities carry the Relationship tab.
 */

import * as React from "react"
import { Link, useParams, useSearchParams } from "react-router"
import { useQuery } from "@tanstack/react-query"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { PageHeader } from "@/components/common/PageHeader"
import { EmptyState, ErrorState, LoadingState } from "@/components/common/States"
import { RelationshipGraph } from "@/components/RelationshipGraph"
import { api, qs } from "@/lib/api"
import { fmtDateTime, titleCase } from "@/lib/format"
import type { AnyRecord, Page } from "@/lib/types"

export interface ResourceSpec {
  /** Route path (dashes) */
  path: string
  /** API collection path (underscores) */
  endpoint: string
  title: string
  permission: string | null
  /** Fields shown in the skeleton list. */
  columns: string[]
  /** Which field labels a row. */
  labelField: string
  /** Graph node type, if detail pages should carry a Relationship tab. */
  graphType?: string
  detail?: boolean
  /** Response is a bare array rather than a Page. */
  listIsArray?: boolean
}

export const RESOURCES: ResourceSpec[] = [
  { path: "contacts", endpoint: "/contacts", title: "Contacts", permission: "contacts.view", columns: ["display_name", "status", "primary_email", "company_name"], labelField: "display_name", graphType: "contact", detail: true },
  { path: "passengers", endpoint: "/passengers", title: "Passengers", permission: "passengers.view", columns: ["first_name", "last_name", "nationality_code", "status"], labelField: "last_name", graphType: "passenger", detail: true },
  { path: "aircraft", endpoint: "/aircraft", title: "Aircraft", permission: "aircraft.view", columns: ["tail_number", "status", "year_of_manufacture", "hourly_rate_cents"], labelField: "tail_number", graphType: "aircraft", detail: true },
  { path: "operators", endpoint: "/operators", title: "Operators", permission: "operators.view", columns: ["legal_name", "status", "country_code", "regulatory_part"], labelField: "legal_name", graphType: "operator", detail: true },
  { path: "airports", endpoint: "/airports", title: "Airports", permission: "airports.view", columns: ["icao_code", "iata_code", "name", "country_code"], labelField: "name", graphType: "airport", detail: true },
  { path: "crew", endpoint: "/crew", title: "Crew", permission: "crew.view", columns: ["first_name", "last_name", "primary_role", "medical_expiry"], labelField: "last_name", graphType: "crew_member", detail: true },
  { path: "trips", endpoint: "/trips", title: "Trips", permission: "trips.view", columns: ["trip_number", "status", "departure_date", "pax_count", "total_sell_cents"], labelField: "trip_number", graphType: "trip", detail: true },
  { path: "empty-legs", endpoint: "/empty_legs", title: "Empty legs", permission: "empty_legs.view", columns: ["status", "earliest_departure_at", "seats_available", "asking_price_cents"], labelField: "id", graphType: "empty_leg", detail: true },
  { path: "quotes", endpoint: "/quotes", title: "Quotes", permission: "quotes.view", columns: ["quote_number", "revision", "status", "total_cents", "currency"], labelField: "quote_number", graphType: "quote", detail: true },
  { path: "bookings", endpoint: "/bookings", title: "Bookings", permission: "bookings.view", columns: ["booking_number", "status", "total_cents"], labelField: "booking_number", graphType: "booking", detail: true },
  { path: "invoices", endpoint: "/invoices", title: "Invoices", permission: "invoices.view", columns: ["invoice_number", "invoice_type", "status", "due_date", "balance_cents"], labelField: "invoice_number", graphType: "invoice", detail: true },
  { path: "documents", endpoint: "/documents", title: "Documents", permission: "documents.view", columns: ["title", "document_type", "status", "expires_at"], labelField: "title", graphType: "document", detail: true },
  { path: "tasks", endpoint: "/tasks", title: "Tasks", permission: "tasks.view", columns: ["title", "status", "priority", "due_at"], labelField: "title", graphType: "task", detail: true },
  { path: "account-holders", endpoint: "/account_holders", title: "Account holders", permission: "account_holders.view", columns: ["account_number", "name", "status", "balance_cents"], labelField: "name", graphType: "account_holder", detail: true },
  { path: "manufacturers", endpoint: "/manufacturers", title: "Manufacturers", permission: "manufacturers.view", columns: ["name", "code", "country_code"], labelField: "name", graphType: "manufacturer", detail: true },
  { path: "aircraft-models", endpoint: "/aircraft_models", title: "Aircraft models", permission: "aircraft_models.view", columns: ["name", "family", "icao_type_code", "category"], labelField: "name", graphType: "aircraft_model", detail: true },
  { path: "segments", endpoint: "/segments", title: "Segments", permission: "segments.view", columns: ["name", "code", "segment_type"], labelField: "name", graphType: "segment", detail: true },
  { path: "admin/users", endpoint: "/admin/users", title: "Users", permission: "users.view", columns: ["full_name", "email", "role", "status"], labelField: "full_name", graphType: "user", detail: true },
  { path: "admin/roles", endpoint: "/admin/roles", title: "Roles", permission: "users.view", columns: [], labelField: "role" },
  { path: "admin/audit-log", endpoint: "/admin/audit-log", title: "Audit log", permission: "audit.view", columns: ["occurred_at", "action", "entity_type", "entity_label", "actor_label"], labelField: "entity_label" },
]

function renderValue(v: unknown): React.ReactNode {
  if (v === null || v === undefined) return <span className="text-muted-foreground">—</span>
  if (typeof v === "boolean") return v ? "Yes" : "No"
  if (typeof v === "number") return v.toLocaleString()
  if (typeof v === "string") {
    if (/^\d{4}-\d{2}-\d{2}T/.test(v)) return fmtDateTime(v)
    return v
  }
  return JSON.stringify(v)
}

function isPage(v: unknown): v is Page<AnyRecord> {
  return typeof v === "object" && v !== null && "items" in v && Array.isArray((v as Page<unknown>).items)
}

export function ResourceListPage({ resource }: { resource: ResourceSpec }) {
  const [params, setParams] = useSearchParams()
  const page = Math.max(1, Number(params.get("page") ?? 1))
  const pageSize = 25
  const query = useQuery({
    queryKey: [resource.endpoint, "list", page],
    queryFn: () => api.get<Page<AnyRecord> | AnyRecord[] | Record<string, unknown>>(`${resource.endpoint}${resource.columns.length ? qs({ page, page_size: pageSize }) : ""}`),
  })

  // /admin/roles is a map, not a list: render it as such.
  if (resource.path === "admin/roles") {
    return (
      <div>
        <PageHeader title={resource.title} description="Role → permission map (from the API)" />
        {query.isPending ? <LoadingState /> : query.isError ? <ErrorState error={query.error} onRetry={() => void query.refetch()} /> : (
          <div className="grid gap-4 md:grid-cols-2">
            {Object.entries(query.data as Record<string, string[]>).map(([role, perms]) => (
              <Card key={role}><CardContent>
                <div className="mb-2 font-medium">{titleCase(role)} <span className="text-xs text-muted-foreground">({perms.length})</span></div>
                <div className="flex flex-wrap gap-1">{perms.slice(0, 40).map((p) => <Badge key={p} variant="secondary" className="font-mono text-[10px]">{p}</Badge>)}{perms.length > 40 && <Badge variant="outline">+{perms.length - 40} more</Badge>}</div>
              </CardContent></Card>
            ))}
          </div>
        )}
      </div>
    )
  }

  const items: AnyRecord[] = isPage(query.data) ? query.data.items : Array.isArray(query.data) ? (query.data as AnyRecord[]) : []
  const total = isPage(query.data) ? query.data.total : items.length
  const pageCount = Math.max(1, Math.ceil(total / pageSize))

  return (
    <div>
      <PageHeader title={resource.title} description={<span>Skeleton view — full implementation arrives in Sprint 5. <span className="text-xs">({total} total)</span></span>} />
      {query.isPending ? <LoadingState /> : query.isError ? <ErrorState error={query.error} onRetry={() => void query.refetch()} /> : items.length === 0 ? <EmptyState>No {resource.title.toLowerCase()} yet</EmptyState> : (
        <div className="rounded-lg border bg-card">
          <Table>
            <TableHeader><TableRow>{resource.columns.map((c) => <TableHead key={c}>{titleCase(c)}</TableHead>)}</TableRow></TableHeader>
            <TableBody>
              {items.map((row) => (
                <TableRow key={row.id} data-testid="table-row">
                  {resource.columns.map((c, i) => (
                    <TableCell key={c}>
                      {i === 0 && resource.detail ? <Link className="font-medium hover:underline" to={`/${resource.path}/${row.id}`}>{renderValue(row[c])}</Link> : renderValue(row[c])}
                    </TableCell>
                  ))}
                </TableRow>
              ))}
            </TableBody>
          </Table>
          {pageCount > 1 && (
            <div className="flex items-center justify-end gap-2 border-t p-2 text-sm">
              <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setParams({ page: String(page - 1) })}>Previous</Button>
              <span className="text-muted-foreground">Page {page} of {pageCount}</span>
              <Button variant="outline" size="sm" disabled={page >= pageCount} onClick={() => setParams({ page: String(page + 1) })}>Next</Button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export function ResourceDetailPage({ resource }: { resource: ResourceSpec }) {
  const { id = "" } = useParams()
  const [params, setParams] = useSearchParams()
  const tab = params.get("tab") ?? "overview"
  const query = useQuery({ queryKey: [resource.endpoint, id], queryFn: () => api.get<AnyRecord>(`${resource.endpoint}/${id}`), enabled: id.length > 0 })
  const label = query.data ? String(query.data[resource.labelField] ?? id) : "…"

  return (
    <div>
      <PageHeader title={label} description={`${resource.title.replace(/s$/, "")} · skeleton view`} />
      {query.isPending ? <LoadingState /> : query.isError ? <ErrorState error={query.error} onRetry={() => void query.refetch()} /> : (
        <Tabs value={tab} onValueChange={(v) => setParams({ tab: v })}>
          <TabsList>
            <TabsTrigger value="overview">Overview</TabsTrigger>
            {resource.graphType && <TabsTrigger value="relationship" data-testid="tab-relationship">Relationship</TabsTrigger>}
          </TabsList>
          <TabsContent value="overview">
            <Card><CardContent>
              <dl className="grid gap-x-8 gap-y-2 text-sm sm:grid-cols-2 lg:grid-cols-3">
                {Object.entries(query.data).filter(([k]) => !["search_tsv", "ocr_tsv"].includes(k)).map(([k, v]) => (
                  <div key={k} className="flex flex-col"><dt className="text-xs text-muted-foreground">{titleCase(k)}</dt><dd className="truncate">{renderValue(v)}</dd></div>
                ))}
              </dl>
            </CardContent></Card>
          </TabsContent>
          {resource.graphType && (
            <TabsContent value="relationship">
              <RelationshipGraph entityType={resource.graphType} entityId={id} />
            </TabsContent>
          )}
        </Tabs>
      )}
    </div>
  )
}
