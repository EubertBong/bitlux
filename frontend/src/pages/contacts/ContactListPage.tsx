/** /contacts -- the reference CRUD list: search + filters, per-row ⋯ menu, create dialog, first-run empty state. */

import * as React from "react"
import { Link, useSearchParams } from "react-router"
import { useQuery } from "@tanstack/react-query"
import type { ColumnDef, SortingState } from "@tanstack/react-table"
import { Building2, Users, X } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { PageHeader } from "@/components/common/PageHeader"
import { DataTable } from "@/components/common/DataTable"
import { EmptyState, ErrorState, LoadingState } from "@/components/common/States"
import { ActionMenu, CreateButton } from "@/components/actions"
import { CONTACT_STATUSES } from "@/entities/contact"
import { api, qs } from "@/lib/api"
import { ago, titleCase } from "@/lib/format"
import { useSegmentOptions, useUserOptions } from "@/lib/lookups"
import type { Contact, Page } from "@/lib/types"
import { ContactStatusBadge } from "./contactShared"

const PAGE_SIZE = 25
const ALL = "__all__"

function useDebounced<T>(value: T, ms: number): T {
  const [v, setV] = React.useState(value)
  React.useEffect(() => {
    const t = setTimeout(() => setV(value), ms)
    return () => clearTimeout(t)
  }, [value, ms])
  return v
}

export function ContactListPage() {
  const [params, setParams] = useSearchParams()
  const page = Math.max(1, Number(params.get("page") ?? 1))
  const orderBy = params.get("order_by") ?? "display_name"
  const status = params.get("status") ?? ALL
  const segment = params.get("segment") ?? ALL
  const owner = params.get("owner") ?? ALL
  const urlQ = params.get("q") ?? ""
  const [qInput, setQInput] = React.useState(urlQ)
  const debouncedQ = useDebounced(qInput, 250)

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
    if (debouncedQ !== urlQ) update({ q: debouncedQ })
  }, [debouncedQ, urlQ, update])

  const hasFilters = Boolean(urlQ) || status !== ALL || segment !== ALL || owner !== ALL
  const contacts = useQuery({
    queryKey: ["contacts", "list", { page, orderBy, status, segment, owner, q: urlQ }],
    queryFn: () => api.get<Page<Contact>>(`/contacts${qs({ page, page_size: PAGE_SIZE, order_by: orderBy, q: urlQ || null, status: status === ALL ? null : status, segment_id: segment === ALL ? null : segment, owner_user_id: owner === ALL ? null : owner })}`),
    placeholderData: (prev) => prev,
  })
  const segments = useSegmentOptions()
  const users = useUserOptions()
  const segmentName = React.useCallback((id: string | null) => segments.options.find((o) => o.value === id)?.label ?? null, [segments.options])
  const userName = React.useCallback((id: string | null) => users.options.find((o) => o.value === id)?.label ?? null, [users.options])

  const sorting: SortingState = React.useMemo(() => [{ id: orderBy.replace(/^-/, ""), desc: orderBy.startsWith("-") }], [orderBy])
  const columns = React.useMemo<ColumnDef<Contact, unknown>[]>(
    () => [
      {
        id: "display_name", header: "Name",
        cell: ({ row }) => (
          <div className="flex min-w-0 items-center gap-2">
            {row.original.contact_type === "company" ? <Building2 className="size-4 shrink-0 text-muted-foreground" aria-label="Company" /> : <Users className="size-4 shrink-0 text-muted-foreground" aria-label="Person" />}
            <div className="min-w-0">
              <Link to={`/contacts/${row.original.id}`} className="font-medium hover:underline">{row.original.display_name}</Link>
              {row.original.job_title && <div className="truncate text-xs text-muted-foreground">{row.original.job_title}</div>}
            </div>
          </div>
        ),
      },
      { id: "company_name", header: "Company", cell: ({ row }) => row.original.contact_type === "company" ? <span className="text-muted-foreground">—</span> : row.original.company_name ?? <span className="text-muted-foreground">—</span> },
      { id: "primary_email", header: "Primary email", cell: ({ row }) => row.original.primary_email ? <a href={`mailto:${row.original.primary_email}`} className="hover:underline">{row.original.primary_email}</a> : <span className="text-muted-foreground">—</span> },
      { id: "owner_user_id", header: "Owner", enableSorting: false, cell: ({ row }) => userName(row.original.owner_user_id) ?? <span className="text-muted-foreground">{row.original.owner_user_id ? "…" : "Unassigned"}</span> },
      { id: "segment_id", header: "Segment", enableSorting: false, cell: ({ row }) => segmentName(row.original.segment_id) ?? <span className="text-muted-foreground">—</span> },
      { id: "status", header: "Status", cell: ({ row }) => <ContactStatusBadge status={row.original.status} /> },
      { id: "last_activity_at", header: "Last activity", cell: ({ row }) => <span title={row.original.last_activity_at ?? ""}>{ago(row.original.last_activity_at)}</span> },
      { id: "actions", header: "", enableSorting: false, cell: ({ row }) => <div className="text-right"><ActionMenu entity="contact" id={row.original.id} row={row.original} /></div> },
    ],
    [segmentName, userName],
  )

  const showFirstRun = contacts.isSuccess && contacts.data.total === 0 && !hasFilters

  return (
    <div>
      <PageHeader
        title="Contacts"
        description={contacts.data ? `${contacts.data.total.toLocaleString()} in your book` : "People and companies you do business with."}
        actions={<CreateButton entity="contact" label="New Contact" />}
      >
        <div className="flex flex-wrap items-center gap-2" data-testid="contact-filters">
          <Input placeholder="Search name, company, email…" value={qInput} onChange={(e) => setQInput(e.target.value)} className="w-64" aria-label="Search contacts" />
          <Select value={status} onValueChange={(v) => update({ status: v })}>
            <SelectTrigger className="w-40" aria-label="Status filter"><SelectValue placeholder="Status" /></SelectTrigger>
            <SelectContent><SelectItem value={ALL}>All statuses</SelectItem>{CONTACT_STATUSES.map((s) => <SelectItem key={s} value={s}>{titleCase(s)}</SelectItem>)}</SelectContent>
          </Select>
          {!segments.unavailable && (
            <Select value={segment} onValueChange={(v) => update({ segment: v })}>
              <SelectTrigger className="w-44" aria-label="Segment filter"><SelectValue placeholder="Segment" /></SelectTrigger>
              <SelectContent><SelectItem value={ALL}>All segments</SelectItem>{segments.options.map((s) => <SelectItem key={s.value} value={s.value}>{s.label}</SelectItem>)}</SelectContent>
            </Select>
          )}
          {!users.unavailable && (
            <Select value={owner} onValueChange={(v) => update({ owner: v })}>
              <SelectTrigger className="w-44" aria-label="Owner filter"><SelectValue placeholder="Owner" /></SelectTrigger>
              <SelectContent><SelectItem value={ALL}>Any owner</SelectItem>{users.options.map((u) => <SelectItem key={u.value} value={u.value}>{u.label}</SelectItem>)}</SelectContent>
            </Select>
          )}
          {hasFilters && <Button variant="ghost" size="sm" onClick={() => { setQInput(""); update({ q: null, status: null, segment: null, owner: null }) }}><X /> Clear</Button>}
        </div>
      </PageHeader>

      {contacts.isError ? (
        <ErrorState error={contacts.error} onRetry={() => void contacts.refetch()} />
      ) : contacts.isPending ? (
        <LoadingState />
      ) : showFirstRun ? (
        <EmptyState icon={Users} title="No contacts yet" description="Get started by creating your first contact. Everything else — passengers, trips, quotes — hangs off a contact." action={<CreateButton entity="contact" label="New Contact" />} />
      ) : (
        <DataTable<Contact>
          columns={columns}
          data={contacts.data.items}
          total={contacts.data.total}
          page={page}
          pageSize={PAGE_SIZE}
          onPageChange={(p) => update({ page: String(p) })}
          sorting={sorting}
          onSortingChange={(updater) => {
            const next = typeof updater === "function" ? updater(sorting) : updater
            const first = next[0]
            update({ order_by: first ? `${first.desc ? "-" : ""}${first.id}` : null })
          }}
          isLoading={contacts.isFetching}
          getRowId={(r) => r.id}
          emptyMessage="No contacts match these filters"
        />
      )}
    </div>
  )
}
