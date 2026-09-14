/**
 * /clients -- the reference list pattern.
 *
 * A Client is the tenant root (DATA_MODEL 3.1), and RLS shows a user only the
 * tenant they belong to, so this table has one row per tenant the user can
 * see (one, for the demo). The pattern -- server-driven TanStack table with
 * URL-backed page/sort/filters, permission-gated create -- is what later
 * sprints copy for the multi-row resources.
 */

import * as React from "react"
import { Link, useSearchParams } from "react-router"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import type { ColumnDef, SortingState } from "@tanstack/react-table"
import { Plus } from "lucide-react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { PageHeader } from "@/components/common/PageHeader"
import { DataTable } from "@/components/common/DataTable"
import { ErrorState } from "@/components/common/States"
import { api, ApiError, qs } from "@/lib/api"
import { useAuth } from "@/lib/auth"
import { ago, titleCase } from "@/lib/format"
import type { Activity, Client, Page, Segment, User } from "@/lib/types"
import { CLIENT_STATUSES, ClientStatusBadge } from "./clientShared"

export interface ClientRow {
  client: Client
  segments: number
  contacts: number
  trips: number
  owner: string | null
  lastActivity: string | null
}

const PAGE_SIZE = 25
const ALL = "__all__"

const createSchema = z.object({
  name: z.string().trim().min(2, "Name is required"),
  slug: z.string().trim().min(2, "Slug is required").regex(/^[a-z0-9-]+$/, "Lower-case letters, digits and dashes"),
  legal_name: z.string().trim().optional(),
})
type CreateValues = z.infer<typeof createSchema>

function NewClientDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const qc = useQueryClient()
  const form = useForm<CreateValues>({ resolver: zodResolver(createSchema), defaultValues: { name: "", slug: "", legal_name: "" } })
  const create = useMutation({
    mutationFn: (values: CreateValues) => api.post<Client>("/clients", { ...values, legal_name: values.legal_name || null }),
    onSuccess: (c) => {
      toast.success(`Created ${c.name}`)
      void qc.invalidateQueries({ queryKey: ["clients"] })
      onOpenChange(false)
      form.reset()
    },
    onError: (err) => toast.error(err instanceof ApiError ? err.message : "Could not create client"),
  })
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New client</DialogTitle>
          <DialogDescription>A client is a tenant. Creating one is a platform operation; inside a tenant the API will refuse it.</DialogDescription>
        </DialogHeader>
        <form onSubmit={form.handleSubmit((v) => create.mutate(v))} className="flex flex-col gap-3" noValidate>
          <div className="flex flex-col gap-1.5"><Label htmlFor="c-name">Name</Label><Input id="c-name" {...form.register("name")} />{form.formState.errors.name && <p className="text-xs text-destructive">{form.formState.errors.name.message}</p>}</div>
          <div className="flex flex-col gap-1.5"><Label htmlFor="c-slug">Slug</Label><Input id="c-slug" placeholder="acme-jets" {...form.register("slug")} />{form.formState.errors.slug && <p className="text-xs text-destructive">{form.formState.errors.slug.message}</p>}</div>
          <div className="flex flex-col gap-1.5"><Label htmlFor="c-legal">Legal name</Label><Input id="c-legal" {...form.register("legal_name")} /></div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
            <Button type="submit" disabled={create.isPending}>{create.isPending ? "Creating…" : "Create"}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

export function ClientListPage() {
  const { can } = useAuth()
  const [params, setParams] = useSearchParams()
  const page = Math.max(1, Number(params.get("page") ?? 1))
  const orderBy = params.get("order_by") ?? "name"
  const status = params.get("status") ?? ALL
  const segment = params.get("segment") ?? ALL
  const owner = params.get("owner") ?? ALL
  const q = params.get("q") ?? ""
  const [dialogOpen, setDialogOpen] = React.useState(false)

  const update = (patch: Record<string, string | null>) => {
    const next = new URLSearchParams(params)
    for (const [k, v] of Object.entries(patch)) {
      if (v === null || v === "" || v === ALL) next.delete(k)
      else next.set(k, v)
    }
    if (!("page" in patch)) next.delete("page")
    setParams(next)
  }

  const clients = useQuery({
    queryKey: ["clients", { page, orderBy, status }],
    queryFn: () => api.get<Page<Client>>(`/clients${qs({ page, page_size: PAGE_SIZE, order_by: orderBy, status: status === ALL ? null : status })}`),
  })
  // Tenant-wide counts: everything the user can see belongs to their own tenant.
  const segments = useQuery({ queryKey: ["segments", "all"], queryFn: () => api.get<Page<Segment>>(`/segments${qs({ page_size: 100 })}`), enabled: can("segments.view") })
  const contacts = useQuery({ queryKey: ["contacts", "count"], queryFn: () => api.get<Page<unknown>>(`/contacts${qs({ page_size: 1 })}`), enabled: can("contacts.view") })
  const trips = useQuery({ queryKey: ["trips", "count"], queryFn: () => api.get<Page<unknown>>(`/trips${qs({ page_size: 1 })}`), enabled: can("trips.view") })
  const latest = useQuery({ queryKey: ["activities", "latest"], queryFn: () => api.get<Page<Activity>>(`/activities${qs({ page_size: 1, order_by: "-occurred_at" })}`), enabled: can("activities.view") })
  const users = useQuery({ queryKey: ["users", "all"], queryFn: () => api.get<Page<User>>(`/admin/users${qs({ page_size: 100 })}`), enabled: can("users.view") })

  const ownerUser = users.data?.items.find((u) => u.role === "owner") ?? null
  const rows: ClientRow[] = React.useMemo(() => {
    const items = clients.data?.items ?? []
    return items
      .map((c) => ({
        client: c,
        segments: segments.data?.total ?? 0,
        contacts: contacts.data?.total ?? 0,
        trips: trips.data?.total ?? 0,
        owner: ownerUser ? ownerUser.full_name : null,
        lastActivity: latest.data?.items[0]?.occurred_at ?? null,
      }))
      .filter((r) => (q ? r.client.name.toLowerCase().includes(q.toLowerCase()) : true))
      .filter(() => (segment === ALL ? true : (segments.data?.items.some((s) => s.id === segment) ?? false)))
      .filter(() => (owner === ALL ? true : ownerUser?.id === owner))
  }, [clients.data, segments.data, contacts.data, trips.data, latest.data, ownerUser, q, segment, owner])

  const sorting: SortingState = React.useMemo(() => [{ id: orderBy.replace(/^-/, ""), desc: orderBy.startsWith("-") }], [orderBy])
  const columns = React.useMemo<ColumnDef<ClientRow, unknown>[]>(
    () => [
      { id: "name", header: "Name", cell: ({ row }) => <Link to={`/clients/${row.original.client.id}`} className="font-medium hover:underline">{row.original.client.name}</Link> },
      { id: "status", header: "Status", cell: ({ row }) => <ClientStatusBadge status={row.original.client.status} /> },
      { id: "segments", header: "Segments", enableSorting: false, cell: ({ row }) => row.original.segments },
      { id: "contacts", header: "Contacts", enableSorting: false, cell: ({ row }) => row.original.contacts },
      { id: "trips", header: "Trips", enableSorting: false, cell: ({ row }) => row.original.trips },
      { id: "owner", header: "Owner", enableSorting: false, cell: ({ row }) => row.original.owner ?? <span className="text-muted-foreground">—</span> },
      { id: "created_at", header: "Last activity", cell: ({ row }) => <span title={row.original.lastActivity ?? ""}>{ago(row.original.lastActivity)}</span> },
    ],
    [],
  )

  return (
    <div>
      <PageHeader
        title="Clients"
        description="Tenants you belong to. A client is the root of everything else."
        actions={can("clients.create") && <Button onClick={() => setDialogOpen(true)}><Plus /> New Client</Button>}
      >
        <div className="flex flex-wrap items-center gap-2" data-testid="client-filters">
          <Input placeholder="Search by name…" value={q} onChange={(e) => update({ q: e.target.value })} className="w-56" aria-label="Search clients" />
          <Select value={status} onValueChange={(v) => update({ status: v })}>
            <SelectTrigger className="w-40" aria-label="Status filter"><SelectValue placeholder="Status" /></SelectTrigger>
            <SelectContent><SelectItem value={ALL}>All statuses</SelectItem>{CLIENT_STATUSES.map((s) => <SelectItem key={s} value={s}>{titleCase(s)}</SelectItem>)}</SelectContent>
          </Select>
          {segments.data && (
            <Select value={segment} onValueChange={(v) => update({ segment: v })}>
              <SelectTrigger className="w-44" aria-label="Segment filter"><SelectValue placeholder="Segment" /></SelectTrigger>
              <SelectContent><SelectItem value={ALL}>All segments</SelectItem>{segments.data.items.map((s) => <SelectItem key={s.id} value={s.id}>{s.name}</SelectItem>)}</SelectContent>
            </Select>
          )}
          {users.data && (
            <Select value={owner} onValueChange={(v) => update({ owner: v })}>
              <SelectTrigger className="w-44" aria-label="Owner filter"><SelectValue placeholder="Owner" /></SelectTrigger>
              <SelectContent><SelectItem value={ALL}>Any owner</SelectItem>{users.data.items.map((u) => <SelectItem key={u.id} value={u.id}>{u.full_name}</SelectItem>)}</SelectContent>
            </Select>
          )}
        </div>
      </PageHeader>

      {clients.isError ? (
        <ErrorState error={clients.error} onRetry={() => void clients.refetch()} />
      ) : (
        <DataTable<ClientRow>
          columns={columns}
          data={rows}
          total={clients.data?.total ?? 0}
          page={page}
          pageSize={PAGE_SIZE}
          onPageChange={(p) => update({ page: String(p) })}
          sorting={sorting}
          onSortingChange={(updater) => {
            const next = typeof updater === "function" ? updater(sorting) : updater
            const first = next[0]
            update({ order_by: first ? `${first.desc ? "-" : ""}${first.id}` : null })
          }}
          isLoading={clients.isPending}
          getRowId={(r) => r.client.id}
          emptyMessage="No clients match"
        />
      )}
      {can("clients.create") && <NewClientDialog open={dialogOpen} onOpenChange={setDialogOpen} />}
    </div>
  )
}
