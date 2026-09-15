/**
 * Generic list and detail pages for every resource without a bespoke page yet.
 *
 * They are real pages: server-driven table with search, status filter, sorting
 * and paging; the standard header actions (New, ⋯ Actions with CSV export and a
 * column chooser); a per-row ⋯ menu (View / Edit / Duplicate / Archive /
 * Delete); and a detail page with Back, title, status, Edit / Delete / ⋯ More,
 * a details card, the entity's related sections and the Relationship graph.
 * What each entity can do comes from its module in src/entities.
 */

import * as React from "react"
import { Link, useNavigate, useParams, useSearchParams } from "react-router"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import type { ColumnDef, RowSelectionState, SortingState, VisibilityState } from "@tanstack/react-table"
import { Plus, X } from "lucide-react"
import { toast } from "sonner"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { PageHeader } from "@/components/common/PageHeader"
import { DataTable } from "@/components/common/DataTable"
import { BackLink } from "@/components/common/BackLink"
import { ListActionsMenu, SelectionBar } from "@/components/common/ListActionsMenu"
import { EmptyState, ErrorState, LoadingState } from "@/components/common/States"
import { RelationshipGraph } from "@/components/RelationshipGraph"
import { ActionMenu, CreateButton, DeleteButton, EditButton, MoreMenu, Planned, ResourceForm } from "@/components/actions"
import { getEntity, type AnyRow, type EntityConfig, type SectionSpec } from "@/components/actions/registry"
import { api, qs } from "@/lib/api"
import { useAuth } from "@/lib/auth"
import { fmtDate, fmtDateTime, money, titleCase } from "@/lib/format"
import { useFkLabels, type FkLabel } from "@/lib/fkLabels"
import type { AnyRecord, Page } from "@/lib/types"

export interface ResourceSpec {
  /** Route path (dashes) */
  path: string
  /** API collection path (underscores) */
  endpoint: string
  title: string
  permission: string | null
  /** Fields shown in the list. */
  columns: string[]
  /** Which field labels a row. */
  labelField: string
  /** Graph node type, if detail pages should carry a Relationship tab. */
  graphType?: string
  detail?: boolean
  /** Registry kind (src/entities) that drives the actions. */
  entity?: string
}

export const RESOURCES: ResourceSpec[] = [
  { path: "contacts", endpoint: "/contacts", title: "Contacts", permission: "contacts.view", columns: ["display_name", "status", "primary_email", "company_name"], labelField: "display_name", graphType: "contact", detail: true, entity: "contact" },
  { path: "passengers", endpoint: "/passengers", title: "Passengers", permission: "passengers.view", columns: ["first_name", "last_name", "nationality_code", "date_of_birth", "status"], labelField: "last_name", graphType: "passenger", detail: true, entity: "passenger" },
  { path: "aircraft", endpoint: "/aircraft", title: "Aircraft", permission: "aircraft.view", columns: ["tail_number", "status", "year_of_manufacture", "max_passengers", "hourly_rate_cents"], labelField: "tail_number", graphType: "aircraft", detail: true, entity: "aircraft" },
  { path: "operators", endpoint: "/operators", title: "Operators", permission: "operators.view", columns: ["legal_name", "status", "country_code", "regulatory_part", "is_preferred"], labelField: "legal_name", graphType: "operator", detail: true, entity: "operator" },
  { path: "airports", endpoint: "/airports", title: "Airports", permission: "airports.view", columns: ["icao_code", "iata_code", "name", "city", "country_code"], labelField: "name", graphType: "airport", detail: true, entity: "airport" },
  { path: "crew", endpoint: "/crew", title: "Crew", permission: "crew.view", columns: ["first_name", "last_name", "primary_role", "status", "medical_expiry"], labelField: "last_name", graphType: "crew_member", detail: true, entity: "crew_member" },
  { path: "trips", endpoint: "/trips", title: "Trips", permission: "trips.view", columns: ["trip_number", "status", "trip_type", "departure_date", "pax_count", "total_sell_cents"], labelField: "trip_number", graphType: "trip", detail: true, entity: "trip" },
  { path: "empty-legs", endpoint: "/empty_legs", title: "Empty legs", permission: "empty_legs.view", columns: ["status", "earliest_departure_at", "latest_departure_at", "seats_available", "asking_price_cents"], labelField: "id", graphType: "empty_leg", detail: true, entity: "empty_leg" },
  { path: "quotes", endpoint: "/quotes", title: "Quotes", permission: "quotes.view", columns: ["quote_number", "revision", "status", "total_cents", "currency", "valid_until"], labelField: "quote_number", graphType: "quote", detail: true, entity: "quote" },
  { path: "bookings", endpoint: "/bookings", title: "Bookings", permission: "bookings.view", columns: ["booking_number", "status", "total_cents", "deposit_due_at"], labelField: "booking_number", graphType: "booking", detail: true, entity: "booking" },
  { path: "invoices", endpoint: "/invoices", title: "Invoices", permission: "invoices.view", columns: ["invoice_number", "invoice_type", "status", "due_date", "total_cents", "balance_cents"], labelField: "invoice_number", graphType: "invoice", detail: true, entity: "invoice" },
  { path: "documents", endpoint: "/documents", title: "Documents", permission: "documents.view", columns: ["title", "document_type", "status", "expires_at"], labelField: "title", graphType: "document", detail: true, entity: "document" },
  { path: "tasks", endpoint: "/tasks", title: "Tasks", permission: "tasks.view", columns: ["title", "status", "priority", "task_type", "due_at"], labelField: "title", graphType: "task", detail: true, entity: "task" },
  { path: "account-holders", endpoint: "/account_holders", title: "Account holders", permission: "account_holders.view", columns: ["account_number", "name", "account_type", "status", "balance_cents"], labelField: "name", graphType: "account_holder", detail: true, entity: "account_holder" },
  { path: "manufacturers", endpoint: "/manufacturers", title: "Manufacturers", permission: "manufacturers.view", columns: ["name", "code", "country_code"], labelField: "name", graphType: "manufacturer", detail: true, entity: "manufacturer" },
  { path: "aircraft-models", endpoint: "/aircraft_models", title: "Aircraft models", permission: "aircraft_models.view", columns: ["name", "family", "icao_type_code", "category", "range_nm"], labelField: "name", graphType: "aircraft_model", detail: true, entity: "aircraft_model" },
  { path: "segments", endpoint: "/segments", title: "Segments", permission: "segments.view", columns: ["name", "code", "segment_type"], labelField: "name", graphType: "segment", detail: true, entity: "segment" },
  { path: "admin/users", endpoint: "/admin/users", title: "Users", permission: "users.view", columns: ["full_name", "email", "role", "status", "last_login_at"], labelField: "full_name", graphType: "user", detail: true, entity: "user" },
  { path: "admin/roles", endpoint: "/admin/roles", title: "Roles", permission: "users.view", columns: [], labelField: "role" },
  { path: "admin/audit-log", endpoint: "/admin/audit-log", title: "Audit log", permission: "audit.view", columns: ["occurred_at", "action", "entity_type", "entity_label", "actor_label"], labelField: "entity_label", entity: "audit_log" },
]

/**
 * Dashboard tiles deep-link into a list with a named view, e.g. /documents?expiring=30
 * and /tasks?assigned=me. Each maps to an endpoint the API already exposes; the list
 * shows a removable chip so the narrowing is never invisible.
 */
const VIEWS: Record<string, { param: string; label: (v: string) => string; endpoint: (v: string) => string }> = {
  documents: { param: "expiring", label: (v) => `Expiring within ${v} days`, endpoint: (v) => `/documents/expiring${qs({ days: Number(v) || 30 })}` },
  tasks: { param: "assigned", label: () => "Assigned to me", endpoint: () => "/tasks/my-queue" },
}

/** Resources whose list endpoint accepts ?q= (see backend ResourceSpec.search_type). */
const SEARCHABLE = new Set(["contacts", "passengers", "operators", "aircraft", "trips", "quotes", "airports", "documents", "manufacturers", "aircraft-models"])
const PAGE_SIZE = 25
const ALL = "__all__"

const STATUS_VARIANT: Record<string, "success" | "secondary" | "warning" | "destructive" | "outline"> = {
  active: "success", approved: "success", confirmed: "success", completed: "success", paid: "success", available: "success", accepted: "success", cleared: "success",
  lead: "secondary", draft: "secondary", pending: "secondary", open: "secondary", prospect: "warning", sourcing: "warning", quoted: "warning", sent: "warning", viewed: "warning", negotiating: "warning", in_progress: "warning", issued: "warning", partially_paid: "warning", on_hold: "warning", under_review: "warning", conditional: "warning", blocked: "warning", maintenance: "warning", overdue: "destructive", aog: "destructive",
  cancelled: "outline", archived: "outline", expired: "outline", withdrawn: "outline", superseded: "outline", declined: "destructive", void: "outline", suspended: "destructive", blacklisted: "destructive", inactive: "outline", retired: "outline", disabled: "outline", locked: "destructive", dormant: "outline", churned: "outline",
}
export function StatusBadge({ value }: { value: string }) {
  return <Badge variant={STATUS_VARIANT[value] ?? "secondary"}>{titleCase(value)}</Badge>
}

function isPage(v: unknown): v is Page<AnyRecord> {
  return typeof v === "object" && v !== null && "items" in v && Array.isArray((v as Page<unknown>).items)
}

const MONEY = /_cents$/
const DATE_ONLY = /(_date|_expiry|date_of_birth|due_date|issue_date|expiry_date)$/

export function renderValue(key: string, v: unknown, currency = "USD", fk?: (field: string, id: string) => FkLabel | null): React.ReactNode {
  if (v === null || v === undefined || v === "") return <span className="text-muted-foreground">—</span>
  if (typeof v === "boolean") return v ? "Yes" : "No"
  if (typeof v === "number") return MONEY.test(key) ? money(v, currency) : v.toLocaleString()
  if (typeof v === "string") {
    if (key === "status" || key.endsWith("_status")) return <StatusBadge value={v} />
    if (/^\d{4}-\d{2}-\d{2}T/.test(v)) return fmtDateTime(v)
    if (/^\d{4}-\d{2}-\d{2}$/.test(v) || DATE_ONLY.test(key)) return fmtDate(v)
    if (/^[0-9a-f]{8}-[0-9a-f]{4}-/.test(v)) {
      const hit = fk?.(key, v)
      if (hit) return hit.to ? <Link className="font-medium hover:underline" to={hit.to}>{hit.label}</Link> : hit.label
      return <span className="font-mono text-xs text-muted-foreground" title={v}>{v.slice(0, 8)}…</span>
    }
    return v
  }
  if (Array.isArray(v)) return v.length ? v.map(String).join(", ") : <span className="text-muted-foreground">—</span>
  return <pre className="whitespace-pre-wrap font-mono text-xs">{JSON.stringify(v, null, 2)}</pre>
}

function RolesPage({ resource }: { resource: ResourceSpec }) {
  const query = useQuery({ queryKey: [resource.endpoint], queryFn: () => api.get<Record<string, string[]>>(resource.endpoint) })
  return (
    <div>
      <PageHeader title={resource.title} description="Role → permission map, as the API enforces it" />
      {query.isPending ? <LoadingState /> : query.isError ? <ErrorState error={query.error} onRetry={() => void query.refetch()} /> : (
        <div className="grid gap-4 md:grid-cols-2">
          {Object.entries(query.data).map(([role, perms]) => (
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

export function ResourceListPage({ resource }: { resource: ResourceSpec }) {
  if (resource.path === "admin/roles") return <RolesPage resource={resource} />
  return <GenericListPage resource={resource} />
}

function GenericListPage({ resource }: { resource: ResourceSpec }) {
  const cfg: EntityConfig | null = resource.entity ? getEntity(resource.entity) : null
  const { can } = useAuth()
  const [params, setParams] = useSearchParams()
  const page = Math.max(1, Number(params.get("page") ?? 1))
  const orderBy = params.get("order_by") ?? ""
  const status = params.get("status") ?? ALL
  const urlQ = params.get("q") ?? ""
  const [qInput, setQInput] = React.useState(urlQ)
  const searchable = SEARCHABLE.has(resource.path)
  const viewSpec = VIEWS[resource.path]
  const viewValue = viewSpec ? params.get(viewSpec.param) : null
  const [visibility, setVisibility] = React.useState<VisibilityState>({})
  const [selection, setSelection] = React.useState<RowSelectionState>({})

  const update = React.useCallback((patch: Record<string, string | null>) => {
    setParams((prev) => {
      const next = new URLSearchParams(prev)
      for (const [k, v] of Object.entries(patch)) {
        if (v === null || v === "" || v === ALL) next.delete(k)
        else next.set(k, v)
      }
      if (!("page" in patch)) next.delete("page")
      return next
    })
  }, [setParams])
  React.useEffect(() => {
    const t = setTimeout(() => { if (qInput !== urlQ) update({ q: qInput }) }, 250)
    return () => clearTimeout(t)
  }, [qInput, urlQ, update])

  const query = useQuery({
    queryKey: [resource.endpoint, "list", { page, orderBy, status, q: urlQ, view: viewValue }],
    queryFn: () =>
      api.get<Page<AnyRecord> | AnyRecord[]>(
        viewValue && viewSpec
          ? viewSpec.endpoint(viewValue)
          : `${resource.endpoint}${qs({ page, page_size: PAGE_SIZE, order_by: orderBy || null, q: searchable && urlQ ? urlQ : null, status: status === ALL ? null : status })}`,
      ),
    placeholderData: (prev) => prev,
  })
  const items: AnyRow[] = React.useMemo(() => (isPage(query.data) ? query.data.items : Array.isArray(query.data) ? query.data : []) as AnyRow[], [query.data])
  const total = isPage(query.data) ? query.data.total : items.length
  const hasFilters = Boolean(urlQ) || status !== ALL || Boolean(viewValue)

  const sorting: SortingState = React.useMemo(() => (orderBy ? [{ id: orderBy.replace(/^-/, ""), desc: orderBy.startsWith("-") }] : []), [orderBy])
  const columns = React.useMemo<ColumnDef<AnyRow, unknown>[]>(() => {
    const cols: ColumnDef<AnyRow, unknown>[] = []
    if (cfg && !cfg.readOnly) {
      cols.push({
        id: "select", enableSorting: false, enableHiding: false, size: 32, meta: { className: "w-8 pr-0" },
        header: ({ table }) => <Checkbox aria-label="Select all rows on this page" checked={table.getIsAllPageRowsSelected()} onChange={(e) => table.toggleAllPageRowsSelected(e.target.checked)} />,
        cell: ({ row }) => <Checkbox aria-label={`Select ${cfg.nameOf(row.original)}`} checked={row.getIsSelected()} onChange={(e) => row.toggleSelected(e.target.checked)} />,
      })
    }
    resource.columns.forEach((c, i) => {
      cols.push({
        id: c, header: titleCase(c.replace(/_cents$/, "").replace(/_at$/, "")),
        cell: ({ row }) => {
          const v = row.original[c]
          if (i === 0 && resource.detail) return <Link className="font-medium hover:underline" to={`/${resource.path}/${row.original.id}`}>{v === null || v === undefined ? "—" : renderValue(c, v, String(row.original.currency ?? "USD"))}</Link>
          return renderValue(c, v, String(row.original.currency ?? "USD"))
        },
      })
    })
    if (cfg && !cfg.readOnly) cols.push({ id: "actions", header: "", enableSorting: false, enableHiding: false, meta: { className: "w-10 text-right" }, cell: ({ row }) => <div className="text-right"><ActionMenu entity={cfg.kind} id={row.original.id} row={row.original} /></div> })
    return cols
  }, [cfg, resource])

  const selectedCount = Object.values(selection).filter(Boolean).length
  const columnToggles = resource.columns.map((c) => ({ id: c, label: titleCase(c.replace(/_cents$/, "")), visible: visibility[c] !== false, onToggle: (v: boolean) => setVisibility((s) => ({ ...s, [c]: v })) }))
  const canCreate = cfg ? can(`${cfg.permissionPrefix}.create`) : false
  const Icon = cfg?.icon

  return (
    <div>
      <PageHeader
        title={resource.title}
        description={query.data ? `${total.toLocaleString()} total` : undefined}
        actions={
          <>
            {cfg && <CreateButton entity={cfg.kind} />}
            <ListActionsMenu title={resource.title} rows={items} columns={columnToggles} onRefresh={() => void query.refetch()} />
          </>
        }
      >
        <div className="flex flex-wrap items-center gap-2" data-testid="list-filters">
          {searchable && <Input placeholder={`Search ${resource.title.toLowerCase()}…`} value={qInput} onChange={(e) => setQInput(e.target.value)} className="w-64" aria-label={`Search ${resource.title.toLowerCase()}`} />}
          {cfg?.statuses && (
            <Select value={status} onValueChange={(v) => update({ status: v })}>
              <SelectTrigger className="w-44" aria-label="Status filter"><SelectValue placeholder="Status" /></SelectTrigger>
              <SelectContent><SelectItem value={ALL}>All statuses</SelectItem>{cfg.statuses.map((s) => <SelectItem key={s} value={s}>{titleCase(s)}</SelectItem>)}</SelectContent>
            </Select>
          )}
          {urlQ && <Badge variant="secondary" className="gap-1">“{urlQ}” <button type="button" aria-label="Clear search" onClick={() => setQInput("")}><X className="size-3" /></button></Badge>}
          {status !== ALL && <Badge variant="secondary" className="gap-1">{titleCase(status)} <button type="button" aria-label="Clear status filter" onClick={() => update({ status: null })}><X className="size-3" /></button></Badge>}
          {viewValue && viewSpec && <Badge variant="secondary" className="gap-1" data-testid="view-chip">{viewSpec.label(viewValue)} <button type="button" aria-label="Clear view" onClick={() => update({ [viewSpec.param]: null })}><X className="size-3" /></button></Badge>}
        </div>
      </PageHeader>

      <SelectionBar count={selectedCount} onClear={() => setSelection({})}>
        <Planned reason="Bulk archive and bulk assign arrive in a later sprint"><Button size="sm" variant="outline" disabled>Archive selected</Button></Planned>
      </SelectionBar>

      {query.isError ? (
        <ErrorState error={query.error} onRetry={() => void query.refetch()} />
      ) : query.isPending ? (
        <LoadingState />
      ) : total === 0 && !hasFilters ? (
        <EmptyState
          icon={Icon}
          title={`No ${resource.title.toLowerCase()} yet`}
          description={canCreate && cfg?.form ? `Get started by creating your first ${cfg.label.toLowerCase()}.` : canCreate ? `Creating ${resource.title.toLowerCase()} from the app is planned; the API accepts them today.` : `Contact your administrator to add ${resource.title.toLowerCase()}.`}
          action={cfg && canCreate ? <CreateButton entity={cfg.kind} /> : undefined}
        />
      ) : (
        <DataTable<AnyRow>
          columns={columns}
          data={items}
          total={total}
          page={page}
          pageSize={PAGE_SIZE}
          onPageChange={(p) => update({ page: String(p) })}
          sorting={sorting}
          onSortingChange={(updater) => {
            const next = typeof updater === "function" ? updater(sorting) : updater
            const first = next[0]
            update({ order_by: first ? `${first.desc ? "-" : ""}${first.id}` : null })
          }}
          isLoading={query.isFetching}
          getRowId={(r) => r.id}
          emptyMessage={`No ${resource.title.toLowerCase()} match these filters`}
          columnVisibility={visibility}
          onColumnVisibilityChange={setVisibility}
          rowSelection={selection}
          onRowSelectionChange={setSelection}
        />
      )}
    </div>
  )
}

// ------------------------------------------------------------------ detail

const HIDDEN_ALWAYS = new Set(["id", "client_id", "created_by", "updated_by", "search_tsv", "deleted_at"])

function DetailsCard({ row, cfg }: { row: AnyRow; cfg: EntityConfig | null }) {
  const fk = useFkLabels(row)
  const hidden = new Set([...HIDDEN_ALWAYS, ...(cfg?.hideFields ?? [])])
  const entries = Object.entries(row).filter(([k]) => !hidden.has(k) && k !== "created_at" && k !== "updated_at")
  return (
    <Card>
      <CardHeader><CardTitle>Details</CardTitle></CardHeader>
      <CardContent>
        <dl className="grid gap-x-8 gap-y-1 sm:grid-cols-2" data-testid="details">
          {entries.map(([k, v]) => (
            <div key={k} className="flex flex-col gap-0.5 border-b py-2 sm:flex-row sm:gap-4">
              <dt className="w-44 shrink-0 text-sm text-muted-foreground">{titleCase(k.replace(/_cents$/, "").replace(/_id$/, ""))}</dt>
              <dd className="min-w-0 text-sm">{renderValue(k, v, String(row.currency ?? "USD"), fk)}</dd>
            </div>
          ))}
        </dl>
      </CardContent>
    </Card>
  )
}

function SectionAddDialog({ section, parentId, cfg, open, onOpenChange }: { section: SectionSpec; parentId: string; cfg: EntityConfig; open: boolean; onOpenChange: (o: boolean) => void }) {
  const qc = useQueryClient()
  const add = section.add && !("planned" in section.add) ? section.add : null
  const run = useMutation({
    mutationFn: (values: Record<string, unknown>) => api.post<unknown>(add!.post(parentId), add!.body(values, parentId)),
    onSuccess: () => {
      toast.success(add!.success)
      void qc.invalidateQueries({ queryKey: ["section", section.key, parentId] })
      void qc.invalidateQueries({ queryKey: [cfg.queryKey] })
      onOpenChange(false)
    },
  })
  if (!add) return null
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto" data-testid="section-add-dialog">
        <DialogHeader><DialogTitle>{add.label}</DialogTitle><DialogDescription>Added to this {cfg.label.toLowerCase()} and audited.</DialogDescription></DialogHeader>
        <ResourceForm key={`${section.key}-${parentId}`} schema={add.schema} fields={add.fields} defaultValues={add.defaults} onSubmit={(v) => run.mutateAsync(v)} onCancel={() => onOpenChange(false)} submitLabel={add.label} />
      </DialogContent>
    </Dialog>
  )
}

function Section({ section, parentId, cfg, currency }: { section: SectionSpec; parentId: string; cfg: EntityConfig; currency: string }) {
  const { can } = useAuth()
  const [addOpen, setAddOpen] = React.useState(false)
  const allowed = can(section.permission)
  const query = useQuery({ queryKey: ["section", section.key, parentId], queryFn: () => api.get<AnyRow[] | Page<AnyRow>>(section.list(parentId)), enabled: allowed })
  const rows: AnyRow[] = React.useMemo(() => (isPage(query.data) ? (query.data.items as AnyRow[]) : Array.isArray(query.data) ? query.data : []), [query.data])
  const fk = useFkLabels(rows[0])
  const add = section.add
  const addAllowed = add ? can(add.permission) : false
  const addButton = add && addAllowed ? ("planned" in add ? <Planned><Button size="sm" variant="outline" disabled><Plus /> {add.label}</Button></Planned> : <Button size="sm" variant="outline" onClick={() => setAddOpen(true)} data-testid={`add-${section.key}`}><Plus /> {add.label}</Button>) : null
  return (
    <Card data-testid={`section-${section.key}`}>
      <CardHeader className="flex flex-row items-center justify-between gap-3">
        <CardTitle className="flex items-center gap-2">{section.icon && <section.icon className="size-4 text-muted-foreground" />}{section.title}{rows.length > 0 && <span className="text-xs font-normal text-muted-foreground">({rows.length})</span>}</CardTitle>
        {addButton}
      </CardHeader>
      <CardContent>
        {!allowed ? <EmptyState>Your role cannot view {section.title.toLowerCase()}.</EmptyState> : query.isPending ? <LoadingState rows={3} /> : query.isError ? <ErrorState error={query.error} onRetry={() => void query.refetch()} /> : rows.length === 0 ? (
          <div className="flex flex-col items-center gap-2 rounded-lg border border-dashed px-4 py-6 text-center text-sm text-muted-foreground" data-testid="section-empty">
            <span>{section.empty}</span>
          </div>
        ) : (
          <div className="overflow-x-auto rounded-lg border">
            <Table>
              <TableHeader><TableRow>{section.columns.map((c) => <TableHead key={c.key}>{c.label}</TableHead>)}</TableRow></TableHeader>
              <TableBody>
                {rows.map((r) => (
                  <TableRow key={r.id} data-testid="section-row">
                    {section.columns.map((c) => {
                      const v = r[c.key]
                      let node: React.ReactNode
                      if (v === null || v === undefined) node = <span className="text-muted-foreground">—</span>
                      else if (c.kind === "money") node = money(Number(v), String(r.currency ?? currency))
                      else if (c.kind === "date") node = fmtDate(String(v))
                      else if (c.kind === "datetime") node = fmtDateTime(String(v))
                      else if (c.kind === "status") node = <StatusBadge value={String(v)} />
                      else if (c.kind === "link" && c.to) node = <Link className="font-medium hover:underline" to={c.to(r)}>{String(v)}</Link>
                      else node = renderValue(c.key, v, currency, fk)
                      return <TableCell key={c.key}>{node}</TableCell>
                    })}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </CardContent>
      {add && !("planned" in add) && <SectionAddDialog section={section} parentId={parentId} cfg={cfg} open={addOpen} onOpenChange={setAddOpen} />}
    </Card>
  )
}

export function ResourceDetailPage({ resource }: { resource: ResourceSpec }) {
  const { id = "" } = useParams()
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const cfg: EntityConfig | null = resource.entity ? getEntity(resource.entity) : null
  const tab = params.get("tab") === "relationship" && resource.graphType ? "relationship" : "overview"
  const query = useQuery({ queryKey: [cfg?.queryKey ?? resource.endpoint, id], queryFn: () => api.get<AnyRow>(`${resource.endpoint}/${id}`), enabled: id.length > 0 })

  if (query.isPending) return <div><PageHeader title={resource.title} /><LoadingState /></div>
  if (query.isError) return <div><BackLink to={`/${resource.path}`} label={resource.title} /><PageHeader title={resource.title} /><ErrorState error={query.error} onRetry={() => void query.refetch()} /></div>
  const row = query.data
  const name = cfg ? cfg.nameOf(row) : String(row[resource.labelField] ?? resource.title)
  const currency = String(row.currency ?? "USD")

  return (
    <div>
      <BackLink to={`/${resource.path}`} label={resource.title} />
      <PageHeader
        title={<span className="flex flex-wrap items-center gap-3">{name}{typeof row.status === "string" && <StatusBadge value={row.status} />}</span>}
        description={`${resource.title.replace(/s$/, "")} · created ${fmtDateTime(String(row.created_at))}${row.updated_at && row.updated_at !== row.created_at ? ` · updated ${fmtDateTime(String(row.updated_at))}` : ""}`}
        actions={
          cfg ? (
            <>
              <EditButton entity={cfg.kind} id={id} />
              <DeleteButton entity={cfg.kind} id={id} name={name} onDeleted={() => navigate(`/${resource.path}`)} />
              <MoreMenu entity={cfg.kind} row={row} />
            </>
          ) : undefined
        }
      />
      {resource.graphType ? (
        <Tabs value={tab} onValueChange={(v) => setParams((prev) => { const next = new URLSearchParams(prev); if (v === "overview") next.delete("tab"); else next.set("tab", v); return next }, { replace: true })}>
          <TabsList aria-label={`${resource.title} sections`}>
            <TabsTrigger value="overview" data-testid="tab-overview">Overview</TabsTrigger>
            <TabsTrigger value="relationship" data-testid="tab-relationship">Relationship</TabsTrigger>
          </TabsList>
          <TabsContent value="overview">
            <div className="flex flex-col gap-4">
              <DetailsCard row={row} cfg={cfg} />
              {cfg?.sections?.map((s) => <Section key={s.key} section={s} parentId={id} cfg={cfg} currency={currency} />)}
            </div>
          </TabsContent>
          <TabsContent value="relationship"><RelationshipGraph entityType={resource.graphType} entityId={id} /></TabsContent>
        </Tabs>
      ) : (
        <div className="flex flex-col gap-4">
          <DetailsCard row={row} cfg={cfg} />
          {cfg?.sections?.map((s) => <Section key={s.key} section={s} parentId={id} cfg={cfg} currency={currency} />)}
        </div>
      )}
    </div>
  )
}
