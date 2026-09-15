/** /clients/:id -- the reference detail pattern: header, tabs, KPIs, the Relationship graph. */

import * as React from "react"
import { Link, useParams, useSearchParams } from "react-router"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { Archive, Pencil } from "lucide-react"
import { toast } from "sonner"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { PageHeader } from "@/components/common/PageHeader"
import { BackLink } from "@/components/common/BackLink"
import { EmptyState, ErrorState, LoadingState } from "@/components/common/States"
import { RelationshipGraph } from "@/components/RelationshipGraph"
import { api, ApiError, qs } from "@/lib/api"
import { useAuth } from "@/lib/auth"
import { ago, fmtDate, fmtDateTime, money, titleCase } from "@/lib/format"
import type { Activity, AgingReport, AnyRecord, Client, Contact, Page, Trip, User } from "@/lib/types"
import { RESOURCES, type ResourceSpec } from "@/pages/resources"
import { ClientStatusBadge } from "./clientShared"

const TABS = [
  { key: "overview", label: "Overview" },
  { key: "segments", label: "Segments", resource: "segments" },
  { key: "contacts", label: "Contacts", resource: "contacts" },
  { key: "passengers", label: "Passengers", resource: "passengers" },
  { key: "account-holders", label: "Account Holders", resource: "account-holders" },
  { key: "trips", label: "Trips", resource: "trips" },
  { key: "documents", label: "Documents", resource: "documents" },
  { key: "relationship", label: "Relationship" },
  { key: "activity", label: "Activity" },
] as const
type TabKey = (typeof TABS)[number]["key"]

function Kpi({ label, value, hint }: { label: string; value: React.ReactNode; hint?: string }) {
  return (
    <Card className="gap-1 py-4" data-testid="kpi">
      <CardHeader className="px-4"><CardDescription>{label}</CardDescription></CardHeader>
      <CardContent className="px-4"><div className="text-2xl font-semibold tabular-nums">{value}</div>{hint && <div className="text-xs text-muted-foreground">{hint}</div>}</CardContent>
    </Card>
  )
}

function renderCell(v: unknown): React.ReactNode {
  if (v === null || v === undefined) return <span className="text-muted-foreground">—</span>
  if (typeof v === "number") return v.toLocaleString()
  if (typeof v === "string" && /^\d{4}-\d{2}-\d{2}T/.test(v)) return fmtDateTime(v)
  if (typeof v === "boolean") return v ? "Yes" : "No"
  return String(v)
}

/** First page of a related resource, rendered from its ResourceSpec (Sprint 5 replaces these). */
function RelatedTable({ resource }: { resource: ResourceSpec }) {
  const { can } = useAuth()
  const allowed = resource.permission === null || can(resource.permission)
  const query = useQuery({ queryKey: [resource.endpoint, "related"], queryFn: () => api.get<Page<AnyRecord>>(`${resource.endpoint}${qs({ page_size: 25 })}`), enabled: allowed })
  if (!allowed) return <EmptyState>Your role cannot view {resource.title.toLowerCase()}.</EmptyState>
  if (query.isPending) return <LoadingState />
  if (query.isError) return <ErrorState error={query.error} onRetry={() => void query.refetch()} />
  if (query.data.items.length === 0) return <EmptyState>No {resource.title.toLowerCase()}</EmptyState>
  return (
    <div className="rounded-lg border bg-card">
      <Table>
        <TableHeader><TableRow>{resource.columns.map((c) => <TableHead key={c}>{titleCase(c)}</TableHead>)}</TableRow></TableHeader>
        <TableBody>
          {query.data.items.map((row) => (
            <TableRow key={row.id} data-testid="related-row">
              {resource.columns.map((c, i) => (
                <TableCell key={c}>{i === 0 ? <Link className="font-medium hover:underline" to={`/${resource.path}/${row.id}`}>{renderCell(row[c])}</Link> : renderCell(row[c])}</TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
      <div className="border-t p-2 text-right text-xs text-muted-foreground">{query.data.total} total · <Link className="hover:underline" to={`/${resource.path}`}>open {resource.title.toLowerCase()}</Link></div>
    </div>
  )
}

function Overview({ client }: { client: Client }) {
  const { can } = useAuth()
  const trips = useQuery({ queryKey: ["trips", "all-for-kpi"], queryFn: () => api.get<Page<Trip>>(`/trips${qs({ page_size: 500 })}`), enabled: can("trips.view") })
  const upcoming = useQuery({ queryKey: ["trips", "upcoming"], queryFn: () => api.get<Page<Trip>>(`/trips/upcoming${qs({ page_size: 5 })}`), enabled: can("trips.view") })
  const aging = useQuery({ queryKey: ["invoices", "ar-aging"], queryFn: () => api.get<AgingReport>("/invoices/ar-aging"), enabled: can("invoices.view") })
  const activity = useQuery({ queryKey: ["activities", "recent"], queryFn: () => api.get<Page<Activity>>(`/activities${qs({ page_size: 8, order_by: "-occurred_at" })}`), enabled: can("activities.view") })
  const lifetime = trips.data ? trips.data.items.reduce((n, t) => n + t.total_sell_cents, 0) : null
  const balance = aging.data ? Object.values(aging.data.buckets).reduce((n, b) => n + b.balance_cents, 0) : null
  return (
    <div className="flex flex-col gap-4">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Kpi label="Lifetime value" value={lifetime === null ? "—" : money(lifetime, client.default_currency)} hint="sum of priced trips" />
        <Kpi label="Trips" value={trips.data?.total ?? "—"} />
        <Kpi label="Active trips" value={upcoming.data?.total ?? "—"} hint="confirmed or in progress" />
        <Kpi label="Balance outstanding" value={balance === null ? "—" : money(balance, client.default_currency)} hint={aging.data ? `as of ${fmtDate(aging.data.as_of)}` : undefined} />
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader><CardTitle>Recent activity</CardTitle></CardHeader>
          <CardContent>
            {activity.isPending ? <LoadingState rows={4} /> : activity.isError ? <ErrorState error={activity.error} onRetry={() => void activity.refetch()} /> : activity.data.items.length === 0 ? <EmptyState>No activity yet</EmptyState> : (
              <ul className="divide-y text-sm">{activity.data.items.map((a) => <li key={a.id} className="flex justify-between gap-3 py-2"><span className="min-w-0 truncate">{a.subject ?? titleCase(a.activity_type)}</span><span className="shrink-0 text-xs text-muted-foreground">{ago(a.occurred_at)}</span></li>)}</ul>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Upcoming trips</CardTitle></CardHeader>
          <CardContent>
            {upcoming.isPending ? <LoadingState rows={4} /> : upcoming.isError ? <ErrorState error={upcoming.error} onRetry={() => void upcoming.refetch()} /> : upcoming.data.items.length === 0 ? <EmptyState>No upcoming trips</EmptyState> : (
              <ul className="divide-y text-sm">{upcoming.data.items.map((t) => <li key={t.id} className="flex justify-between gap-3 py-2"><Link to={`/trips/${t.id}`} className="font-medium hover:underline">{t.trip_number}</Link><span className="text-muted-foreground">{fmtDate(t.departure_date)}</span><Badge variant="secondary">{titleCase(t.status)}</Badge></li>)}</ul>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

function ActivityTab() {
  const { can } = useAuth()
  const [contactId, setContactId] = React.useState<string>("__all__")
  const contacts = useQuery({ queryKey: ["contacts", "for-filter"], queryFn: () => api.get<Page<Contact>>(`/contacts${qs({ page_size: 100, order_by: "display_name" })}`), enabled: can("contacts.view") })
  const activity = useQuery({
    queryKey: ["activities", "tab", contactId],
    queryFn: () => api.get<Page<Activity>>(`/activities${qs({ page_size: 50, order_by: "-occurred_at", contact_id: contactId === "__all__" ? null : contactId })}`),
  })
  return (
    <div className="flex flex-col gap-3">
      {contacts.data && (
        <Select value={contactId} onValueChange={setContactId}>
          <SelectTrigger className="w-64" aria-label="Filter by contact"><SelectValue /></SelectTrigger>
          <SelectContent><SelectItem value="__all__">All contacts</SelectItem>{contacts.data.items.map((c) => <SelectItem key={c.id} value={c.id}>{c.display_name}</SelectItem>)}</SelectContent>
        </Select>
      )}
      {activity.isPending ? <LoadingState /> : activity.isError ? <ErrorState error={activity.error} onRetry={() => void activity.refetch()} /> : activity.data.items.length === 0 ? <EmptyState>No activity</EmptyState> : (
        <ul className="divide-y rounded-lg border bg-card text-sm">
          {activity.data.items.map((a) => (
            <li key={a.id} className="flex flex-col gap-0.5 px-4 py-2">
              <div className="flex items-center justify-between gap-3"><span className="font-medium">{a.subject ?? titleCase(a.activity_type)}</span><span className="text-xs text-muted-foreground">{fmtDateTime(a.occurred_at)}</span></div>
              <div className="text-xs text-muted-foreground">{titleCase(a.activity_type)} · {a.direction}{a.body ? ` · ${a.body}` : ""}</div>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

const editSchema = z.object({
  name: z.string().trim().min(2, "Name is required"),
  legal_name: z.string().trim().optional(),
  billing_email: z.string().trim().email("Enter a valid email").or(z.literal("")).optional(),
  timezone: z.string().trim().min(1),
})
type EditValues = z.infer<typeof editSchema>

function EditDialog({ client, open, onOpenChange }: { client: Client; open: boolean; onOpenChange: (o: boolean) => void }) {
  const qc = useQueryClient()
  const form = useForm<EditValues>({ resolver: zodResolver(editSchema), values: { name: client.name, legal_name: client.legal_name ?? "", billing_email: client.billing_email ?? "", timezone: client.timezone } })
  const save = useMutation({
    mutationFn: (v: EditValues) => api.patch<Client>(`/clients/${client.id}`, { name: v.name, legal_name: v.legal_name || null, billing_email: v.billing_email || null, timezone: v.timezone }),
    onSuccess: () => { toast.success("Saved"); void qc.invalidateQueries({ queryKey: ["clients"] }); onOpenChange(false) },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Save failed"),
  })
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader><DialogTitle>Edit client</DialogTitle><DialogDescription>Changes are audited.</DialogDescription></DialogHeader>
        <form onSubmit={form.handleSubmit((v) => save.mutate(v))} className="flex flex-col gap-3" noValidate>
          <div className="flex flex-col gap-1.5"><Label htmlFor="e-name">Name</Label><Input id="e-name" {...form.register("name")} />{form.formState.errors.name && <p className="text-xs text-destructive">{form.formState.errors.name.message}</p>}</div>
          <div className="flex flex-col gap-1.5"><Label htmlFor="e-legal">Legal name</Label><Input id="e-legal" {...form.register("legal_name")} /></div>
          <div className="flex flex-col gap-1.5"><Label htmlFor="e-email">Billing email</Label><Input id="e-email" type="email" {...form.register("billing_email")} />{form.formState.errors.billing_email && <p className="text-xs text-destructive">{form.formState.errors.billing_email.message}</p>}</div>
          <div className="flex flex-col gap-1.5"><Label htmlFor="e-tz">Timezone</Label><Input id="e-tz" {...form.register("timezone")} /></div>
          <DialogFooter><Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button><Button type="submit" disabled={save.isPending}>Save</Button></DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

export function ClientDetailPage() {
  const { id = "" } = useParams()
  const { can } = useAuth()
  const qc = useQueryClient()
  const [params, setParams] = useSearchParams()
  const tab = (TABS.some((t) => t.key === params.get("tab")) ? params.get("tab") : "overview") as TabKey
  const [editOpen, setEditOpen] = React.useState(false)
  const [archiveOpen, setArchiveOpen] = React.useState(false)

  const client = useQuery({ queryKey: ["clients", id], queryFn: () => api.get<Client>(`/clients/${id}`), enabled: id.length > 0 })
  const users = useQuery({ queryKey: ["users", "all"], queryFn: () => api.get<Page<User>>(`/admin/users${qs({ page_size: 100 })}`), enabled: can("users.view") })
  const owner = users.data?.items.find((u) => u.role === "owner")

  // "Archive" suspends rather than soft-deletes: soft-deleting the tenant root would hide
  // it from RLS and lock everyone -- including the archiver -- out of the account.
  const archive = useMutation({
    mutationFn: () => api.patch<Client>(`/clients/${id}`, { status: "suspended" }),
    onSuccess: () => { toast.success("Client archived (suspended)"); void qc.invalidateQueries({ queryKey: ["clients"] }); setArchiveOpen(false) },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Archive failed"),
  })

  if (client.isPending) return <div><PageHeader title="Client" /><LoadingState /></div>
  if (client.isError) return <div><PageHeader title="Client" /><ErrorState error={client.error} onRetry={() => void client.refetch()} /></div>
  const c = client.data

  return (
    <div>
      <BackLink to="/clients" label="Clients" />
      <PageHeader
        title={<span className="flex items-center gap-3">{c.name} <ClientStatusBadge status={c.status} /></span>}
        description={<span>{c.legal_name ?? c.slug} · {c.timezone}{owner ? <> · Owner: <span className="text-foreground">{owner.full_name}</span></> : null}</span>}
        actions={
          <>
            {can("clients.edit") && <Button variant="outline" onClick={() => setEditOpen(true)}><Pencil /> Edit</Button>}
            {can("clients.edit") && c.status !== "suspended" && <Button variant="outline" onClick={() => setArchiveOpen(true)}><Archive /> Archive</Button>}
          </>
        }
      />
      <Tabs value={tab} onValueChange={(v) => setParams((prev) => { const next = new URLSearchParams(prev); if (v === "overview") next.delete("tab"); else next.set("tab", v); return next }, { replace: true })}>
        <TabsList aria-label="Client sections">
          {TABS.map((t) => <TabsTrigger key={t.key} value={t.key} data-testid={`tab-${t.key}`}>{t.label}</TabsTrigger>)}
        </TabsList>
        <TabsContent value="overview"><Overview client={c} /></TabsContent>
        {TABS.filter((t): t is Extract<(typeof TABS)[number], { resource: string }> => "resource" in t).map((t) => {
          const spec = RESOURCES.find((r) => r.path === t.resource)
          return <TabsContent key={t.key} value={t.key}>{spec ? <RelatedTable resource={spec} /> : null}</TabsContent>
        })}
        <TabsContent value="relationship"><RelationshipGraph entityType="client" entityId={id} /></TabsContent>
        <TabsContent value="activity"><ActivityTab /></TabsContent>
      </Tabs>

      {can("clients.edit") && <EditDialog client={c} open={editOpen} onOpenChange={setEditOpen} />}
      <Dialog open={archiveOpen} onOpenChange={setArchiveOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>Archive {c.name}?</DialogTitle><DialogDescription>The client is set to <b>suspended</b>. Users keep access to their data; nothing is deleted.</DialogDescription></DialogHeader>
          <DialogFooter><Button variant="outline" onClick={() => setArchiveOpen(false)}>Cancel</Button><Button variant="destructive" onClick={() => archive.mutate()} disabled={archive.isPending}>Archive</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
